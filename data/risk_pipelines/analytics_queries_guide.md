# Risk Analytics Data Mart - Business Intelligence Guide

## Complete Guide to Querying Risk, Impact, Likelihood, and Survival Analytics

---

## Table of Contents
1. [Risk Score Trend Analysis](#risk-score-trend-analysis)
2. [Likelihood & Impact Decomposition](#likelihood--impact-decomposition)
3. [Survival Analysis Queries](#survival-analysis-queries)
4. [Cohort Analysis](#cohort-analysis)
5. [Risk Driver Analysis](#risk-driver-analysis)
6. [Executive Dashboards](#executive-dashboards)
7. [Predictive Analytics](#predictive-analytics)

---

## Risk Score Trend Analysis

### Query 1: Individual Entity Risk Trajectory

```sql
-- Track risk score trends for specific entity over time
-- Shows overall risk, likelihood, impact with 7-day and 30-day moving averages

SELECT 
    e.entity_id,
    e.entity_name,
    dt.date_actual as assessment_date,
    f.overall_risk_score,
    f.likelihood_score,
    f.impact_score,
    f.risk_level,
    
    -- Moving averages for trend smoothing
    AVG(f.overall_risk_score) OVER (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as risk_7day_ma,
    
    AVG(f.overall_risk_score) OVER (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as risk_30day_ma,
    
    -- Change metrics
    f.overall_risk_score - LAG(f.overall_risk_score, 1) OVER (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key
    ) as daily_change,
    
    f.overall_risk_score - LAG(f.overall_risk_score, 7) OVER (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key
    ) as weekly_change,
    
    -- Likelihood and Impact trends
    f.likelihood_score - LAG(f.likelihood_score, 1) OVER (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key
    ) as likelihood_change,
    
    f.impact_score - LAG(f.impact_score, 1) OVER (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key
    ) as impact_change

FROM fact_risk_assessment f
JOIN dim_entity e ON f.entity_key = e.entity_key
JOIN dim_date dt ON f.assessment_date_key = dt.date_key
JOIN dim_risk_domain d ON f.domain_key = d.domain_key

WHERE e.entity_id = 'USR12345'
  AND d.domain_name = 'Employee Attrition'
  AND dt.date_actual >= CURRENT_DATE - INTERVAL '90 days'
  
ORDER BY dt.date_actual;
```

**Use Case**: Display in line chart showing risk trajectory with intervention points

---

### Query 2: Population-Level Risk Distribution Over Time

```sql
-- Risk distribution across entire population by month
-- Shows how many entities are in each risk category over time

SELECT 
    dt.year_number,
    dt.month_number,
    dt.month_name,
    d.domain_name,
    
    COUNT(DISTINCT f.entity_key) as total_entities_assessed,
    
    -- Distribution counts
    COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') as critical_count,
    COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') as high_count,
    COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') as medium_count,
    COUNT(*) FILTER (WHERE f.risk_level = 'LOW') as low_count,
    
    -- Distribution percentages
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') / COUNT(*), 1) as pct_critical,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') / COUNT(*), 1) as pct_high,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') / COUNT(*), 1) as pct_medium,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.risk_level = 'LOW') / COUNT(*), 1) as pct_low,
    
    -- Average scores
    ROUND(AVG(f.overall_risk_score), 1) as avg_risk_score,
    ROUND(AVG(f.likelihood_score), 1) as avg_likelihood,
    ROUND(AVG(f.impact_score), 1) as avg_impact,
    
    -- Score changes from previous month
    ROUND(AVG(f.overall_risk_score), 1) - LAG(ROUND(AVG(f.overall_risk_score), 1)) OVER (
        PARTITION BY d.domain_key
        ORDER BY dt.year_number, dt.month_number
    ) as mom_risk_change

FROM fact_risk_assessment f
JOIN dim_date dt ON f.assessment_date_key = dt.date_key
JOIN dim_risk_domain d ON f.domain_key = d.domain_key

WHERE dt.date_actual >= CURRENT_DATE - INTERVAL '12 months'

GROUP BY 
    dt.year_number, 
    dt.month_number, 
    dt.month_name,
    d.domain_key,
    d.domain_name
    
ORDER BY 
    d.domain_name,
    dt.year_number, 
    dt.month_number;
```

**Use Case**: Stacked area chart showing risk distribution evolution

---

### Query 3: Risk Velocity Analysis (Rate of Change)

```sql
-- Identify entities with fastest changing risk scores
-- Useful for detecting rapid deterioration or improvement

WITH risk_velocity AS (
    SELECT 
        e.entity_id,
        e.entity_name,
        e.entity_type,
        d.domain_name,
        
        -- Current state
        FIRST_VALUE(f.overall_risk_score) OVER w as current_risk,
        FIRST_VALUE(f.risk_level) OVER w as current_level,
        FIRST_VALUE(dt.date_actual) OVER w as latest_assessment,
        
        -- 30 days ago
        NTH_VALUE(f.overall_risk_score, 30) OVER w as risk_30d_ago,
        
        -- Calculate velocity (points per day)
        (FIRST_VALUE(f.overall_risk_score) OVER w - 
         NTH_VALUE(f.overall_risk_score, 30) OVER w) / 30.0 as velocity_30d,
        
        -- Acceleration (change in velocity)
        ((FIRST_VALUE(f.overall_risk_score) OVER w - NTH_VALUE(f.overall_risk_score, 15) OVER w) / 15.0 -
         (NTH_VALUE(f.overall_risk_score, 15) OVER w - NTH_VALUE(f.overall_risk_score, 30) OVER w) / 15.0
        ) as acceleration_30d
        
    FROM fact_risk_assessment f
    JOIN dim_entity e ON f.entity_key = e.entity_key
    JOIN dim_date dt ON f.assessment_date_key = dt.date_key
    JOIN dim_risk_domain d ON f.domain_key = d.domain_key
    
    WHERE dt.date_actual >= CURRENT_DATE - INTERVAL '60 days'
    
    WINDOW w AS (
        PARTITION BY f.entity_key, f.domain_key
        ORDER BY f.assessment_date_key DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)

SELECT DISTINCT
    entity_id,
    entity_name,
    entity_type,
    domain_name,
    current_risk,
    current_level,
    latest_assessment,
    ROUND(velocity_30d, 2) as velocity_points_per_day,
    ROUND(acceleration_30d, 2) as acceleration,
    
    CASE 
        WHEN velocity_30d > 1.0 THEN 'RAPID_INCREASE'
        WHEN velocity_30d > 0.3 THEN 'MODERATE_INCREASE'
        WHEN velocity_30d < -1.0 THEN 'RAPID_DECREASE'
        WHEN velocity_30d < -0.3 THEN 'MODERATE_DECREASE'
        ELSE 'STABLE'
    END as velocity_category

FROM risk_velocity

WHERE current_risk IS NOT NULL

ORDER BY ABS(velocity_30d) DESC

LIMIT 50;
```

**Use Case**: Alert dashboard for entities requiring immediate attention

---

## Likelihood & Impact Decomposition

### Query 4: Likelihood vs Impact Scatter Analysis

```sql
-- Scatter plot analysis: Likelihood vs Impact
-- Identifies entities in different risk quadrants

WITH latest_scores AS (
    SELECT DISTINCT ON (e.entity_id, d.domain_code)
        e.entity_id,
        e.entity_name,
        e.entity_type,
        e.level_1 as department,
        d.domain_name,
        f.overall_risk_score,
        f.likelihood_score,
        f.impact_score,
        f.risk_level,
        dt.date_actual as assessment_date
    FROM fact_risk_assessment f
    JOIN dim_entity e ON f.entity_key = e.entity_key
    JOIN dim_risk_domain d ON f.domain_key = d.domain_key
    JOIN dim_date dt ON f.assessment_date_key = dt.date_key
    ORDER BY e.entity_id, d.domain_code, dt.date_actual DESC
)

SELECT 
    entity_id,
    entity_name,
    entity_type,
    department,
    domain_name,
    ROUND(likelihood_score, 1) as likelihood,
    ROUND(impact_score, 1) as impact,
    ROUND(overall_risk_score, 1) as risk,
    risk_level,
    
    -- Categorize into quadrants
    CASE 
        WHEN likelihood_score >= 70 AND impact_score >= 70 THEN 'HIGH_LIKELIHOOD_HIGH_IMPACT'
        WHEN likelihood_score >= 70 AND impact_score < 70 THEN 'HIGH_LIKELIHOOD_LOW_IMPACT'
        WHEN likelihood_score < 70 AND impact_score >= 70 THEN 'LOW_LIKELIHOOD_HIGH_IMPACT'
        ELSE 'LOW_LIKELIHOOD_LOW_IMPACT'
    END as risk_quadrant,
    
    -- Strategy recommendation
    CASE 
        WHEN likelihood_score >= 70 AND impact_score >= 70 THEN 'URGENT: Reduce both likelihood and impact'
        WHEN likelihood_score >= 70 AND impact_score < 70 THEN 'FOCUS: Reduce likelihood through prevention'
        WHEN likelihood_score < 70 AND impact_score >= 70 THEN 'MONITOR: Prepare impact mitigation plans'
        ELSE 'MAINTAIN: Continue monitoring'
    END as strategy_recommendation,
    
    assessment_date

FROM latest_scores

ORDER BY overall_risk_score DESC;
```

**Use Case**: 2x2 matrix visualization with strategic recommendations

---

### Query 5: Likelihood and Impact Trend Decomposition

```sql
-- Decompose risk changes into likelihood vs impact drivers
-- Answers: "Is risk increasing due to higher likelihood or impact?"

WITH monthly_scores AS (
    SELECT 
        e.entity_id,
        e.entity_name,
        d.domain_name,
        dt.year_number,
        dt.month_number,
        AVG(f.overall_risk_score) as avg_risk,
        AVG(f.likelihood_score) as avg_likelihood,
        AVG(f.impact_score) as avg_impact
    FROM fact_risk_assessment f
    JOIN dim_entity e ON f.entity_key = e.entity_key
    JOIN dim_risk_domain d ON f.domain_key = d.domain_key
    JOIN dim_date dt ON f.assessment_date_key = dt.date_key
    WHERE dt.date_actual >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY e.entity_id, e.entity_name, d.domain_name, dt.year_number, dt.month_number
),

changes AS (
    SELECT 
        entity_id,
        entity_name,
        domain_name,
        year_number,
        month_number,
        avg_risk,
        avg_likelihood,
        avg_impact,
        
        -- Month-over-month changes
        avg_risk - LAG(avg_risk) OVER w as risk_change,
        avg_likelihood - LAG(avg_likelihood) OVER w as likelihood_change,
        avg_impact - LAG(avg_impact) OVER w as impact_change,
        
        -- Contribution analysis
        CASE 
            WHEN (avg_risk - LAG(avg_risk) OVER w) != 0 THEN
                (avg_likelihood - LAG(avg_likelihood) OVER w) / 
                (avg_risk - LAG(avg_risk) OVER w) * 100
            ELSE 0
        END as pct_from_likelihood_change,
        
        CASE 
            WHEN (avg_risk - LAG(avg_risk) OVER w) != 0 THEN
                (avg_impact - LAG(avg_impact) OVER w) / 
                (avg_risk - LAG(avg_risk) OVER w) * 100
            ELSE 0
        END as pct_from_impact_change
        
    FROM monthly_scores
    WINDOW w AS (PARTITION BY entity_id, domain_name ORDER BY year_number, month_number)
)

SELECT 
    entity_id,
    entity_name,
    domain_name,
    TO_DATE(year_number || '-' || LPAD(month_number::TEXT, 2, '0') || '-01', 'YYYY-MM-DD') as month,
    ROUND(avg_risk, 1) as risk_score,
    ROUND(avg_likelihood, 1) as likelihood_score,
    ROUND(avg_impact, 1) as impact_score,
    ROUND(risk_change, 1) as risk_change,
    ROUND(likelihood_change, 1) as likelihood_change,
    ROUND(impact_change, 1) as impact_change,
    ROUND(pct_from_likelihood_change, 1) as pct_driven_by_likelihood,
    ROUND(pct_from_impact_change, 1) as pct_driven_by_impact,
    
    -- Primary driver
    CASE 
        WHEN ABS(likelihood_change) > ABS(impact_change) THEN 'Likelihood'
        WHEN ABS(impact_change) > ABS(likelihood_change) THEN 'Impact'
        ELSE 'Both Equal'
    END as primary_driver

FROM changes

WHERE risk_change IS NOT NULL

ORDER BY entity_id, domain_name, year_number, month_number DESC;
```

**Use Case**: Waterfall charts showing risk decomposition

---

## Survival Analysis Queries

### Query 6: Kaplan-Meier Survival Function

```sql
-- Calculate survival probabilities at different time points
-- Shows what % of high-risk entities avoid the negative event

WITH survival_data AS (
    SELECT 
        survival_time_days,
        event_occurred::INTEGER as event,
        COUNT(*) as n
    FROM fact_survival_events s
    JOIN dim_risk_domain d ON s.domain_key = d.domain_key
    WHERE d.domain_name = 'Employee Attrition'
      AND s.cohort_month >= '2024-01-01'
    GROUP BY survival_time_days, event_occurred
),

-- Calculate survival function
km_calculation AS (
    SELECT 
        survival_time_days as time_point,
        SUM(event * n) as events_at_time,
        SUM(n) as at_risk_at_time,
        
        -- Cumulative survival
        EXP(SUM(LN(1.0 - (SUM(event * n) OVER (ORDER BY survival_time_days) * 1.0 / 
                          SUM(SUM(n)) OVER (ORDER BY survival_time_days))))) as survival_probability
        
    FROM survival_data
    GROUP BY survival_time_days
)

SELECT 
    time_point as days,
    ROUND(survival_probability * 100, 2) as survival_pct,
    events_at_time,
    at_risk_at_time,
    
    -- Key milestones
    CASE 
        WHEN time_point = 30 THEN '30-day'
        WHEN time_point = 60 THEN '60-day'
        WHEN time_point = 90 THEN '90-day'
        WHEN time_point = 180 THEN '6-month'
        WHEN time_point = 365 THEN '1-year'
    END as milestone

FROM km_calculation

WHERE time_point IN (30, 60, 90, 180, 365)
   OR time_point % 7 = 0  -- Weekly intervals

ORDER BY time_point;
```

**Use Case**: Survival curve visualization

---

### Query 7: Median Time-to-Event by Risk Score Bucket

```sql
-- Calculate median survival time for different initial risk score levels
-- Validates that higher risk scores predict faster events

WITH risk_buckets AS (
    SELECT 
        s.survival_time_days,
        s.event_occurred,
        s.risk_score_at_entry,
        
        CASE 
            WHEN s.risk_score_at_entry >= 80 THEN '80-100 (Critical)'
            WHEN s.risk_score_at_entry >= 60 THEN '60-79 (High)'
            WHEN s.risk_score_at_entry >= 40 THEN '40-59 (Medium)'
            ELSE '0-39 (Low)'
        END as entry_risk_bucket
        
    FROM fact_survival_events s
    JOIN dim_risk_domain d ON s.domain_key = d.domain_key
    WHERE d.domain_name = 'Employee Attrition'
)

SELECT 
    entry_risk_bucket,
    COUNT(*) as cohort_size,
    SUM(event_occurred::INTEGER) as events_occurred,
    ROUND(100.0 * SUM(event_occurred::INTEGER) / COUNT(*), 1) as event_rate_pct,
    
    -- Median survival time (50th percentile)
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY survival_time_days) as median_days_to_event,
    
    -- 25th and 75th percentiles
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY survival_time_days) as p25_days,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY survival_time_days) as p75_days,
    
    -- Among those who had event
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY CASE WHEN event_occurred THEN survival_time_days END
    ) as median_days_to_event_when_occurred

FROM risk_buckets

GROUP BY entry_risk_bucket

ORDER BY 
    CASE entry_risk_bucket
        WHEN '80-100 (Critical)' THEN 1
        WHEN '60-79 (High)' THEN 2
        WHEN '40-59 (Medium)' THEN 3
        ELSE 4
    END;
```

**Use Case**: Validate risk score calibration

---

### Query 8: Survival by Risk Trajectory (Increasing vs Stable vs Decreasing)

```sql
-- Compare survival between entities with different risk trends
-- Tests if intervening to reduce risk actually extends survival

SELECT 
    s.risk_trend,
    COUNT(*) as cohort_size,
    
    -- Event statistics
    SUM(s.event_occurred::INTEGER) as events,
    ROUND(100.0 * SUM(s.event_occurred::INTEGER) / COUNT(*), 1) as event_rate_pct,
    
    -- Survival times
    ROUND(AVG(s.survival_time_days), 1) as avg_survival_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY s.survival_time_days) as median_survival_days,
    
    -- Risk scores
    ROUND(AVG(s.risk_score_at_entry), 1) as avg_entry_risk,
    ROUND(AVG(s.peak_risk_score), 1) as avg_peak_risk,
    
    -- Intervention effectiveness
    SUM(CASE WHEN s.intervention_applied THEN 1 ELSE 0 END) as interventions_count,
    ROUND(AVG(CASE WHEN s.intervention_applied THEN s.survival_time_days END), 1) as avg_survival_with_intervention

FROM fact_survival_events s
JOIN dim_risk_domain d ON s.domain_key = d.domain_key

WHERE d.domain_name = 'Employee Attrition'
  AND s.cohort_month >= '2024-01-01'

GROUP BY s.risk_trend

ORDER BY median_survival_days DESC;
```

**Use Case**: Demonstrate ROI of risk reduction interventions

---

## Cohort Analysis

### Query 9: Monthly Cohort Retention Analysis

```sql
-- Cohort analysis showing retention rates over time
-- Classic retention table: rows = cohorts, columns = time periods

WITH cohorts AS (
    -- Define cohorts by month of entry
    SELECT 
        s.cohort_month,
        s.entity_key,
        s.entry_date,
        s.exit_date,
        s.event_occurred,
        s.survival_time_days
    FROM fact_survival_events s
    JOIN dim_risk_domain d ON s.domain_key = d.domain_key
    WHERE d.domain_name = 'Employee Attrition'
      AND s.cohort_month >= '2024-01-01'
),

retention_matrix AS (
    SELECT 
        cohort_month,
        COUNT(DISTINCT entity_key) as cohort_size,
        
        -- Retention at different time points
        COUNT(DISTINCT CASE 
            WHEN survival_time_days >= 30 AND (NOT event_occurred OR exit_date > entry_date + INTERVAL '30 days')
            THEN entity_key 
        END) as retained_30d,
        
        COUNT(DISTINCT CASE 
            WHEN survival_time_days >= 60 AND (NOT event_occurred OR exit_date > entry_date + INTERVAL '60 days')
            THEN entity_key 
        END) as retained_60d,
        
        COUNT(DISTINCT CASE 
            WHEN survival_time_days >= 90 AND (NOT event_occurred OR exit_date > entry_date + INTERVAL '90 days')
            THEN entity_key 
        END) as retained_90d,
        
        COUNT(DISTINCT CASE 
            WHEN survival_time_days >= 180 AND (NOT event_occurred OR exit_date > entry_date + INTERVAL '180 days')
            THEN entity_key 
        END) as retained_180d,
        
        COUNT(DISTINCT CASE 
            WHEN survival_time_days >= 365 AND (NOT event_occurred OR exit_date > entry_date + INTERVAL '365 days')
            THEN entity_key 
        END) as retained_365d
        
    FROM cohorts
    GROUP BY cohort_month
)

SELECT 
    cohort_month,
    cohort_size,
    
    -- Absolute retention
    retained_30d,
    retained_60d,
    retained_90d,
    retained_180d,
    retained_365d,
    
    -- Retention rates (%)
    ROUND(100.0 * retained_30d / cohort_size, 1) as retention_rate_30d,
    ROUND(100.0 * retained_60d / cohort_size, 1) as retention_rate_60d,
    ROUND(100.0 * retained_90d / cohort_size, 1) as retention_rate_90d,
    ROUND(100.0 * retained_180d / cohort_size, 1) as retention_rate_180d,
    ROUND(100.0 * retained_365d / cohort_size, 1) as retention_rate_365d

FROM retention_matrix

ORDER BY cohort_month DESC;
```

**Use Case**: Cohort retention table (heatmap visualization)

---

## Risk Driver Analysis

### Query 10: Top Risk Drivers Across Population

```sql
-- Identify which factors contribute most to overall risk
-- Aggregated across all entities

SELECT 
    rf.factor_name,
    rf.factor_category,
    d.domain_name,
    
    COUNT(DISTINCT frd.assessment_key) as assessments_count,
    
    -- Average contribution
    ROUND(AVG(frd.contribution_percentage), 1) as avg_contribution_pct,
    ROUND(AVG(frd.weighted_score), 1) as avg_weighted_score,
    
    -- How often is this a primary driver (top 3)?
    SUM(CASE WHEN frd.is_primary_driver THEN 1 ELSE 0 END) as times_primary_driver,
    ROUND(100.0 * SUM(CASE WHEN frd.is_primary_driver THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_primary_driver,
    
    -- Typical values
    ROUND(AVG(frd.raw_value), 2) as avg_raw_value,
    ROUND(STDDEV(frd.raw_value), 2) as stddev_raw_value

FROM fact_risk_factor_detail frd
JOIN dim_risk_factor rf ON frd.factor_key = rf.factor_key
JOIN fact_risk_assessment fra ON frd.assessment_key = fra.assessment_key
JOIN dim_risk_domain d ON fra.domain_key = d.domain_key
JOIN dim_date dt ON fra.assessment_date_key = dt.date_key

WHERE dt.date_actual >= CURRENT_DATE - INTERVAL '30 days'
  AND fra.risk_level IN ('CRITICAL', 'HIGH')  -- Focus on high-risk cases

GROUP BY 
    rf.factor_key,
    rf.factor_name,
    rf.factor_category,
    d.domain_name

ORDER BY avg_contribution_pct DESC

LIMIT 20;
```

**Use Case**: Bar chart of top risk drivers

---

### Query 11: Risk Driver Changes Over Time

```sql
-- Track how importance of different risk factors changes over time
-- Useful for detecting emerging risk patterns

WITH monthly_drivers AS (
    SELECT 
        dt.year_number,
        dt.month_number,
        rf.factor_name,
        d.domain_name,
        AVG(frd.contribution_percentage) as avg_contribution,
        COUNT(*) as sample_size
    FROM fact_risk_factor_detail frd
    JOIN dim_risk_factor rf ON frd.factor_key = rf.factor_key
    JOIN fact_risk_assessment fra ON frd.assessment_key = fra.assessment_key
    JOIN dim_risk_domain d ON fra.domain_key = d.domain_key
    JOIN dim_date dt ON fra.assessment_date_key = dt.date_key
    WHERE dt.date_actual >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY dt.year_number, dt.month_number, rf.factor_name, d.domain_name
)

SELECT 
    TO_DATE(year_number || '-' || LPAD(month_number::TEXT, 2, '0') || '-01', 'YYYY-MM-DD') as month,
    domain_name,
    factor_name,
    ROUND(avg_contribution, 1) as contribution_pct,
    sample_size,
    
    -- Change from previous month
    ROUND(avg_contribution - LAG(avg_contribution) OVER (
        PARTITION BY factor_name, domain_name
        ORDER BY year_number, month_number
    ), 1) as mom_change,
    
    -- Rank within domain for this month
    RANK() OVER (
        PARTITION BY year_number, month_number, domain_name
        ORDER BY avg_contribution DESC
    ) as importance_rank

FROM monthly_drivers

ORDER BY domain_name, year_number, month_number, avg_contribution DESC;
```

**Use Case**: Line chart showing factor importance evolution

---

## Executive Dashboards

### Query 12: Executive Summary - Current Risk Posture

```sql
-- Single-page executive summary of current risk state
-- Suitable for CEO/Board dashboard

WITH current_snapshot AS (
    SELECT 
        d.domain_name,
        COUNT(DISTINCT e.entity_key) as total_entities,
        
        -- Risk distribution
        COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') as critical,
        COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') as high,
        COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') as medium,
        COUNT(*) FILTER (WHERE f.risk_level = 'LOW') as low,
        
        -- Average scores
        AVG(f.overall_risk_score) as avg_risk,
        AVG(f.likelihood_score) as avg_likelihood,
        AVG(f.impact_score) as avg_impact,
        
        -- Trends (vs 30 days ago)
        AVG(f.risk_score_change) as avg_30d_change,
        COUNT(*) FILTER (WHERE f.risk_level_change = 'INCREASED') as deteriorating,
        COUNT(*) FILTER (WHERE f.risk_level_change = 'DECREASED') as improving
        
    FROM fact_risk_assessment f
    JOIN dim_entity e ON f.entity_key = e.entity_key
    JOIN dim_risk_domain d ON f.domain_key = d.domain_key
    JOIN dim_date dt ON f.assessment_date_key = dt.date_key
    
    WHERE dt.date_actual = CURRENT_DATE - INTERVAL '1 day'  -- Latest available
    
    GROUP BY d.domain_key, d.domain_name
)

SELECT 
    domain_name as "Risk Domain",
    total_entities as "Entities Assessed",
    
    -- Risk counts
    critical as "Critical",
    high as "High",
    medium as "Medium",
    low as "Low",
    
    -- Percentages
    ROUND(100.0 * (critical + high) / total_entities, 1) || '%' as "% Critical+High",
    
    -- Scores
    ROUND(avg_risk, 1) as "Avg Risk Score",
    ROUND(avg_likelihood, 1) as "Avg Likelihood",
    ROUND(avg_impact, 1) as "Avg Impact",
    
    -- Trend indicators
    CASE 
        WHEN avg_30d_change > 2 THEN '↑ INCREASING'
        WHEN avg_30d_change < -2 THEN '↓ DECREASING'
        ELSE '→ STABLE'
    END as "30-Day Trend",
    
    deteriorating as "Deteriorating",
    improving as "Improving",
    
    -- Status
    CASE 
        WHEN critical > 0 THEN '🔴 IMMEDIATE ACTION REQUIRED'
        WHEN high > total_entities * 0.2 THEN '🟡 ELEVATED RISK'
        ELSE '🟢 WITHIN TOLERANCE'
    END as "Status"

FROM current_snapshot

ORDER BY (critical + high) DESC;
```

**Use Case**: Executive summary table

---

These queries form the foundation for comprehensive risk analytics. Next, I'll create visualization examples and a complete workflow guide.

Would you like me to continue with:
1. Visualization code (Python/Plotly) for these queries?
2. Complete end-to-end workflow (from data ingestion to dashboard)?
3. Advanced predictive analytics queries?
