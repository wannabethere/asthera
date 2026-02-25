"""DS-specific SQL generator for per-step pipeline generation.

This module provides SQL generation that uses virtual DDL from previous pipeline
steps as schema context. It does NOT modify sql_rag_agent — it is a separate path
for DS pipeline steps. It REUSES the shared sql prompts and sql functions
(sql_generation_system_prompt, construct_instructions, appendix) as those serve
a common purpose.

Flow:
  Step 1: Schema = actual DDL from retrieval (data selection/filtering)
  Step 2+: Schema = virtual DDL built from previous step's output_columns

SQL generation is driven by the step plan: nl_question_spec (must_include, must_not_include,
output_shape), filters, transformation_logic, output_columns, and function (when present).
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from app.agents.nodes.sql.utils.sql_prompts import (
    Configuration,
    construct_instructions,
    sql_generation_system_prompt,
)

logger = logging.getLogger("lexy-ai-service")

DS_STEP_CONTEXT_HEADER = """
### DS PIPELINE STEP {step_number} ###
This is step {step_number} of a data science pipeline.
- Step 1: Use the provided schema (real tables). Apply all filters, select required columns.
- Step 2+: The schema describes the output of the specified input step. Reference the exact
  table name shown in the schema DDL (e.g. step_1_output, step_2_output).
  IMPORTANT: Your SQL must reference the table specified in the schema, which may NOT be
  the immediately previous step — in parallel-branch pipelines, multiple steps can read
  from the same earlier step output.
"""


def build_ddl_for_step_output(
    step_plan: Dict[str, Any],
    table_alias: str = "step_output",
) -> str:
    """
    Build a virtual DDL string from a pipeline step's output_columns.
    Used as schema context for any step that reads this step's output.

    IMPORTANT for parallel branch pipelines (e.g., ANOMALY_DETECTION_WITH_TREND):
    Step 3 and step 4 may both read from step_2_output. The orchestrator must call
    this function with the step's actual input_source, not just the previous step.

    Example:
        # step_4 has input_source="step_2" — build DDL from step_2's output
        ddl = build_ddl_for_step_output(
            step_plan=plan["steps"]["step_2"],
            table_alias="step_2_output"
        )

    Args:
        step_plan: Step definition with output_columns (list of {name, type})
        table_alias: Name for the virtual table — must match input_source + "_output"
                     e.g. if step reads from "step_2", table_alias="step_2_output"

    Returns:
        DDL string used as schema context for the SQL generator.
    """
    output_cols = step_plan.get("output_columns", [])
    if not output_cols:
        return f"-- Virtual table {table_alias}: (no columns specified)"

    lines = [f"CREATE TABLE {table_alias} ("]
    for col in output_cols:
        if isinstance(col, dict):
            name = col.get("name", "col")
            ctype = col.get("type", "VARCHAR")
            lines.append(f"    {name} {ctype},")
        elif isinstance(col, str):
            lines.append(f"    {col} VARCHAR,")
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append(");")
    return "\n".join(lines)


def extract_select_aliases(sql: str) -> List[str]:
    """
    Extract column aliases from the outermost SELECT clause.
    Used to propagate output columns to the next step when plan lacks output_columns.
    """
    if not sql or not sql.strip():
        return []
    sql = sql.strip()
    # Find the last SELECT...FROM (outermost) to handle CTEs
    matches = list(re.finditer(r"SELECT\s+(.*?)\s+FROM\s+", sql, re.DOTALL | re.IGNORECASE))
    if not matches:
        return []
    select_match = matches[-1]
    select_clause = select_match.group(1)
    aliases = []
    for token in select_clause.split(","):
        token = token.strip()
        as_match = re.search(r"\bAS\s+(\w+)\s*$", token, re.IGNORECASE)
        if as_match:
            aliases.append(as_match.group(1))
        elif re.match(r"^\w+$", token):
            aliases.append(token)
        elif "." in token:
            aliases.append(token.split(".")[-1].strip())
    return aliases


def propagate_step_context(
    generated_sql: str,
    step_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build schema context for the next step from this step's generated SQL.
    Falls back to step plan output_columns if extraction fails.
    """
    extracted = extract_select_aliases(generated_sql)
    if not extracted:
        output_cols = step_plan.get("output_columns", [])
        extracted = [
            c.get("name", c) if isinstance(c, dict) else str(c)
            for c in output_cols
        ]
    return {
        "available_columns": extracted,
        "output_columns": [
            {"name": c, "type": "VARCHAR"} for c in extracted
        ],
    }


def get_schema_for_step(
    step_key: str,
    step_plan: Dict[str, Any],
    all_steps: Dict[str, Any],
    real_schema_ddl: str,
) -> str:
    """
    Get the correct schema DDL for a pipeline step.
    Handles parallel branches by looking up the actual input_source step.

    The orchestrator calls this instead of always using the previous step's output.
    For parallel branches (e.g., step_3 and step_4 both reading step_2), both will
    receive step_2's DDL as their schema context.

    Args:
        step_key: Current step key (e.g., "step_3")
        step_plan: Current step's plan dict
        all_steps: Full steps dict from the pipeline plan
        real_schema_ddl: Actual DDL string for step 1 (from retrieval_helper)

    Returns:
        DDL string to pass as schema_ddl to generate_sql_for_ds_step
    """
    input_source = step_plan.get("input_source", "")

    # Step 1 always uses real table DDL
    if step_key == "step_1" or not input_source or input_source not in all_steps:
        return real_schema_ddl

    # For all other steps, build virtual DDL from the input_source step's output_columns
    source_step_plan = all_steps[input_source]
    table_alias = f"{input_source}_output"
    return build_ddl_for_step_output(source_step_plan, table_alias=table_alias)


def _infer_group_columns(step_plan: Dict[str, Any]) -> str:
    """
    Infer the group/dimension column name from step plan for LATERAL pattern.
    Returns the first input column that is not a JSONB series column.
    """
    fn_spec = step_plan.get("function", {}) or {}
    input_col = fn_spec.get("input_column", "")
    input_cols = step_plan.get("input_columns", [])
    for col in input_cols:
        name = col if isinstance(col, str) else col.get("name", "")
        if not name:
            continue
        if name == input_col:
            continue
        if any(x in name.lower() for x in ("series", "metric_", "jsonb")):
            continue
        return name
    return "group_col"


def _build_plan_spec_block(step_plan: Dict[str, Any]) -> str:
    """Build instruction block from the step plan (nl_question_spec, filters, transformation_logic)."""
    blocks = []
    spec = step_plan.get("nl_question_spec", {})
    purpose = step_plan.get("purpose", "")
    transformation_logic = step_plan.get("transformation_logic", "")
    filters = step_plan.get("filters", [])
    input_cols = step_plan.get("input_columns", [])
    output_cols = step_plan.get("output_columns", [])

    if purpose:
        blocks.append(f"Purpose: {purpose}")
    if transformation_logic:
        blocks.append(f"Transformation: {transformation_logic}")
    if spec.get("intent"):
        blocks.append(f"Intent: {spec['intent']}")
    if input_cols:
        blocks.append(f"Input columns (from schema): {', '.join(input_cols)}")
    if output_cols:
        names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in output_cols]
        blocks.append(f"Output columns (must produce): {', '.join(names)}")
    if filters:
        blocks.append(f"Filters (MUST apply): {', '.join(filters)}")
    must_include = spec.get("must_include", [])
    if must_include:
        blocks.append("MUST include in SQL:")
        for m in must_include:
            blocks.append(f"  - {m}")
    must_not = spec.get("must_not_include", [])
    if must_not:
        blocks.append("MUST NOT include:")
        for m in must_not:
            blocks.append(f"  - {m}")
    if spec.get("output_shape"):
        blocks.append(f"Output shape: {spec['output_shape']}")

    if not blocks:
        return ""
    return "\n".join(blocks)


def _build_ds_step_instructions(
    nl_question: str,
    schema_ddl: str,
    appendix_block: str,
    step_number: int,
    previous_step_sql: Optional[str],
    step_plan: Optional[Dict[str, Any]] = None,
    config: Optional[Configuration] = None,
) -> str:
    """
    Build instructions for DS step SQL generation from the step plan.
    The plan (nl_question_spec, filters, transformation_logic, output_columns) drives SQL generation.
    """
    config = config or Configuration()
    instructions = construct_instructions(
        configuration=config,
        has_calculated_field=False,
        has_metric=False,
        instructions=None,
    )
    instructions += DS_STEP_CONTEXT_HEADER.format(step_number=step_number)

    # Use both plan and nl_question — plan drives structure, nl_question adds context
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
        # Normalize source to CTE output alias (e.g. "step_2" -> "step_2_output")
        if source_table and not source_table.endswith("_output") and source_table.startswith("step_"):
            source_table = f"{source_table}_output"
        group_col = _infer_group_columns(step_plan or {})
        # Build the exact signature with column reference substituted
        fn_call = fn_sig.replace(input_col, f"s.{input_col}")

        instructions += f"""
### CRITICAL: REQUIRED SQL PATTERN FOR THIS STEP ###

This step calls an appendix SQL function. You MUST use CROSS JOIN LATERAL.
Any other pattern (subquery, FROM func() JOIN, correlated query) will produce wrong SQL.

REQUIRED PATTERN (copy this structure exactly):
  SELECT
      s.{group_col},
      fn.*
  FROM {source_table} AS s
  CROSS JOIN LATERAL {fn_call} AS fn

Rules:
- MUST use CROSS JOIN LATERAL — not FROM func() AS alias JOIN ... ON true
- Pass {input_col} as s.{input_col} — NOT json_agg() or any aggregate inside the call
- s.{input_col} is already a JSONB array from the previous step — do NOT re-aggregate it
- Select s.{group_col} alongside fn.* to carry the group dimension through
- Add WHERE and ORDER BY after the LATERAL join if needed (post-function filters only)

DO NOT:
  ❌ SELECT ... FROM {fn_name}(...) AS fn JOIN {source_table} ON true
  ❌ {fn_name}(json_agg(...))  — aggregate inside function call
  ❌ {fn_name}(ARRAY_AGG(...)) — wrong type, must be JSONB
"""
    if previous_step_sql:
        instructions += f"\n### PREVIOUS STEP SQL (your step consumes this output) ###\n{previous_step_sql}\n"
    if appendix_block:
        instructions += f"\n### AVAILABLE SQL FUNCTIONS ###\n{appendix_block}\n"
    instructions += (
        f"\n### DATABASE SCHEMA ###\n{schema_ddl}\n\n"
        f"### TASK ###\nGenerate SQL for this step only. "
        f"Follow the STEP PLAN exactly. Current Time: {config.show_current_time()}\n"
    )
    return instructions


async def generate_sql_for_ds_step(
    llm: Any,
    nl_question: str,
    schema_ddl: str,
    appendix_block: str,
    step_number: int,
    previous_step_sql: Optional[str] = None,
    step_plan: Optional[Dict[str, Any]] = None,
    extract_sql_fn: Optional[Callable[[str], str]] = None,
    configuration: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate SQL for a single DS pipeline step using the provided schema.

    Uses shared sql_generation_system_prompt and construct_instructions from
    sql.utils.sql_prompts — does NOT modify sql_rag_agent.

    Args:
        llm: LangChain LLM instance
        nl_question: Natural language question for this step
        schema_ddl: DDL string (real or virtual) describing input schema
        appendix_block: Formatted appendix of allowed functions (from appendix_loader)
        step_number: 1-based step index
        previous_step_sql: SQL from previous step (for step 2+)
        step_plan: Step definition from pipeline planner; drives SQL generation (must_include, must_not_include, etc.)
        extract_sql_fn: Optional fn(content) -> str to extract SQL from LLM response
        configuration: Optional config dict for construct_instructions

    Returns:
        {"sql": str, "success": bool, "error": str|None}
    """
    config = Configuration(**(configuration or {}))
    instructions = _build_ds_step_instructions(
        nl_question=nl_question,
        schema_ddl=schema_ddl,
        appendix_block=appendix_block or "",
        step_number=step_number,
        previous_step_sql=previous_step_sql or None,
        step_plan=step_plan,
        config=config,
    )
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=sql_generation_system_prompt),
            HumanMessage(content=instructions),
        ]
        result = await llm.ainvoke(messages)
        content = result.content if hasattr(result, "content") else str(result)
        sql = content.strip()
        if extract_sql_fn:
            extracted = extract_sql_fn(content)
            if extracted:
                sql = extracted
        # Extract from JSON (sql_generation_system_prompt format) or <sql></sql> or ```sql
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "sql" in parsed:
                raw = parsed["sql"]
                inner = re.search(r"<sql>\s*([\s\S]*?)</sql>", raw, re.IGNORECASE)
                sql = inner.group(1).strip() if inner else raw.strip()
        except (json.JSONDecodeError, TypeError):
            sql_match = re.search(r"<sql>\s*([\s\S]*?)</sql>", sql, re.IGNORECASE)
            if sql_match:
                sql = sql_match.group(1).strip()
            elif "```" in sql:
                code_match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", sql)
                if code_match:
                    sql = code_match.group(1).strip()
        return {"sql": sql, "success": bool(sql), "error": None}
    except Exception as e:
        logger.warning(f"DS step SQL generation failed: {e}")
        return {"sql": "", "success": False, "error": str(e)}
