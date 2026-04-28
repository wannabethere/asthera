"""
Airflow DAG: dashboard_dbt_pipeline

Triggered by workflowservices after every dashboard/report publish.
Receives a fully-specified cube payload via dag_run.conf and executes:

  T1  generate_dbt_sql        POST complianceskill /api/v1/dbt/generate (LLM)
  T2  write_to_s3             SQL + yml → s3_artifact_path
  T3  write_model_locally     SQL → airflow/dbt/models/gold/{model}.sql for dbt run
  T4  dbt_run                 dbt run --select {model_name}  (Spark via dbt-spark)
  T5  dbt_test                dbt test --select {model_name}
  T6  read_table_version      inspect Delta/Iceberg table version from run artifacts
  T7  callback                POST workflowservices /dbt-artifacts/callback
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import boto3
import httpx
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

logger = logging.getLogger(__name__)

COMPLIANCE_SKILL_URL   = os.getenv("COMPLIANCE_SKILL_URL",   "http://complianceskill:8002")
DBT_PROFILES_DIR       = os.getenv("DBT_PROFILES_DIR",       "/opt/airflow/dbt")
DBT_MODELS_DIR         = os.getenv("DBT_MODELS_DIR",         "/opt/airflow/dbt/models/gold")
AWS_REGION             = os.getenv("AWS_DEFAULT_REGION",      "us-east-1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _parse_s3_path(s3_path: str) -> tuple[str, str]:
    """Return (bucket, prefix) from s3://bucket/prefix/."""
    parts  = s3_path.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

@dag(
    dag_id="dashboard_dbt_pipeline",
    schedule_interval=None,          # triggered exclusively via Airflow REST API
    start_date=days_ago(1),
    catchup=False,
    tags=["dbt", "gold", "compliance"],
    doc_md=__doc__,
)
def dashboard_dbt_pipeline():

    # ------------------------------------------------------------------
    # T1: generate dbt SQL via complianceskill LLM endpoint
    # ------------------------------------------------------------------
    @task
    def generate_dbt_sql(**context) -> dict:
        conf = context["dag_run"].conf or {}
        payload = {
            "model_name":         conf["model_name"],
            "grain":              conf["grain"],
            "dimensions":         conf["dimensions"],
            "metrics":            conf["metrics"],
            "source_tables":      conf["source_tables"],
            "event_date_column":  conf.get("event_date_column", "event_date"),
            "tenant_id":          conf["tenant_id"],
            "dashboard_id":       conf["dashboard_id"],
            "destination_type":   conf.get("destination_type", "internal_s3"),
            "description":        conf.get("description", ""),
        }
        resp = httpx.post(
            f"{COMPLIANCE_SKILL_URL}/api/v1/dbt/generate",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("Generated dbt SQL for model=%s", conf["model_name"])
        return result   # { model_name, sql, schema_yml, cube_yaml }

    # ------------------------------------------------------------------
    # T2: write SQL + yml artifact files to S3
    # ------------------------------------------------------------------
    @task
    def write_to_s3(sql_result: dict, **context) -> str:
        conf            = context["dag_run"].conf or {}
        s3_artifact_path = conf["s3_artifact_path"]   # s3://bucket/path/
        model_name      = sql_result["model_name"]

        bucket, prefix = _parse_s3_path(s3_artifact_path)
        s3 = _s3_client()

        for key_suffix, content in [
            (f"{model_name}.sql",         sql_result["sql"]),
            (f"{model_name}.yml",         sql_result["schema_yml"]),
            (f"{model_name}_cube.yml",    sql_result["cube_yaml"]),
        ]:
            s3.put_object(
                Bucket=bucket,
                Key=f"{prefix}{key_suffix}",
                Body=content.encode("utf-8"),
                ContentType="text/plain",
            )

        # Update current.txt pointer
        version_folder = prefix.rstrip("/").rsplit("/", 1)[-1]   # e.g. "v3"
        s3.put_object(
            Bucket=bucket,
            Key=prefix.rstrip("/").rsplit("/", 1)[0] + "/current.txt",
            Body=version_folder.encode("utf-8"),
        )

        logger.info("Wrote artifacts to s3://%s/%s", bucket, prefix)
        return s3_artifact_path

    # ------------------------------------------------------------------
    # T3: write SQL to local dbt models dir so dbt run can pick it up
    # ------------------------------------------------------------------
    @task
    def write_model_locally(sql_result: dict, **context) -> str:
        model_name = sql_result["model_name"]
        sql        = sql_result["sql"]
        dest_path  = Path(DBT_MODELS_DIR) / f"{model_name}.sql"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(sql, encoding="utf-8")
        logger.info("Wrote dbt model to %s", dest_path)
        return str(dest_path)

    # ------------------------------------------------------------------
    # T4: dbt run
    # ------------------------------------------------------------------
    @task.bash
    def dbt_run(**context) -> str:
        conf       = context["dag_run"].conf or {}
        model_name = conf["model_name"]
        return (
            f"cd {DBT_PROFILES_DIR} && "
            f"dbt run --select {model_name} --profiles-dir {DBT_PROFILES_DIR} --no-use-colors 2>&1"
        )

    # ------------------------------------------------------------------
    # T5: dbt test
    # ------------------------------------------------------------------
    @task.bash
    def dbt_test(**context) -> str:
        conf       = context["dag_run"].conf or {}
        model_name = conf["model_name"]
        return (
            f"cd {DBT_PROFILES_DIR} && "
            f"dbt test --select {model_name} --profiles-dir {DBT_PROFILES_DIR} --no-use-colors 2>&1"
        )

    # ------------------------------------------------------------------
    # T6: read table version / snapshot from dbt run artifacts
    # ------------------------------------------------------------------
    @task
    def read_table_version(**context) -> dict:
        conf         = context["dag_run"].conf or {}
        model_name   = conf["model_name"]
        dest_type    = conf.get("destination_type", "internal_s3")
        dest_cfg     = conf.get("destination_config", {})

        table_meta: dict = {
            "destination_table_uri": None,
            "table_snapshot_id":     None,
            "table_version_number":  None,
        }

        if dest_type in ("internal_s3", "customer_s3", "azure_adls"):
            bucket = dest_cfg.get("bucket", os.getenv("DBT_DATA_BUCKET", "dbt-tables"))
            table_meta["destination_table_uri"] = f"s3://{bucket}/dbt-tables/gold/{model_name}/"
            # Read Delta _delta_log to find latest version
            try:
                s3  = _s3_client()
                log_prefix = f"dbt-tables/gold/{model_name}/_delta_log/"
                resp       = s3.list_objects_v2(Bucket=bucket, Prefix=log_prefix)
                log_files  = sorted(
                    [o["Key"] for o in resp.get("Contents", []) if o["Key"].endswith(".json")],
                    reverse=True,
                )
                if log_files:
                    version_str = Path(log_files[0]).stem
                    table_meta["table_version_number"] = int(version_str)
            except Exception as exc:
                logger.warning("Could not read Delta log: %s", exc)

        elif dest_type == "databricks":
            catalog = dest_cfg.get("catalog", "main")
            schema  = dest_cfg.get("schema", "gold")
            table_meta["destination_table_uri"] = f"{catalog}.{schema}.{model_name}"

        elif dest_type == "snowflake":
            database = dest_cfg.get("database", "")
            schema   = dest_cfg.get("schema",   "GOLD")
            table_meta["destination_table_uri"] = f"{database}.{schema}.{model_name}".upper()

        elif dest_type == "bigquery":
            project = dest_cfg.get("project", "")
            dataset = dest_cfg.get("dataset", "gold")
            table_meta["destination_table_uri"] = f"{project}.{dataset}.{model_name}"

        return table_meta

    # ------------------------------------------------------------------
    # T7: callback to workflowservices
    # ------------------------------------------------------------------
    @task
    def callback(
        sql_result:   dict,
        table_meta:   dict,
        dbt_run_log:  str,
        dbt_test_log: str,
        **context,
    ) -> None:
        conf         = context["dag_run"].conf or {}
        callback_url = conf.get("callback_url")
        dag_run_id   = context["dag_run"].run_id

        if not callback_url:
            logger.warning("No callback_url in conf — skipping callback")
            return

        run_log = f"=== dbt run ===\n{dbt_run_log}\n\n=== dbt test ===\n{dbt_test_log}"
        payload = {
            "dag_run_id":            dag_run_id,
            "status":                "passed",
            "model_sql":             sql_result.get("sql"),
            "schema_yml":            sql_result.get("schema_yml"),
            "cube_yaml":             sql_result.get("cube_yaml"),
            "destination_table_uri": table_meta.get("destination_table_uri"),
            "table_snapshot_id":     table_meta.get("table_snapshot_id"),
            "table_version_number":  table_meta.get("table_version_number"),
            "run_log":               run_log,
        }

        try:
            resp = httpx.post(callback_url, json=payload, timeout=30.0)
            resp.raise_for_status()
            logger.info("Callback sent to %s", callback_url)
        except Exception as exc:
            logger.error("Callback failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Wire up task dependencies
    # ------------------------------------------------------------------
    sql_result   = generate_dbt_sql()
    _s3          = write_to_s3(sql_result)
    _local       = write_model_locally(sql_result)
    run_log      = dbt_run()
    test_log     = dbt_test()
    table_meta   = read_table_version()
    _cb          = callback(sql_result, table_meta, run_log, test_log)

    # Ordering
    [_s3, _local] >> run_log >> test_log >> table_meta >> _cb


dashboard_dbt_pipeline()
