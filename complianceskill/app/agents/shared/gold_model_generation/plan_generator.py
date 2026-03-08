"""
Gold Model Plan Generator for Compliance Skill

A reusable class for generating GoldModelPlan from metrics using LLMs.
Can be used for both gold model generation and dashboard generation workflows.

Assumption: Silver tables already exist and are available.
"""

import logging
from typing import Any, Optional

from langchain_core.messages import HumanMessage

from app.core.dependencies import get_llm

from .models import (
    GoldModelPlan,
    GoldModelPlanGeneratorInput,
    GoldModelSpecification,
    OutputColumn,
    SilverTableInfo,
)

logger = logging.getLogger(__name__)


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

    def _filter_metrics_by_focus_area(
        self, metrics: list[dict[str, Any]], focus_area: str
    ) -> list[dict[str, Any]]:
        """
        Filter metrics by focus area.

        Args:
            metrics: List of metrics to filter
            focus_area: Focus area name to filter by

        Returns:
            Filtered list of metrics
        """
        if not focus_area:
            return metrics

        # Focus area mapping to metric categories/keywords
        FOCUS_AREA_KEYWORDS = {
            "vulnerability_management": ["vulnerability", "vuln", "cve", "patch", "exploit"],
            "asset_inventory": ["asset", "inventory", "host", "endpoint"],
            "compliance_training": ["training", "course", "certification", "compliance"],
            "identity_access_management": ["access", "authentication", "iam", "identity"],
            "authentication_mfa": ["mfa", "authentication", "2fa"],
            "log_management_siem": ["log", "siem", "audit", "event"],
            "incident_detection": ["incident", "alert", "detection", "mttr"],
            "cloud_security_posture": ["cloud", "misconfig", "finding"],
            "patch_management": ["patch", "update", "remediation"],
            "endpoint_detection": ["endpoint", "edr", "host"],
            "network_detection": ["network", "traffic", "anomaly"],
            "data_classification": ["data", "classification", "pii"],
            "audit_logging_compliance": ["audit", "logging", "compliance"],
        }

        keywords = FOCUS_AREA_KEYWORDS.get(focus_area.lower(), [focus_area.lower()])

        filtered = []
        for metric in metrics:
            # Check metric name, description, calculation_plan_steps, and data_source_required
            metric_text = " ".join([
                metric.get("name", ""),
                metric.get("description", ""),
                metric.get("natural_language_question", ""),
                metric.get("data_source_required", ""),
                " ".join(metric.get("calculation_plan_steps", [])),
            ]).lower()

            # Check if any keyword matches
            if any(keyword in metric_text for keyword in keywords):
                filtered.append(metric)

        logger.debug(f"Filtered {len(filtered)} metrics for focus area: {focus_area} (from {len(metrics)} total)")
        return filtered

    async def generate_for_focus_area(
        self, input_data: GoldModelPlanGeneratorInput, focus_area: str
    ) -> GoldModelPlan:
        """
        Generate a GoldModelPlan for a specific focus area.
        This creates hierarchical plans (daily, weekly, monthly) for the focus area.

        Args:
            input_data: Input containing metrics, silver tables, and optional context
            focus_area: Focus area to generate plan for

        Returns:
            GoldModelPlan with hierarchical specifications (daily, weekly, monthly) for the focus area
        """
        # Filter metrics by focus area
        filtered_metrics = self._filter_metrics_by_focus_area(input_data.metrics, focus_area)

        if not filtered_metrics:
            logger.warning(f"No metrics found for focus area: {focus_area}")
            return GoldModelPlan(
                requires_gold_model=False,
                reasoning=f"No metrics found for focus area: {focus_area}",
                specifications=[],
            )

        logger.info(
            f"Generating gold model plan for focus area '{focus_area}': "
            f"{len(filtered_metrics)} metrics, {len(input_data.silver_tables_info)} silver tables"
        )

        # Create input data for this focus area
        focus_area_input = GoldModelPlanGeneratorInput(
            metrics=filtered_metrics,
            silver_tables_info=input_data.silver_tables_info,
            user_request=input_data.user_request,
            kpis=input_data.kpis,
            medallion_context=input_data.medallion_context,
            focus_areas=[focus_area],  # Single focus area for this call
        )

        # Get LLM instance
        llm = get_llm(
            temperature=self.temperature,
            model=self.model,
        )

        # Use structured output
        structured_model = llm.with_structured_output(GoldModelPlan)

        # Build prompt from input data (will create hierarchical plan)
        prompt = self._build_prompt(focus_area_input)

        try:
            # Invoke LLM to generate plan
            response = await structured_model.ainvoke([HumanMessage(content=prompt)])

            gold_model_plan = GoldModelPlan.model_validate(response)

            logger.info(
                f"Gold model plan generated for focus area '{focus_area}': "
                f"requires_gold_model={gold_model_plan.requires_gold_model}, "
                f"specifications_count={len(gold_model_plan.specifications or [])}"
            )

            # Validate and ensure connection_id is present in all specifications
            self._ensure_connection_id(gold_model_plan)

            return gold_model_plan

        except Exception as e:
            logger.exception(f"Error generating gold model plan for focus area '{focus_area}': %s", str(e))
            raise

    async def generate(
        self, input_data: GoldModelPlanGeneratorInput
    ) -> GoldModelPlan:
        """
        Generate a GoldModelPlan from metrics and silver tables.

        If focus areas are provided, generates plans for each focus area separately
        and combines them. Otherwise, generates a single plan for all metrics.

        Args:
            input_data: Input containing metrics, silver tables, and optional context

        Returns:
            GoldModelPlan with specifications for gold models needed to support the metrics
        """
        # If focus areas are provided, generate plans for each focus area
        if input_data.focus_areas and len(input_data.focus_areas) > 0:
            logger.info(
                f"Generating gold model plans by focus area: {input_data.focus_areas}"
            )

            all_specifications = []
            all_reasoning = []

            for focus_area in input_data.focus_areas:
                focus_plan = await self.generate_for_focus_area(input_data, focus_area)

                if focus_plan.requires_gold_model and focus_plan.specifications:
                    all_specifications.extend(focus_plan.specifications)
                    all_reasoning.append(f"Focus area '{focus_area}': {focus_plan.reasoning}")

            # Combine all plans
            combined_plan = GoldModelPlan(
                requires_gold_model=len(all_specifications) > 0,
                reasoning="\n\n".join(all_reasoning) if all_reasoning else "Generated plans for multiple focus areas",
                specifications=all_specifications,
            )

            logger.info(
                f"Combined gold model plan: {len(all_specifications)} specifications across {len(input_data.focus_areas)} focus areas"
            )

            return combined_plan

        # Fallback to original behavior if no focus areas
        logger.info(
            f"Generating gold model plan: {len(input_data.metrics)} metrics, "
            f"{len(input_data.silver_tables_info)} silver tables (no focus areas provided)"
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

        # Format focus areas if available
        focus_areas_text = ""
        if input_data.focus_areas:
            # If single focus area, emphasize hierarchical planning
            if len(input_data.focus_areas) == 1:
                focus_area = input_data.focus_areas[0]
                focus_areas_text = f"\n**Focus Area (SINGLE):** {focus_area}\n"
                focus_areas_text += f"\n**CRITICAL**: You are planning gold models for the '{focus_area}' focus area ONLY.\n"
                focus_areas_text += "**Create a hierarchical plan** with separate models for:\n"
                focus_areas_text += "1. **Daily models** - incremental daily snapshots (foundation layer, build from silver tables)\n"
                focus_areas_text += "2. **Weekly models** - weekly aggregations (can reference daily models using `ref()` or build from silver)\n"
                focus_areas_text += "3. **Monthly models** - monthly aggregations (can reference weekly models using `ref()` or build from silver)\n"
                focus_areas_text += "\nEach time grain should have separate models per data source (e.g., qualys daily, snyk daily).\n"
                focus_areas_text += "Weekly and monthly models should prefer referencing lower-level models when possible for efficiency.\n"
            else:
                focus_areas_text = f"\n**Focus Areas:**\n{', '.join(input_data.focus_areas)}\n"
                focus_areas_text += "\n**IMPORTANT**: Create hierarchical plans (daily, weekly, monthly) for each focus area.\n"

        prompt = f"""You are an expert in dbt modeling and Databricks data warehouse design for security analytics.

Your task is to generate a GoldModelPlan that determines what gold-layer dbt models are needed to support the provided metrics.

**CRITICAL ASSUMPTION:** Silver tables already exist and are available. You should plan gold models that build on top of these silver tables.

{user_request_text}
{focus_areas_text}
**Metrics to Support:**
{metrics_text}
{kpis_text}
**Available Silver Tables:**
{tables_text}
{medallion_text}
**Instructions:**

1. **Determine if gold models are needed:**
   - If metrics can be served directly from silver tables (simple queries), set `requires_gold_model=False`
   - If metrics require aggregations, joins across multiple silver tables (from the SAME source), or complex transformations, set `requires_gold_model=True`
   - **IMPORTANT**: Even if metrics need data from multiple sources, gold models are still needed - create separate gold models per source, then a combined model if needed

2. **For each gold model specification (if needed):**
   - **Name**: Follow convention `gold_{{vendor}}_{{entity}}` or `gold_{{vendor}}_{{entity}}_{{purpose}}`
     - Example: `gold_snyk_issues_mttr`, `gold_qualys_vulnerabilities_by_severity`
   - **Description**: Clearly explain:
     - Which silver tables to use (reference by name from available tables) - MUST be from the same data source
     - For combined models: Which source-specific gold models to reference using `ref()` (e.g., `ref('gold_qualys_vulnerabilities_daily_snapshot')`)
     - What joins to perform (if multiple tables from the SAME source - never join across different sources)
     - What transformations/aggregations to apply
     - What the output represents (what metrics/KPIs it supports)
     - **CRITICAL**: Explain how each metric can be calculated from the gold table columns (identify which columns are needed for each metric)
   - **Materialization**: Choose based on:
     - `incremental`: For time-series metrics that need regular updates
     - `table`: For aggregated metrics that can be fully refreshed
     - `view`: For simple transformations that don't need materialization
   - **Source Tables**:
     * For source-specific gold models: List ALL silver table names that this gold model will query/join. Must reference tables from the available silver tables provided. MUST be from the SAME data source (e.g., only qualys tables, or only snyk tables).
     * For combined gold models: List the source-specific gold model names (e.g., `gold_qualys_vulnerabilities_daily_snapshot`, `gold_snyk_issues_vulnerabilities_daily_snapshot`) that will be referenced using `ref()`.
   - **Source Columns**: List the specific columns from each source table that will be used:
     - Include columns used for joins (join keys)
     - Include columns used for filters/WHERE clauses
     - Include columns used in aggregations (GROUP BY, COUNT, SUM, etc.)
     - Include columns that are directly mapped to output columns
     - For each column, specify: table_name, column_name, and usage (e.g., "join key", "filter", "aggregation", "direct mapping")
   - **Expected Columns**: List all columns the gold model should produce:
     - MUST include `connection_id` (required for multi-tenant filtering)
     - **CRITICAL**: Identify ALL necessary columns for calculating each metric on top of the gold table
     - For each metric, analyze to identify required columns:
       * `calculation_plan_steps`: Identify all columns mentioned in calculation steps
       * `available_filters`: Columns needed for filtering (WHERE clauses)
       * `available_groups`: Columns needed for grouping (GROUP BY clauses)
       * `kpis_covered`: Understand what the metric measures to identify required columns
       * `natural_language_question`: Understand the metric's intent to identify implicit columns
     - Include all dimensions needed for grouping/filtering (based on metric `available_groups` and `available_filters`)
     - Include all measures/metrics to be calculated (based on metric `calculation_plan_steps`)
     - Include any derived fields from field_instructions (if provided in metrics)
     - **IMPORTANT**: The gold model should be designed so that ALL metrics can be calculated using simple SELECT queries on the gold table, without needing to join back to silver tables
     - **CRITICAL**: For each expected column, you MUST include `mapped_metrics` - a list of metric IDs/names that require this column
     - Map columns to metrics by identifying which metrics need each column:
       * Columns mentioned in calculation_plan_steps
       * Columns in available_filters (used for filtering)
       * Columns in available_groups (used for grouping)
       * Columns implied by kpis_covered (what the KPI measures)
       * Columns needed for the metric's natural_language_question
     - Example: If metric "vuln_count_by_severity" uses severity for grouping and filtering, then the "severity" column should have mapped_metrics: ["vuln_count_by_severity"]
     - This mapping is ESSENTIAL to show why each column exists and which metrics depend on it

3. **Source Table Separation Strategy (CRITICAL):**
   - **NEVER join tables from different data sources in the same gold model**
   - Each gold model should only use silver tables from a SINGLE data source (e.g., only qualys tables, or only snyk tables)
   - If metrics require data from multiple sources (e.g., qualys + snyk), create:
     a. Separate gold models for each data source (e.g., `gold_qualys_vulnerabilities_by_severity`, `gold_snyk_issues_vulnerabilities_by_severity`)
     b. A combined gold model (materialized view or table) that joins the source-specific gold models (e.g., `gold_combined_vulnerabilities_by_severity`)
   - The combined model should use `ref()` to reference the source-specific gold models, NOT join silver tables directly
   - Example structure:
     - `gold_qualys_vulnerabilities_daily_snapshot` (uses only qualys silver tables)
     - `gold_snyk_issues_vulnerabilities_daily_snapshot` (uses only snyk silver tables)
     - `gold_combined_vulnerabilities_daily_snapshot` (uses `ref('gold_qualys_vulnerabilities_daily_snapshot')` and `ref('gold_snyk_issues_vulnerabilities_daily_snapshot')`)

4. **Hierarchical Planning Strategy (CRITICAL - Create Daily, Weekly, Monthly Hierarchy):**
   - **You are working on a SINGLE focus area** - all metrics provided belong to the same focus area
   - **Create a hierarchical plan** with separate gold models for different time grains:
     * **Daily models**: For metrics that need daily snapshots, trends, or real-time monitoring
       - Example: `gold_{{vendor}}_{{entity}}_daily_snapshot` (e.g., `gold_snyk_issues_daily_snapshot`)
       - Use `incremental` materialization with daily grain
       - Supports daily trends, rolling averages, and time-series analysis
       - Build directly from silver tables
     * **Weekly models**: For metrics that need weekly aggregations or weekly trends
       - Example: `gold_{{vendor}}_{{entity}}_weekly_snapshot` (e.g., `gold_snyk_issues_weekly_snapshot`)
       - Use `incremental` or `table` materialization with weekly grain
       - Can reference daily models using `ref('gold_{{vendor}}_{{entity}}_daily_snapshot')` for aggregation, OR build from silver tables
       - Prefer referencing daily models if they exist (more efficient)
     * **Monthly models**: For metrics that need monthly aggregations or monthly reporting
       - Example: `gold_{{vendor}}_{{entity}}_monthly_snapshot` (e.g., `gold_snyk_issues_monthly_snapshot`)
       - Use `table` materialization with monthly grain
       - Can reference weekly models using `ref('gold_{{vendor}}_{{entity}}_weekly_snapshot')` OR daily models OR build from silver tables
       - Prefer referencing weekly/daily models if they exist (more efficient)
   - **Hierarchy Rules:**
     * Daily models are the foundation - they build directly from silver tables
     * Weekly models should reference daily models using `ref('gold_{{vendor}}_{{entity}}_daily_snapshot')` when possible (more efficient than rebuilding from silver)
     * Monthly models should reference weekly models using `ref('gold_{{vendor}}_{{entity}}_weekly_snapshot')` when possible (more efficient than rebuilding from silver or daily)
     * If a time grain model doesn't exist yet, build from silver tables
   - **Data Source Separation:**
     * Each time grain model should only use tables from a SINGLE data source (e.g., only qualys, or only snyk)
     * If metrics need data from multiple sources, create separate models per source per time grain, then a combined model if needed
   - **Example hierarchical structure for vulnerability_management focus area:**
     * Daily: `gold_snyk_issues_daily_snapshot` (from snyk silver tables)
     * Daily: `gold_qualys_vulnerabilities_daily_snapshot` (from qualys silver tables)
     * Weekly: `gold_snyk_issues_weekly_snapshot` (from `ref('gold_snyk_issues_daily_snapshot')` - aggregates daily)
     * Weekly: `gold_qualys_vulnerabilities_weekly_snapshot` (from `ref('gold_qualys_vulnerabilities_daily_snapshot')` - aggregates daily)
     * Monthly: `gold_snyk_issues_monthly_snapshot` (from `ref('gold_snyk_issues_weekly_snapshot')` - aggregates weekly)
     * Monthly: `gold_qualys_vulnerabilities_monthly_snapshot` (from `ref('gold_qualys_vulnerabilities_weekly_snapshot')` - aggregates weekly)
   - **Benefits of hierarchical planning:**
     * Reduces prompt size (each focus area gets its own focused plan)
     * Creates efficient data pipelines (weekly/monthly can aggregate from daily/weekly)
     * Improves model organization and maintainability
     * Allows incremental refreshes at appropriate grains
     * SQL generation becomes simple execution of the hierarchical plan
   - **All metrics must be calculable from the resulting gold table(s)** - ensure every metric can be computed using the columns in the gold model(s)

5. **Column Identification for Metric Calculations:**
   - **CRITICAL**: Identify ALL necessary columns for calculating each metric on top of the gold table
   - For each metric, analyze:
     * `calculation_plan_steps`: Identify all columns mentioned in calculation steps
     * `available_filters`: Columns needed for filtering (WHERE clauses)
     * `available_groups`: Columns needed for grouping (GROUP BY clauses)
     * `kpis_covered`: Understand what the metric measures to identify required columns
     * `natural_language_question`: Understand the metric's intent to identify implicit columns
   - Ensure the gold model's `expected_columns` include ALL columns needed to calculate ALL assigned metrics
   - Each column in `expected_columns` must be:
     * Directly mapped from source silver table columns, OR
     * Calculated/aggregated from source columns (e.g., COUNT, SUM, AVG)
     * Derived from transformations (e.g., DATE_TRUNC for time grain normalization)
   - The gold model should be designed so that metrics can be calculated using simple SELECT queries on the gold table, without needing to join back to silver tables

6. **Column Extraction:**
   - Extract columns from metric dimensions, measures, and filters
   - Reference actual column names from the silver table schemas provided
   - Ensure all referenced columns exist in the silver tables
   - For combined models (multi-source), extract columns from the source-specific gold models (using `ref()`), not from silver tables

**Output Format:**
Generate a GoldModelPlan with:
- `requires_gold_model`: Boolean indicating if gold models are needed
- `reasoning`: Explanation of why gold models are or are not needed
- `specifications`: List of GoldModelSpecification objects (only if requires_gold_model=True)

Each specification must include:
- `name`: Gold model name following convention
- `description`: Detailed description of transformations
- `materialization`: "incremental", "table", or "view"
- `source_tables`:
  * For source-specific gold models: List of silver table names (strings) that this gold model will use as sources (MUST be from the same data source)
  * For combined gold models: List of source-specific gold model names (strings) that will be referenced using `ref()`
- `source_columns`: List of SourceTableColumn objects with:
  - `table_name`: Name of the source silver table (for source-specific models) OR source gold model name (for combined models)
  - `column_name`: Name of the column in that table/model
  - `usage`: How the column is used (e.g., "join key", "filter", "aggregation", "direct mapping")
- `expected_columns`: List of OutputColumn objects, MUST include connection_id
  - Each OutputColumn must include:
    - `name`: Column name
    - `description`: What the column represents
    - `mapped_metrics`: List of metric IDs/names that require this column (ESSENTIAL - shows which metrics depend on this column)

**IMPORTANT - Metric Bucketing and Source Tables:**
- **CRITICAL**: You MUST bucket metrics into separate gold models based on focus area, data source, time grain, and entity
- Each bucket should result in a separate gold model specification
- For source-specific gold models: You MUST explicitly list ALL silver tables that each gold model will query or join (MUST be from the same data source)
- For combined gold models: You MUST list the source-specific gold model names that will be referenced using `ref()` (e.g., `ref('gold_qualys_vulnerabilities_daily_snapshot')`)
- You MUST list the specific columns from each source table (or source gold model) that will be used
- This documentation is critical for data lineage and validation
- Reference the actual table and column names from the "Available Silver Tables" section above
- **CRITICAL**: NEVER join silver tables from different data sources (e.g., qualys and snyk) in the same gold model. Create separate gold models per source, then a combined model if needed.
- **For each gold model specification, clearly indicate which bucket it belongs to** (focus_area, data_source, time_grain, entity) in the description or name

**CRITICAL - Metric-to-Column Mapping:**
- For EVERY expected column, you MUST populate the `mapped_metrics` field
- **IMPORTANT**: `mapped_metrics` MUST ONLY include metric IDs that exist in the input metrics list provided above
- **DO NOT** include metric IDs that are not in the input metrics list (e.g., filtered out metrics, non-existent metrics)
- This field shows which metrics from the input metrics list require this column
- To determine mappings:
  1. Read each metric's `id` field from the input metrics list - these are the ONLY valid metric IDs to use
  2. Read each metric's `calculation_plan_steps` - identify column names mentioned
  3. Check `available_filters` - these are columns used for filtering
  4. Check `available_groups` - these are columns used for grouping
  5. Check `kpis_covered` - understand what the metric measures
  6. Check `natural_language_question` - understand the metric's intent
- Example mapping:
  - Column "severity" -> mapped_metrics: ["vuln_count_by_severity", "vuln_count_by_severity_critical_vuln_count"] (only if both metrics exist in input list)
  - Column "connection_id" -> mapped_metrics: list of all metric IDs from input list (since it's required for all)
- This mapping is ESSENTIAL to show why each column exists and which metrics depend on it
- Without this mapping, it's unclear why columns are needed and which metrics they support
- **VALIDATION**: After generating the plan, verify that every metric ID in `mapped_metrics` appears in the input metrics list
"""

        return prompt

    def _format_metrics(self, metrics: list[dict[str, Any]]) -> str:
        """Format metrics list for prompt."""
        if not metrics:
            return "No metrics provided."

        formatted = []
        for i, metric in enumerate(metrics[:20], 1):  # Limit to first 20
            metric_id = metric.get("id") or metric.get("metric_id", f"metric_{i}")
            name = metric.get("name") or metric.get("metric_name") or metric_id
            description = metric.get("description") or metric.get("metric_definition", "")

            # Extract key fields
            dimensions = metric.get("dimensions") or metric.get("data_groups", [])
            measures = metric.get("measure") or metric.get("calculation_method", "")
            base_table = metric.get("base_table") or metric.get("table_name", "")
            source_schemas = metric.get("source_schemas", [])

            # Extract fields needed for column mapping
            calculation_steps = metric.get("calculation_plan_steps", [])
            available_filters = metric.get("available_filters", [])
            available_groups = metric.get("available_groups", [])
            kpis_covered = metric.get("kpis_covered", [])
            natural_language_question = metric.get("natural_language_question", "")

            formatted.append(f"{i}. **{name}** (ID: {metric_id})")
            if description:
                formatted.append(f"   Description: {description}")
            if natural_language_question:
                formatted.append(f"   Question: {natural_language_question}")
            if base_table:
                formatted.append(f"   Base Table: {base_table}")
            if source_schemas:
                formatted.append(f"   Source Schemas: {', '.join(source_schemas[:3])}")
            if dimensions:
                formatted.append(f"   Dimensions: {', '.join(dimensions[:5])}")
            if measures:
                formatted.append(f"   Measure: {measures[:100]}")  # Truncate long measures
            if calculation_steps:
                formatted.append(f"   Calculation Steps: {len(calculation_steps)} steps")
                # Show first 2 steps to give context about columns used
                for step_idx, step in enumerate(calculation_steps[:2], 1):
                    formatted.append(f"     Step {step_idx}: {step[:150]}")
            if available_filters:
                formatted.append(f"   Available Filters: {', '.join(available_filters[:5])}")
            if available_groups:
                formatted.append(f"   Available Groups: {', '.join(available_groups[:5])}")
            if kpis_covered:
                formatted.append(f"   KPIs Covered: {', '.join(str(k) for k in kpis_covered[:5])}")
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
