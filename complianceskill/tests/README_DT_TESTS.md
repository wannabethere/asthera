# Detection & Triage Workflow Tests

## Quick Start - Focused Use Cases

Run only the 3 focused use cases (fastest):

```bash
# Run all 3 use cases
python tests/test_detection_triage_workflow.py --test use_cases

# Run individual use cases
python tests/test_detection_triage_workflow.py --test use_case_1  # Metrics Help
python tests/test_detection_triage_workflow.py --test use_case_2  # Dashboard Metrics
python tests/test_detection_triage_workflow.py --test use_case_3  # Detection + Metrics Full

# Skip slow operations
python tests/test_detection_triage_workflow.py --test use_cases --skip-slow
```

## Output Structure

Test outputs are organized in a clear directory structure:

```
tests/outputs/
├── use_case_1_metrics_help/
│   └── 20260219_120000/
│       ├── output.json              # Full test result
│       └── outputs/
│           ├── state_snapshot.json  # Key state fields
│           ├── resolved_metrics.json
│           ├── resolved_schemas.json
│           └── metric_recommendations.json
├── use_case_2_dashboard_metrics/
│   └── 20260219_120500/
│       ├── output.json
│       └── outputs/
│           ├── state_snapshot.json
│           ├── resolved_metrics.json
│           ├── resolved_schemas.json
│           ├── metric_recommendations.json
│           └── medallion_plan.json
└── use_case_3_detection_metrics_full/
    └── 20260219_121000/
        ├── output.json
        └── outputs/
            ├── state_snapshot.json
            ├── siem_rules.json
            ├── metric_recommendations.json
            └── medallion_plan.json
```

## Use Cases

### Use Case 1: Metrics Help
**Purpose:** User wants to understand what metrics they can track for compliance.

**Query:** "What metrics should I track for SOC2 vulnerability management compliance? I have Qualys and Snyk configured."

**Outputs:**
- `resolved_metrics.json` - Available metrics from registry
- `resolved_schemas.json` - MDL schemas for those metrics
- `metric_recommendations.json` - Recommended metrics with calculation steps

**Nodes Executed:**
- Intent Classifier
- Planner
- Framework Retrieval
- Metrics Retrieval
- MDL Schema Retrieval
- Scoring Validator
- Triage Engineer

### Use Case 2: Dashboard Metrics Workflow
**Purpose:** User wants to build a compliance dashboard with metrics.

**Query:** "I need to build a SOC2 compliance dashboard showing vulnerability management metrics. Generate the metric recommendations and medallion architecture plan."

**Outputs:**
- `resolved_metrics.json` - Metrics selected for dashboard
- `resolved_schemas.json` - MDL schemas
- `metric_recommendations.json` - 10+ metric recommendations
- `medallion_plan.json` - Bronze/Silver/Gold architecture plan

**Nodes Executed:**
- Full triage workflow (all nodes up to playbook assembler)
- Metric validation
- Playbook assembly

### Use Case 3: Detection + Metrics Full Workflow
**Purpose:** User wants both SIEM detection rules and compliance metrics.

**Query:** "Build a complete SOC2 compliance package. I need both Sentinel detection rules and compliance dashboard metrics."

**Outputs:**
- `siem_rules.json` - Detection rules
- `metric_recommendations.json` - Compliance metrics
- `medallion_plan.json` - Data pipeline architecture
- Full playbook with traceability

**Nodes Executed:**
- Complete workflow (Template C - full chain)

## Running Individual Tests

```bash
# Individual node tests (for debugging)
python tests/test_detection_triage_workflow.py --test intent_classifier
python tests/test_detection_triage_workflow.py --test metrics_retrieval
python tests/test_detection_triage_workflow.py --test mdl_schema
python tests/test_detection_triage_workflow.py --test triage_engineer

# Full workflow tests
python tests/test_detection_triage_workflow.py --test playbook_assembler
python tests/test_detection_triage_workflow.py --test hipaa_detection

# All tests (slow - runs all 12+ tests)
python tests/test_detection_triage_workflow.py --test all
```

## Performance Tips

1. **Use `--test use_cases`** - Only runs the 3 focused use cases (fastest)
2. **Use `--skip-slow`** - Skips full workflow tests (Use Case 3)
3. **Run individual tests** - For debugging specific nodes
4. **Check logs** - Look for timing information in the logs

## Output Files Explained

### `output.json`
Complete test result including:
- Test name and timestamp
- Validation results
- Full state snapshot
- All workflow outputs

### `outputs/state_snapshot.json`
Key state fields summary:
- Intent, framework_id
- Playbook template
- Data sources in scope
- Counts of metrics, schemas, rules, recommendations

### `outputs/resolved_metrics.json`
Metrics retrieved from `leen_metrics_registry`:
- metric_id, name, description
- source_capabilities
- source_schemas
- category, kpis, trends

### `outputs/resolved_schemas.json`
MDL schemas found:
- table_name
- table_ddl
- column_metadata
- project_id, product_id, capability_id

### `outputs/metric_recommendations.json`
Metric recommendations from triage engineer:
- id, name, description
- calculation_plan_steps (natural language)
- mapped_control_codes
- data_source_required

### `outputs/medallion_plan.json`
Medallion architecture plan:
- entries (one per metric)
- bronze_table, silver_table_suggestion, gold_table
- needs_silver, gold_available
- calculation_steps

### `outputs/siem_rules.json`
SIEM detection rules:
- rule_id, name, description
- log_sources_required
- mapped_control_codes
- alert_config
- rule_logic

## Troubleshooting

### Tests are slow
- Use `--test use_cases` instead of `--test all`
- Use `--skip-slow` to skip full workflow tests
- Run individual node tests for debugging

### No schemas found
- Check logs for product capabilities lookup
- Verify `product_capabilities` collection is populated
- Check that MDL schemas have correct `project_id` format

### Empty metrics
- Verify `leen_metrics_registry` collection is populated
- Check that metrics have `source_capabilities` matching your data sources
- Ensure `source_schemas` field is populated in metrics

### Output files not created
- Check that `tests/outputs/` directory exists and is writable
- Look for errors in the logs
- Verify test completed successfully (check `success` field in output.json)



# Only the 3 focused use cases (faster)
python tests/test_detection_triage_workflow.py --test use_cases

# A single use case
python tests/test_detection_triage_workflow.py --test use_case_1    # Metrics Help
python tests/test_detection_triage_workflow.py --test use_case_2    # Dashboard Metrics
python tests/test_detection_triage_workflow.py --test use_case_3    # Detection + Metrics Full

# Individual node tests
python tests/test_detection_triage_workflow.py --test intent_classifier
python tests/test_detection_triage_workflow.py --test planner
python tests/test_detection_triage_workflow.py --test metric_validator
python tests/test_detection_triage_workflow.py --test triage_engineer
