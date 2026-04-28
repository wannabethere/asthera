"""
dbt Artifact Service.

Single entry point called after every dashboard/report publish.
Responsibilities:
  1. Hash the cube definition — skip Airflow trigger if nothing changed
  2. Create / update DbtArtifact + DbtArtifactVersion rows
  3. Trigger the Airflow dashboard_dbt_pipeline DAG via REST API
  4. Receive the callback from Airflow and store results
"""
import hashlib
import json
import logging
import os
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dbt_artifact import (
    ArtifactType,
    DbtArtifact,
    DbtArtifactStatus,
    DbtArtifactVersion,
    DbtIntegrationType,
    DbtRunStatus,
)
from app.models.gold_destination import GoldDestinationConfig, GoldDestinationType
from app.models.workflowmodels import ThreadComponent

logger = logging.getLogger(__name__)

AIRFLOW_BASE_URL  = os.getenv("AIRFLOW_BASE_URL", "http://airflow-webserver:8080")
AIRFLOW_USER      = os.getenv("AIRFLOW_USER", "airflow")
AIRFLOW_PASSWORD  = os.getenv("AIRFLOW_PASSWORD", "airflow")
AIRFLOW_DAG_ID    = "dashboard_dbt_pipeline"
SELF_BASE_URL     = os.getenv("WORKFLOW_SERVICES_BASE_URL", "http://workflowservices:8000")
DBT_S3_BUCKET     = os.getenv("DBT_S3_BUCKET", "dbt-artifacts")


# ---------------------------------------------------------------------------
# Payload extraction helpers
# ---------------------------------------------------------------------------

def _extract_dbt_payload(
    components: list[ThreadComponent],
    workflow_metadata: dict,
    dashboard_id: str,
    model_name: str,
) -> dict:
    """
    Extract cube definition from published dashboard components + metadata.

    Priority order for grain / dimensions / metrics:
    1. Explicit values stored in workflow_metadata["dbt_config"] (user-overrides)
    2. Derived from component chart_config / configuration fields
    3. Sensible defaults
    """
    dbt_cfg = workflow_metadata.get("dbt_config", {})

    grain      = dbt_cfg.get("grain", "day")
    dimensions = dbt_cfg.get("dimensions", [])
    metrics    = dbt_cfg.get("metrics", [])
    source_tables = dbt_cfg.get("source_tables", [])
    event_date_column = dbt_cfg.get("event_date_column", "event_date")

    # Derive from components if not explicitly set
    if not dimensions or not metrics:
        for comp in components:
            cfg = comp.chart_config or comp.configuration or {}
            if isinstance(cfg, dict):
                dimensions = dimensions or cfg.get("dimensions", cfg.get("groups", []))
                metrics    = metrics    or cfg.get("metrics",    cfg.get("measures", []))
                source_tables = source_tables or cfg.get("source_tables", [])

    # Normalise metrics to list[dict] format expected by complianceskill
    normalised_metrics = []
    for m in metrics:
        if isinstance(m, str):
            normalised_metrics.append({"name": m, "column": m, "aggregation": "COUNT"})
        elif isinstance(m, dict):
            normalised_metrics.append(m)

    # Normalise dimensions similarly
    normalised_dims = []
    for d in dimensions:
        if isinstance(d, str):
            normalised_dims.append({"name": d, "type": "string", "description": ""})
        elif isinstance(d, dict):
            normalised_dims.append(d)

    return {
        "grain": grain,
        "dimensions": normalised_dims,
        "metrics": normalised_metrics,
        "source_tables": source_tables or ["silver_source"],
        "event_date_column": event_date_column,
        "model_name": model_name,
        "dashboard_id": dashboard_id,
    }


def _compute_hash(payload: dict) -> str:
    """SHA-256 of the stable cube definition — detects no-op republishes."""
    stable = {
        "grain":        payload["grain"],
        "dimensions":   sorted(json.dumps(d, sort_keys=True) for d in payload["dimensions"]),
        "metrics":      sorted(json.dumps(m, sort_keys=True) for m in payload["metrics"]),
        "source_tables": sorted(payload["source_tables"]),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------------------
# DbtArtifactService
# ---------------------------------------------------------------------------

class DbtArtifactService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def on_publish(
        self,
        workflow_id: str,
        artifact_type: ArtifactType,
        dashboard_version: str,      # "2.0" from dashboard.version / report.version
        dashboard_id: str,
        components: list[ThreadComponent],
        workflow_metadata: dict,
        tenant_id: str,
        user_id: str | None = None,
    ) -> DbtArtifact:
        """
        Called by publish_dashboard() / publish_report() AFTER db.commit().

        Creates or updates the DbtArtifact and fires the Airflow DAG.
        Failures here are logged but never propagate — publish must not be blocked.
        """
        try:
            model_name = self._model_name(artifact_type, workflow_id)
            payload    = _extract_dbt_payload(components, workflow_metadata, dashboard_id, model_name)
            new_hash   = _compute_hash(payload)

            artifact = await self._get_or_create_artifact(
                workflow_id, artifact_type, model_name, tenant_id, user_id
            )

            if artifact.model_hash == new_hash:
                logger.info(
                    "dbt artifact hash unchanged for workflow=%s — skipping rebuild", workflow_id
                )
                return artifact

            # Deprecate the previous current version
            if artifact.current_version_id:
                await self._set_version_not_current(artifact.current_version_id)

            version_number    = int(float(dashboard_version))
            dest_config       = await self._get_default_destination(tenant_id)
            destination_type  = dest_config.destination_type.value if dest_config else GoldDestinationType.INTERNAL_S3.value
            s3_artifact_path  = (
                f"s3://{DBT_S3_BUCKET}/dbt-artifacts/gold/{artifact.id}/v{version_number}/"
            )

            new_version = DbtArtifactVersion(
                artifact_id          = artifact.id,
                version_number       = version_number,
                s3_artifact_path     = s3_artifact_path,
                destination_config_id= dest_config.id if dest_config else None,
                destination_type     = destination_type,
                grain                = payload["grain"],
                dimensions           = payload["dimensions"],
                metrics              = payload["metrics"],
                source_tables        = payload["source_tables"],
                run_status           = DbtRunStatus.PENDING,
                previous_version_id  = artifact.current_version_id,
                is_current           = True,
            )
            self.db.add(new_version)
            artifact.model_hash   = new_hash
            artifact.status       = DbtArtifactStatus.BUILDING
            await self.db.flush()   # get new_version.id without committing

            artifact.current_version_id = new_version.id
            await self.db.commit()

            await self._trigger_airflow(artifact, new_version, payload, dest_config)
            return artifact

        except Exception:
            logger.exception("dbt artifact service failed for workflow=%s", workflow_id)
            return None

    async def receive_callback(self, body: dict) -> None:
        """
        Called by POST /dbt-artifacts/callback (Airflow T7).

        Updates DbtArtifactVersion with generated SQL, run status, and
        Iceberg/Delta table location.
        """
        dag_run_id = body.get("dag_run_id")
        if not dag_run_id:
            raise ValueError("dag_run_id is required in callback body")

        stmt = select(DbtArtifactVersion).where(DbtArtifactVersion.dag_run_id == dag_run_id)
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()
        if not version:
            raise ValueError(f"No DbtArtifactVersion found for dag_run_id={dag_run_id}")

        version.dbt_model_sql        = body.get("model_sql")
        version.dbt_schema_yml       = body.get("schema_yml")
        version.cube_yaml            = body.get("cube_yaml")
        version.run_status           = DbtRunStatus(body.get("status", "failed"))
        version.run_log              = body.get("run_log")
        version.destination_table_uri = body.get("destination_table_uri")
        version.table_snapshot_id    = body.get("table_snapshot_id")
        version.table_version_number = body.get("table_version_number")

        stmt = select(DbtArtifact).where(DbtArtifact.id == version.artifact_id)
        result = await self.db.execute(stmt)
        artifact = result.scalar_one()
        artifact.status = (
            DbtArtifactStatus.ACTIVE
            if version.run_status == DbtRunStatus.PASSED
            else DbtArtifactStatus.FAILED
        )
        await self.db.commit()

    async def get_artifact(self, workflow_id: str, artifact_type: ArtifactType) -> DbtArtifact | None:
        stmt = select(DbtArtifact).where(
            DbtArtifact.dashboard_workflow_id == workflow_id
            if artifact_type == ArtifactType.DASHBOARD
            else DbtArtifact.report_workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _model_name(artifact_type: ArtifactType, workflow_id: str) -> str:
        short_id = workflow_id.replace("-", "")[:8]
        return f"gold_{artifact_type.value}_{short_id}_cube"

    async def _get_or_create_artifact(
        self,
        workflow_id: str,
        artifact_type: ArtifactType,
        model_name: str,
        tenant_id: str,
        user_id: str | None,
    ) -> DbtArtifact:
        wf_col = (
            DbtArtifact.dashboard_workflow_id
            if artifact_type == ArtifactType.DASHBOARD
            else DbtArtifact.report_workflow_id
        )
        stmt   = select(DbtArtifact).where(wf_col == workflow_id)
        result = await self.db.execute(stmt)
        artifact = result.scalar_one_or_none()

        if artifact is None:
            artifact = DbtArtifact(
                artifact_type=artifact_type,
                model_name=model_name,
                tenant_id=tenant_id,
                created_by=user_id,
                integration_type=DbtIntegrationType.ASTHERA_UX,
                status=DbtArtifactStatus.BUILDING,
                **{
                    "dashboard_workflow_id": workflow_id
                    if artifact_type == ArtifactType.DASHBOARD
                    else None,
                    "report_workflow_id": workflow_id
                    if artifact_type == ArtifactType.REPORT
                    else None,
                },
            )
            self.db.add(artifact)
            await self.db.flush()

        return artifact

    async def _set_version_not_current(self, version_id: str) -> None:
        stmt   = select(DbtArtifactVersion).where(DbtArtifactVersion.id == version_id)
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()
        if version:
            version.is_current = False

    async def _get_default_destination(self, tenant_id: str) -> GoldDestinationConfig | None:
        stmt = select(GoldDestinationConfig).where(
            GoldDestinationConfig.tenant_id == tenant_id,
            GoldDestinationConfig.is_default == True,   # noqa: E712
            GoldDestinationConfig.is_active == True,    # noqa: E712
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _trigger_airflow(
        self,
        artifact: DbtArtifact,
        version: DbtArtifactVersion,
        payload: dict,
        dest_config: GoldDestinationConfig | None,
    ) -> None:
        conf: dict[str, Any] = {
            "artifact_id":     artifact.id,
            "version_id":      version.id,
            "version_number":  version.version_number,
            "model_name":      artifact.model_name,
            "s3_artifact_path": version.s3_artifact_path,
            "action":          "replace" if version.previous_version_id else "create",
            "grain":           payload["grain"],
            "dimensions":      payload["dimensions"],
            "metrics":         payload["metrics"],
            "source_tables":   payload["source_tables"],
            "event_date_column": payload.get("event_date_column", "event_date"),
            "dashboard_id":    payload["dashboard_id"],
            "tenant_id":       artifact.tenant_id,
            "destination_type": version.destination_type or GoldDestinationType.INTERNAL_S3.value,
            "destination_config": dest_config.connection_config if dest_config else {},
            "callback_url":    f"{SELF_BASE_URL}/dbt-artifacts/callback",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{AIRFLOW_BASE_URL}/api/v1/dags/{AIRFLOW_DAG_ID}/dagRuns",
                    json={"conf": conf},
                    auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
                )
                resp.raise_for_status()
                dag_run_id = resp.json().get("dag_run_id")

            # Store correlation key — needed to match the callback
            version.dag_run_id = dag_run_id
            await self.db.commit()
            logger.info(
                "Airflow DAG triggered: dag_run_id=%s artifact=%s version=%s",
                dag_run_id, artifact.id, version.id,
            )
        except Exception:
            logger.exception(
                "Failed to trigger Airflow for artifact=%s — version remains PENDING",
                artifact.id,
            )
