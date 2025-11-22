# Workflow Executor Enhancements

This document describes the enhancements made to `workflow_executor.py` to generate comprehensive data pipeline artifacts including dbt models, enhanced data marts, and gold metrics.

## New Workflow Steps

### Step 1: Silver Tables Cleaning (Enhanced)
- **Location**: Already exists in workflow, now enhanced with LLM-based generation
- **Purpose**: Clean and normalize raw data into silver layer
- **Output**: Silver table SQL transformations

### Step 2: Data Marts from Human-in-the-Loop
- **Location**: Step 4 in workflow
- **Purpose**: Generate data marts based on business goals collected through human-in-the-loop
- **Output**: Data mart plans with SQL and natural language questions
- **Integration**: Uses `SilverHumanInLoopAgent` and `DataMartPlannerAgent`

### Step 3: Enhance Data Marts with Transformations (NEW)
- **Location**: Step 10 in workflow
- **Method**: `_enhance_data_marts_with_transformations()`
- **Purpose**: Add transformations, optimizations, and business logic to data marts
- **Process**:
  1. Takes data mart plans from human-in-the-loop
  2. Uses LLM to enhance SQL with:
     - Indexes for performance
     - Calculated fields and metrics
     - Data quality checks
     - Optimized aggregations
     - Time-based partitioning (if applicable)
     - Proper constraints and data types
- **Output**: Enhanced SQL files (`{mart_name}_enhanced.sql`)

### Step 4: Generate Gold Metrics (NEW)
- **Location**: Step 11 in workflow
- **Method**: `_generate_gold_metrics()`
- **Purpose**: Extract dimensions, measures, and metrics from enhanced data marts
- **Process**:
  1. Analyzes enhanced SQL CREATE TABLE statements
  2. Uses LLM to extract:
     - **Dimensions**: Categorical fields for grouping
     - **Measures**: Numeric fields for aggregation (sum, avg, count, max, min)
     - **Metrics**: Calculated business metrics
- **Output**: JSON file with gold metrics structure

### Step 5: Write to dbt and Cube.js (NEW)
- **Location**: Step 12 in workflow (enhanced `_save_artifacts()`)
- **Methods**: 
  - `_generate_dbt_model()`: Converts SQL to dbt models
  - `_generate_dbt_schema()`: Generates dbt schema.yml
- **Purpose**: Generate both dbt and Cube.js outputs
- **Outputs**:
  - **dbt Models**: `dbt/models/gold/{mart_name}.sql`
  - **dbt Schema**: `dbt/schema.yml` (with models, columns, metrics)
  - **Cube.js**: Already generated (existing functionality)
  - **Gold Metrics**: `documentation/gold_metrics.json`

## New Methods

### `_enhance_data_marts_with_transformations()`
```python
def _enhance_data_marts_with_transformations(
    self,
    data_mart_plans: List[Dict[str, Any]],
    silver_result: Dict,
    gold_result: Optional[Dict]
) -> List[Dict[str, Any]]
```

Enhances data marts with LLM-generated transformations.

### `_generate_gold_metrics()`
```python
def _generate_gold_metrics(
    self,
    enhanced_data_marts: List[Dict[str, Any]],
    gold_result: Optional[Dict],
    schema_analyses: Dict
) -> Dict[str, Any]
```

Generates gold layer metrics from DDL, dimensions, and measures.

### `_generate_dbt_model()`
```python
def _generate_dbt_model(
    self,
    mart_name: str,
    sql: str,
    mart_info: Dict[str, Any]
) -> str
```

Converts SQL CREATE TABLE statements to dbt models.

### `_generate_dbt_schema()`
```python
def _generate_dbt_schema(
    self,
    enhanced_data_marts: Optional[List[Dict[str, Any]]],
    gold_metrics: Optional[Dict[str, Any]],
    schema_analyses: Dict
) -> str
```

Generates dbt schema.yml with models, columns, and metrics.

## Output Structure

After running the enhanced workflow, you'll get:

```
output/
├── cubes/
│   ├── raw/          # Cube.js definitions (existing)
│   ├── silver/       # Cube.js definitions (existing)
│   └── gold/         # Cube.js definitions (existing)
├── dbt/
│   ├── models/
│   │   └── gold/     # NEW: dbt models
│   └── schema.yml    # NEW: dbt schema with metrics
├── data_marts/
│   ├── {mart_name}.sql              # Original data mart SQL
│   └── {mart_name}_enhanced.sql     # NEW: Enhanced SQL
├── sql/
│   ├── raw_to_silver/   # Silver cleaning SQL
│   └── silver_to_gold/  # Gold transformation SQL
├── documentation/
│   └── gold_metrics.json  # NEW: Gold metrics JSON
└── ...
```

## Usage

The enhanced workflow executor works the same way as before:

```python
from app.agents.cubes.workflow_executor import WorkflowExecutor
import json

# Load workflow configuration
with open('asset_risk_workflow.json', 'r') as f:
    workflow_config = json.load(f)

# Execute workflow
executor = WorkflowExecutor(output_dir="./output")
result = executor.execute_workflow_sync(workflow_config)

# Access new outputs
print(f"dbt Models: {result['saved_paths']['dbt_models']}")
print(f"Gold Metrics: {result['saved_paths']['gold_metrics']}")
```

## Key Features

1. **LLM-Powered Enhancement**: Uses LLM to enhance data marts with best practices
2. **Automatic dbt Generation**: Converts SQL to dbt models automatically
3. **Metrics Extraction**: Automatically extracts dimensions, measures, and metrics
4. **Dual Output**: Generates both dbt and Cube.js formats
5. **Production-Ready**: Includes indexes, constraints, and optimizations

## Integration with Existing Workflow

The enhancements are backward compatible:
- Existing steps continue to work
- New steps are added after existing steps
- All existing outputs are still generated
- New outputs are additional, not replacements

## Next Steps

1. Run the workflow with your configuration
2. Review generated dbt models in `dbt/models/gold/`
3. Review dbt schema in `dbt/schema.yml`
4. Review gold metrics in `documentation/gold_metrics.json`
5. Deploy dbt models to your data warehouse
6. Use Cube.js definitions for analytics layer

