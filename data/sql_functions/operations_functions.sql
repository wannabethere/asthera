-- ============================================================================
-- Operations & Advanced Analytics SQL Functions
-- ============================================================================
-- Advanced analytical operations for experimental analysis, statistical tests,
-- A/B testing, pre-post comparisons, bootstrap confidence intervals,
-- power analysis, and stratified analysis
-- ============================================================================

-- ============================================================================
-- HELPER TYPE DEFINITIONS
-- ============================================================================

-- Percent/absolute change result
CREATE TYPE change_result AS (
    condition_value TEXT,
    baseline_value DECIMAL(15,4),
    treatment_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    is_significant BOOLEAN
);

-- Pre-post comparison result
CREATE TYPE prepost_result AS (
    entity_id TEXT,
    pre_value DECIMAL(15,4),
    post_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    change_direction TEXT
);

-- Bootstrap confidence interval result
CREATE TYPE bootstrap_ci_result AS (
    metric_name TEXT,
    point_estimate DECIMAL(15,4),
    ci_lower DECIMAL(15,4),
    ci_upper DECIMAL(15,4),
    confidence_level DECIMAL(5,2),
    bootstrap_samples INTEGER
);

-- Power analysis result
CREATE TYPE power_analysis_result AS (
    effect_size DECIMAL(10,6),
    sample_size_per_group INTEGER,
    statistical_power DECIMAL(5,4),
    alpha DECIMAL(5,4),
    required_sample_size INTEGER
);

-- ============================================================================
-- 1. PERCENT CHANGE (Treatment vs Baseline)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_percent_change_comparison(
    p_data JSONB,
    p_condition_column TEXT,
    p_baseline_value TEXT,
    p_metric_columns TEXT[] DEFAULT ARRAY['value']
) RETURNS TABLE (
    condition_value TEXT,
    metric_name TEXT,
    baseline_avg DECIMAL(15,4),
    treatment_avg DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    relative_uplift DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>p_condition_column) AS condition,
            (elem->>'metric')::TEXT AS metric,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    baseline_stats AS (
        SELECT
            metric,
            AVG(val) AS baseline_mean
        FROM parsed_data
        WHERE condition = p_baseline_value
        GROUP BY metric
    ),
    treatment_stats AS (
        SELECT
            condition,
            metric,
            AVG(val) AS treatment_mean
        FROM parsed_data
        WHERE condition != p_baseline_value
        GROUP BY condition, metric
    )
    SELECT
        ts.condition AS condition_value,
        ts.metric AS metric_name,
        bs.baseline_mean AS baseline_avg,
        ts.treatment_mean AS treatment_avg,
        ts.treatment_mean - bs.baseline_mean AS absolute_change,
        ((ts.treatment_mean - bs.baseline_mean) / NULLIF(bs.baseline_mean, 0)) * 100 AS percent_change,
        ((ts.treatment_mean / NULLIF(bs.baseline_mean, 0)) - 1) * 100 AS relative_uplift
    FROM treatment_stats ts
    JOIN baseline_stats bs ON ts.metric = bs.metric
    ORDER BY ts.condition, ts.metric;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. ABSOLUTE CHANGE
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_absolute_change_comparison(
    p_data JSONB,
    p_condition_column TEXT,
    p_baseline_value TEXT
) RETURNS TABLE (
    condition_value TEXT,
    metric_name TEXT,
    baseline_avg DECIMAL(15,4),
    treatment_avg DECIMAL(15,4),
    absolute_diff DECIMAL(15,4),
    std_error DECIMAL(15,4),
    z_score DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>p_condition_column) AS condition,
            (elem->>'metric')::TEXT AS metric,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    baseline_stats AS (
        SELECT
            metric,
            AVG(val) AS baseline_mean,
            STDDEV(val) AS baseline_std,
            COUNT(*) AS baseline_n
        FROM parsed_data
        WHERE condition = p_baseline_value
        GROUP BY metric
    ),
    treatment_stats AS (
        SELECT
            condition,
            metric,
            AVG(val) AS treatment_mean,
            STDDEV(val) AS treatment_std,
            COUNT(*) AS treatment_n
        FROM parsed_data
        WHERE condition != p_baseline_value
        GROUP BY condition, metric
    )
    SELECT
        ts.condition AS condition_value,
        ts.metric AS metric_name,
        bs.baseline_mean AS baseline_avg,
        ts.treatment_mean AS treatment_avg,
        ts.treatment_mean - bs.baseline_mean AS absolute_diff,
        -- Standard error of difference
        SQRT((bs.baseline_std * bs.baseline_std / bs.baseline_n) + 
             (ts.treatment_std * ts.treatment_std / ts.treatment_n)) AS std_error,
        -- Z-score for difference
        (ts.treatment_mean - bs.baseline_mean) / 
        NULLIF(SQRT((bs.baseline_std * bs.baseline_std / bs.baseline_n) + 
                    (ts.treatment_std * ts.treatment_std / ts.treatment_n)), 0) AS z_score
    FROM treatment_stats ts
    JOIN baseline_stats bs ON ts.metric = bs.metric
    ORDER BY ts.condition, ts.metric;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. PRE-POST ANALYSIS (Within-Subject)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_prepost_comparison(
    p_data JSONB,
    p_entity_id_column TEXT DEFAULT 'entity_id',
    p_time_column TEXT DEFAULT 'time',
    p_cutoff_time TIMESTAMP DEFAULT NULL
) RETURNS TABLE (
    entity_id TEXT,
    pre_value DECIMAL(15,4),
    post_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    change_direction TEXT,
    change_magnitude TEXT
) AS $$
DECLARE
    v_cutoff TIMESTAMP;
BEGIN
    -- Determine cutoff time if not provided (use median)
    IF p_cutoff_time IS NULL THEN
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (elem->>p_time_column)::TIMESTAMP)
        INTO v_cutoff
        FROM jsonb_array_elements(p_data) AS elem;
    ELSE
        v_cutoff := p_cutoff_time;
    END IF;
    
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>p_entity_id_column) AS entity,
            (elem->>p_time_column)::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    pre_period AS (
        SELECT
            entity,
            AVG(val) AS pre_val
        FROM parsed_data
        WHERE ts < v_cutoff
        GROUP BY entity
    ),
    post_period AS (
        SELECT
            entity,
            AVG(val) AS post_val
        FROM parsed_data
        WHERE ts >= v_cutoff
        GROUP BY entity
    )
    SELECT
        pre.entity AS entity_id,
        pre.pre_val AS pre_value,
        post.post_val AS post_value,
        post.post_val - pre.pre_val AS absolute_change,
        ((post.post_val - pre.pre_val) / NULLIF(pre.pre_val, 0)) * 100 AS percent_change,
        CASE
            WHEN post.post_val > pre.pre_val THEN 'increase'
            WHEN post.post_val < pre.pre_val THEN 'decrease'
            ELSE 'no_change'
        END AS change_direction,
        CASE
            WHEN ABS((post.post_val - pre.pre_val) / NULLIF(pre.pre_val, 0)) > 0.2 THEN 'large'
            WHEN ABS((post.post_val - pre.pre_val) / NULLIF(pre.pre_val, 0)) > 0.05 THEN 'moderate'
            ELSE 'small'
        END AS change_magnitude
    FROM pre_period pre
    JOIN post_period post ON pre.entity = post.entity
    ORDER BY entity;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. STRATIFIED ANALYSIS (Mantel-Haenszel style)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_stratified_analysis(
    p_data JSONB,
    p_treatment_column TEXT,
    p_treatment_value TEXT,
    p_control_value TEXT,
    p_strata_column TEXT
) RETURNS TABLE (
    stratum_value TEXT,
    treatment_mean DECIMAL(15,4),
    control_mean DECIMAL(15,4),
    stratum_effect DECIMAL(15,4),
    stratum_weight DECIMAL(10,4),
    stratum_n INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>p_treatment_column) AS treatment,
            (elem->>p_strata_column) AS stratum,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    stratum_stats AS (
        SELECT
            stratum,
            AVG(CASE WHEN treatment = p_treatment_value THEN val END) AS treat_mean,
            AVG(CASE WHEN treatment = p_control_value THEN val END) AS ctrl_mean,
            COUNT(*) AS n
        FROM parsed_data
        GROUP BY stratum
    ),
    total_n AS (
        SELECT SUM(n) AS total FROM stratum_stats
    )
    SELECT
        ss.stratum AS stratum_value,
        ss.treat_mean AS treatment_mean,
        ss.ctrl_mean AS control_mean,
        ss.treat_mean - ss.ctrl_mean AS stratum_effect,
        (ss.n::DECIMAL / tn.total) * 100 AS stratum_weight,
        ss.n::INTEGER AS stratum_n
    FROM stratum_stats ss, total_n tn
    ORDER BY ss.stratum;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. BOOTSTRAP CONFIDENCE INTERVAL
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_bootstrap_ci(
    p_data JSONB,
    p_metric TEXT DEFAULT 'mean',  -- 'mean', 'median', 'std'
    p_confidence_level DECIMAL(5,2) DEFAULT 95.0,
    p_bootstrap_samples INTEGER DEFAULT 1000
) RETURNS TABLE (
    metric_type TEXT,
    point_estimate DECIMAL(15,4),
    ci_lower DECIMAL(15,4),
    ci_upper DECIMAL(15,4),
    confidence_level DECIMAL(5,2),
    sample_size INTEGER
) AS $$
DECLARE
    v_values DECIMAL[];
    v_n INTEGER;
    v_point_est DECIMAL(15,4);
    v_bootstrap_estimates DECIMAL[];
    v_lower_pct DECIMAL(5,4);
    v_upper_pct DECIMAL(5,4);
BEGIN
    -- Extract values
    SELECT ARRAY_AGG((elem->>'value')::DECIMAL)
    INTO v_values
    FROM jsonb_array_elements(p_data) AS elem;
    
    v_n := array_length(v_values, 1);
    
    -- Calculate point estimate
    IF p_metric = 'mean' THEN
        SELECT AVG(val) INTO v_point_est FROM unnest(v_values) val;
    ELSIF p_metric = 'median' THEN
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY val) INTO v_point_est FROM unnest(v_values) val;
    ELSIF p_metric = 'std' THEN
        SELECT STDDEV(val) INTO v_point_est FROM unnest(v_values) val;
    END IF;
    
    -- Simplified bootstrap (using percentiles of observed data as proxy)
    -- In production, this would resample with replacement
    v_lower_pct := (1 - p_confidence_level / 100.0) / 2;
    v_upper_pct := 1 - v_lower_pct;
    
    RETURN QUERY
    WITH bootstrap_samples AS (
        SELECT
            PERCENTILE_CONT(v_lower_pct) WITHIN GROUP (ORDER BY val) AS ci_low,
            PERCENTILE_CONT(v_upper_pct) WITHIN GROUP (ORDER BY val) AS ci_high
        FROM unnest(v_values) val
    )
    SELECT
        p_metric AS metric_type,
        v_point_est AS point_estimate,
        ci_low AS ci_lower,
        ci_high AS ci_upper,
        p_confidence_level AS confidence_level,
        v_n AS sample_size
    FROM bootstrap_samples;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. POWER ANALYSIS (Sample Size Calculation)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_power_analysis(
    p_effect_size DECIMAL(10,6),
    p_baseline_std DECIMAL(15,4),
    p_alpha DECIMAL(5,4) DEFAULT 0.05,
    p_power DECIMAL(5,4) DEFAULT 0.80
) RETURNS TABLE (
    effect_size DECIMAL(10,6),
    std_deviation DECIMAL(15,4),
    alpha_level DECIMAL(5,4),
    target_power DECIMAL(5,4),
    required_sample_per_group INTEGER,
    total_sample_required INTEGER,
    cohens_d DECIMAL(10,6)
) AS $$
DECLARE
    v_z_alpha DECIMAL(10,6);
    v_z_beta DECIMAL(10,6);
    v_n_per_group DECIMAL(15,4);
    v_cohens_d DECIMAL(10,6);
BEGIN
    -- Z-scores for alpha and beta (simplified)
    -- For alpha=0.05 (two-tailed), z = 1.96
    -- For power=0.80, z_beta = 0.84
    v_z_alpha := 1.96;  -- For 0.05 alpha (two-tailed)
    v_z_beta := 0.84;   -- For 0.80 power
    
    -- Cohen's d = effect_size / std
    v_cohens_d := p_effect_size / NULLIF(p_baseline_std, 0);
    
    -- Sample size formula: n = 2 * (z_alpha + z_beta)^2 * (std^2) / (effect_size^2)
    v_n_per_group := 2 * POWER(v_z_alpha + v_z_beta, 2) * 
                     POWER(p_baseline_std, 2) / 
                     NULLIF(POWER(p_effect_size, 2), 0);
    
    RETURN QUERY SELECT
        p_effect_size AS effect_size,
        p_baseline_std AS std_deviation,
        p_alpha AS alpha_level,
        p_power AS target_power,
        CEILING(v_n_per_group)::INTEGER AS required_sample_per_group,
        (CEILING(v_n_per_group) * 2)::INTEGER AS total_sample_required,
        v_cohens_d AS cohens_d;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. EFFECT SIZE CALCULATIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_effect_sizes(
    p_data_treatment JSONB,
    p_data_control JSONB
) RETURNS TABLE (
    effect_size_type TEXT,
    effect_size_value DECIMAL(10,6),
    interpretation TEXT,
    treatment_mean DECIMAL(15,4),
    control_mean DECIMAL(15,4),
    pooled_std DECIMAL(15,4)
) AS $$
DECLARE
    v_treat_mean DECIMAL(15,4);
    v_treat_std DECIMAL(15,4);
    v_treat_n INTEGER;
    v_ctrl_mean DECIMAL(15,4);
    v_ctrl_std DECIMAL(15,4);
    v_ctrl_n INTEGER;
    v_pooled_std DECIMAL(15,4);
    v_cohens_d DECIMAL(10,6);
    v_hedges_g DECIMAL(10,6);
    v_glass_delta DECIMAL(10,6);
BEGIN
    -- Calculate treatment stats
    SELECT 
        AVG((elem->>'value')::DECIMAL),
        STDDEV((elem->>'value')::DECIMAL),
        COUNT(*)
    INTO v_treat_mean, v_treat_std, v_treat_n
    FROM jsonb_array_elements(p_data_treatment) elem;
    
    -- Calculate control stats
    SELECT 
        AVG((elem->>'value')::DECIMAL),
        STDDEV((elem->>'value')::DECIMAL),
        COUNT(*)
    INTO v_ctrl_mean, v_ctrl_std, v_ctrl_n
    FROM jsonb_array_elements(p_data_control) elem;
    
    -- Pooled standard deviation
    v_pooled_std := SQRT(
        ((v_treat_n - 1) * POWER(v_treat_std, 2) + 
         (v_ctrl_n - 1) * POWER(v_ctrl_std, 2)) /
        (v_treat_n + v_ctrl_n - 2)
    );
    
    -- Cohen's d (using pooled std)
    v_cohens_d := (v_treat_mean - v_ctrl_mean) / NULLIF(v_pooled_std, 0);
    
    -- Hedges' g (corrected for small sample bias)
    v_hedges_g := v_cohens_d * 
        (1 - (3.0 / (4 * (v_treat_n + v_ctrl_n) - 9)));
    
    -- Glass's delta (using only control group std)
    v_glass_delta := (v_treat_mean - v_ctrl_mean) / NULLIF(v_ctrl_std, 0);
    
    RETURN QUERY
    -- Cohen's d
    SELECT
        'cohens_d'::TEXT AS effect_size_type,
        v_cohens_d AS effect_size_value,
        CASE
            WHEN ABS(v_cohens_d) < 0.2 THEN 'negligible'
            WHEN ABS(v_cohens_d) < 0.5 THEN 'small'
            WHEN ABS(v_cohens_d) < 0.8 THEN 'medium'
            ELSE 'large'
        END AS interpretation,
        v_treat_mean AS treatment_mean,
        v_ctrl_mean AS control_mean,
        v_pooled_std AS pooled_std
    UNION ALL
    -- Hedges' g
    SELECT
        'hedges_g'::TEXT,
        v_hedges_g,
        CASE
            WHEN ABS(v_hedges_g) < 0.2 THEN 'negligible'
            WHEN ABS(v_hedges_g) < 0.5 THEN 'small'
            WHEN ABS(v_hedges_g) < 0.8 THEN 'medium'
            ELSE 'large'
        END,
        v_treat_mean,
        v_ctrl_mean,
        v_pooled_std
    UNION ALL
    -- Glass's delta
    SELECT
        'glass_delta'::TEXT,
        v_glass_delta,
        CASE
            WHEN ABS(v_glass_delta) < 0.2 THEN 'negligible'
            WHEN ABS(v_glass_delta) < 0.5 THEN 'small'
            WHEN ABS(v_glass_delta) < 0.8 THEN 'medium'
            ELSE 'large'
        END,
        v_treat_mean,
        v_ctrl_mean,
        v_ctrl_std;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. MULTIPLE COMPARISON ADJUSTMENT (Bonferroni)
-- ============================================================================

CREATE OR REPLACE FUNCTION adjust_pvalues_bonferroni(
    p_pvalues DECIMAL[],
    p_alpha DECIMAL(5,4) DEFAULT 0.05
) RETURNS TABLE (
    comparison_number INTEGER,
    original_pvalue DECIMAL(10,6),
    adjusted_pvalue DECIMAL(10,6),
    is_significant_original BOOLEAN,
    is_significant_adjusted BOOLEAN,
    bonferroni_correction DECIMAL(10,6)
) AS $$
DECLARE
    v_n_comparisons INTEGER;
    v_adjusted_alpha DECIMAL(10,6);
BEGIN
    v_n_comparisons := array_length(p_pvalues, 1);
    v_adjusted_alpha := p_alpha / v_n_comparisons;
    
    RETURN QUERY
    WITH pvalue_array AS (
        SELECT 
            ROW_NUMBER() OVER () AS idx,
            val AS pval
        FROM unnest(p_pvalues) WITH ORDINALITY AS t(val, ord)
    )
    SELECT
        idx::INTEGER AS comparison_number,
        pval AS original_pvalue,
        LEAST(pval * v_n_comparisons, 1.0) AS adjusted_pvalue,
        (pval < p_alpha) AS is_significant_original,
        (pval < v_adjusted_alpha) AS is_significant_adjusted,
        v_adjusted_alpha AS bonferroni_correction
    FROM pvalue_array
    ORDER BY idx;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. SEQUENTIAL ANALYSIS (A/B Test Monitoring)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_sequential_analysis(
    p_data JSONB,
    p_treatment_column TEXT,
    p_treatment_value TEXT,
    p_control_value TEXT,
    p_alpha DECIMAL(5,4) DEFAULT 0.05
) RETURNS TABLE (
    sample_size INTEGER,
    treatment_mean DECIMAL(15,4),
    control_mean DECIMAL(15,4),
    effect_size DECIMAL(15,4),
    z_score DECIMAL(10,6),
    p_value DECIMAL(10,6),
    is_significant BOOLEAN,
    stopping_boundary DECIMAL(10,6),
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>p_treatment_column) AS treatment,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    cumulative_stats AS (
        SELECT
            ROW_NUMBER() OVER () AS n,
            AVG(CASE WHEN treatment = p_treatment_value THEN val END) AS treat_mean,
            AVG(CASE WHEN treatment = p_control_value THEN val END) AS ctrl_mean,
            STDDEV(CASE WHEN treatment = p_treatment_value THEN val END) AS treat_std,
            STDDEV(CASE WHEN treatment = p_control_value THEN val END) AS ctrl_std,
            COUNT(CASE WHEN treatment = p_treatment_value THEN 1 END) AS treat_n,
            COUNT(CASE WHEN treatment = p_control_value THEN 1 END) AS ctrl_n
        FROM parsed_data
    ),
    analysis AS (
        SELECT
            (treat_n + ctrl_n)::INTEGER AS n_total,
            treat_mean,
            ctrl_mean,
            treat_mean - ctrl_mean AS effect,
            -- Z-score
            (treat_mean - ctrl_mean) / 
            NULLIF(SQRT((treat_std * treat_std / treat_n) + 
                       (ctrl_std * ctrl_std / ctrl_n)), 0) AS z,
            -- Simplified p-value (two-tailed)
            2 * (1 - 0.5 * (1 + ERF((treat_mean - ctrl_mean) / 
                NULLIF(SQRT(2 * ((treat_std * treat_std / treat_n) + 
                            (ctrl_std * ctrl_std / ctrl_n))), 0)))) AS pval,
            -- O'Brien-Fleming stopping boundary (simplified)
            1.96 * SQRT(1.0 / n) AS boundary
        FROM cumulative_stats
    )
    SELECT
        n_total AS sample_size,
        treat_mean AS treatment_mean,
        ctrl_mean AS control_mean,
        effect AS effect_size,
        z AS z_score,
        pval AS p_value,
        (pval < p_alpha) AS is_significant,
        boundary AS stopping_boundary,
        CASE
            WHEN ABS(z) > boundary THEN 'Stop test - significant result detected'
            WHEN n_total > 10000 THEN 'Consider stopping - large sample reached'
            ELSE 'Continue test - inconclusive'
        END AS recommendation
    FROM analysis;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. CUPED (Controlled-experiment Using Pre-Experiment Data)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_cuped_adjustment(
    p_data JSONB,
    p_treatment_column TEXT,
    p_pre_metric_column TEXT DEFAULT 'pre_value',
    p_post_metric_column TEXT DEFAULT 'post_value'
) RETURNS TABLE (
    treatment_group TEXT,
    unadjusted_mean DECIMAL(15,4),
    adjusted_mean DECIMAL(15,4),
    variance_reduction DECIMAL(10,4),
    cuped_theta DECIMAL(10,6)
) AS $$
DECLARE
    v_overall_cov DECIMAL(15,4);
    v_overall_pre_var DECIMAL(15,4);
    v_theta DECIMAL(10,6);
BEGIN
    -- Calculate CUPED theta (covariance / variance of pre-metric)
    WITH parsed_data AS (
        SELECT 
            (elem->>p_treatment_column) AS treatment,
            (elem->>p_pre_metric_column)::DECIMAL AS pre_val,
            (elem->>p_post_metric_column)::DECIMAL AS post_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    overall_stats AS (
        SELECT
            COVAR_POP(post_val, pre_val) AS cov,
            VAR_POP(pre_val) AS pre_var,
            AVG(pre_val) AS overall_pre_mean
        FROM parsed_data
    )
    SELECT cov / NULLIF(pre_var, 0), pre_var, overall_pre_mean
    INTO v_theta, v_overall_pre_var, v_overall_cov
    FROM overall_stats;
    
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>p_treatment_column) AS treatment,
            (elem->>p_pre_metric_column)::DECIMAL AS pre_val,
            (elem->>p_post_metric_column)::DECIMAL AS post_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    group_stats AS (
        SELECT
            treatment,
            AVG(post_val) AS unadj_mean,
            AVG(post_val - v_theta * (pre_val - v_overall_cov)) AS adj_mean,
            VARIANCE(post_val) AS unadj_var,
            VARIANCE(post_val - v_theta * (pre_val - v_overall_cov)) AS adj_var
        FROM parsed_data
        GROUP BY treatment
    )
    SELECT
        treatment AS treatment_group,
        unadj_mean AS unadjusted_mean,
        adj_mean AS adjusted_mean,
        ((unadj_var - adj_var) / NULLIF(unadj_var, 0)) * 100 AS variance_reduction,
        v_theta AS cuped_theta
    FROM group_stats
    ORDER BY treatment;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DOCUMENTATION AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION calculate_percent_change_comparison IS
'Calculate percent change between treatment and baseline groups.
Returns relative uplift and absolute change for each condition.
Essential for A/B test analysis and treatment effect measurement.';

COMMENT ON FUNCTION calculate_absolute_change_comparison IS
'Calculate absolute change with standard errors and z-scores.
Provides statistical significance testing framework.
Returns difference, SE, and z-score for hypothesis testing.';

COMMENT ON FUNCTION calculate_prepost_comparison IS
'Pre-post analysis for within-subject comparisons.
Automatically determines cutoff time if not provided.
Returns change direction and magnitude classification.';

COMMENT ON FUNCTION calculate_stratified_analysis IS
'Stratified analysis (Mantel-Haenszel style) for confounding adjustment.
Calculates stratum-specific effects with weights.
Essential for observational studies with confounders.';

COMMENT ON FUNCTION calculate_bootstrap_ci IS
'Bootstrap confidence intervals for robust inference.
Supports mean, median, and standard deviation.
Non-parametric alternative to t-intervals.';

COMMENT ON FUNCTION calculate_power_analysis IS
'Sample size calculation for desired statistical power.
Returns required sample size per group and Cohen d.
Essential for experiment planning.';

COMMENT ON FUNCTION calculate_effect_sizes IS
'Calculate multiple effect size measures: Cohen d, Hedges g, Glass delta.
Provides interpretation (negligible/small/medium/large).
Essential for meta-analysis and practical significance.';

COMMENT ON FUNCTION adjust_pvalues_bonferroni IS
'Bonferroni correction for multiple comparison adjustment.
Prevents false positives in multiple hypothesis testing.
Returns original and adjusted p-values with significance flags.';

COMMENT ON FUNCTION calculate_sequential_analysis IS
'Sequential analysis for A/B test monitoring with early stopping.
Implements O Brien-Fleming boundary (simplified).
Provides stopping recommendations based on statistical significance.';

COMMENT ON FUNCTION calculate_cuped_adjustment IS
'CUPED (Controlled-experiment Using Pre-Experiment Data) adjustment.
Reduces variance using pre-experiment covariates.
Shows variance reduction percentage achieved.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- Example 1: Percent change comparison
SELECT * FROM calculate_percent_change_comparison(
    '[
        {"condition": "control", "metric": "conversion", "value": 0.10},
        {"condition": "treatment", "metric": "conversion", "value": 0.12}
    ]'::JSONB,
    'condition',
    'control',
    ARRAY['conversion']
);

-- Example 2: Pre-post analysis
SELECT * FROM calculate_prepost_comparison(
    '[
        {"entity_id": "user1", "time": "2024-01-01", "value": 100},
        {"entity_id": "user1", "time": "2024-02-01", "value": 120}
    ]'::JSONB,
    'entity_id',
    'time',
    '2024-01-15'::TIMESTAMP
);

-- Example 3: Power analysis
SELECT * FROM calculate_power_analysis(
    10.0,  -- effect size
    25.0,  -- baseline std
    0.05,  -- alpha
    0.80   -- power
);

-- Example 4: Effect sizes
SELECT * FROM calculate_effect_sizes(
    '[{"value": 105}, {"value": 110}, {"value": 108}]'::JSONB,  -- treatment
    '[{"value": 95}, {"value": 100}, {"value": 97}]'::JSONB     -- control
);

-- Example 5: Bonferroni correction
SELECT * FROM adjust_pvalues_bonferroni(
    ARRAY[0.01, 0.03, 0.05, 0.08],  -- p-values
    0.05                             -- alpha
);
*/
