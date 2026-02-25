# DS Pipeline — Variable Step Count & Function Chaining Fix

## Diagnosis

### Three concrete problems visible in Test Case 5 output

**Test Case 5**: "Detect anomalies in completion rate using 7-day moving average"
The planner correctly identified this needs 4 steps. But two of those 4 steps are wrong.

---

**Problem 1 — Step 4 reads from step_3 (flat rows) instead of step_2 (JSONB series)**

The planner generated:
```json
"step_4": {
  "input_source": "step_3",
  "input_columns": ["division", "time_period", "value"],
  "function": {
    "function_name": "detect_anomalies",
    "p_data": "json_agg(json_build_object('time', time_period, 'metric', value))"
  }
}
```

Step 3 unpacked `calculate_sma` into **flat rows** — one row per division per time point
(division, time_period, sma_value). `detect_anomalies` needs a **JSONB series per division**
as its input. There is no JSONB series in step 3's output — just scalar columns.

The planner tried to patch this by inline-aggregating `json_agg(...)` inside the parameter.
That cannot work — you cannot call an aggregate function inside a function call parameter
without GROUP BY, and GROUP BY would collapse the per-division structure wrong.

**Correct pattern**: Both functions in a chain need JSONB series input.
Both should read from **step_2**, which already has the JSONB series per division.
Step 3 and step 4 are parallel branches from step_2, not chained through each other.

```
step_1 → step_2 (JSONB series per division)
                ├── step_3: calculate_sma(step_2.metric_series)    ← trend
                └── step_4: detect_anomalies(step_2.metric_series) ← anomalies
```

---

**Problem 2 — Step 3's nl_question_spec is missing CROSS JOIN LATERAL**

The generated step 3 plan had:
```json
"must_include": [
  "calculate_moving_average(metric_series, 7, 'sma')",
  "select division from step_2",
  "unpack output columns time_period and value"
]
```

No `"CROSS JOIN LATERAL"` in must_include. The SQL generator didn't know the LATERAL
pattern was required. Result:

```sql
-- What was generated (WRONG)
SELECT division, time_period, value
FROM calculate_moving_average(metric_series, 7, 'sma') AS moving_avg
JOIN step_2_output ON true

-- What should be generated (CORRECT)
SELECT s.division, fn.*
FROM step_2_output s
CROSS JOIN LATERAL calculate_sma(s.metric_series, 7) AS fn
```

---

**Problem 3 — ds_sql_generator.py doesn't enforce LATERAL for function steps**

`_build_plan_spec_block` and `_build_ds_step_instructions` treat all steps equally.
When a step has `function` defined, there's no enforcement that CROSS JOIN LATERAL
is used. The generator trusts the nl_question_spec entirely, which is insufficient.

---

## Fix 1 — ds_pipeline_planner.md: Two New Hard Rules

Add these rules to the `### RULES ###` section of `ds_pipeline_planner.md`:

```markdown
### FUNCTION CHAINING RULE — READ THIS FIRST FOR MULTI-FUNCTION PLANS ###

When two or more functions are called in the same pipeline, they ALMOST ALWAYS
both need JSONB array input. Function output is unpacked as FLAT ROWS (one row
per time point, per group). Flat rows cannot be passed to a second function.

CRITICAL RULE — When chaining functions A → B:
  - Step 2 produces the JSONB series (one row per group with JSONB column)
  - Step 3 calls function A, reading from step_2 (LATERAL per group)
  - Step 4 calls function B, ALSO reading from step_2 (LATERAL per group)
  - Step 4 NEVER reads from step_3

This means step_3 and step_4 are PARALLEL BRANCHES from step_2, not sequential.
The combined SQL uses step_2 as the source for both CTEs:

  step_3_output AS (SELECT s.division, fn.* FROM step_2_output s CROSS JOIN LATERAL func_a(...))
  step_4_output AS (SELECT s.division, fn.* FROM step_2_output s CROSS JOIN LATERAL func_b(...))

VIOLATION to avoid:
  ❌ step_4 reads from step_3 — step_3 output has flat rows, not JSONB series
  ❌ "p_data": "json_agg(...)" inside the function parameter — this is an aggregate
     inside a non-aggregate context and will error

EXCEPTION: If function B explicitly requires the OUTPUT of function A as its input
(e.g., function B needs the SMA values, not the original metric), then a re-aggregation
step must be inserted:
  Step 3: Call function A → flat rows
  Step 4: Re-aggregate flat rows back to JSONB series per group (new step, no function)
  Step 5: Call function B on the re-aggregated series

---

### LATERAL RULE — ALL FUNCTION STEPS ###

Every step that calls an appendix function MUST include these exact items in
nl_question_spec.must_include:
  - "CROSS JOIN LATERAL"
  - The exact function call expression: "function_name(input_col, params)"
  - "select [group_column] from [source_table]"
  - The exact alias for the function output: "alias function result as fn" or "AS fn"

NEVER omit "CROSS JOIN LATERAL" from must_include for any step that has function ≠ null.
```

---

## Fix 2 — ds_sql_generator.py: Enforce LATERAL for Function Steps

In `_build_ds_step_instructions`, add a hard LATERAL instruction block when
`step_plan.function` is not None. This fires regardless of what nl_question_spec says.

```python
def _build_ds_step_instructions(
    nl_question: str,
    schema_ddl: str,
    appendix_block: str,
    step_number: int,
    previous_step_sql: Optional[str],
    step_plan: Optional[Dict[str, Any]] = None,
    config: Optional[Configuration] = None,
) -> str:
    config = config or Configuration()
    instructions = construct_instructions(
        configuration=config,
        has_calculated_field=False,
        has_metric=False,
        instructions=None,
    )
    instructions += DS_STEP_CONTEXT_HEADER.format(step_number=step_number)

    plan_block = _build_plan_spec_block(step_plan or {})
    if plan_block:
        instructions += (
            "\n### STEP PLAN (generate SQL from this) ###\n"
            f"{plan_block}\n"
        )
    if nl_question:
        instructions += f"\n### STEP QUESTION ###\n{nl_question}\n"

    fn_spec = (step_plan or {}).get("function")
    if fn_spec:
        fn_name = fn_spec.get("function_name", "")
        fn_sig = fn_spec.get("signature", f"{fn_name}(...)")
        input_col = fn_spec.get("input_column", "series_data")
        source_table = (step_plan or {}).get("input_source", "prev_step_output")
        group_cols = _infer_group_columns(step_plan or {})

        # ← NEW: Hard LATERAL enforcement block
        instructions += f"""
### CRITICAL: SQL PATTERN FOR THIS STEP (MUST FOLLOW EXACTLY) ###

This step calls a SQL function. You MUST use CROSS JOIN LATERAL. No other pattern is valid.

REQUIRED PATTERN:
  SELECT
      s.{group_cols},
      fn.*
  FROM {source_table}_output AS s
  CROSS JOIN LATERAL {fn_sig.replace(input_col, f's.{input_col}')} AS fn
  [WHERE clause for post-function filters only]
  ORDER BY {group_cols}, fn.time_period;

DO NOT use:
  - Subquery: (SELECT ... FROM function_name(...))
  - FROM function_name(...) AS alias JOIN ... ON true
  - Correlated subquery
  - ARRAY_AGG as function input
  - json_agg() inside the function call parameter

The function {fn_name} takes a JSONB array column from the source table as p_data.
Pass the column by name: s.{input_col} — NOT an aggregate expression.

"""

    if previous_step_sql:
        instructions += f"\n### PREVIOUS STEP SQL (your step reads this output) ###\n{previous_step_sql}\n"
    if appendix_block:
        instructions += f"\n### AVAILABLE SQL FUNCTIONS ###\n{appendix_block}\n"
    instructions += (
        f"\n### DATABASE SCHEMA ###\n{schema_ddl}\n\n"
        f"### TASK ###\nGenerate SQL for this step only. "
        f"Follow the STEP PLAN and CRITICAL PATTERN exactly. Current Time: {config.show_current_time()}\n"
    )
    return instructions


def _infer_group_columns(step_plan: Dict[str, Any]) -> str:
    """Extract the group/dimension column name from step plan for LATERAL pattern."""
    fn_spec = step_plan.get("function", {}) or {}
    input_cols = step_plan.get("input_columns", [])
    # The group column is the non-JSONB, non-series input column
    for col in input_cols:
        name = col if isinstance(col, str) else col.get("name", "")
        if name and "series" not in name.lower() and "metric" not in name.lower():
            return name
    return "group_col"
```

---

## Fix 3 — ds_pipeline_planner.md: ANOMALY_DETECTION_WITH_TREND step_4 source

The planner prompt `ANOMALY_DETECTION_WITH_TREND` example correctly shows
`step_4.input_source: "step_2"`. But the prompt needs an explicit rule
paragraph before the examples, not just implicit example behavior.

Add this to the `ANOMALY_DETECTION_WITH_TREND` plan type description:

```markdown
**PLAN_TYPE: ANOMALY_DETECTION_WITH_TREND** (4 steps — REQUIRED when user asks for anomalies)

Step 3 and step 4 BOTH read from step_2. This is intentional and correct.
Step 4 MUST have input_source: "step_2" and input_columns from step_2.output_columns.
Step 4 MUST NOT have input_source: "step_3".

Why: step_2 has the JSONB series per group. Both calculate_sma and detect_anomalies
need the same JSONB series as input. Step 3's output (flat rows) cannot be fed to
detect_anomalies — it has no JSONB column.

In the combined CTE SQL, this looks like:
  step_3_output AS (... FROM step_2_output CROSS JOIN LATERAL calculate_sma ...)
  step_4_output AS (... FROM step_2_output CROSS JOIN LATERAL detect_anomalies ...)
  SELECT
      trend.division, trend.time_period,
      trend.sma_value, trend.upper_band, trend.lower_band,
      anom.anomaly_type, anom.anomaly_score
  FROM step_3_output trend
  JOIN step_4_output anom
      ON trend.division = anom.division
      AND trend.time_period = anom.time_period
```

---

## Fix 4 — ds_rag_agent.py: CTE Assembler handles parallel branches

When step_4 reads from step_2 (not step_3), the CTE assembler needs to detect
this and produce the correct JOIN at the final SELECT instead of a simple
`SELECT * FROM step_N_output`.

Modify `_assemble_pipeline_sql` in `ds_rag_agent.py`:

```python
def _assemble_pipeline_sql(
    self,
    plan: dict,
    step_sqls: dict,
) -> str:
    """
    Assemble individual step SQLs into a single CTE pipeline.
    Handles both sequential chains and parallel branches (for function chaining).
    """
    steps = plan.get("steps", {})
    step_keys = sorted(steps.keys())  # step_1, step_2, step_3, step_4...

    # Detect parallel branches: two or more steps sharing the same input_source
    input_sources = {k: steps[k].get("input_source", "") for k in step_keys}
    source_counts = {}
    for src in input_sources.values():
        source_counts[src] = source_counts.get(src, 0) + 1
    shared_sources = {src for src, count in source_counts.items() if count > 1}

    ctes = []
    for step_key in step_keys:
        sql = step_sqls.get(f"{step_key}_sql", "").strip()
        if not sql:
            continue
        # Replace CTE name references with step_output names for portability
        ctes.append(f"{step_key}_output AS (\n{sql}\n)")

    if not ctes:
        return ""

    cte_block = "WITH\n" + ",\n".join(ctes)

    # Determine final SELECT
    last_step = step_keys[-1]
    second_to_last = step_keys[-2] if len(step_keys) > 1 else None

    # Parallel branch: last two steps both read from same source (e.g., both from step_2)
    if (
        second_to_last
        and len(step_keys) >= 4
        and input_sources.get(last_step) == input_sources.get(second_to_last)
        and input_sources.get(last_step) in shared_sources
    ):
        # Both branches read from same source — JOIN them on group + time
        branch_a = second_to_last  # e.g., step_3 (trend)
        branch_b = last_step        # e.g., step_4 (anomalies)

        group_col = _infer_group_columns(steps.get(branch_a, {}))
        final_sql = f"""
{cte_block}
SELECT
    trend.{group_col},
    trend.time_period,
    trend.sma_value,
    trend.upper_band,
    trend.lower_band,
    anom.value,
    anom.anomaly_type,
    anom.anomaly_score
FROM {branch_a}_output trend
JOIN {branch_b}_output anom
    ON trend.{group_col} = anom.{group_col}
    AND trend.time_period = anom.time_period
WHERE anom.anomaly_type != 'normal'
ORDER BY trend.{group_col}, trend.time_period;
"""
    else:
        # Sequential chain — just SELECT * from the final step
        final_sql = f"{cte_block}\nSELECT * FROM {last_step}_output"

    return final_sql.strip()
```

---

## What the Correct 4-Step Output Should Look Like

**For Test Case 5**: "Detect anomalies using 7-day moving average"

```sql
WITH
step_1_output AS (
    SELECT division, completed_date
    FROM csod_training_records
    WHERE is_completed = TRUE
      AND completed_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '6 months'
      AND completed_date < DATE_TRUNC('month', CURRENT_DATE)
),
step_2_output AS (
    SELECT
        division,
        json_agg(
            json_build_object('time', completed_date, 'metric', COUNT(*))
            ORDER BY completed_date
        ) AS metric_series
    FROM step_1_output
    GROUP BY division
),
-- Step 3: trend baseline (reads step_2)
step_3_output AS (
    SELECT s.division, fn.*
    FROM step_2_output s
    CROSS JOIN LATERAL calculate_sma(s.metric_series, 7) AS fn
),
-- Step 4: anomaly detection (ALSO reads step_2 — same JSONB series)
step_4_output AS (
    SELECT s.division, fn.*
    FROM step_2_output s
    CROSS JOIN LATERAL detect_anomalies(s.metric_series, 'zscore', 2.0) AS fn
    WHERE fn.anomaly_type != 'normal'
)
-- Final: join trend + anomaly results on division + time_period
SELECT
    trend.division,
    trend.time_period,
    trend.sma_value,
    trend.upper_band,
    trend.lower_band,
    anom.value           AS observed_value,
    anom.anomaly_type,
    anom.anomaly_score
FROM step_3_output trend
JOIN step_4_output anom
    ON trend.division = anom.division
    AND trend.time_period = anom.time_period
ORDER BY trend.division, trend.time_period;
```

---

## Summary

| # | File | What Changes |
|---|------|--------------|
| 1 | `ds_pipeline_planner.md` | Add **FUNCTION CHAINING RULE**: parallel branches from step_2, never step_N → step_N+1 when both need JSONB series |
| 2 | `ds_pipeline_planner.md` | Add **LATERAL RULE**: `CROSS JOIN LATERAL` always in `must_include` for any function step |
| 3 | `ds_pipeline_planner.md` | Strengthen `ANOMALY_DETECTION_WITH_TREND` description: explicitly state step_4 reads step_2, not step_3 |
| 4 | `ds_sql_generator.py` | `_build_ds_step_instructions`: inject hard LATERAL enforcement block when `step_plan.function != null` |
| 4b | `ds_sql_generator.py` | Add `_infer_group_columns()` helper |
| 5 | `ds_rag_agent.py` | `_assemble_pipeline_sql`: detect parallel branches and produce correct JOIN at final SELECT |

## General Rule for Any Future Plan Type

**When two sequential steps both call functions that take JSONB series as input,
they are ALWAYS parallel branches from the last JSONB-producing step, not chained.**

A function output is flat rows. To chain from flat rows to another function,
you need an explicit re-aggregation step between them. The planner must insert
that step — it cannot be expressed as an inline aggregate inside a function call.