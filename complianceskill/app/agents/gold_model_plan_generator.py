"""
Gold Model Plan Generator for Compliance Skill

A reusable class for generating GoldModelPlan from metrics using LLMs.
Can be used for both gold model generation and dashboard generation workflows.

This is a standalone implementation that does NOT depend on leen_iris models.
Assumption: Silver tables already exist and are available.
"""

import logging
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, model_validator

from app.core.dependencies import get_llm

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models (Standalone - no leen_iris dependencies)
# ============================================================================

class OutputColumn(BaseModel):
    """Column specification for gold model output schema."""

    name: str = Field(..., description="Column name")
    description: Optional[str] = Field(
        None,
        description="Description of the column (required only when name is not self-explanatory)",
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
        if not any(col.name == "connection_id" for col in self.expected_columns):
            raise ValueError("expected_columns must include 'connection_id'")
        return self


class GoldModelPlan(BaseModel):
    """Plan for generating dbt gold models.

    Determines whether gold models are needed and provides specifications
    for each model if required.
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
        """Render schema information as a formatted string for prompts.
        
        Matches leen_iris DatabricksSchemaInfo.render_schema() format:
        - Returns just column lines (no table name, description, or DDL)
        - Format: "- column_name: type -- comment"
        - Table name is added separately in _format_silver_tables()
        """
        column_metadata = self.schema_info.get("column_metadata", [])
        if not column_metadata:
            return ""
        
        lines = []
        for col in column_metadata:
            if isinstance(col, dict):
                col_name = col.get("column_name") or col.get("name", "unknown")
                col_type = col.get("type") or col.get("data_type", "")
                col_comment = col.get("comment") or col.get("description") or col.get("display_name", "")
                
                # Match leen_iris format: "- column_name: type -- comment"
                comment_str = f" -- {col_comment}" if col_comment else ""
                lines.append(f"- {col_name}: {col_type}{comment_str}")
            else:
                # Fallback for string columns
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


# ============================================================================
# Gold Model Plan Generator
# ============================================================================

class GoldModelPlanGenerator:
    """
    Generates GoldModelPlan from metrics using LLMs.
    
    This class is reusable for:
    - Gold model generation workflows
    - Dashboard generation workflows
    - Any workflow that needs to plan gold models from metrics
    
    Assumption: Silver tables already exist and are provided in silver_tables_info.
    """

    def __init__(
        self,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ):
        """
        Initialize the gold model plan generator.
        
        Args:
            temperature: Temperature for LLM generation (default: 0.3)
            max_tokens: Maximum tokens for LLM response (default: 4096)
            model: Optional model override (uses default from get_llm if None)
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = model

    async def generate(
        self, input_data: GoldModelPlanGeneratorInput
    ) -> GoldModelPlan:
        """
        Generate a GoldModelPlan from metrics and silver tables.
        
        Args:
            input_data: Input containing metrics, silver tables, and optional context
            
        Returns:
            GoldModelPlan with specifications for gold models needed to support the metrics
        """
        logger.info(
            f"Generating gold model plan: {len(input_data.metrics)} metrics, "
            f"{len(input_data.silver_tables_info)} silver tables"
        )

        # Get LLM instance
        llm = get_llm(
            temperature=self.temperature,
            model=self.model,
        )

        # Use structured output
        structured_model = llm.with_structured_output(GoldModelPlan)

        # Build prompt from input data
        prompt = self._build_prompt(input_data)

        try:
            # Invoke LLM to generate plan
            response = await structured_model.ainvoke([HumanMessage(content=prompt)])

            gold_model_plan = GoldModelPlan.model_validate(response)

            logger.info(
                f"Gold model plan generated: requires_gold_model={gold_model_plan.requires_gold_model}, "
                f"specifications_count={len(gold_model_plan.specifications or [])}"
            )

            # Validate and ensure connection_id is present in all specifications
            self._ensure_connection_id(gold_model_plan)

            return gold_model_plan

        except Exception as e:
            logger.exception("Error generating gold model plan: %s", str(e))
            raise

    def _build_prompt(self, input_data: GoldModelPlanGeneratorInput) -> str:
        """
        Build the prompt for LLM to generate gold model plan.
        
        Args:
            input_data: Input data for plan generation
            
        Returns:
            Formatted prompt string
        """
        # Format metrics
        metrics_text = self._format_metrics(input_data.metrics)

        # Format KPIs if available
        kpis_text = ""
        if input_data.kpis:
            kpis_text = "\n\n**KPIs to Support:**\n"
            for kpi in input_data.kpis[:10]:  # Limit to first 10
                kpi_name = kpi.get("kpi_name") or kpi.get("name") or kpi.get("kpi_id", "unknown")
                calc_method = kpi.get("calculation_method") or kpi.get("description", "")
                kpis_text += f"- {kpi_name}: {calc_method}\n"

        # Format silver tables
        tables_text = self._format_silver_tables(input_data.silver_tables_info)

        # Format medallion context if available
        medallion_text = ""
        if input_data.medallion_context:
            bronze = input_data.medallion_context.get("bronze_tables", [])
            silver = input_data.medallion_context.get("silver_tables", [])
            gold = input_data.medallion_context.get("gold_tables", [])
            medallion_text = f"""
**Medallion Architecture Context:**
- Bronze Tables: {', '.join(bronze) if bronze else 'None'}
- Silver Tables: {', '.join(silver) if silver else 'None'}
- Gold Tables: {', '.join(gold) if gold else 'None (to be created)'}
"""

        # Build user request context
        user_request_text = ""
        if input_data.user_request:
            user_request_text = f"\n**User Request:**\n{input_data.user_request}\n"

        prompt = f"""You are an expert in dbt modeling and Databricks data warehouse design for security analytics.

Your task is to generate a GoldModelPlan that determines what gold-layer dbt models are needed to support the provided metrics.

**CRITICAL ASSUMPTION:** Silver tables already exist and are available. You should plan gold models that build on top of these silver tables.

{user_request_text}
**Metrics to Support:**
{metrics_text}
{kpis_text}
**Available Silver Tables:**
{tables_text}
{medallion_text}
**Instructions:**

1. **Determine if gold models are needed:**
   - If metrics can be served directly from silver tables (simple queries), set `requires_gold_model=False`
   - If metrics require aggregations, joins across multiple silver tables, or complex transformations, set `requires_gold_model=True`

2. **For each gold model specification (if needed):**
   - **Name**: Follow convention `gold_{{vendor}}_{{entity}}` or `gold_{{vendor}}_{{entity}}_{{purpose}}`
     - Example: `gold_snyk_issues_mttr`, `gold_qualys_vulnerabilities_by_severity`
   - **Description**: Clearly explain:
     - Which silver tables to use (reference by name from available tables)
     - What joins to perform (if multiple tables)
     - What transformations/aggregations to apply
     - What the output represents (what metrics/KPIs it supports)
   - **Materialization**: Choose based on:
     - `incremental`: For time-series metrics that need regular updates
     - `table`: For aggregated metrics that can be fully refreshed
     - `view`: For simple transformations that don't need materialization
   - **Source Tables**: List ALL silver table names that this gold model will query/join. Must reference tables from the available silver tables provided.
   - **Source Columns**: List the specific columns from each source table that will be used:
     - Include columns used for joins (join keys)
     - Include columns used for filters/WHERE clauses
     - Include columns used in aggregations (GROUP BY, COUNT, SUM, etc.)
     - Include columns that are directly mapped to output columns
     - For each column, specify: table_name, column_name, and usage (e.g., "join key", "filter", "aggregation", "direct mapping")
   - **Expected Columns**: List all columns the gold model should produce:
     - MUST include `connection_id` (required for multi-tenant filtering)
     - Include all dimensions needed for grouping/filtering
     - Include all measures/metrics to be calculated
     - Include any derived fields from field_instructions (if provided in metrics)

3. **Grouping Strategy:**
   - Group related metrics into a single gold model if they share the same base tables and dimensions
   - Create separate gold models if metrics have different base tables or require different aggregation strategies
   - Consider time grain: metrics with different time grains (daily vs weekly) may need separate models

4. **Column Extraction:**
   - Extract columns from metric dimensions, measures, and filters
   - Reference actual column names from the silver table schemas provided
   - Ensure all referenced columns exist in the silver tables

**Output Format:**
Generate a GoldModelPlan with:
- `requires_gold_model`: Boolean indicating if gold models are needed
- `reasoning`: Explanation of why gold models are or are not needed
- `specifications`: List of GoldModelSpecification objects (only if requires_gold_model=True)

Each specification must include:
- `name`: Gold model name following convention
- `description`: Detailed description of transformations
- `materialization`: "incremental", "table", or "view"
- `source_tables`: List of silver table names (strings) that this gold model will use as sources
- `source_columns`: List of SourceTableColumn objects with:
  - `table_name`: Name of the source silver table
  - `column_name`: Name of the column in that table
  - `usage`: How the column is used (e.g., "join key", "filter", "aggregation", "direct mapping")
- `expected_columns`: List of OutputColumn objects, MUST include connection_id

**IMPORTANT - Source Tables and Columns:**
- You MUST explicitly list ALL silver tables that each gold model will query or join
- You MUST list the specific columns from each source table that will be used
- This documentation is critical for data lineage and validation
- Reference the actual table and column names from the "Available Silver Tables" section above
"""

        return prompt

    def _format_metrics(self, metrics: list[dict[str, Any]]) -> str:
        """Format metrics list for prompt."""
        if not metrics:
            return "No metrics provided."

        formatted = []
        for i, metric in enumerate(metrics[:20], 1):  # Limit to first 20
            name = metric.get("name") or metric.get("metric_name") or metric.get("metric_id", f"metric_{i}")
            description = metric.get("description") or metric.get("metric_definition", "")
            
            # Extract key fields
            dimensions = metric.get("dimensions") or metric.get("data_groups", [])
            measures = metric.get("measure") or metric.get("calculation_method", "")
            base_table = metric.get("base_table") or metric.get("table_name", "")
            source_schemas = metric.get("source_schemas", [])
            
            formatted.append(f"{i}. **{name}**")
            if description:
                formatted.append(f"   Description: {description}")
            if base_table:
                formatted.append(f"   Base Table: {base_table}")
            if source_schemas:
                formatted.append(f"   Source Schemas: {', '.join(source_schemas[:3])}")
            if dimensions:
                formatted.append(f"   Dimensions: {', '.join(dimensions[:5])}")
            if measures:
                formatted.append(f"   Measure: {measures[:100]}")  # Truncate long measures
            formatted.append("")

        return "\n".join(formatted)

    def _format_silver_tables(self, tables_info: list[SilverTableInfo]) -> str:
        """Format silver tables info for prompt."""
        if not tables_info:
            return "No silver tables available."

        formatted = []
        for table_info in tables_info:
            formatted.append(f"**Table: {table_info.table_name}**")
            if table_info.reason:
                formatted.append(f"Reason: {table_info.reason}")
            
            # Format schema using the render_schema method
            schema_text = table_info.render_schema()
            formatted.append(f"Schema:\n{schema_text}")
            
            if table_info.relevant_columns:
                formatted.append(f"Relevant Columns: {', '.join(table_info.relevant_columns)}")
            if table_info.relevant_columns_reasoning:
                formatted.append(f"Column Reasoning: {table_info.relevant_columns_reasoning}")
            
            formatted.append("")

        return "\n".join(formatted)

    def _ensure_connection_id(self, plan: GoldModelPlan) -> None:
        """
        Ensure connection_id is present in all specifications' expected_columns.
        
        This is a safety check - the LLM should include it, but we enforce it.
        """
        if not plan.specifications:
            return

        for spec in plan.specifications:
            column_names = {col.name for col in spec.expected_columns}
            if "connection_id" not in column_names:
                logger.warning(
                    f"Adding missing connection_id to specification: {spec.name}"
                )
                spec.expected_columns.append(
                    OutputColumn(
                        name="connection_id",
                        description="Required for multi-tenant filtering",
                    )
                )
