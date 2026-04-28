"""
SQL Builder — renders gold_cube.sql.j2 for a given destination type.

The config() block is destination-specific (Iceberg vs Snowflake vs BigQuery etc.).
The SELECT body is standard dbt and identical across all destinations.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .models import DestinationType, DbtGenerateRequest

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _build_config_block(req: DbtGenerateRequest) -> str:
    dim_names = [d.name for d in req.dimensions]
    unique_key = ["connection_id", "tenant_id", "period"] + dim_names
    unique_key_str = "[" + ", ".join(f"'{k}'" for k in unique_key) + "]"

    tags = f"['gold', 'cube', 'dashboard_{req.dashboard_id}']"

    if req.destination_type in (DestinationType.INTERNAL_S3, DestinationType.CUSTOMER_S3, DestinationType.AZURE_ADLS):
        return (
            "{{% config(\n"
            "    materialized='incremental',\n"
            "    incremental_strategy='merge',\n"
            f"    unique_key={unique_key_str},\n"
            "    file_format='iceberg',\n"
            "    partition_by=[{{'field': 'period', 'data_type': 'date'}}],\n"
            "    on_schema_change='append_new_columns',\n"
            f"    tags={tags}\n"
            ") %}}"
        )

    if req.destination_type == DestinationType.DATABRICKS:
        return (
            "{{% config(\n"
            "    materialized='incremental',\n"
            "    incremental_strategy='merge',\n"
            f"    unique_key={unique_key_str},\n"
            "    file_format='delta',\n"
            "    partition_by=['period'],\n"
            "    on_schema_change='append_new_columns',\n"
            f"    tags={tags}\n"
            ") %}}"
        )

    if req.destination_type == DestinationType.SNOWFLAKE:
        return (
            "{{% config(\n"
            "    materialized='incremental',\n"
            "    incremental_strategy='merge',\n"
            f"    unique_key={unique_key_str},\n"
            "    on_schema_change='append_new_columns',\n"
            f"    tags={tags}\n"
            ") %}}"
        )

    if req.destination_type == DestinationType.BIGQUERY:
        return (
            "{{% config(\n"
            "    materialized='incremental',\n"
            "    incremental_strategy='merge',\n"
            f"    unique_key={unique_key_str},\n"
            "    partition_by={{'field': 'period', 'data_type': 'date'}},\n"
            "    on_schema_change='append_new_columns',\n"
            f"    tags={tags}\n"
            ") %}}"
        )

    # REDSHIFT / POSTGRES — table materialization (no merge on these targets)
    return (
        "{{% config(\n"
        "    materialized='table',\n"
        f"    tags={tags}\n"
        ") %}}"
    )


def build_sql(req: DbtGenerateRequest) -> str:
    """Render the gold cube dbt SQL for the given request."""
    # Use only the first source table in the FROM clause.
    # Multi-source joins are handled at the silver layer; gold cubes read one silver table.
    source_table = req.source_tables[0] if req.source_tables else "silver_source"
    incremental = req.destination_type not in (DestinationType.REDSHIFT, DestinationType.POSTGRES)

    template = _env.get_template("gold_cube.sql.j2")
    return template.render(
        config_block=_build_config_block(req),
        source_table=source_table,
        event_date_column=req.event_date_column,
        grain=req.grain.value,
        dimensions=req.dimensions,
        metrics=req.metrics,
        incremental=incremental,
        incremental_lookback_days=req.incremental_lookback_days,
    )
