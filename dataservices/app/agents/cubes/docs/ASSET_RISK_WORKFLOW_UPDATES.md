# Asset Risk Workflow Configuration Updates

This document describes the enhancements made to `asset_risk_workflow.json` to support the enhanced workflow executor pipeline.

## New Configuration Fields

### 1. `silver_cleaning_hints` (NEW)
Provides hints to the LLM for silver table cleaning steps:

```json
"silver_cleaning_hints": {
  "assets": {
    "cleaning_steps": [
      "Remove duplicate asset_id entries",
      "Validate criticality is between 1-100",
      "Standardize business_unit and env values",
      "Ensure timestamps are valid"
    ]
  },
  "vulnerabilities": {
    "cleaning_steps": [
      "Validate CVSS scores are between 0-10",
      "Validate EPSS scores are between 0-1",
      "Ensure CVE IDs follow standard format",
      "Handle null values in scores"
    ]
  },
  "misconfigurations": {
    "cleaning_steps": [
      "Standardize severity values (low/med/high/critical)",
      "Validate category values",
      "Ensure config_id is unique per asset"
    ]
  }
}
```

**Purpose**: Guides the LLM in Step 1 (Silver Tables Cleaning) to generate appropriate cleaning SQL.

### 2. `gold_metrics_config` (NEW)
Configures gold layer metrics extraction:

```json
"gold_metrics_config": {
  "dimensions": [
    "business_unit",
    "env",
    "asset_id",
    "os_category"
  ],
  "measures": [
    "attack_surface_index",
    "exploitability_likelihood",
    "external_exposure_score",
    "vulnerability_exposure_score",
    "misconfiguration_exposure_score",
    "identity_exposure_score",
    "software_exposure_score"
  ],
  "time_grain": "month",
  "aggregation_types": ["sum", "avg", "count", "max", "min", "percentile"]
}
```

**Purpose**: 
- Guides Step 11 (Gold Metrics Generation) to extract the right dimensions and measures
- Helps LLM identify expected metrics from data marts
- Specifies time grain and aggregation types for trend analysis

### 3. `enable_dbt_generation` (NEW)
```json
"enable_dbt_generation": true
```

**Purpose**: Controls whether dbt models and schema.yml are generated (Step 12).

### 4. `enable_enhanced_data_marts` (NEW)
```json
"enable_enhanced_data_marts": true
```

**Purpose**: Controls whether data marts are enhanced with transformations (Step 10).

### 5. `enable_gold_metrics` (NEW)
```json
"enable_gold_metrics": true
```

**Purpose**: Controls whether gold metrics are extracted from data marts (Step 11).

### 6. `output_formats` (NEW)
```json
"output_formats": ["cubejs", "dbt"]
```

**Purpose**: Specifies which output formats to generate (currently supports "cubejs" and "dbt").

### 7. Enhanced `expected_outputs` (UPDATED)
Added `dbt_models` section:

```json
"expected_outputs": {
  ...
  "dbt_models": [
    "attack_surface_index",
    "attack_surface_by_bu",
    "attack_surface_by_env_os",
    "exploitability_likelihood",
    "exposure_trends_monthly"
  ]
}
```

## Workflow Execution Flow

With these enhancements, the workflow now executes:

1. **Step 1**: Parse inputs
2. **Step 2**: Initialize silver workflow state
3. **Step 3**: Enrich table metadata
4. **Step 4**: Human-in-the-loop collection and data mart planning
   - Uses `data_mart_goals` from config
5. **Step 5**: Analyze schemas
6. **Step 6**: Plan transformations
7. **Step 7**: Execute silver generation workflow
   - Uses `silver_cleaning_hints` if available
8. **Step 8**: Generate gold layer (if `generate_gold: true`)
9. **Step 9**: Generate enhanced cube definitions
10. **Step 10**: Enhance data marts with transformations (if `enable_enhanced_data_marts: true`)
11. **Step 11**: Generate gold metrics (if `enable_gold_metrics: true`)
    - Uses `gold_metrics_config` to guide extraction
12. **Step 12**: Save all artifacts
    - Generates dbt models if `enable_dbt_generation: true`
    - Generates Cube.js (always)
13. **Step 13**: Generate documentation

## Configuration Options

All new features can be enabled/disabled:

| Feature | Config Field | Default | Description |
|---------|-------------|---------|-------------|
| Enhanced Data Marts | `enable_enhanced_data_marts` | `true` | Add transformations to data marts |
| Gold Metrics | `enable_gold_metrics` | `true` | Extract metrics from data marts |
| dbt Generation | `enable_dbt_generation` | `true` | Generate dbt models and schema |
| Gold Layer | `generate_gold` | `true` | Generate gold layer cubes |

## Benefits

1. **Better Silver Cleaning**: `silver_cleaning_hints` guides LLM to generate appropriate cleaning logic
2. **Accurate Metrics**: `gold_metrics_config` helps LLM extract the right dimensions and measures
3. **Flexible Execution**: Can enable/disable features as needed
4. **Dual Output**: Generates both Cube.js and dbt formats
5. **Production Ready**: Enhanced data marts include indexes, constraints, and optimizations

## Usage

The workflow file is now ready to use with the enhanced workflow executor:

```python
from app.agents.cubes.workflow_executor import WorkflowExecutor
import json

# Load workflow configuration
with open('asset_risk_workflow.json', 'r') as f:
    workflow_config = json.load(f)

# Execute workflow
executor = WorkflowExecutor(output_dir="./output")
result = executor.execute_workflow_sync(workflow_config)

# All enhanced features will be generated automatically
```

## Validation

The JSON file has been validated and is properly formatted. All required fields are present:
- ✅ `workflow_name`
- ✅ `raw_schemas`
- ✅ `lod_configurations`
- ✅ `relationship_mappings`
- ✅ `user_query`
- ✅ `data_mart_goals`
- ✅ `generate_gold`
- ✅ New optional fields for enhanced features

