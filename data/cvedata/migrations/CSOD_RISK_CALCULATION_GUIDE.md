# CSOD Risk Calculation Guide

## Overview

This guide explains how to calculate likelihood and impact scores using the CSOD risk scoring metadata tables and generic calculation functions.

## What You Have

### 1. **Metadata Tables** (`create_csod_risk_scoring_metadata_tables.sql`)
- `csod_risk_model_metadata` - Defines models (compliance, attrition)
- `csod_risk_factor_metadata` - Lists factors with weights for impact/likelihood
- `csod_risk_factor_lookup_metadata` - Maps categorical values → scores
- `csod_risk_factor_bucket_metadata` - Maps numeric ranges → scores
- `csod_risk_score_band_metadata` - Defines risk categories (Low/Moderate/High/Critical)

### 2. **Generic Calculation Functions**
- `calculate_generic_likelihood()` - Accepts array of parameters with weights
- `calculate_generic_impact()` - Accepts array of parameters with weights
- JSON interfaces: `calculate_likelihood_from_json()`, `calculate_impact_from_json()`

### 3. **Bridge Functions** (`csod_risk_calculation_functions.sql`) ✨ NEW
- `get_factor_score()` - Maps source values to scores using metadata
- `calculate_csod_likelihood()` - Calculates likelihood from source row
- `calculate_csod_impact()` - Calculates impact from source row
- `calculate_csod_risk()` - Complete risk calculation (impact + likelihood + risk)
- `calculate_csod_risk_batch()` - Batch processing from tables

## What Was Needed

### The Gap
The metadata tables define **what** to calculate, but there was no function to:
1. Read metadata to discover factors
2. Extract values from source data rows
3. Map values to scores (lookup/bucket)
4. Collect parameters with weights
5. Call generic calculation functions

### The Solution
The bridge functions (`csod_risk_calculation_functions.sql`) provide:

1. **Factor Score Mapping** (`get_factor_score`)
   - Queries metadata to determine scoring type
   - For `lookup`: Joins to `csod_risk_factor_lookup_metadata`
   - For `bucket`: Matches numeric value to bucket ranges
   - Returns score or default if unmapped

2. **Likelihood Calculation** (`calculate_csod_likelihood`)
   - Queries `csod_risk_factor_metadata` for active likelihood factors
   - Extracts source values from JSONB row data
   - Gets scores for each factor
   - Builds parameter array with weights
   - Calls `calculate_likelihood_from_json()`

3. **Impact Calculation** (`calculate_csod_impact`)
   - Same pattern as likelihood but for impact factors
   - Calls `calculate_impact_from_json()`

4. **Complete Risk Calculation** (`calculate_csod_risk`)
   - Calculates both impact and likelihood
   - Applies risk formula: `sqrt(impact_score * likelihood_score)`
   - Determines risk category from bands
   - Returns comprehensive results

## Usage Examples

### Example 1: Calculate Compliance Risk

```sql
SELECT * FROM calculate_csod_risk(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress",
        "lastLoginDays": 10,
        "userCompletionRate": 65.0,
        "positionLevel": "Senior Management",
        "activityType": "Compliance",
        "estimatedDuration": 90,
        "cost": 500
    }'::JSONB
);
```

**Returns:**
- `impact_score`: Calculated from position level, activity type, duration, cost
- `likelihood_score`: Calculated from days until due, completion %, status, login days, etc.
- `risk_score`: `sqrt(impact_score * likelihood_score)`
- `risk_category`: "High", "Critical", etc.
- Detailed breakdowns in JSONB columns

### Example 2: Calculate Only Likelihood

```sql
SELECT * FROM calculate_csod_likelihood(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress",
        "lastLoginDays": 10
    }'::JSONB
);
```

### Example 3: From Actual Table Row

```sql
-- Convert table row to JSONB and calculate
WITH row_data AS (
    SELECT row_to_json(cr.*)::JSONB AS data
    FROM compliance_risk_silver cr
    WHERE id = 123
)
SELECT 
    r.impact_score,
    r.likelihood_score,
    r.risk_score,
    r.risk_category
FROM row_data rd
CROSS JOIN LATERAL calculate_csod_risk('compliance', rd.data) r;
```

### Example 4: Batch Processing

```sql
SELECT * FROM calculate_csod_risk_batch(
    'compliance',
    'compliance_risk_silver',
    'id',
    100  -- limit
);
```

## How It Works

### Step-by-Step Process

1. **Metadata Discovery**
   ```sql
   SELECT factor_code, weight, scoring_type, source_columns
   FROM csod_risk_factor_metadata
   WHERE model_code = 'compliance' AND dimension = 'likelihood' AND is_active = TRUE
   ```

2. **Value Extraction**
   - Parse `source_columns` (comma-separated list)
   - Extract value from JSONB row data using first column name
   - Handle both text (for lookups) and numeric (for buckets)

3. **Score Mapping**
   - **Lookup**: `SELECT score FROM csod_risk_factor_lookup_metadata WHERE input_value = 'In Progress'`
   - **Bucket**: Match numeric value to bucket range using min/max with inclusive flags
   - **Default**: Use `default_score` from factor metadata if unmapped

4. **Parameter Collection**
   - Build JSONB array of parameters:
   ```json
   [
     {
       "param_name": "days_until_due",
       "param_value": 95.0,
       "param_weight": 0.20,
       "max_value": 100.0
     },
     ...
   ]
   ```

5. **Generic Function Call**
   - Pass parameter array to `calculate_likelihood_from_json()` or `calculate_impact_from_json()`
   - Generic function applies weights and aggregation method
   - Returns overall score with detailed breakdown

## Column Mapping

### Source Column Names

The functions use `source_columns` from `csod_risk_factor_metadata` to know which columns to read. Common mappings:

**Compliance Likelihood:**
- `daysUntilDue` → `days_until_due` factor
- `completionPercentage` → `completion_percentage` factor
- `trainingStatus` → `course_completion_status` factor (lookup)
- `lastLoginDays` → `last_login_days` factor

**Compliance Impact:**
- `positionLevel` → `position_level` factor (lookup)
- `activityType` → `activity_type` factor (lookup)
- `estimatedDuration` → `estimated_duration` factor (bucket)
- `cost` → `activity_cost` factor (bucket)

**Attrition Likelihood:**
- `tenureRiskBand` → `tenure_risk_band` factor (lookup)
- `learningEngagementScore` → `learning_engagement` factor (bucket)
- `overdueCourseCount` → `overdue_course_count` factor (bucket)

**Attrition Impact:**
- `positionLevel` → `position_level` factor (lookup)
- `directReportCount` → `direct_report_count` factor (bucket)
- `trainingInvestment` → `training_investment` factor (bucket)

## Requirements

### What You Need

1. **Metadata Tables Populated**
   - Run `create_csod_risk_scoring_metadata_tables.sql` to create and seed tables

2. **Generic Functions Available**
   - `generic_likelihood_functions.sql` must be loaded
   - `generic_impact_functions.sql` must be loaded

3. **Bridge Functions**
   - `csod_risk_calculation_functions.sql` must be loaded

4. **Source Data Format**
   - Row data as JSONB with column names matching `source_columns` in metadata
   - Or use `row_to_json()` to convert table rows

### Column Name Matching

The functions extract values using column names from `source_columns`. If your source table uses different names, you have options:

1. **Rename columns** in source data JSONB:
   ```sql
   SELECT calculate_csod_risk(
       'compliance',
       jsonb_build_object(
           'daysUntilDue', days_until_due,  -- map your column name
           'completionPercentage', completion_pct,
           ...
       )
   )
   ```

2. **Update metadata** `source_columns` to match your actual column names

3. **Create view** that maps column names before converting to JSONB

## Limitations & Considerations

### Current Limitations

1. **Single Column Per Factor**
   - Currently uses first column from `source_columns` comma-separated list
   - Could be enhanced to support multiple columns per factor

2. **No Derived Columns**
   - Doesn't calculate derived metrics (e.g., `division_overdue_rate` from `overdueCount/totalAssignments`)
   - These should be pre-calculated in source data

3. **No Time-Based Decay**
   - Generic functions support decay functions, but bridge functions don't pass `time_delta`
   - Could be enhanced to support temporal decay

4. **Linear Scoring Type**
   - Basic implementation for linear scoring
   - May need enhancement based on specific requirements

### Performance Considerations

- **Indexes**: Ensure indexes exist on metadata tables (already created in migration)
- **Batch Processing**: Use `calculate_csod_risk_batch()` for bulk operations
- **Caching**: Consider caching metadata queries if processing many rows

## Next Steps

### Enhancements You Could Add

1. **Support Multiple Columns Per Factor**
   ```sql
   -- Parse all columns from source_columns and aggregate
   ```

2. **Derived Metrics**
   ```sql
   -- Calculate division_overdue_rate on-the-fly
   ```

3. **Time-Based Decay**
   ```sql
   -- Pass assessmentDate or time_delta to generic functions
   ```

4. **Custom Aggregation Methods**
   ```sql
   -- Allow model-specific aggregation methods from metadata
   ```

5. **Rule-Based Scoring**
   ```sql
   -- Implement scoring_type='rule' for complex logic
   ```

## Testing

### Test with Sample Data

```sql
-- Test compliance likelihood
SELECT * FROM calculate_csod_likelihood(
    'compliance',
    jsonb_build_object(
        'daysUntilDue', -5,
        'completionPercentage', 45.0,
        'trainingStatus', 'In Progress',
        'lastLoginDays', 10
    )
);

-- Test impact
SELECT * FROM calculate_csod_impact(
    'compliance',
    jsonb_build_object(
        'positionLevel', 'Senior Management',
        'activityType', 'Compliance',
        'estimatedDuration', 90
    )
);

-- Test complete risk
SELECT * FROM calculate_csod_risk(
    'compliance',
    jsonb_build_object(
        'daysUntilDue', -5,
        'completionPercentage', 45.0,
        'trainingStatus', 'In Progress',
        'positionLevel', 'Senior Management',
        'activityType', 'Compliance'
    )
);
```

## Summary

✅ **Yes, it's possible** to calculate likelihood and impact scores using metadata tables and generic functions.

✅ **What was needed**: Bridge functions that connect metadata → source data → generic functions.

✅ **What you now have**: Complete calculation pipeline from source rows to risk scores.

The solution is **metadata-driven**, **configurable**, and **reusable** across different models (compliance, attrition) and future models you might add.

