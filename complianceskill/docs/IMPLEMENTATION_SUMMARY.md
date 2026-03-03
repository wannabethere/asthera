# GoldModelPlanGenerator Implementation Summary

## What Was Implemented

A reusable `GoldModelPlanGenerator` class that generates `GoldModelPlan` from metrics using LLMs. This class can be used for both gold model generation and dashboard generation workflows.

## Files Created

1. **`gold_model_plan_generator.py`**: Main implementation
   - `GoldModelPlanGenerator` class
   - `GoldModelPlanGeneratorInput` Pydantic model
   - LLM-based plan generation logic

2. **`gold_model_plan_generator_test.py`**: Unit tests
   - Tests for basic plan generation
   - Tests with KPIs
   - Tests for edge cases

3. **`USAGE_EXAMPLES.md`**: Comprehensive usage documentation
   - Examples for different use cases
   - Integration patterns
   - Error handling

4. **`__init__.py`**: Updated exports

## Key Features

### 1. Reusable Design
- Can be used in planning_graph, dt_workflow, dashboard generation
- Configurable model, temperature, and max_tokens
- Works with various metric formats (resolved_metrics, dt_metric_recommendations, goal_metrics)

### 2. LLM-Based Generation
- Uses structured output to generate `GoldModelPlan`
- Comprehensive prompt that includes:
  - Metrics to support
  - Available silver tables with schemas
  - KPIs (optional)
  - Medallion context (optional)
  - User request context

### 3. Safety Features
- Automatically ensures `connection_id` is present in all specifications
- Validates output against `GoldModelPlan` Pydantic model
- Comprehensive error handling

### 4. Assumption: Silver Tables Exist
- Designed with the assumption that silver tables already exist
- Takes `RelevantTablesInfo` as input (includes schemas)
- Plans gold models that build on top of silver tables

## Usage Pattern

```python
# 1. Initialize generator
generator = GoldModelPlanGenerator()

# 2. Prepare input
input_data = GoldModelPlanGeneratorInput(
    metrics=metrics,
    silver_tables_info=tables_info,
    user_request=user_query,
    kpis=kpis,  # optional
    medallion_context=medallion_plan,  # optional
)

# 3. Generate plan
gold_model_plan = await generator.generate(input_data)

# 4. Use plan
if gold_model_plan.requires_gold_model:
    for spec in gold_model_plan.specifications:
        # Use spec to generate SQL, create dbt models, etc.
        pass
```

## Integration Points

### 1. Planning Graph
Replace `_generate_gold_model_plan` node to use the generator:

```python
async def _generate_gold_model_plan(self, state, runtime):
    generator = GoldModelPlanGenerator()
    input_data = GoldModelPlanGeneratorInput(
        metrics=state.get("resolved_metrics", []),
        silver_tables_info=state.relevant_tables_info,
        user_request=state.generated_user_request,
    )
    plan = await generator.generate(input_data)
    return {"gold_model_plan": plan}
```

### 2. DT Workflow
Use in `dt_triage_engineer_node` or `dt_unified_format_converter_node`:

```python
# Generate plan from dt_workflow metrics
generator = GoldModelPlanGenerator()
input_data = GoldModelPlanGeneratorInput(
    metrics=state.get("resolved_metrics", []),
    silver_tables_info=_convert_dt_schemas_to_tables_info(state.get("dt_resolved_schemas", [])),
    kpis=state.get("kpis", []),
)
plan = await generator.generate(input_data)
state["dt_medallion_plan"] = plan.model_dump()
```

### 3. Dashboard Generation
Use in `dt_dashboard_assembler_node`:

```python
# Generate plan for dashboard metrics
generator = GoldModelPlanGenerator()
input_data = GoldModelPlanGeneratorInput(
    metrics=state.get("resolved_metrics", []),
    silver_tables_info=_convert_dashboard_tables(state.get("dt_dashboard_available_tables", [])),
    user_request=state.get("user_query", ""),
)
plan = await generator.generate(input_data)
# Store for later gold model generation
state["dashboard_gold_model_plan"] = plan.model_dump()
```

## Next Steps

1. **Integrate into planning_graph**: Replace `_generate_gold_model_plan` to use the generator
2. **Integrate into dt_workflow**: Use in medallion plan generation
3. **Integrate into dashboard generation**: Use in dashboard assembler
4. **Add tests**: Run integration tests with real metrics and tables
5. **Tune prompts**: Refine prompts based on real-world usage

## Benefits

1. **Separation of Concerns**: Plan generation logic is isolated and reusable
2. **Consistency**: Same logic used across all workflows
3. **Maintainability**: Single place to update plan generation logic
4. **Testability**: Can be tested independently
5. **Flexibility**: Configurable for different use cases
