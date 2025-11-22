# How to Run the Workflow Executor

This guide explains how to run the Cube.js generation workflow executor.

## Prerequisites

1. **Python Environment**: Ensure you have the required dependencies installed
2. **LLM Configuration**: The executor uses `get_llm()` from `app.core.dependencies`, which requires:
   - OpenAI API key configured in settings
   - Or a custom LLM instance passed to the executor

3. **Workflow Configuration**: You need a workflow configuration JSON file or Python dict

## Method 1: Command Line Interface (CLI)

Run the executor as a command-line script with a JSON configuration file:

```bash
# From the project root
python -m dataservices.app.agents.cubes.workflow_executor network_device_workflow.json

# Or with custom output directory
python -m dataservices.app.agents.cubes.workflow_executor network_device_workflow.json --output-dir ./my_output
```

**Example:**
```bash
cd /Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml
python -m dataservices.app.agents.cubes.workflow_executor dataservices/app/agents/cubes/network_device_workflow.json --output-dir ./output
```

## Method 2: Direct Python Script Execution

Run the script directly (uses the example workflow):

```bash
# From the project root
python dataservices/app/agents/cubes/workflow_executor.py
```

This will execute the `network_device_workflow` example from `workflow_examples.py`.

## Method 3: Programmatic Usage (Recommended)

Use the executor in your Python code:

```python
from app.agents.cubes.workflow_executor import WorkflowExecutor
from app.agents.cubes.workflow_examples import network_device_workflow
import pandas as pd

# Option 1: Basic usage (uses get_llm() automatically)
executor = WorkflowExecutor(output_dir="./output")
result = executor.execute_workflow_sync(network_device_workflow)

# Option 2: With pandas DataFrames for statistics
table_dataframes = {
    "dev_network_devices": df  # Your pandas DataFrame
}

executor = WorkflowExecutor(
    output_dir="./output",
    table_dataframes=table_dataframes
)
result = executor.execute_workflow_sync(network_device_workflow)

# Option 3: With custom LLM
from app.core.dependencies import get_llm

custom_llm = get_llm(temperature=0.0, model="gpt-4o")
executor = WorkflowExecutor(
    output_dir="./output",
    llm=custom_llm
)
result = executor.execute_workflow_sync(network_device_workflow)

# Access results
print(f"Generated {len(result['result']['silver_cubes'])} silver cubes")
print(f"Planned {len(result.get('data_mart_plans', []))} data marts")

# Access data mart plans
for plan in result.get('data_mart_plans', []):
    print(f"\nGoal: {plan['goal']}")
    for mart in plan['marts']:
        print(f"  - {mart['mart_name']}")
        print(f"    Question: {mart['natural_language_question']}")
        print(f"    SQL: {mart['sql'][:100]}...")
```

## Method 4: Async Usage

For async environments:

```python
import asyncio
from app.agents.cubes.workflow_executor import WorkflowExecutor
from app.agents.cubes.workflow_examples import network_device_workflow

async def run_workflow():
    executor = WorkflowExecutor(output_dir="./output")
    result = await executor.execute_workflow(network_device_workflow)
    return result

# Run it
result = asyncio.run(run_workflow())
```

## Workflow Configuration Format

Your workflow configuration should be a dictionary or JSON file with:

```python
{
    "workflow_name": "my_workflow",
    "description": "Description of the workflow",
    "raw_schemas": [
        {
            "table_name": "table1",
            "table_ddl": "CREATE TABLE table1 (...);",
            "relationships": [],
            "layer": "raw"
        }
    ],
    "lod_configurations": [
        {
            "table_name": "table1",
            "lod_type": "FIXED",
            "dimensions": ["id", "timestamp"],
            "description": "Deduplication config"
        }
    ],
    "relationship_mappings": [],
    "user_query": "Your analytical requirements...",
    "data_mart_goals": [  # Optional
        "Create customer analytics dashboard",
        "Build sales summary data mart"
    ],
    "generate_gold": true  # Optional, default: true
}
```

## Using Existing JSON Files

You can use the pre-generated JSON files:

```bash
# Network device workflow
python -m dataservices.app.agents.cubes.workflow_executor \
    dataservices/app/agents/cubes/network_device_workflow.json

# E-commerce workflow
python -m dataservices.app.agents.cubes.workflow_executor \
    dataservices/app/agents/cubes/ecommerce_workflow.json

# LMS workflow
python -m dataservices.app.agents.cubes.workflow_executor \
    dataservices/app/agents/cubes/lms_workflow.json
```

## Output Structure

After execution, you'll find:

```
output/
├── cubes/
│   ├── raw/
│   ├── silver/
│   └── gold/
├── views/
├── transformations/
│   ├── raw_to_silver/
│   └── silver_to_gold/
├── sql/
│   ├── raw_to_silver/
│   └── silver_to_gold/
├── data_marts/          # NEW: Data mart SQL files
│   ├── data_mart_plan_1.json
│   ├── customer_analytics.sql
│   └── ...
├── documentation/
│   └── {workflow_name}_README.md
└── ...
```

## Example: Complete Workflow

```python
from app.agents.cubes.workflow_executor import WorkflowExecutor
from app.agents.cubes.workflow_examples import ecommerce_workflow
import pandas as pd

# Create sample DataFrames (optional, for testing)
customers_df = pd.DataFrame({
    'customer_id': [1, 2, 3],
    'email': ['a@example.com', 'b@example.com', 'c@example.com'],
    'country': ['US', 'UK', 'CA']
})

orders_df = pd.DataFrame({
    'order_id': [1, 2, 3],
    'customer_id': [1, 2, 1],
    'order_date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
    'total_amount': [100.0, 200.0, 150.0]
})

# Initialize executor with DataFrames
executor = WorkflowExecutor(
    output_dir="./output",
    table_dataframes={
        "customers": customers_df,
        "orders": orders_df
    }
)

# Execute workflow
result = executor.execute_workflow_sync(ecommerce_workflow)

# Check results
print(f"✅ Workflow completed!")
print(f"📊 Generated {len(result['result']['silver_cubes'])} silver cubes")
print(f"📦 Generated {len(result.get('gold_result', {}).get('gold_cubes', []))} gold cubes")
print(f"📈 Planned {len(result.get('data_mart_plans', []))} data marts")

# Access data mart SQL
for plan in result.get('data_mart_plans', []):
    print(f"\n🎯 Goal: {plan['goal']}")
    for mart in plan['marts']:
        print(f"  📝 {mart['mart_name']}")
        print(f"     Q: {mart['natural_language_question']}")
        # The SQL is in mart['sql']
```

## Troubleshooting

### Issue: "No module named 'app'"
**Solution**: Make sure you're running from the project root or have PYTHONPATH set:
```bash
export PYTHONPATH=/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml:$PYTHONPATH
```

### Issue: "get_llm() not found"
**Solution**: Ensure dependencies are installed and the app structure is correct.

### Issue: "AsyncIO event loop already running"
**Solution**: Use `execute_workflow_sync()` instead of `execute_workflow()` in sync contexts.

### Issue: No data mart plans generated
**Solution**: 
- Ensure `data_mart_goals` are provided in workflow config
- Check that `enable_data_mart_planning=True` in `SilverHumanInLoopAgent` (default: True)

## Next Steps

1. Review generated artifacts in the output directory
2. Check the README.md in documentation/ for workflow details
3. Execute data mart SQL files from data_marts/ directory
4. Deploy Cube.js definitions to your Cube.js instance

