"""
dbt Generation — Pydantic models.

Request/response types for the template-driven dbt model generation endpoint.
Called by Airflow during the dashboard publish pipeline.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AggregationType(str, Enum):
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    SUM = "SUM"
    AVG = "AVG"
    MAX = "MAX"
    MIN = "MIN"


class GrainType(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class DestinationType(str, Enum):
    INTERNAL_S3 = "internal_s3"
    CUSTOMER_S3 = "customer_s3"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    DATABRICKS = "databricks"
    REDSHIFT = "redshift"
    AZURE_ADLS = "azure_adls"
    POSTGRES = "postgres"


class MetricDefinition(BaseModel):
    name: str = Field(..., description="Output column name, e.g. open_count")
    column: str = Field(..., description="Source column to aggregate, e.g. id")
    aggregation: AggregationType
    description: str = ""


class DimensionDefinition(BaseModel):
    name: str = Field(..., description="Column name in source table")
    type: str = Field(default="string", description="SQL type hint: string, number, time")
    description: str = ""


class DbtGenerateRequest(BaseModel):
    model_name: str = Field(
        ...,
        description="dbt model name, e.g. gold_vuln_exposure_cube",
    )
    grain: GrainType = Field(..., description="Aggregation time grain")
    dimensions: list[DimensionDefinition] = Field(
        ...,
        description="Non-time grouping columns",
    )
    metrics: list[MetricDefinition] = Field(
        ...,
        description="Aggregated measure columns",
    )
    source_tables: list[str] = Field(
        ...,
        description="Silver table names this cube reads from",
    )
    event_date_column: str = Field(
        default="event_date",
        description="Timestamp column used for DATE_TRUNC and incremental filter",
    )
    tenant_id: str
    dashboard_id: str
    description: str = ""
    destination_type: DestinationType = DestinationType.INTERNAL_S3
    # incremental lookback window in days to handle late-arriving data
    incremental_lookback_days: int = Field(
        default=3,
        description="How many days back to re-process on incremental runs",
    )


class DbtGenerateResponse(BaseModel):
    model_name: str
    sql: str = Field(..., description="dbt-spark SQL with {{ config(...) }} block")
    schema_yml: str = Field(..., description="dbt schema.yml with column tests")
    cube_yaml: str = Field(..., description="Semantic layer cube definition (YAML)")
