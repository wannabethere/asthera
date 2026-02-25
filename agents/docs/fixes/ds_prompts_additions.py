"""
Additions to append to ds_prompts.py
-------------------------------------
1. DS_FUNCTION_MAP_GENERATOR_PROMPT  — replaces keyword-matching in Python
2. get_ds_function_map_generator_prompt() getter
3. DS_PIPELINE_PLANNER_FINAL_SELECT_ADDENDUM — paste into ds_pipeline_planner.md
"""

# =============================================================================
# DS_FUNCTION_MAP_GENERATOR
# Loaded by ds_rag_agent._generate_function_map()
# =============================================================================

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


def get_ds_function_map_generator_prompt() -> str:
    """DS_FUNCTION_MAP_GENERATOR — selects appendix functions needed for the pipeline."""
    return DS_FUNCTION_MAP_GENERATOR_PROMPT


# =============================================================================
# DS_PIPELINE_PLANNER — final_select addendum
# Paste this block into ds_pipeline_planner.md after the `output_columns` spec.
# =============================================================================

DS_PIPELINE_PLANNER_FINAL_SELECT_ADDENDUM = """
`final_select`
  Specifies exactly how the final SELECT is built from the step CTEs.
  The SQL assembler reads this verbatim — no conditions in Python code.

  Two types:

  **type: "simple"** — single output step (all steps form a linear chain)
  {
    "type": "simple",
    "from_step": "step_3",         ← the step whose output is the final answer
    "post_filter": null,            ← or e.g. "sma_value > 0"
    "order_by": ["division", "time_period"]
  }

  **type: "join"** — parallel branch steps (two or more steps share same input_source)
  {
    "type": "join",
    "primary_step": "step_3",      ← first branch CTE, aliased as "p"
    "primary_columns": ["division", "time_period", "sma_value", "upper_band", "lower_band"],
    "join_steps": [
      {
        "step": "step_4",          ← second branch CTE, aliased as "j0"
        "join_type": "JOIN",
        "on": ["division", "time_period"],
        "select_columns": ["value", "anomaly_type", "anomaly_score"]
      }
    ],
    "post_filter": "j0.anomaly_type != 'normal'",
    "order_by": ["division", "time_period"]
  }

RULES for final_select:
- Use "simple" when every step has a unique input_source (linear chain)
- Use "join" when two or more steps share the same input_source (parallel branches)
- primary_columns: list only column names from primary_step.output_columns
- select_columns: list only the columns the user needs from the join step;
  omit join key columns (they are already in primary_columns)
- join_type is always "JOIN" (inner join on shared group + time keys)
- post_filter uses alias "j0" for join_steps[0], "j1" for join_steps[1];
  primary step has no alias prefix
- order_by uses bare column names (no alias prefix needed)

EXAMPLES:

  3-step linear pipeline → "simple", from_step: "step_3"

  4-step anomaly + trend pipeline (step_3 and step_4 both read step_2) →
    "join", primary_step: "step_3", join_steps: [{step: "step_4", on: ["division", "time_period"]}]
"""
