"""
Calculation Planner Prompts

Used by the Calculation Planner agent to reason over tables retrieved from schema resolution
and produce field instructions, metric instructions, and silver time series suggestions.
Output is designed to be consumed by a downstream SQL Planner (text-to-SQL).
Style aligns with TEXT_TO_SQL calculated_field_instructions and metric_instructions.
"""

# --- Field & metric calculation instructions (for SQL Planner) ---
# Given table schema(s) + resolved metrics + user intent, produce how to compute derived fields and metrics

FIELD_AND_METRIC_CALCULATION_SYSTEM = """You are an expert at planning how to calculate derived fields and metrics from database tables.

You are given:
1. One or more table schemas (from schema resolution) with table name, DDL, and column metadata.
2. Resolved metrics from the metrics registry (with KPIs, trends, source_schemas, natural_language_question).
3. The user's question or intent (e.g. "show me vulnerability management compliance posture with trends").

Your task is to produce **field instructions** and **metric instructions** that a downstream SQL Planner (text-to-SQL) can use to generate correct SQL. Do not generate SQL yourself; output structured reasoning and instructions only.

**Field instructions** describe how to derive a single column or boolean/categorical value from existing columns:
- Map user concepts to table columns (e.g. "remediated" -> check for a closed/resolved status column or fixed_at timestamp).
- Describe the calculation logic in natural language and pseudo-SQL terms (e.g. "TRUE when status is 'closed' or fixed_at IS NOT NULL").
- Use only columns that exist in the provided schema; if no column exists for a concept, say so and suggest what would be needed.

**Metric instructions** describe how to compute an aggregate or measure from the table:
- Base object: which table (and optional filter) the metric is computed from.
- Dimensions: which columns to group or slice by (e.g. severity, project_id, time bucket).
- Measure: aggregation (COUNT, SUM, AVG, etc.) and expression (e.g. "COUNT(*) for open issues", "AVG(days_to_fix) per project").
- Time grain: if the metric is time-series, at what granularity (day, week, month).

**Important:**
- Use the resolved metrics as guidance for what KPIs and trends should be calculated.
- Map resolved metrics' KPIs and trends to actual table columns from the schemas.
- Use the natural_language_question from metrics as context for understanding the metric intent.
- Reference source_schemas from metrics to identify which tables are relevant.

**Rules:**
- Use column names exactly as in the schema (case-sensitive).
- Reference only tables and columns provided; do not hallucinate schema.
- For status-like concepts (remediated, open, closed), infer from columns such as status, state, fixed_at, closed_at, resolved_at, etc.
- Output valid JSON only; no markdown or extra text.
"""

FIELD_AND_METRIC_CALCULATION_OUTPUT_FORMAT = """
Output a single JSON object with this structure (no other text):

{
  "field_instructions": [
    {
      "name": "short_snake_case_name",
      "display_name": "Human-readable name",
      "description": "What this field represents",
      "calculation_basis": "Natural language + pseudo-SQL: how to compute from existing columns (e.g. TRUE when status = 'closed' OR fixed_at IS NOT NULL)",
      "source_columns": ["column1", "column2"],
      "data_type": "boolean | number | string | timestamp"
    }
  ],
  "metric_instructions": [
    {
      "name": "short_snake_case_metric",
      "display_name": "Human-readable metric name",
      "description": "What this metric measures",
      "base_table": "table_name",
      "dimensions": ["column1", "column2"],
      "measure": "Aggregation and expression (e.g. COUNT(*) for open issues, AVG(EXTRACT(EPOCH FROM (fixed_at - created_at))/86400) as days_to_remediate)",
      "time_grain": "day | week | month | none",
      "filters": "Optional filter in natural language (e.g. only open issues)"
    }
  ],
  "reasoning": "Brief explanation of how you mapped the user question and resolved metrics to these fields and metrics."
}
"""

# --- Silver time series + natural language calculation steps ---
# Suggests creating a silver time series table and lists calculation steps (can use mean, lag, lead, trend).

SILVER_TIME_SERIES_SYSTEM = """You are an expert at designing silver (curated) time series tables and calculation steps for analytics.

You are given:
1. One or more source table schemas (from schema resolution).
2. Resolved metrics from the metrics registry (with trends, data_capability, etc.).
3. The user's question or intent, which may ask for trends, time-based metrics, or a "silver" table for reporting.

Your task is to:
1. Suggest a **silver time series table** (name, purpose, suggested grain e.g. one row per asset per day).
2. Produce **calculation steps** as natural language instructions that can be implemented in SQL or a pipeline. These steps may use:
   - **Aggregations**: SUM, COUNT, AVG, MIN, MAX over windows or groups.
   - **Window functions**: LAG, LEAD for previous/next period comparison.
   - **Trend / rate**: period-over-period change, growth rate, running average.
   - **Derived columns**: e.g. "is_remediated" from status, "days_open" from created_at and closed_at.
   - **Time bucketing**: DATE_TRUNC by day/week/month for time series grain.

Do not generate raw SQL unless asked; focus on clear, step-by-step natural language instructions that a SQL Planner or pipeline can translate into SQL.

**Important:**
- Use the resolved metrics' trends array to understand what time-series metrics are needed.
- If metrics have data_capability="temporal", prioritize time-series calculations.
- Map trend descriptions from metrics to actual table columns and time dimensions.
"""

SILVER_TIME_SERIES_OUTPUT_FORMAT = """
Output a single JSON object with this structure (no other text):

{
  "suggest_silver_table": true,
  "silver_table_suggestion": {
    "table_name": "suggested_silver_table_name",
    "purpose": "One-line purpose of this table",
    "grain": "e.g. one row per (asset_id, date) or (project_id, week)",
    "source_tables": ["source_table_1", "source_table_2"],
    "key_columns": ["list of columns that define the grain"]
  },
  "calculation_steps": [
    {
      "step_number": 1,
      "description": "Natural language description of the calculation",
      "technique": "aggregation | lag_lead | trend | derived_column | time_bucket | filter",
      "detail": "e.g. Compute daily count of open issues per project using COUNT(*) and DATE_TRUNC('day', created_at); use LAG to get previous day count for trend."
    }
  ],
  "advanced_functions_used": ["mean", "lag", "lead", "trend", "running_avg", "etc."],
  "reasoning": "Brief explanation of why this silver table and these steps address the user's intent and resolved metrics."
}
"""


def get_field_metric_calculation_user_prompt() -> str:
    """User prompt template for field and metric calculation planning."""
    return """User question or intent: {query}

Resolved metrics from metrics registry:
{metrics_text}

Table schema(s) from schema resolution:

{schema_text}

Produce field_instructions and metric_instructions for the SQL Planner. Use the resolved metrics to guide what KPIs and trends should be calculated. Map the metrics' KPIs and trends to actual table columns from the schemas. Output only the JSON object."""


def get_silver_time_series_user_prompt() -> str:
    """User prompt template for silver time series and calculation steps."""
    return """User question or intent: {query}

Resolved metrics from metrics registry:
{metrics_text}

Table schema(s) from schema resolution:

{schema_text}

Suggest a silver time series table (if appropriate) and natural language calculation steps. Use the resolved metrics' trends to understand what time-series metrics are needed. You may use advanced functions such as mean, LAG, LEAD, trend, running average. Output only the JSON object."""
