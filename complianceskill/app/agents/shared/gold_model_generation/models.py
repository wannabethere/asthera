"""
Gold Model Generation — Pydantic models.

Shared data structures for plan generation and SQL generation.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class OutputColumn(BaseModel):
    """Column specification for gold model output schema."""

    name: str = Field(..., description="Column name")
    description: Optional[str] = Field(
        None,
        description="Description of the column (required only when name is not self-explanatory)",
    )
    mapped_metrics: Optional[list[str]] = Field(
        default_factory=list,
        description=(
            "List of metric IDs or names that require this column. "
            "This shows which metrics from the input metrics list depend on this column. "
            "Essential for understanding why each column is needed."
        ),
    )


class SourceTableColumn(BaseModel):
    """A column from a source table."""

    table_name: str = Field(..., description="Name of the source silver table")
    column_name: str = Field(..., description="Name of the column in the source table")
    usage: Optional[str] = Field(
        None,
        description="How this column is used (e.g., 'join key', 'filter', 'aggregation', 'direct mapping')",
    )


class GoldModelSpecification(BaseModel):
    """Specification for a single gold model to be generated."""

    name: str = Field(
        ...,
        description="Gold model name following convention: gold_{vendor}_{entity} or gold_{vendor}_{entity}_{purpose}",
    )
    description: str = Field(
        ...,
        description=(
            "Natural language description of what to generate. "
            "Should explain: what silver tables to use, what joins to perform, "
            "what transformations to apply, and what the output represents."
        ),
    )
    materialization: str = Field(
        ...,
        description="Materialization strategy: 'incremental', 'table', or 'view'",
    )
    source_tables: list[str] = Field(
        ...,
        description="List of silver table names that this gold model will use as sources. Must reference tables from available silver tables.",
    )
    source_columns: list[SourceTableColumn] = Field(
        default_factory=list,
        description=(
            "List of source table columns that will be used to build this gold model. "
            "Include columns used for joins, filters, aggregations, and direct mappings. "
            "This helps document the data lineage and validate that required columns exist."
        ),
    )
    expected_columns: list[OutputColumn] = Field(
        ...,
        description="List of expected output columns. MUST always include connection_id for multi-tenant filtering.",
    )

    @model_validator(mode="after")
    def validate_connection_id(self) -> "GoldModelSpecification":
        """Ensure connection_id is present; auto-add if LLM omitted it."""
        if not any(col.name == "connection_id" for col in self.expected_columns):
            self.expected_columns.insert(
                0,
                OutputColumn(
                    name="connection_id",
                    description="Required for multi-tenant filtering",
                ),
            )
        return self


class SilverModelSpecification(BaseModel):
    """Specification for creating a silver table when silver tables are not found.

    Used when silver_tables_info is empty - downstream can use this to create
    silver tables from bronze/source, then extend to gold. Kept in shared for reuse.
    """

    name: str = Field(
        ...,
        description="Silver model name, e.g. silver_{vendor}_{entity}",
    )
    description: str = Field(
        ...,
        description="What to create: silver table from source/bronze for downstream metrics",
    )
    materialization: str = Field(
        default="table",
        description="Materialization strategy: 'table' or 'incremental'",
    )
    source_tables: list[str] = Field(
        default_factory=list,
        description="Bronze/source table names to build from (empty when unknown)",
    )
    source_schema_names: list[str] = Field(
        default_factory=list,
        description="Schema names from metrics (e.g. from source_schemas) for lookup",
    )
    expected_columns: list[OutputColumn] = Field(
        default_factory=lambda: [
            OutputColumn(name="connection_id", description="Required for multi-tenant filtering"),
        ],
        description="Minimal expected columns; downstream can extend",
    )


class GoldModelPlan(BaseModel):
    """Plan for generating dbt gold and optionally silver models.

    Determines whether gold models are needed and provides specifications.
    When silver tables are missing, silver_specifications can describe silver creation
    for downstream to build silver first, then gold.
    """

    requires_gold_model: bool = Field(
        ...,
        description="Whether a gold model is needed at all (some requests can be served directly by Cube)",
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why a gold model is or is not needed based on the decision framework",
    )
    specifications: Optional[list[GoldModelSpecification]] = Field(
        None,
        description="List of gold model specifications (only if requires_gold_model is True)",
    )
    requires_silver_model: bool = Field(
        default=False,
        description="Whether silver table creation is needed (when silver_tables_info was empty)",
    )
    silver_specifications: Optional[list[SilverModelSpecification]] = Field(
        None,
        description="Specs for creating silver tables when silver_tables_info is empty; downstream extends to gold",
    )


class SilverTableInfo(BaseModel):
    """Information about an available silver table.

    This is a simplified version that works with dict-based schemas from MDL,
    rather than requiring DatabricksSchemaInfo objects.
    """

    table_name: str = Field(..., description="Name of the silver table")
    reason: Optional[str] = Field(
        None, description="Reason why the table is relevant"
    )
    schema_info: dict[str, Any] = Field(
        ...,
        description=(
            "Schema information as a dict. Should contain: "
            "table_name, table_ddl (optional), description (optional), "
            "column_metadata (list of column dicts with column_name, type, description)"
        ),
    )
    relevant_columns: list[str] = Field(
        default_factory=list,
        description="List of relevant columns in the table",
    )
    relevant_columns_reasoning: Optional[str] = Field(
        None, description="Reasoning behind the relevance of the columns"
    )

    def render_schema(self) -> str:
        """Render schema information as a formatted string for prompts."""
        column_metadata = self.schema_info.get("column_metadata", [])
        if not column_metadata:
            return ""

        lines = []
        for col in column_metadata:
            if isinstance(col, dict):
                col_name = col.get("column_name") or col.get("name", "unknown")
                col_type = col.get("type") or col.get("data_type", "")
                col_comment = col.get("comment") or col.get("description") or col.get("display_name", "")

                comment_str = f" -- {col_comment}" if col_comment else ""
                lines.append(f"- {col_name}: {col_type}{comment_str}")
            else:
                lines.append(f"- {col}")

        return "\n".join(lines)


class GoldModelPlanGeneratorInput(BaseModel):
    """Input for gold model plan generation."""

    metrics: list[dict[str, Any]] = Field(
        ...,
        description="List of metrics to support. Can be resolved_metrics, dt_metric_recommendations, or goal_metrics.",
    )
    silver_tables_info: list[SilverTableInfo] = Field(
        ...,
        description="List of available silver tables with schemas. Assumes these tables already exist.",
    )
    user_request: Optional[str] = Field(
        None,
        description="Original user request or query for context.",
    )
    kpis: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Optional list of KPIs to support.",
    )
    medallion_context: Optional[dict[str, Any]] = Field(
        None,
        description="Optional medallion architecture context (bronze/silver/gold layer info).",
    )
    focus_areas: Optional[list[str]] = Field(
        None,
        description="Optional list of focus areas for metric bucketing.",
    )


class GeneratedGoldModelSQL(BaseModel):
    """A generated gold model with SQL."""

    name: str = Field(..., description="Name of the gold model (dbt model name)")
    sql_query: str = Field(..., description="Complete SQL query for the dbt model")
    description: Optional[str] = Field(
        None, description="Description of what this model does"
    )
    materialization: str = Field(
        ..., description="dbt materialization strategy (table, view, incremental)"
    )
    expected_columns: List[str] = Field(
        default_factory=list, description="List of expected output column names"
    )


class GoldModelSQLResponse(BaseModel):
    """Response containing generated SQL for gold models."""

    models: List[GeneratedGoldModelSQL] = Field(
        ..., description="List of generated gold models with SQL"
    )
    artifact_name: Optional[str] = Field(
        None,
        description="Name for the DBT artifact containing these models",
    )
