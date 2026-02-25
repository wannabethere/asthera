# DS RAG Agent — Transformation Ambiguity Prompts

## Where These Fit in the Flow

These two prompts slot between **User Selects Models** and **`_decompose_task_internal()`**.
They fire once, after model confirmation. If no ambiguity is detected the user sees
nothing and the pipeline starts immediately. If ambiguity exists, one chat turn happens
before decomposition runs.

```
User Selects Models
    ↓
Step 0e: DS_TRANSFORMATION_AMBIGUITY_DETECTOR   ← NEW
    → RESOLVED: pipeline starts immediately
    → AMBIGUOUS: surface questions to user
    ↓
User Answers (conditional chat turn)            ← NEW
    ↓
Step 0f: DS_TRANSFORMATION_RESOLUTION_BUILDER
    → resolved_parameters dict
    ↓
_decompose_task_internal()   ← receives resolved_parameters as hard context
    ↓
... rest of pipeline
```

---

## Prompt 1 — DS_TRANSFORMATION_AMBIGUITY_DETECTOR

**Prompt file:** `prompts/ds_transformation_ambiguity_detector.md`

The prompt is loaded at runtime by `ds_prompt_loader.get_prompt("DS_TRANSFORMATION_AMBIGUITY_DETECTOR")`.

---

## Prompt 2 — DS_TRANSFORMATION_RESOLUTION_BUILDER

**Prompt file:** `prompts/ds_transformation_resolution_builder.md`

The prompt is loaded at runtime by `ds_prompt_loader.get_prompt("DS_TRANSFORMATION_RESOLUTION_BUILDER")`.

---

## Code

```python
async def _detect_transformation_ambiguity(
    self,
    query: str,
    confirmed_models: list[dict]
) -> dict:
    """
    Detect which of output_grain, time_spine, comparison_baseline are ambiguous.
    Returns detection output with has_ambiguity flag and user_facing_text if needed.
    """
    models_block = json.dumps(confirmed_models, indent=2)
    prompt = (
        DS_TRANSFORMATION_AMBIGUITY_DETECTOR_PROMPT
        + f"\n\n### USER QUESTION ###\n{query}"
        + f"\n\n### CONFIRMED MODELS ###\n{models_block}"
    )
    result = await self.llm.ainvoke(prompt)
    content = result.content if hasattr(result, "content") else str(result)
    try:
        return json.loads(self._extract_json(content))
    except Exception as e:
        logger.error(f"Ambiguity detection failed: {e}")
        # Safe default — skip user turn, let decomposition infer
        return {"has_ambiguity": False, "skip_user_turn": True, "parameters": {}}


async def _resolve_transformation_parameters(
    self,
    detection_output: dict,
    user_answers: dict,
    confirmed_models: list[dict]
) -> dict:
    """
    Resolve all parameters to concrete values.
    user_answers may be empty if skip_user_turn was True.
    Returns resolved_parameters + pipeline_constraints.
    """
    prompt = (
        DS_TRANSFORMATION_RESOLUTION_BUILDER_PROMPT
        + f"\n\n### AMBIGUITY DETECTION OUTPUT ###\n{json.dumps(detection_output, indent=2)}"
        + f"\n\n### USER ANSWERS ###\n{json.dumps(user_answers, indent=2)}"
        + f"\n\n### CONFIRMED MODELS ###\n{json.dumps(confirmed_models, indent=2)}"
    )
    result = await self.llm.ainvoke(prompt)
    content = result.content if hasattr(result, "content") else str(result)
    try:
        return json.loads(self._extract_json(content))
    except Exception as e:
        logger.error(f"Parameter resolution failed: {e}")
        return {"resolved_parameters": {}, "pipeline_constraints": {}}
```

Updated `run_pipeline_phase` to consume `pipeline_constraints`:

```python
async def run_pipeline_phase(
    self,
    query: str,
    selected_model_names: list[str],
    scored_models: list[dict],
    pipeline_constraints: dict,      # from resolution builder
    language: str = "English"
) -> dict:
    """
    Phase 2: SQL pipeline generation on confirmed models with resolved parameters.
    pipeline_constraints are injected as hard context into decomposition.
    """
    schema_context = self._extract_schema_context(selected_model_names, scored_models)

    decomposition = await self._decompose_task_internal(
        query, language,
        pipeline_constraints=pipeline_constraints   # hard context, not inferred
    )
    function_map = await self._map_functions_internal(
        decomposition, "\n".join(schema_context),
        pipeline_constraints=pipeline_constraints
    )
    reasoning_context = self._build_reasoning_context(
        decomposition, function_map,
        "\n".join(schema_context),
        pipeline_constraints=pipeline_constraints
    )
    reasoning = await super()._reason_sql_internal(
        query, schema_context, language,
        extra_context=reasoning_context
    )
    pipeline = await self._generate_sql_internal(
        query, schema_context,
        reasoning=reasoning.get("reasoning", ""),
        function_map=function_map,
        pipeline_spec=reasoning.get("pipeline_spec", {}),
        pipeline_constraints=pipeline_constraints
    )
    return pipeline
```

---

## Updated Full Flow

```
User Question
    ↓
[PHASE 1 — DISCOVERY]
    ↓
Step 0a: DS_CLARIFYING_QUESTION_GENERATOR
    → grain, entity scope, time model questions
    ↓
User Answers
    ↓
Step 0b: DS_RETRIEVAL_QUERY_BUILDER
    ↓
retrieval_helper.search()
    ↓
Step 0c: DS_MODEL_SCORER
    → ranked model suggestions
    ↓
User Selects Models
    ↓
[PHASE 1.5 — TRANSFORMATION RESOLUTION]
    ↓
Step 0e: DS_TRANSFORMATION_AMBIGUITY_DETECTOR
    → has_ambiguity: false → skip to Phase 2 immediately
    → has_ambiguity: true  → show user_facing_text (1 chat turn)
    ↓
User Answers (conditional)
    ↓
Step 0f: DS_TRANSFORMATION_RESOLUTION_BUILDER
    → pipeline_constraints: {date_filter, bucket_expression, metric_expression, group_by}
    ↓
[PHASE 2 — PIPELINE]
    ↓
_decompose_task_internal()     ← receives pipeline_constraints as hard context
    ↓
_map_functions_internal()      ← receives pipeline_constraints
    ↓
_reason_sql_internal()         ← receives pipeline_constraints
    ↓
_generate_sql_internal()       ← injects constraints directly into step SQLs
    ↓
_validate_appendix_compliance()
    ↓
Return PipelineSQL
```

## What `pipeline_constraints` Prevents

Without it, every Phase 2 step re-derives the time window and aggregation from the
question text. Each step makes slightly different assumptions. The generated SQL ends
up with mismatched date filters between Step 1 and Step 2, or the JSONB field names
don't match what the function expects because the metric alias drifted.

With `pipeline_constraints`, the SQL expressions are decided once in Step 0f and
injected verbatim. Step 1 `WHERE` clause, Step 2 `GROUP BY` and metric expression,
and the JSONB key names are all fixed before decomposition runs. The LLM at each
pipeline step is told what to use, not asked to figure it out.
