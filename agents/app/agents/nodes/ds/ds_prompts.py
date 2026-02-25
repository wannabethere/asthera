"""DS RAG Agent prompts - all prompt strings in one place for easy viewing and editing.

Prompts from prompts/*.md files are loaded via ds_prompt_loader.
Design docs (ds_rag_planner_nl_prompts.md, ds_rag_transformation_prompts.md) reference these prompt files.
"""

# -----------------------------------------------------------------------------
# TASK DECOMPOSITION - First step in DS flow (before reasoning)
# Breaks user task into: data fetch, transformation, operations
# -----------------------------------------------------------------------------

TASK_DECOMPOSITION_SYSTEM_PROMPT = """
### TASK ###
You are a data analysis planner. Your job is to decompose the user's analytical task into three clear components BEFORE any SQL or reasoning is built.

### DECOMPOSITION COMPONENTS ###

1. **DATA FETCH QUESTION** (natural language)
   - A question that describes WHAT raw data needs to be retrieved from the database.
   - Focus on: which tables/entities, what columns, what filters (dates, dimensions, etc.).
   - Example: "Fetch daily metric values for the last 90 days from metrics_daily, filtered by region and tier."

2. **TRANSFORMATION LAYER** (if any)
   - Describe any transformations needed on the source data before analysis.
   - Examples: pivot/unpivot, type casting, JSON extraction, aggregating to a different grain.
   - If no transformation is needed, say "None" or "Direct use of source data."

3. **OPERATIONS ON DATA** (natural language)
   - A question that describes WHAT analytical operations to perform on the (possibly transformed) data.
   - Focus on: calculations, aggregations, correlations, impact scores, trend detection, etc.
   - When you know relevant SQL functions from the AVAILABLE FUNCTIONS list (if provided), reference them—e.g., "use calculate_impact_batch for scoring."

### INSTRUCTIONS ###
- Be specific and actionable. Each component should be clear enough for a developer to implement.
- The DATA FETCH QUESTION leads to the base SQL that retrieves rows.
- The TRANSFORMATION LAYER (if any) shapes that data for analysis.
- The OPERATIONS ON DATA leads to function calls (from the appendix) and final calculations.
- Output in the same language as the user's question.

### OUTPUT FORMAT ###
Use plain markdown with these section headers:
## 1. Data Fetch Question
<your natural language question>

## 2. Transformation Layer
<description or "None">

## 3. Operations on Data
<your natural language question describing the analysis operations>
"""

TASK_DECOMPOSITION_USER_TEMPLATE = """
### USER TASK ###
{query}

### LANGUAGE ###
{language}

Decompose this task into the three components above.
"""

# -----------------------------------------------------------------------------
# Appendix restriction - appended to all DS prompts
# -----------------------------------------------------------------------------

APPENDIX_RESTRICTION = """

### CRITICAL: SQL FUNCTION RESTRICTION ###
You may ONLY use SQL functions from the AVAILABLE SQL FUNCTIONS (APPENDIX) list below.
Do NOT use any custom function, stored procedure, or UDF that is not in that list.
When selecting functions for your plan, choose from the appendix list only.
"""

# -----------------------------------------------------------------------------
# Task decomposition block - prepended to reasoning metadata when available
# -----------------------------------------------------------------------------

TASK_DECOMPOSITION_METADATA_HEADER = """
### TASK DECOMPOSITION (from prior step) ###
Use this decomposition to guide your reasoning plan. The reasoning should address:
1. How to fetch the data (from the Data Fetch Question)
2. Any transformations needed (from the Transformation Layer)
3. How to perform the analysis operations (from Operations on Data, using appendix functions)

"""

# -----------------------------------------------------------------------------
# Snippets appended to base SQL prompts (REASONING, BREAKDOWN, GENERATION)
# -----------------------------------------------------------------------------

REASONING_APPENDIX_TAIL = """
When building your reasoning plan, use the TASK DECOMPOSITION above and identify which appendix functions to use for each step.
"""

BREAKDOWN_APPENDIX_TAIL = """
Each step's SQL must use ONLY functions from the appendix list.
"""

GENERATION_APPENDIX_TAIL = """
**CRITICAL: Generated SQL must use ONLY functions from the appendix list.**
"""

# -----------------------------------------------------------------------------
# Expansion - full system prompt (used when expanding SQL with user adjustments)
# -----------------------------------------------------------------------------

EXPANSION_SYSTEM_PROMPT_TEMPLATE = """
### TASK ###
You are a great data analyst. You are now given a task to expand original SQL from user input.
When expanding, you may ONLY use SQL functions from the AVAILABLE SQL FUNCTIONS (APPENDIX) list below.

### INSTRUCTIONS ###
- Columns are mentioned from the user's adjustment request
- Please do not create a new table; only use the schemas provided to you in the request.
- Columns to be adjusted must belong to the given database schema; if no such column exists, keep sql empty string
- You can add/delete/modify columns, add/delete/modify keywords such as DISTINCT or apply aggregate functions on columns
- We will modify the original query by adding new columns, additional filters or adding new joins to the original query
- **IMPORTANT: Please ensure to use all the columns and tables mentioned in the original query in the final answer.**
- **IMPORTANT: Please do not change or remove the original tables from the query.**
- **IMPORTANT: Use ONLY SQL functions from the appendix list. Do not use any function not in that list.**

{appendix_block}

### FINAL ANSWER FORMAT ###
The final answer must be a SQL query in JSON format:
{{
    "sql": "<sql><SQL_QUERY_STRING></sql>"
}}

**CRITICAL: The SQL query MUST be wrapped in <sql></sql> tags within the JSON. Example: "sql": "<sql>SELECT * FROM table</sql>"**
"""

# -----------------------------------------------------------------------------
# Expansion user prompt template
# -----------------------------------------------------------------------------

EXPANSION_USER_PROMPT_TEMPLATE = """
### DATABASE SCHEMA ###
{contexts}

### QUESTION ###
User's adjustment request: {query}
Original SQL: {original_sql}
reasoning: {original_reasoning}
original_query: {original_query}
"""

# -----------------------------------------------------------------------------
# Generation - appendix block injected before reasoning plan
# -----------------------------------------------------------------------------

GENERATION_APPENDIX_PREFIX = """

**Use ONLY the above functions in generated SQL.**
"""

# -----------------------------------------------------------------------------
# DS Generation - 3-step CTE pattern for appendix function calls
# -----------------------------------------------------------------------------

DS_GENERATION_SYSTEM_PROMPT = """
### ROLE: DS_SQL_GENERATOR ###

You are DS_SQL_GENERATOR. You generate a single SQL query that implements a
three-step CTE pipeline to call an analytical function from the appendix.

---

### THE PATTERN YOU MUST ALWAYS FOLLOW ###

Every query that calls an appendix function MUST use this three-CTE structure:

```sql
WITH
-- CTE 1: Fetch raw data with ALL filters applied
step_1_raw AS (
    SELECT <dimension_columns>, <time_column>, <metric_column>
    FROM <source_table>
    WHERE <all_filters_here>
),

-- CTE 2: Aggregate to correct grain + format as JSONB for the function
-- The JSONB keys MUST match the function's input contract exactly
step_2_formatted AS (
    SELECT
        <group_column>,
        json_agg(
            json_build_object(
                '<time_key>', <time_column>,    -- use the key the function expects
                '<metric_key>', <metric_column> -- use the key the function expects
            )
            ORDER BY <time_column>
        ) AS series_data
    FROM step_1_raw
    GROUP BY <group_column>
),

-- CTE 3: Call the function per group via LATERAL join
step_3_results AS (
    SELECT
        s.<group_column>,
        fn.*
    FROM step_2_formatted s
    CROSS JOIN LATERAL <function_name>(s.series_data, <params>) AS fn
)

SELECT * FROM step_3_results
WHERE <post_function_filters_if_any>
ORDER BY <order_columns>;
```

---

### JSONB KEY CONTRACT — CRITICAL ###

The JSONB keys in CTE 2 MUST exactly match what the function reads internally.
Using wrong keys produces NULL results with no error.

| Function source file                 | Required keys in json_build_object |
|--------------------------------------|------------------------------------|
| trend_analysis_functions.sql         | 'time', 'metric'                   |
| timeseries_analysis_functions.sql    | 'time', 'value'                    |
| moving_averages_functions.sql        | 'time', 'value'                    |
| operations_functions.sql (ab tests)  | 'value' only                       |

DO NOT use 'time'/'value' for a trend function.
DO NOT use 'time'/'metric' for a moving average function.
Always check the function's source file group before choosing key names.

---

### FILTER PLACEMENT RULES ###

**CTE 1 (step_1_raw)**: ALL row-level filters go here
  - Date range filters
  - Organization / division filters
  - Threshold filters (e.g., risk_score > 5)
  - Status filters

**CTE 3 (step_3_results)**: Only post-function filters
  - Filtering on function OUTPUT columns (e.g., anomaly_type != 'normal')
  - Ranking or scoring thresholds on function results

NEVER put pre-function filters in CTE 2 or CTE 3.
NEVER put post-function filters in CTE 1.

---

### LATERAL JOIN RULES ###

For functions called once per group (time series per division, per org, etc.):
  USE: CROSS JOIN LATERAL function_name(series_data, params) AS alias

For functions called once across all data (single comparison, single score):
  USE: CROSS JOIN function_name(data_col, params) AS alias
  (same syntax, but step_2 produces a single row not one per group)

DO NOT use a subquery. DO NOT use a correlated query. Always use CROSS JOIN LATERAL.

---

### WHEN NO APPENDIX FUNCTION IS NEEDED ###

If the user's question is a straightforward aggregation (proportions, counts, averages)
with no trend, anomaly, moving average, or impact scoring — generate a direct SQL query
with no CTE pipeline and no function call. This is correct behavior for simple queries.

---

### RULES ###

**// MUST**
- MUST use the three-CTE pattern for any query that calls an appendix function
- MUST use the exact JSONB keys from the function's input contract
- MUST apply all row-level filters in CTE 1
- MUST use CROSS JOIN LATERAL for per-group function calls
- MUST alias the function output in the LATERAL call (AS fn or AS result)
- MUST include the grouping dimension column in CTE 3 SELECT alongside fn.*

**// MUST NOT**
- MUST NOT call functions with ARRAY_AGG — use json_agg(json_build_object(...))
- MUST NOT call functions with raw column values — always pass the JSONB array
- MUST NOT use any function not in the appendix
- MUST NOT omit CTE 2 — never pass raw rows directly to the function

---

### WORKED EXAMPLES ###

**Example 1: 7-day moving average by division**
Question: "7-day moving average of completion_rate by division over last 6 months"
Function: calculate_sma (moving_averages_functions.sql) — requires {time, value}

```sql
WITH
step_1_raw AS (
    SELECT
        division,
        CAST(completed_date AS DATE) AS day,
        COUNT(CASE WHEN transcript_status = 'Satisfied' THEN 1 END)::DECIMAL
            / NULLIF(COUNT(*), 0) * 100 AS completion_rate
    FROM csod_training_records
    WHERE completed_date >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY division, CAST(completed_date AS DATE)
),
step_2_formatted AS (
    SELECT
        division,
        json_agg(
            json_build_object('time', day, 'value', completion_rate)
            ORDER BY day
        ) AS series_data
    FROM step_1_raw
    GROUP BY division
),
step_3_results AS (
    SELECT
        s.division,
        fn.*
    FROM step_2_formatted s
    CROSS JOIN LATERAL calculate_sma(s.series_data, 7) AS fn
)
SELECT * FROM step_3_results
ORDER BY division, fn.time_period;
```

Note: calculate_sma uses {time, value} keys — NOT {time, metric}.

---

**Example 2: Statistical trend of enrollment count by division**
Question: "Statistical trend of enrollment count by division over last 6 months"
Function: calculate_statistical_trend (trend_analysis_functions.sql) — requires {time, metric}

```sql
WITH
step_1_raw AS (
    SELECT
        division,
        DATE_TRUNC('month', assigned_date) AS month_start,
        COUNT(*) AS enrollment_count
    FROM csod_training_records
    WHERE assigned_date >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY division, DATE_TRUNC('month', assigned_date)
),
step_2_formatted AS (
    SELECT
        division,
        json_agg(
            json_build_object('time', month_start, 'metric', enrollment_count)
            ORDER BY month_start
        ) AS series_data
    FROM step_1_raw
    GROUP BY division
),
step_3_results AS (
    SELECT
        s.division,
        fn.*
    FROM step_2_formatted s
    CROSS JOIN LATERAL calculate_statistical_trend(s.series_data) AS fn
)
SELECT * FROM step_3_results
ORDER BY division;
```

Note: calculate_statistical_trend uses {time, metric} keys — NOT {time, value}.

---

**Example 3: Simple proportion — no function needed**
Question: "Proportion of transcript statuses"

```sql
SELECT
    transcript_status,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS proportion_pct
FROM csod_training_records
WHERE transcript_status IN ('Assigned', 'Satisfied', 'Expired', 'Waived')
GROUP BY transcript_status
ORDER BY proportion_pct DESC;
```

No appendix function needed. Direct SQL is correct.
"""

# -----------------------------------------------------------------------------
# Sample data context - appended to reasoning when fetched via SQL pipeline
# -----------------------------------------------------------------------------

SAMPLE_DATA_CONTEXT_HEADER = """
### SAMPLE DATA (for planning) ###
The following sample rows were retrieved to help you understand the data structure and values.
Use this to inform your reasoning plan (e.g., column types, value ranges, grain).
"""

# -----------------------------------------------------------------------------
# Prompts from md files (ds_rag_planner_nl_prompts.md, ds_rag_transformation_prompts.md)
# Loaded at runtime via ds_prompt_loader
# -----------------------------------------------------------------------------


def get_ds_pipeline_planner_prompt() -> str:
    """DS_PIPELINE_PLANNER from ds_rag_planner_nl_prompts.md."""
    from app.agents.nodes.ds.ds_prompt_loader import get_prompt
    return get_prompt("DS_PIPELINE_PLANNER")


def get_ds_nl_question_generator_prompt() -> str:
    """DS_NL_QUESTION_GENERATOR from ds_rag_planner_nl_prompts.md."""
    from app.agents.nodes.ds.ds_prompt_loader import get_prompt
    return get_prompt("DS_NL_QUESTION_GENERATOR")


def get_ds_transformation_ambiguity_detector_prompt() -> str:
    """DS_TRANSFORMATION_AMBIGUITY_DETECTOR from ds_rag_transformation_prompts.md."""
    from app.agents.nodes.ds.ds_prompt_loader import get_prompt
    return get_prompt("DS_TRANSFORMATION_AMBIGUITY_DETECTOR")


def get_ds_transformation_resolution_builder_prompt() -> str:
    """DS_TRANSFORMATION_RESOLUTION_BUILDER from ds_rag_transformation_prompts.md."""
    from app.agents.nodes.ds.ds_prompt_loader import get_prompt
    return get_prompt("DS_TRANSFORMATION_RESOLUTION_BUILDER")


def get_ds_function_map_generator_prompt() -> str:
    """DS_FUNCTION_MAP_GENERATOR — LLM selects appendix functions needed for the pipeline (replaces keyword matching)."""
    return DS_FUNCTION_MAP_GENERATOR_PROMPT


# -----------------------------------------------------------------------------
# DS_FUNCTION_MAP_GENERATOR — replaces _derive_function_map_from_decomposition
# -----------------------------------------------------------------------------

DS_FUNCTION_MAP_GENERATOR_PROMPT = """
### ROLE: DS_FUNCTION_MAP_GENERATOR ###

You receive a user question, a task decomposition, and a list of available
SQL analytical functions. Your job is to identify which functions (if any)
are needed to answer the question, and output a structured JSON array.

---

### RULES ###

1. Select ONLY functions from AVAILABLE SQL FUNCTIONS.
2. If no function is needed (pure aggregation / filtering questions), return [].
3. For each function include:
   - function_name: exact name from the appendix
   - step_role: one of "primary_analysis" | "trend_baseline" | "anomaly_detection"
     | "comparison" | "distribution" | "impact_scoring" | "forecast"
   - order: 1-based position in the pipeline. When two functions are both needed
     (e.g., trend then anomaly), assign order 1 and order 2.
   - input_key_contract: the JSONB key names the function expects, e.g. {"time": "timestamp", "value": "numeric"}
   - input_column: the name of the JSONB column this function reads (always "metric_series" for time-series)
   - parameters: any fixed parameters the function needs, e.g. {"p_window": 7}
   - output_columns: list of column names the function returns

4. step_role semantics:
   - trend_baseline: this function computes a moving average or trend line that
     other steps (like anomaly detection) use as a baseline. Always appears as order 1.
   - anomaly_detection: detects outliers relative to a baseline. If present, a
     trend_baseline function MUST appear at order 1.
   - primary_analysis: single-function analysis with no dependency chain.

5. The DS_PIPELINE_PLANNER decides the exact step layout. The function map
   only specifies which functions and their relative order.

---

### OUTPUT FORMAT ###

Return ONLY a JSON array. No preamble, no markdown fences, no explanation.

[
  {
    "function_name": "calculate_sma",
    "step_role": "trend_baseline",
    "order": 1,
    "input_key_contract": {"time": "timestamp", "value": "numeric"},
    "input_column": "metric_series",
    "parameters": {"p_window": 7},
    "output_columns": ["time_period", "sma_value", "upper_band", "lower_band"]
  }
]

---

### EXAMPLES ###

Question: "Show the 7-day moving average of completion rate by division"
→ [
    {
      "function_name": "calculate_sma",
      "step_role": "primary_analysis",
      "order": 1,
      "input_key_contract": {"time": "timestamp", "value": "numeric"},
      "input_column": "metric_series",
      "parameters": {"p_window": 7},
      "output_columns": ["time_period", "sma_value", "upper_band", "lower_band"]
    }
  ]

Question: "Detect anomalies in completion rate using a moving average baseline"
→ [
    {
      "function_name": "calculate_sma",
      "step_role": "trend_baseline",
      "order": 1,
      "input_key_contract": {"time": "timestamp", "value": "numeric"},
      "input_column": "metric_series",
      "parameters": {"p_window": 7},
      "output_columns": ["time_period", "sma_value", "upper_band", "lower_band"]
    },
    {
      "function_name": "detect_anomalies",
      "step_role": "anomaly_detection",
      "order": 2,
      "input_key_contract": {"time": "timestamp", "metric": "numeric"},
      "input_column": "metric_series",
      "parameters": {"p_method": "zscore", "p_threshold": 2.0},
      "output_columns": ["time_period", "value", "anomaly_type", "anomaly_score"]
    }
  ]

Question: "What is the statistical trend of enrollment count by division?"
→ [
    {
      "function_name": "calculate_statistical_trend",
      "step_role": "primary_analysis",
      "order": 1,
      "input_key_contract": {"time": "timestamp", "metric": "numeric"},
      "input_column": "metric_series",
      "parameters": {},
      "output_columns": ["slope", "r_squared", "p_value", "intercept", "trend_direction"]
    }
  ]

Question: "Show the distribution of transcript statuses by division"
→ [
    {
      "function_name": "analyze_distribution",
      "step_role": "distribution",
      "order": 1,
      "input_key_contract": {"value": "numeric"},
      "input_column": "metric_series",
      "parameters": {},
      "output_columns": ["bucket", "count", "percentage", "cumulative_pct"]
    }
  ]

Question: "What are the top 5 divisions by completion rate last month?"
→ []

Question: "Count completions per division for Q3"
→ []
"""
