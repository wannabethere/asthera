# GoldModelPlanGenerator Usage Examples

## Overview

`GoldModelPlanGenerator` is a reusable class for generating `GoldModelPlan` from metrics using LLMs. It can be used in:
- Gold model generation workflows
- Dashboard generation workflows
- Any workflow that needs to plan gold models from metrics

**Assumption**: Silver tables already exist and are provided.

## Basic Usage

### Example 1: Generate Plan from DT Workflow Metrics

```python
from leen_iris.agent_graphs.gold_model_builder import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
)

# Initialize generator
generator = GoldModelPlanGenerator(
    model_name=ModelNameEnum.CLAUDE_SONNET_4_5,
    temperature=0.3,
)

# Prepare input from dt_workflow state
input_data = GoldModelPlanGeneratorInput(
    metrics=state.get("resolved_metrics", []),
    silver_tables_info=state.get("relevant_tables_info", []),
    user_request=state.get("user_query", ""),
    kpis=state.get("kpis", []),
    medallion_context=state.get("dt_medallion_plan", {}),
)

# Generate plan
gold_model_plan = await generator.generate(input_data)

# Use the plan
if gold_model_plan.requires_gold_model:
    for spec in gold_model_plan.specifications:
        print(f"Gold model: {spec.name}")
        print(f"  Description: {spec.description}")
        print(f"  Materialization: {spec.materialization}")
        print(f"  Columns: {[col.name for col in spec.expected_columns]}")
```

### Example 2: Use in Planning Graph

```python
# In planning_graph.py

from leen_iris.agent_graphs.gold_model_builder import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
)

async def _dt_workflow_to_gold_model_plan(
    self, state: PlanningState, runtime: Runtime[IrisContext]
) -> dict:
    """Convert dt_workflow outputs to GoldModelPlan."""
    
    # Initialize generator
    generator = GoldModelPlanGenerator()
    
    # Prepare input from state
    input_data = GoldModelPlanGeneratorInput(
        metrics=state.get("resolved_metrics", []) or state.get("dt_metric_recommendations", []),
        silver_tables_info=state.relevant_tables_info,
        user_request=state.generated_user_request,
        kpis=state.get("kpis", []),
        medallion_context=state.get("dt_medallion_plan", {}),
    )
    
    # Generate plan
    gold_model_plan = await generator.generate(input_data)
    
    return {
        "gold_model_plan": gold_model_plan,
    }
```

### Example 3: Use in Dashboard Generation

```python
# In dt_dashboard_assembler_node or similar

from leen_iris.agent_graphs.gold_model_builder import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
)

async def dt_dashboard_assembler_node(state: DT_State) -> DT_State:
    """Assemble dashboard and generate gold model plan if needed."""
    
    # Get metrics for dashboard
    metrics = state.get("resolved_metrics", [])
    available_tables = state.get("dt_dashboard_available_tables", [])
    
    # Convert available_tables to RelevantTablesInfo format
    silver_tables_info = _convert_to_relevant_tables_info(available_tables)
    
    # Generate gold model plan for dashboard metrics
    generator = GoldModelPlanGenerator()
    input_data = GoldModelPlanGeneratorInput(
        metrics=metrics,
        silver_tables_info=silver_tables_info,
        user_request=state.get("user_query", ""),
    )
    
    gold_model_plan = await generator.generate(input_data)
    
    # Store plan for later use (e.g., in planning_graph)
    state["dt_medallion_plan"] = gold_model_plan.model_dump()
    
    return state
```

### Example 4: Custom Configuration

```python
# Use different model or temperature for faster/cheaper generation

generator = GoldModelPlanGenerator(
    model_name=ModelNameEnum.CLAUDE_HAIKU,  # Faster, cheaper
    temperature=0.0,  # More deterministic
    max_tokens=2048,  # Smaller response
)

input_data = GoldModelPlanGeneratorInput(
    metrics=metrics,
    silver_tables_info=tables_info,
)

plan = await generator.generate(input_data)
```

## Input Format

### Metrics Format

The generator accepts metrics in various formats:

```python
# Format 1: resolved_metrics from dt_workflow
metrics = [
    {
        "name": "mttr_metric",
        "description": "Mean time to remediate",
        "base_table": "snyk_issue",
        "dimensions": ["severity", "project_id"],
        "measure": "AVG(EXTRACT(EPOCH FROM (fixed_at - created_at))/86400)",
        "source_schemas": ["snyk_issue"],
    }
]

# Format 2: dt_metric_recommendations
metrics = [
    {
        "metric_name": "vulnerability_count",
        "metric_definition": "Count of vulnerabilities",
        "table_name": "qualys_vulnerability",
        "data_groups": ["severity", "status"],
        "calculation_method": "COUNT(*) WHERE status = 'open'",
    }
]

# Format 3: goal_metrics from planning_graph
metrics = [
    {
        "name": "open_issues",
        "description": "Open security issues",
        "table_name": "snyk_issue",
        "fields": ["id", "severity", "created_at"],
    }
]
```

### Silver Tables Info Format

```python
from leen_iris.agent_graphs.planner.models import RelevantTablesInfo
from leen_iris.agent_graphs.common.databricks_tools import DatabricksSchemaInfo

# Get schema from Databricks
schema = databricks_tools.get_full_table_schema("snyk_issue")

tables_info = [
    RelevantTablesInfo(
        table_name="snyk_issue",
        reason="Snyk vulnerability issues",
        table_schema=schema,
        relevant_columns=["id", "severity", "created_at", "fixed_at"],
        relevant_columns_reasoning="Columns needed for MTTR calculation",
    )
]
```

## Output Format

The generator returns a `GoldModelPlan`:

```python
GoldModelPlan(
    requires_gold_model=True,
    reasoning="Gold models needed for aggregations and joins across multiple tables",
    specifications=[
        GoldModelSpecification(
            name="gold_snyk_issues_mttr",
            description="Gold model for MTTR calculations. Joins snyk_issue with project tables...",
            materialization="incremental",
            expected_columns=[
                OutputColumn(name="connection_id", description="Required for multi-tenant filtering"),
                OutputColumn(name="severity", description="Vulnerability severity"),
                OutputColumn(name="mttr_days", description="Mean time to remediate in days"),
                # ... more columns
            ],
        )
    ],
)
```

## Integration Points

### 1. Planning Graph Integration

Replace `_generate_gold_model_plan` node:

```python
# Before: LLM-based generation in planning_graph
# After: Use GoldModelPlanGenerator

async def _generate_gold_model_plan(...):
    generator = GoldModelPlanGenerator()
    input_data = GoldModelPlanGeneratorInput(...)
    return await generator.generate(input_data)
```

### 2. DT Workflow Integration

Use in `dt_triage_engineer_node` or `dt_unified_format_converter_node`:

```python
# Generate plan from calculation_plan or metrics
generator = GoldModelPlanGenerator()
plan = await generator.generate(input_data)
state["dt_medallion_plan"] = plan.model_dump()
```

### 3. Dashboard Generation Integration

Use in `dt_dashboard_assembler_node`:

```python
# Generate plan for dashboard metrics
generator = GoldModelPlanGenerator()
plan = await generator.generate(input_data)
# Store plan for later gold model generation
```

## Error Handling

```python
from leen_iris.agent_graphs.gold_model_builder import GoldModelPlanGenerator

try:
    generator = GoldModelPlanGenerator()
    plan = await generator.generate(input_data)
except Exception as e:
    logger.error(f"Failed to generate gold model plan: {e}")
    # Fallback: create minimal plan
    plan = GoldModelPlan(
        requires_gold_model=False,
        reasoning=f"Plan generation failed: {str(e)}",
        specifications=None,
    )
```

## Testing

See `gold_model_plan_generator_test.py` for example tests.
