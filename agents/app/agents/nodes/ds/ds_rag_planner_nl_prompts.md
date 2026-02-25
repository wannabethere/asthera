# DS RAG Agent — Pipeline Planner and NL Question Generator Prompts

## Where These Fit

```
[PHASE 1.5 OUTPUT]
resolved_parameters + pipeline_constraints
    ↓
[PHASE 2 — PIPELINE]
    ↓
Step 1: DS_PIPELINE_PLANNER                    ← NEW
    → structured plan: {step_1, step_2, step_3}
    → each step: input_columns, output_columns,
                 transformation_logic, function, nl_question_spec
    ↓
Step 2: DS_NL_QUESTION_GENERATOR               ← NEW
    → 3 precise natural language questions, one per step
    ↓
Step 3: NL-to-SQL Agent × 3                    ← EXISTING AGENT
    → step_1_sql, step_2_sql, step_3_sql
    ↓
Step 4: _propagate_step_context (utility)      ← NEW (no LLM)
    → threads output columns from each step into next question
```

---

## Prompt 1 — DS_PIPELINE_PLANNER

**Prompt file:** `prompts/ds_pipeline_planner.md`

The prompt is loaded at runtime by `ds_prompt_loader.get_prompt("DS_PIPELINE_PLANNER")`.

---

## Prompt 2 — DS_NL_QUESTION_GENERATOR

**Prompt file:** `prompts/ds_nl_question_generator.md`

The prompt is loaded at runtime by `ds_prompt_loader.get_prompt("DS_NL_QUESTION_GENERATOR")`.

---

## Utility — `_propagate_step_context`

No LLM needed. Extracts output column names from generated SQL after each step
and injects them as `available_columns` for the next step's question generation.

```python
import re

def _propagate_step_context(
    self,
    generated_sql: str,
    step_plan: dict,
    function_schema: str | None = None
) -> dict:
    """
    Extract output columns from generated SQL and build agent context
    for the next step. Falls back to plan output_columns if extraction fails.
    """
    # Try to extract SELECT aliases from generated SQL
    extracted_columns = self._extract_select_aliases(generated_sql)

    # Fall back to plan spec if extraction fails or returns empty
    if not extracted_columns:
        extracted_columns = [
            col["name"] for col in step_plan.get("output_columns", [])
        ]

    return {
        "available_tables": ["step_output"],
        "available_columns": extracted_columns,
        "function_schema": function_schema
    }


def _extract_select_aliases(self, sql: str) -> list[str]:
    """
    Pull column aliases from the outermost SELECT clause.
    Handles: col AS alias, func(...) AS alias, plain col_name
    """
    # Strip CTEs to get the final SELECT
    final_select = re.sub(
        r'WITH\s+.*?(?=SELECT)', '', sql,
        flags=re.DOTALL | re.IGNORECASE
    ).strip()

    select_match = re.match(
        r'SELECT\s+(.*?)\s+FROM', final_select,
        flags=re.DOTALL | re.IGNORECASE
    )
    if not select_match:
        return []

    select_clause = select_match.group(1)
    aliases = []

    # Match "... AS alias" or bare column names
    for token in select_clause.split(','):
        token = token.strip()
        as_match = re.search(r'\bAS\s+(\w+)\s*$', token, re.IGNORECASE)
        if as_match:
            aliases.append(as_match.group(1))
        elif re.match(r'^\w+$', token):
            aliases.append(token)
        elif '.' in token:
            # table.column — take the column part
            aliases.append(token.split('.')[-1].strip())

    return aliases
```

---

## Updated Phase 2 Orchestration

```python
async def run_pipeline_phase(
    self,
    query: str,
    selected_model_names: list[str],
    scored_models: list[dict],
    pipeline_constraints: dict,
    language: str = "English"
) -> dict:
    """
    Phase 2: Plan → NL Questions → SQL (via existing NL-to-SQL agent) × 3
    """
    schema_context = self._extract_schema_context(
        selected_model_names, scored_models
    )

    # Step 1: Decompose + map functions (from previous design doc)
    decomposition = await self._decompose_task_internal(
        query, language, pipeline_constraints=pipeline_constraints
    )
    function_map = await self._map_functions_internal(
        decomposition, "\n".join(schema_context),
        pipeline_constraints=pipeline_constraints
    )

    # Step 2: Build the plan
    plan = await self._build_pipeline_plan(
        query=query,
        confirmed_models=scored_models,
        resolved_parameters=pipeline_constraints,
        function_map=function_map
    )

    # Step 3: Generate NL questions + call NL-to-SQL agent per step
    results = {}
    step_context = {
        "available_tables": selected_model_names,
        "available_columns": [
            col["name"]
            for model in scored_models
            for col in model.get("what_it_provides", [])
        ],
        "function_schema": None
    }

    for step_key in ["step_1", "step_2", "step_3"]:
        step_def = plan["steps"][step_key]
        step_num = int(step_key.split("_")[1])

        # Inject function schema into agent context for step 3
        if step_num == 3 and step_def.get("function"):
            step_context["function_schema"] = self._format_function_schema(
                step_def["function"]
            )

        # Generate NL question for this step
        nl_result = await self._generate_nl_question(
            step_definition=step_def,
            available_schema=step_context
        )

        # Call existing NL-to-SQL agent
        sql_result = await self.nl_to_sql_agent.generate(
            question=nl_result["nl_question"],
            schema_context=step_context,
            function_schema=step_context.get("function_schema")
        )

        generated_sql = sql_result.get("sql", "")
        results[f"{step_key}_sql"] = generated_sql
        results[f"{step_key}_nl_question"] = nl_result["nl_question"]

        # Propagate output columns to next step context
        if step_num < 3:
            step_context = self._propagate_step_context(
                generated_sql=generated_sql,
                step_plan=step_def,
                function_schema=None
            )

    # Step 4: Validate appendix compliance across all SQL
    violations = self._validate_appendix_compliance({
        k: v for k, v in results.items() if k.endswith("_sql")
    })
    results["appendix_violations"] = violations
    results["plan"] = plan
    results["success"] = not violations and bool(results.get("step_3_sql"))

    return results


async def _build_pipeline_plan(
    self,
    query: str,
    confirmed_models: list[dict],
    resolved_parameters: dict,
    function_map: list[dict]
) -> dict:
    """Build the structured execution plan from DS_PIPELINE_PLANNER."""
    prompt = (
        DS_PIPELINE_PLANNER_PROMPT
        + f"\n\n### USER QUESTION ###\n{query}"
        + f"\n\n### CONFIRMED MODELS ###\n{json.dumps(confirmed_models, indent=2)}"
        + f"\n\n### RESOLVED PARAMETERS ###\n{json.dumps(resolved_parameters, indent=2)}"
        + f"\n\n### FUNCTION EXECUTION PLAN ###\n{json.dumps(function_map, indent=2)}"
    )
    result = await self.llm.ainvoke(prompt)
    content = result.content if hasattr(result, "content") else str(result)
    try:
        return json.loads(self._extract_json(content))
    except Exception as e:
        logger.error(f"Pipeline planning failed: {e}")
        return {}


async def _generate_nl_question(
    self,
    step_definition: dict,
    available_schema: dict
) -> dict:
    """Generate a single NL question for one pipeline step."""
    prompt = (
        DS_NL_QUESTION_GENERATOR_PROMPT
        + f"\n\n### STEP DEFINITION ###\n{json.dumps(step_definition, indent=2)}"
        + f"\n\n### AVAILABLE SCHEMA ###\n{json.dumps(available_schema, indent=2)}"
    )
    result = await self.llm.ainvoke(prompt)
    content = result.content if hasattr(result, "content") else str(result)
    try:
        return json.loads(self._extract_json(content))
    except Exception as e:
        logger.error(f"NL question generation failed for step: {e}")
        return {"nl_question": ""}


def _format_function_schema(self, function_spec: dict) -> str:
    """Format function spec as a schema string the NL-to-SQL agent understands."""
    output_cols = ", ".join(
        f"{col} TEXT" if "type" not in col else col
        for col in function_spec.get("output_columns", [])
    )
    params = ", ".join(
        f"{k} -- maps to {v}"
        for k, v in function_spec.get("parameters", {}).items()
    )
    return (
        f"FUNCTION {function_spec['function_name']}({params}) "
        f"RETURNS TABLE({output_cols})"
    )
```

---

## Complete Updated Phase 2 Flow

```
resolved_parameters + pipeline_constraints
    ↓
_decompose_task_internal()
    ↓
_map_functions_internal()
    ↓
DS_PIPELINE_PLANNER
    → plan: {plan_type, plan_id, steps: {step_1, step_2, step_3}}
    → each step: input_columns, output_columns, filters,
                 transformation_logic, function, nl_question_spec
    ↓
┌─────────────────────────────────────┐
│  For step_1, step_2, step_3:        │
│                                     │
│  DS_NL_QUESTION_GENERATOR           │
│    → nl_question (self-contained)   │
│    → agent_context                  │
│         ↓                           │
│  NL-to-SQL Agent (existing)         │
│    → step_N_sql                     │
│         ↓                           │
│  _propagate_step_context (utility)  │
│    → available_columns for step N+1 │
└─────────────────────────────────────┘
    ↓
_validate_appendix_compliance()
    ↓
Return {step_1_sql, step_2_sql, step_3_sql,
        step_1_nl_question, step_2_nl_question, step_3_nl_question,
        plan, appendix_violations, success}
```

## Why the Plan Enables Few-Shot Reuse

The `plan_id` and `plan_type` create a library of reusable patterns. A
`TIME_SERIES_ANALYSIS` plan for compliance rate anomaly detection has the same
structure as one for learning completion trend analysis — same three steps, same
LATERAL pattern, same JSONB contract. Only the column names and filters differ.

Storing plans lets you:
- Match new questions against existing plan_ids by structural similarity
- Inject a matching plan as a few-shot example into DS_PIPELINE_PLANNER
- Skip the planner entirely for known patterns and go straight to NL generation
- Audit why a particular SQL was generated by inspecting the plan


python -m pytest agents/tests/ds_agents/test_ds_rag_agent.py -v


python -m app.indexing.project_reader_qdrant indexing_and_retrieval \
  --base-path /Users/sameermangalampalli/flowharmonicai/data/sql_meta \
  --ds-functions-path /Users/sameermangalampalli/flowharmonicai/data/sql_functions