# Test Improvements Summary

## Changes Made

### 1. **Organized Output Structure**
   - **Before:** All outputs in `tests/output/` with flat filenames
   - **After:** Organized structure: `tests/outputs/testcase_name/timestamp/outputs/`
   
   **New Structure:**
   ```
   tests/outputs/
   ├── use_case_1_metrics_help/
   │   └── 20260219_120000/
   │       ├── output.json
   │       └── outputs/
   │           ├── state_snapshot.json
   │           ├── resolved_metrics.json
   │           ├── resolved_schemas.json
   │           └── metric_recommendations.json
   ```

### 2. **Focused Use Cases**
   Added 3 focused test cases for your primary use cases:
   
   - **Use Case 1: Metrics Help** - Quick metrics lookup and recommendations
   - **Use Case 2: Dashboard Metrics Workflow** - Full triage workflow with medallion plan
   - **Use Case 3: Detection + Metrics Full** - Complete Template C workflow

### 3. **Performance Optimizations**
   - Added `--test use_cases` option to run only the 3 focused use cases (much faster)
   - Added `--skip-slow` flag to skip full workflow tests
   - Better organized outputs make it easier to find what you need

### 4. **Enhanced Output Files**
   Each test now generates:
   - `output.json` - Complete test result
   - `outputs/state_snapshot.json` - Key state summary
   - `outputs/resolved_metrics.json` - Metrics found
   - `outputs/resolved_schemas.json` - MDL schemas
   - `outputs/metric_recommendations.json` - Metric recommendations
   - `outputs/medallion_plan.json` - Medallion architecture (if applicable)
   - `outputs/siem_rules.json` - SIEM rules (if applicable)

## Quick Usage

### Run Focused Use Cases (Recommended)
```bash
# Run all 3 use cases (fastest)
python tests/test_detection_triage_workflow.py --test use_cases

# Run individual use cases
python tests/test_detection_triage_workflow.py --test use_case_1
python tests/test_detection_triage_workflow.py --test use_case_2
python tests/test_detection_triage_workflow.py --test use_case_3
```

### Run Individual Node Tests (For Debugging)
```bash
python tests/test_detection_triage_workflow.py --test metrics_retrieval
python tests/test_detection_triage_workflow.py --test mdl_schema
python tests/test_detection_triage_workflow.py --test triage_engineer
```

### Skip Slow Operations
```bash
python tests/test_detection_triage_workflow.py --test use_cases --skip-slow
```

## Output Location

All outputs are now in: `tests/outputs/testcase_name/timestamp/`

Each test run creates a new timestamped directory, so you can:
- Compare multiple runs
- Keep history of test results
- Easily find the latest run for each test case

## Benefits

1. **Faster Testing** - Run only what you need with `--test use_cases`
2. **Better Organization** - Clear directory structure per test case
3. **Easier Debugging** - Separate JSON files for each output type
4. **Historical Tracking** - Timestamped directories for each run
5. **Focused Use Cases** - 3 clear test cases matching your primary workflows
