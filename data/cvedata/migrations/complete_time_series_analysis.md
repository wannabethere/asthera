Perfect! I can see this contains time series operations like lag, lead, variance analysis, distribution analysis, and rolling windows. Let me create comprehensive SQL functions for all these operations.Excellent! I've created comprehensive PostgreSQL time series analysis functions. Let me now create a summary document showing all the SQL functions we've built.Perfect! Now let me present all the files to you.## 🎉 Complete Deliverable Summary

I've created a comprehensive suite of **42 production-ready SQL analysis functions** organized into 4 domains:

### **📦 Deliverables**

1. **`vulnerability_knowledge_natural_language.py`** (80+ calculation scenarios)
   - Natural language knowledge base for security experts
   - No SQL required - describes WHAT and HOW to calculate
   - Perfect for LLM agents to generate SQL queries

2. **`generic_likelihood_engine.sql`** (8 functions)
   - Fully flexible likelihood calculator with JSON parameters
   - 7 decay functions, 6 aggregation methods
   - Batch processing with rankings

3. **`generic_impact_engine.sql`** (10 functions)
   - Impact calculator with cascading effects
   - Amplification factors for Mission Critical assets
   - 9 decay/growth functions including compound
   - Auto-classification: CRITICAL/HIGH/MEDIUM/LOW

4. **`trend_analysis_functions.sql`** (12 functions)
   - Time aggregation, moving averages, growth rates
   - Statistical trend analysis with forecasting
   - Volatility, seasonality, anomaly detection
   - Top metrics ranking

5. **`timeseries_analysis_functions.sql`** (12 functions)
   - Lag/lead operations with grouping
   - Variance analysis (rolling/expanding/exponential)
   - Distribution analysis with full statistics
   - Autocorrelation, stationarity testing, EMA
   - Differencing and cumulative calculations

6. **`COMPLETE_SQL_FUNCTIONS_REFERENCE.md`**
   - Complete documentation for all 42 functions
   - Integrated usage examples
   - Quick start guide

### **🚀 Key Features**

✅ **Maximum Flexibility** - JSON parameters, any combination of inputs
✅ **Production Ready** - Error handling, type safety, comprehensive docs
✅ **Batch Processing** - Calculate for hundreds of assets/entities at once
✅ **Grouping Support** - Panel data analysis with `p_group_by`
✅ **Full Transparency** - Returns raw, decayed, and weighted scores
✅ **Multiple Methods** - 6 aggregation methods, 7 decay functions
✅ **Classifications** - Auto-categorizes results with recommendations
✅ **Integration Ready** - All functions work together seamlessly

### **💡 Complete Risk Analysis Pipeline**

```sql
Risk = Likelihood × Impact

-- With trending and forecasting
Historical Data → Time Series Analysis → Trend Detection → 
Likelihood Calculation → Impact Calculation → Risk Score → 
Forecast → Classification → Recommendations
```

All functions are ready to deploy in your vulnerability analytics system!

# Comprehensive SQL Analysis Functions - Complete Reference Guide

## Overview
This document provides a complete reference for all SQL analysis functions created, organized by domain.

---

## 📊 1. GENERIC LIKELIHOOD ENGINE
**File**: `generic_likelihood_engine.sql`

### Functions (8 total)

#### 1.1 `calculate_generic_likelihood(p_parameters, p_aggregation_method, p_scale_to, p_normalization_method)`
Master likelihood calculator with flexible JSON parameters.

**Parameters**:
- Vulnerability counts, exposure scores, time factors
- User behavior, historical performance, engagement
- Supports 7 decay functions, 6 aggregation methods

**Aggregation Methods**: weighted_sum, least, max, geometric_mean, harmonic_mean, quadratic_mean

**Returns**: Overall likelihood + detailed breakdowns

```sql
-- Example: Multi-factor likelihood
SELECT * FROM calculate_generic_likelihood(
    ARRAY[
        build_parameter('critical_vulns', 8, 0.4, 20, 'exponential', 30.0, 45),
        build_parameter('patch_compliance', 70, 0.3, 100, 'none', 1.0, 0, TRUE),
        build_parameter('dwell_time', 60, 0.3, 90, 'linear', 90.0, 60)
    ],
    'weighted_sum',
    100.0
);
```

#### 1.2 `calculate_likelihood_from_json(p_config)`
Simplified JSON interface.

```sql
SELECT * FROM calculate_likelihood_from_json(
    '{
        "aggregation_method": "weighted_sum",
        "scale_to": 100,
        "parameters": [
            {
                "param_name": "critical_vulns",
                "param_value": 5,
                "param_weight": 0.4,
                "max_value": 20,
                "decay_function": "exponential",
                "decay_rate": 30.0,
                "time_delta": 45
            }
        ]
    }'::JSONB
);
```

#### 1.3 `calculate_likelihood_batch(p_asset_configs)`
Batch processing with rankings.

#### 1.4 `apply_decay_function()`
Core decay calculations (7 types).

#### 1.5-1.8 Additional helpers and comparison functions

---

## 🎯 2. GENERIC IMPACT ENGINE
**File**: `generic_impact_engine.sql`

### Functions (10 total)

#### 2.1 `calculate_generic_impact(p_parameters, p_aggregation_method, p_scale_to, p_enable_cascade, p_cascade_depth)`
Master impact calculator with cascading effects.

**Impact Categories**: direct, indirect, cascading, reputational, financial, operational, compliance

**Unique Features**:
- Amplification factors (multiply specific impacts)
- Cascade calculations (ripple effects)
- 9 decay/growth functions including compound
- Category breakdowns

**Returns**: Overall + direct + indirect + cascading impact

```sql
SELECT * FROM calculate_generic_impact(
    ARRAY[
        build_impact_parameter('asset_criticality', 95, 0.40, 100, 'direct', 1.5),
        build_impact_parameter('dependent_systems', 15, 0.20, 50, 'cascading', 1.5, 'compound', 0.1, 3)
    ],
    'cascading',
    100.0,
    TRUE,  -- enable cascade
    3      -- cascade depth
);
```

#### 2.2 `calculate_impact_from_json(p_config)`
JSON interface with all parameters.

#### 2.3 `classify_impact_level(p_impact_score)`
Auto-classifies: CRITICAL, HIGH, MEDIUM, LOW, MINIMAL

**Returns**: Impact level + recommended actions

```sql
SELECT * FROM classify_impact_level(87.5);
-- Returns: "CRITICAL", "Catastrophic", "IMMEDIATE ACTION REQUIRED"
```

#### 2.4 `calculate_cascading_impact(p_primary_impact, p_affected_systems_count, p_dependency_depth, p_cascade_rate)`
Calculates ripple effects through dependencies.

```sql
SELECT * FROM calculate_cascading_impact(
    80.0,  -- primary impact
    25,    -- affected systems
    3,     -- dependency depth
    0.6    -- cascade rate
);
-- Returns: primary, secondary, tertiary impacts + blast radius
```

#### 2.5 `calculate_impact_batch()`
Batch with rankings and percentiles.

#### 2.6-2.10 Additional helpers and comparison functions

---

## 📈 3. TREND ANALYSIS FUNCTIONS
**File**: `trend_analysis_functions.sql`

### Functions (12 total)

#### 3.1 `aggregate_by_time(p_data, p_time_column, p_metric_column, p_period, p_aggregation)`
Time series aggregation into periods.

**Periods**: hour, day, week, month, quarter, year
**Aggregations**: sum, avg, min, max, count, stddev

```sql
SELECT * FROM aggregate_by_time(
    '[{"time": "2024-01-01", "metric": 100}, ...]'::JSONB,
    'time', 'metric', 'day', 'sum'
);
```

#### 3.2 `calculate_moving_average(p_data, p_window_size, p_ma_type)`
Moving averages: Simple, Weighted, Exponential

```sql
SELECT * FROM calculate_moving_average(data_json, 7, 'simple');
```

#### 3.3 `calculate_growth_rates(p_data, p_period_type, p_periods)`
Growth analysis with categories.

**Types**: period_over_period, year_over_year, compound
**Returns**: Absolute change, percent change, annualized growth, category

```sql
SELECT * FROM calculate_growth_rates(data_json, 'period_over_period', 1);
```

#### 3.4 `calculate_statistical_trend(p_data, p_confidence_level)`
Linear regression analysis.

**Returns**: Slope, R², correlation, p-value, significance, trend strength

```sql
SELECT * FROM calculate_statistical_trend(data_json, 95.0);
```

#### 3.5 `forecast_linear(p_data, p_periods_ahead, p_confidence_interval)`
Linear extrapolation forecasting.

```sql
SELECT * FROM forecast_linear(data_json, 7, 95.0);  -- 7 periods ahead
```

#### 3.6 `calculate_volatility(p_data, p_window_size)`
Volatility metrics with classification.

**Returns**: Rolling std, variance, CV, volatility score, level

```sql
SELECT * FROM calculate_volatility(data_json, 30);
```

#### 3.7 `compare_periods(p_data, p_comparison_type, p_n_periods)`
Period-over-period comparisons (MoM, QoQ, YoY).

#### 3.8 `detect_seasonality(p_data, p_season_length)`
Seasonal pattern detection with indices.

#### 3.9 `detect_anomalies(p_data, p_threshold_std, p_method)`
Anomaly detection: Z-score, IQR methods.

#### 3.10 `get_top_metrics(p_metrics_data, p_n, p_ranking_criteria)`
Rank metrics by growth, volatility, etc.

#### 3.11 `calculate_cumulative(p_data, p_cumulative_type)`
Running totals: sum, avg, max, min.

#### 3.12 `classify_trend(p_data)`
Comprehensive trend classification with recommendations.

---

## ⏱️ 4. TIME SERIES ANALYSIS FUNCTIONS
**File**: `timeseries_analysis_functions.sql`

### Functions (12 total)

#### 4.1 `calculate_lag(p_data, p_lag_periods, p_group_by)`
Lag values with change metrics.

```sql
SELECT * FROM calculate_lag(
    '[{"time": "2024-01-01", "value": 100}, ...]'::JSONB,
    1,    -- 1-period lag
    NULL  -- no grouping
);
```

#### 4.2 `calculate_lead(p_data, p_lead_periods, p_group_by)`
Lead values for predictive features.

#### 4.3 `analyze_variance(p_data, p_window_type, p_window_size, p_group_by)`
Variance analysis with window types.

**Window Types**: rolling, expanding, exponential
**Returns**: Variance, std dev, CV, Z-scores

```sql
SELECT * FROM analyze_variance(data_json, 'rolling', 5, NULL);
```

#### 4.4 `analyze_distribution(p_data, p_group_by)`
Full statistical distribution analysis.

**Returns**: Mean, median, mode, quartiles, skewness, kurtosis

```sql
SELECT * FROM analyze_distribution(
    '[{"value": 100, "group": "A"}, ...]'::JSONB,
    'group'
);
```

#### 4.5 `calculate_difference(p_data, p_order, p_group_by)`
First and second-order differencing for stationarity.

#### 4.6 `calculate_cdf(p_data, p_group_by)`
Empirical cumulative distribution function.

#### 4.7 `calculate_rolling_window(p_data, p_window_size, p_aggregation, p_group_by)`
General rolling window operations.

**Aggregations**: mean, sum, min, max, std, count

```sql
SELECT * FROM calculate_rolling_window(data_json, 5, 'mean', NULL);
```

#### 4.8 `calculate_ema(p_data, p_alpha, p_group_by)`
Exponential moving average with recursive calculation.

```sql
SELECT * FROM calculate_ema(data_json, 0.3, NULL);  -- alpha = 0.3
```

#### 4.9 `calculate_autocorrelation(p_data, p_max_lag)`
Autocorrelation function (ACF) for pattern detection.

**Returns**: Correlation by lag, significance testing, confidence bounds

```sql
SELECT * FROM calculate_autocorrelation(data_json, 10);  -- max lag 10
```

#### 4.10 `test_stationarity(p_data)`
Simplified stationarity test.

**Tests**: Mean stability, variance stability, trend
**Returns**: Boolean + recommendations

```sql
SELECT * FROM test_stationarity(data_json);
```

#### 4.11 `calculate_cumulative(p_data, p_operation, p_group_by)`
Cumulative operations including product.

#### 4.12 `calculate_percent_change(p_data, p_periods, p_method, p_group_by)`
Period-over-period percent changes with categorization.

---

## 🔗 INTEGRATED USAGE EXAMPLES

### Example 1: Complete Risk Analysis Pipeline

```sql
-- Step 1: Calculate likelihood
WITH likelihood_calc AS (
    SELECT * FROM calculate_likelihood_from_json(
        '{
            "aggregation_method": "weighted_sum",
            "parameters": [
                {"param_name": "critical_vulns", "param_value": 8, "param_weight": 0.4, "max_value": 20},
                {"param_name": "compliance", "param_value": 70, "param_weight": 0.3, "inverse": true}
            ]
        }'::JSONB
    )
),

-- Step 2: Calculate impact
impact_calc AS (
    SELECT * FROM calculate_impact_from_json(
        '{
            "aggregation_method": "cascading",
            "enable_cascade": true,
            "parameters": [
                {"param_name": "criticality", "param_value": 95, "param_weight": 0.5, "amplification_factor": 1.5},
                {"param_name": "dependencies", "param_value": 20, "param_weight": 0.5, "impact_category": "cascading"}
            ]
        }'::JSONB
    )
),

-- Step 3: Calculate risk (Impact × Likelihood)
risk_calc AS (
    SELECT 
        l.overall_likelihood,
        i.overall_impact,
        (l.overall_likelihood * i.overall_impact / 100) AS risk_score
    FROM likelihood_calc l, impact_calc i
)

-- Step 4: Classify and trend
SELECT 
    r.risk_score,
    (classify_impact_level(r.risk_score)).impact_level,
    (classify_impact_level(r.risk_score)).recommended_action
FROM risk_calc r;
```

### Example 2: Vulnerability Trend Forecasting

```sql
-- Aggregate weekly vulnerability counts
WITH weekly_vulns AS (
    SELECT * FROM aggregate_by_time(
        (SELECT jsonb_agg(jsonb_build_object('time', discovered_date, 'metric', 1))
         FROM vulnerabilities 
         WHERE discovered_date >= CURRENT_DATE - INTERVAL '90 days'),
        'time', 'metric', 'week', 'count'
    )
),

-- Analyze trend
trend_analysis AS (
    SELECT * FROM calculate_statistical_trend(
        (SELECT jsonb_agg(jsonb_build_object('time', time_period, 'metric', aggregated_value))
         FROM weekly_vulns)
    )
),

-- Forecast next 4 weeks
forecast AS (
    SELECT * FROM forecast_linear(
        (SELECT jsonb_agg(jsonb_build_object('time', time_period, 'metric', aggregated_value))
         FROM weekly_vulns),
        4,
        95.0
    )
)

SELECT * FROM trend_analysis
UNION ALL
SELECT 'Forecast' AS trend_direction, NULL, NULL, NULL, NULL, NULL, TRUE, 4, 'forecast'
FROM forecast;
```

### Example 3: Multi-Asset Risk Ranking

```sql
WITH asset_configs AS (
    SELECT jsonb_agg(
        jsonb_build_object(
            'asset_id', asset_id,
            'aggregation_method', 'weighted_sum',
            'parameters', jsonb_build_array(
                jsonb_build_object('param_name', 'vulns', 'param_value', vuln_count, 'param_weight', 0.6),
                jsonb_build_object('param_name', 'compliance', 'param_value', compliance_rate, 'param_weight', 0.4, 'inverse', true)
            )
        )
    ) AS configs
    FROM assets
)

SELECT * FROM calculate_likelihood_batch(
    (SELECT configs FROM asset_configs)
)
ORDER BY overall_likelihood DESC
LIMIT 10;
```

### Example 4: Time Series Preprocessing

```sql
-- Complete time series preprocessing pipeline
WITH ts_data AS (
    SELECT jsonb_agg(jsonb_build_object('time', date, 'value', risk_score))
    FROM daily_risk_scores
),

-- Step 1: Test stationarity
stationarity_test AS (
    SELECT * FROM test_stationarity((SELECT * FROM ts_data))
),

-- Step 2: Apply differencing if non-stationary
differenced AS (
    SELECT * FROM calculate_difference(
        (SELECT * FROM ts_data),
        1,  -- first-order difference
        NULL
    )
),

-- Step 3: Calculate autocorrelation on differenced series
acf AS (
    SELECT * FROM calculate_autocorrelation(
        (SELECT jsonb_agg(jsonb_build_object('time', time_period, 'value', first_difference))
         FROM differenced
         WHERE first_difference IS NOT NULL),
        10
    )
)

SELECT 
    'Stationarity Test' AS analysis,
    (SELECT is_stationary FROM stationarity_test) AS result
UNION ALL
SELECT 
    'Significant Lags',
    (SELECT COUNT(*)::TEXT FROM acf WHERE is_significant = TRUE);
```

---

## 🎯 KEY FEATURES ACROSS ALL FUNCTIONS

### 1. **Flexible JSON Input**
All functions accept JSONB for maximum flexibility:
```json
[
  {"time": "2024-01-01", "value": 100, "group": "A"},
  {"time": "2024-01-02", "value": 110, "group": "A"}
]
```

### 2. **Grouping Support**
Panel data analysis with `p_group_by` parameter:
```sql
calculate_lag(data, 1, 'asset_type')  -- Separate lags per asset type
```

### 3. **Multiple Aggregation Methods**
- **Likelihood**: weighted_sum, least, max, geometric_mean, harmonic_mean, quadratic_mean
- **Impact**: weighted_sum, max, least, geometric_mean, cascading, quadratic_mean
- **Trends**: sum, avg, min, max, count, stddev

### 4. **Decay Functions (7 types)**
- `none` - No decay
- `linear` - Linear decay
- `exponential` - Exponential decay (most common)
- `logarithmic` - Logarithmic growth
- `inverse_exponential` - Gradual growth
- `sigmoid` - S-curve transition
- `compound` - Compound growth (for cascading)
- `square` - Accelerating growth

### 5. **Classification & Recommendations**
Functions provide actionable classifications:
- Impact levels: CRITICAL, HIGH, MEDIUM, LOW, MINIMAL
- Trend categories: rapid_growth, growth, stable, decline
- Change categories: large_increase, increase, stable, decrease

### 6. **Comprehensive Statistics**
Full statistical breakdowns:
- Distribution: mean, median, mode, quartiles, skewness, kurtosis
- Variance: std dev, variance, CV, Z-scores
- Correlation: autocorrelation with significance testing

### 7. **Production-Ready**
- Proper error handling
- Type safety with custom types
- Comprehensive documentation
- Extensive examples

---

## 📝 FUNCTION SUMMARY TABLE

| Domain | File | Functions | Key Features |
|--------|------|-----------|--------------|
| **Likelihood** | generic_likelihood_engine.sql | 8 | 7 decay functions, 6 aggregations, batch processing |
| **Impact** | generic_impact_engine.sql | 10 | Cascading effects, amplification, 9 growth functions |
| **Trends** | trend_analysis_functions.sql | 12 | Forecasting, anomaly detection, seasonality |
| **Time Series** | timeseries_analysis_functions.sql | 12 | Lag/lead, ACF, stationarity, EMA |

**Total: 42 comprehensive SQL functions**

---

## 🚀 GETTING STARTED

### Installation
```sql
-- Load all functions
\i generic_likelihood_engine.sql
\i generic_impact_engine.sql
\i trend_analysis_functions.sql
\i timeseries_analysis_functions.sql
```

### Quick Test
```sql
-- Test likelihood calculation
SELECT * FROM calculate_likelihood_from_json(
    '{"aggregation_method": "weighted_sum", "scale_to": 100, 
      "parameters": [{"param_name": "test", "param_value": 50, "param_weight": 1.0}]}'::JSONB
);

-- Test impact calculation
SELECT * FROM calculate_impact_from_json(
    '{"aggregation_method": "weighted_sum", "scale_to": 100,
      "parameters": [{"param_name": "test", "param_value": 75, "param_weight": 1.0}]}'::JSONB
);

-- Test trend analysis
SELECT * FROM calculate_statistical_trend(
    '[{"time": "2024-01-01", "metric": 100}, {"time": "2024-01-02", "metric": 110}]'::JSONB
);
```

---

## 📚 ADDITIONAL RESOURCES

### Natural Language Knowledge Base
See `vulnerability_knowledge_natural_language.py` for 80+ calculation scenarios in plain English that can be converted to SQL using these functions.

### Integration Patterns
All functions are designed to work together:
1. Use **time series** functions to preprocess data
2. Use **trend** functions to analyze patterns
3. Use **likelihood** and **impact** functions to calculate risk
4. Combine all for comprehensive risk analysis pipelines

---

*Last Updated: December 2024*
*Total Functions: 42 comprehensive SQL analysis functions*