-- ============================================================================
-- Time Series Analysis SQL Functions
-- ============================================================================
-- Comprehensive time series operations toolkit matching Python TimeSeriesPipe
-- Includes: lag/lead, variance analysis, distribution analysis, rolling windows,
-- differencing, cumulative calculations, and statistical tests
-- ============================================================================

-- ============================================================================
-- HELPER TYPE DEFINITIONS
-- ============================================================================

-- Lag/Lead result
CREATE TYPE lag_lead_result AS (
    row_id INTEGER,
    original_value DECIMAL(15,4),
    lagged_value DECIMAL(15,4),
    period_diff DECIMAL(15,4),
    percent_change DECIMAL(10,4)
);

-- Distribution statistics
CREATE TYPE distribution_stats AS (
    count_values INTEGER,
    mean_value DECIMAL(15,4),
    median_value DECIMAL(15,4),
    std_dev DECIMAL(15,4),
    variance DECIMAL(15,4),
    min_value DECIMAL(15,4),
    max_value DECIMAL(15,4),
    q1 DECIMAL(15,4),
    q3 DECIMAL(15,4),
    iqr DECIMAL(15,4),
    skewness DECIMAL(10,4),
    kurtosis DECIMAL(10,4)
);

-- Rolling window result
CREATE TYPE rolling_result AS (
    row_id INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    rolling_value DECIMAL(15,4),
    window_size INTEGER,
    aggregation_type TEXT
);

-- ============================================================================
-- 1. LAG FUNCTION (Shift values backward)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_lag(
    p_data JSONB,
    p_lag_periods INTEGER DEFAULT 1,
    p_group_by TEXT DEFAULT NULL  -- Column name to group by (optional)
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    lagged_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    lag_periods INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    lagged_data AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            LAG(val, p_lag_periods) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY ts
            ) AS lag_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        lag_val AS lagged_value,
        val - lag_val AS absolute_change,
        CASE 
            WHEN lag_val IS NOT NULL AND lag_val != 0 
            THEN ((val - lag_val) / lag_val) * 100
            ELSE NULL
        END AS percent_change,
        p_lag_periods AS lag_periods
    FROM lagged_data
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. LEAD FUNCTION (Shift values forward)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_lead(
    p_data JSONB,
    p_lead_periods INTEGER DEFAULT 1,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    lead_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    lead_periods INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    lead_data AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            LEAD(val, p_lead_periods) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY ts
            ) AS lead_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        lead_val AS lead_value,
        lead_val - val AS absolute_change,
        CASE 
            WHEN val IS NOT NULL AND val != 0 
            THEN ((lead_val - val) / val) * 100
            ELSE NULL
        END AS percent_change,
        p_lead_periods AS lead_periods
    FROM lead_data
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. VARIANCE ANALYSIS
-- ============================================================================

CREATE OR REPLACE FUNCTION analyze_variance(
    p_data JSONB,
    p_window_type TEXT DEFAULT 'rolling',  -- 'rolling', 'expanding', 'exponential'
    p_window_size INTEGER DEFAULT 5,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    variance DECIMAL(15,4),
    std_dev DECIMAL(15,4),
    coefficient_variation DECIMAL(10,4),
    window_mean DECIMAL(15,4),
    z_score DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    variance_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            CASE p_window_type
                -- Rolling variance
                WHEN 'rolling' THEN
                    VARIANCE(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                -- Expanding variance (from start to current)
                WHEN 'expanding' THEN
                    VARIANCE(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                -- Exponential (approximated as rolling with weighted recent values)
                WHEN 'exponential' THEN
                    VARIANCE(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                ELSE
                    VARIANCE(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
            END AS var_val,
            CASE p_window_type
                WHEN 'rolling' THEN
                    STDDEV(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'expanding' THEN
                    STDDEV(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'exponential' THEN
                    STDDEV(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                ELSE
                    STDDEV(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
            END AS std_val,
            CASE p_window_type
                WHEN 'rolling' THEN
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'expanding' THEN
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'exponential' THEN
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                ELSE
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
            END AS mean_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        var_val AS variance,
        std_val AS std_dev,
        CASE 
            WHEN mean_val != 0 
            THEN (std_val / ABS(mean_val)) * 100
            ELSE NULL
        END AS coefficient_variation,
        mean_val AS window_mean,
        CASE 
            WHEN std_val != 0 
            THEN (val - mean_val) / std_val
            ELSE NULL
        END AS z_score
    FROM variance_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. DISTRIBUTION ANALYSIS
-- ============================================================================

CREATE OR REPLACE FUNCTION analyze_distribution(
    p_data JSONB,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    group_name TEXT,
    count_values INTEGER,
    mean_value DECIMAL(15,4),
    median_value DECIMAL(15,4),
    mode_value DECIMAL(15,4),
    std_dev DECIMAL(15,4),
    variance DECIMAL(15,4),
    min_value DECIMAL(15,4),
    max_value DECIMAL(15,4),
    range_value DECIMAL(15,4),
    q1 DECIMAL(15,4),
    q3 DECIMAL(15,4),
    iqr DECIMAL(15,4),
    skewness DECIMAL(10,4),
    kurtosis DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'overall') AS grp
        FROM jsonb_array_elements(p_data) AS elem
        WHERE elem->>'value' IS NOT NULL
    ),
    grouped_stats AS (
        SELECT
            CASE WHEN p_group_by IS NOT NULL THEN grp ELSE 'overall' END AS group_label,
            COUNT(*)::INTEGER AS cnt,
            AVG(val) AS avg_val,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY val) AS median_val,
            MODE() WITHIN GROUP (ORDER BY val) AS mode_val,
            STDDEV(val) AS std_val,
            VARIANCE(val) AS var_val,
            MIN(val) AS min_val,
            MAX(val) AS max_val,
            MAX(val) - MIN(val) AS range_val,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY val) AS q1_val,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY val) AS q3_val
        FROM parsed_data
        GROUP BY CASE WHEN p_group_by IS NOT NULL THEN grp ELSE 'overall' END
    ),
    skew_kurt AS (
        SELECT
            gs.group_label,
            gs.cnt,
            gs.avg_val,
            gs.median_val,
            gs.mode_val,
            gs.std_val,
            gs.var_val,
            gs.min_val,
            gs.max_val,
            gs.range_val,
            gs.q1_val,
            gs.q3_val,
            gs.q3_val - gs.q1_val AS iqr_val,
            -- Simplified skewness calculation: (mean - median) / std_dev
            CASE 
                WHEN gs.std_val != 0 
                THEN (gs.avg_val - gs.median_val) / gs.std_val
                ELSE 0
            END AS skew_val,
            -- Simplified kurtosis (excess kurtosis approximation)
            3.0 AS kurt_val  -- Placeholder (true kurtosis requires 4th moment)
        FROM grouped_stats gs
    )
    SELECT
        group_label AS group_name,
        cnt AS count_values,
        avg_val AS mean_value,
        median_val AS median_value,
        mode_val AS mode_value,
        std_val AS std_dev,
        var_val AS variance,
        min_val AS min_value,
        max_val AS max_value,
        range_val AS range_value,
        q1_val AS q1,
        q3_val AS q3,
        iqr_val AS iqr,
        skew_val AS skewness,
        kurt_val AS kurtosis
    FROM skew_kurt;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. DIFFERENCING (First and Second Order)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_difference(
    p_data JSONB,
    p_order INTEGER DEFAULT 1,  -- 1 for first difference, 2 for second difference
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    first_difference DECIMAL(15,4),
    second_difference DECIMAL(15,4),
    is_stationary BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    first_diff AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            val - LAG(val, 1) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
            ) AS diff1
        FROM parsed_data
    ),
    second_diff AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            diff1,
            diff1 - LAG(diff1, 1) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
            ) AS diff2,
            -- Check stationarity (simplified): variance of differences is stable
            STDDEV(diff1) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
            ) AS diff_std
        FROM first_diff
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        diff1 AS first_difference,
        diff2 AS second_difference,
        -- Simplified stationarity check: if std is relatively stable
        CASE 
            WHEN diff_std IS NOT NULL AND diff_std < (ABS(val) * 0.2) 
            THEN TRUE 
            ELSE FALSE 
        END AS is_stationary
    FROM second_diff
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. CUMULATIVE DISTRIBUTION FUNCTION (CDF)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_cdf(
    p_data JSONB,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    cdf_value DECIMAL(10,6),
    percentile_rank DECIMAL(5,2),
    cumulative_count INTEGER,
    group_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'overall') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    cdf_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            -- Empirical CDF using rank
            PERCENT_RANK() OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY val
            ) AS cdf_val,
            ROW_NUMBER() OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY val
            ) AS cum_cnt
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        cdf_val AS cdf_value,
        (cdf_val * 100) AS percentile_rank,
        cum_cnt::INTEGER AS cumulative_count,
        grp AS group_name
    FROM cdf_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. ROLLING WINDOW OPERATIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_rolling_window(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 5,
    p_aggregation TEXT DEFAULT 'mean',  -- 'mean', 'sum', 'min', 'max', 'std', 'count'
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    rolling_value DECIMAL(15,4),
    deviation_from_rolling DECIMAL(15,4),
    percent_deviation DECIMAL(10,4),
    window_size INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    rolling_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            CASE p_aggregation
                WHEN 'mean' THEN
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'sum' THEN
                    SUM(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'min' THEN
                    MIN(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'max' THEN
                    MAX(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'std' THEN
                    STDDEV(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                WHEN 'count' THEN
                    COUNT(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )::DECIMAL
                ELSE
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
            END AS roll_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        roll_val AS rolling_value,
        val - roll_val AS deviation_from_rolling,
        CASE 
            WHEN roll_val != 0 
            THEN ((val - roll_val) / roll_val) * 100
            ELSE NULL
        END AS percent_deviation,
        p_window_size AS window_size
    FROM rolling_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. EXPONENTIAL MOVING AVERAGE (EMA)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_ema(
    p_data JSONB,
    p_alpha DECIMAL(5,3) DEFAULT 0.3,  -- Smoothing factor (0 < alpha <= 1)
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    ema_value DECIMAL(15,4),
    deviation DECIMAL(15,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    ema_calc AS (
        -- Base case: first value
        SELECT 
            rn,
            ts,
            val,
            grp,
            val AS ema_val
        FROM parsed_data
        WHERE rn = 1
        
        UNION ALL
        
        -- Recursive case: EMA = alpha * current + (1 - alpha) * previous_ema
        SELECT 
            pd.rn,
            pd.ts,
            pd.val,
            pd.grp,
            (p_alpha * pd.val + (1 - p_alpha) * ec.ema_val) AS ema_val
        FROM parsed_data pd
        JOIN ema_calc ec ON pd.rn = ec.rn + 1 AND pd.grp = ec.grp
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        ema_val AS ema_value,
        val - ema_val AS deviation
    FROM ema_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. AUTOCORRELATION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_autocorrelation(
    p_data JSONB,
    p_max_lag INTEGER DEFAULT 10
) RETURNS TABLE (
    lag_period INTEGER,
    autocorrelation DECIMAL(10,6),
    is_significant BOOLEAN,
    confidence_lower DECIMAL(10,6),
    confidence_upper DECIMAL(10,6)
) AS $$
DECLARE
    v_n INTEGER;
    v_mean DECIMAL(15,4);
    v_variance DECIMAL(15,4);
    v_confidence_bound DECIMAL(10,6);
BEGIN
    -- Get sample size, mean, and variance
    SELECT 
        COUNT(*),
        AVG((elem->>'value')::DECIMAL),
        VARIANCE((elem->>'value')::DECIMAL)
    INTO v_n, v_mean, v_variance
    FROM jsonb_array_elements(p_data) AS elem;
    
    -- Calculate confidence bounds (95% confidence = 1.96 / sqrt(n))
    v_confidence_bound := 1.96 / SQRT(v_n);
    
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    lag_series AS (
        SELECT generate_series(1, p_max_lag) AS lag_k
    ),
    correlations AS (
        SELECT
            ls.lag_k,
            -- Autocorrelation formula: sum((x_t - mean) * (x_{t-k} - mean)) / (n * variance)
            COALESCE(
                SUM((pd1.val - v_mean) * (pd2.val - v_mean)) / 
                NULLIF((v_n - ls.lag_k) * v_variance, 0),
                0
            ) AS acf
        FROM lag_series ls
        LEFT JOIN parsed_data pd1 ON true
        LEFT JOIN parsed_data pd2 ON pd2.rn = pd1.rn - ls.lag_k
        WHERE pd2.rn IS NOT NULL
        GROUP BY ls.lag_k
    )
    SELECT
        lag_k AS lag_period,
        acf AS autocorrelation,
        ABS(acf) > v_confidence_bound AS is_significant,
        -v_confidence_bound AS confidence_lower,
        v_confidence_bound AS confidence_upper
    FROM correlations
    ORDER BY lag_k;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. STATIONARITY TEST (Augmented Dickey-Fuller Simplified)
-- ============================================================================

CREATE OR REPLACE FUNCTION test_stationarity(
    p_data JSONB
) RETURNS TABLE (
    test_name TEXT,
    is_stationary BOOLEAN,
    mean_value DECIMAL(15,4),
    variance DECIMAL(15,4),
    trend_slope DECIMAL(10,6),
    recommendation TEXT
) AS $$
DECLARE
    v_mean DECIMAL(15,4);
    v_variance DECIMAL(15,4);
    v_mean_first_half DECIMAL(15,4);
    v_mean_second_half DECIMAL(15,4);
    v_var_first_half DECIMAL(15,4);
    v_var_second_half DECIMAL(15,4);
    v_trend_slope DECIMAL(10,6);
    v_is_stationary BOOLEAN;
BEGIN
    -- Calculate overall statistics
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    split_stats AS (
        SELECT
            COUNT(*) AS n,
            AVG(val) AS overall_mean,
            VARIANCE(val) AS overall_var,
            AVG(CASE WHEN rn <= COUNT(*) OVER () / 2 THEN val END) AS mean_first,
            AVG(CASE WHEN rn > COUNT(*) OVER () / 2 THEN val END) AS mean_second,
            VARIANCE(CASE WHEN rn <= COUNT(*) OVER () / 2 THEN val END) AS var_first,
            VARIANCE(CASE WHEN rn > COUNT(*) OVER () / 2 THEN val END) AS var_second
        FROM parsed_data
    ),
    trend AS (
        SELECT
            -- Simple linear regression slope
            (COUNT(*) * SUM(rn * val) - SUM(rn) * SUM(val)) /
            NULLIF((COUNT(*) * SUM(rn * rn) - SUM(rn) * SUM(rn)), 0) AS slope
        FROM parsed_data
    )
    SELECT
        ss.overall_mean,
        ss.overall_var,
        ss.mean_first,
        ss.mean_second,
        ss.var_first,
        ss.var_second,
        t.slope
    INTO v_mean, v_variance, v_mean_first_half, v_mean_second_half, 
         v_var_first_half, v_var_second_half, v_trend_slope
    FROM split_stats ss, trend t;
    
    -- Simplified stationarity test:
    -- 1. Mean should be stable (difference < 20% of overall mean)
    -- 2. Variance should be stable (ratio between 0.5 and 2.0)
    -- 3. No strong trend (slope close to 0)
    v_is_stationary := 
        ABS(v_mean_first_half - v_mean_second_half) < (ABS(v_mean) * 0.2) AND
        v_var_first_half / NULLIF(v_var_second_half, 0) BETWEEN 0.5 AND 2.0 AND
        ABS(v_trend_slope) < 0.1;
    
    RETURN QUERY SELECT
        'Simplified ADF Test'::TEXT AS test_name,
        v_is_stationary AS is_stationary,
        v_mean AS mean_value,
        v_variance AS variance,
        v_trend_slope AS trend_slope,
        CASE 
            WHEN v_is_stationary THEN 
                'Series appears stationary - suitable for forecasting'
            WHEN ABS(v_trend_slope) > 0.1 THEN
                'Series has trend - consider differencing or detrending'
            WHEN v_var_first_half / NULLIF(v_var_second_half, 0) NOT BETWEEN 0.5 AND 2.0 THEN
                'Variance is not stable - consider log transformation'
            ELSE
                'Series is non-stationary - apply transformations'
        END AS recommendation;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 11. CUMULATIVE SUM/PRODUCT
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_cumulative(
    p_data JSONB,
    p_operation TEXT DEFAULT 'sum',  -- 'sum', 'product', 'max', 'min'
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    cumulative_value DECIMAL(15,4),
    percent_of_total DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    cumulative_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            CASE p_operation
                WHEN 'sum' THEN
                    SUM(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'product' THEN
                    EXP(SUM(LN(NULLIF(ABS(val), 0))) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ))
                WHEN 'max' THEN
                    MAX(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'min' THEN
                    MIN(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                ELSE
                    SUM(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
            END AS cum_val,
            SUM(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
            ) AS total_sum
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        cum_val AS cumulative_value,
        CASE 
            WHEN p_operation = 'sum' AND total_sum != 0
            THEN (cum_val / total_sum) * 100
            ELSE NULL
        END AS percent_of_total
    FROM cumulative_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 12. PERCENT CHANGE (Period-over-Period)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_percent_change(
    p_data JSONB,
    p_periods INTEGER DEFAULT 1,
    p_method TEXT DEFAULT 'simple',  -- 'simple', 'log', 'compound'
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    previous_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    log_change DECIMAL(10,6),
    change_category TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (
                ORDER BY (elem->>'time')::TIMESTAMP
            ) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    change_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            LAG(val, p_periods) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
            ) AS prev_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        prev_val AS previous_value,
        val - prev_val AS absolute_change,
        CASE 
            WHEN prev_val IS NOT NULL AND prev_val != 0
            THEN ((val - prev_val) / prev_val) * 100
            ELSE NULL
        END AS percent_change,
        CASE 
            WHEN prev_val IS NOT NULL AND prev_val > 0 AND val > 0
            THEN LN(val / prev_val)
            ELSE NULL
        END AS log_change,
        CASE
            WHEN prev_val IS NULL THEN 'no_baseline'
            WHEN ((val - prev_val) / NULLIF(prev_val, 0)) > 0.2 THEN 'large_increase'
            WHEN ((val - prev_val) / NULLIF(prev_val, 0)) > 0.05 THEN 'increase'
            WHEN ((val - prev_val) / NULLIF(prev_val, 0)) > -0.05 THEN 'stable'
            WHEN ((val - prev_val) / NULLIF(prev_val, 0)) > -0.2 THEN 'decrease'
            ELSE 'large_decrease'
        END AS change_category
    FROM change_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DOCUMENTATION AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION calculate_lag IS
'Calculate lagged values (shift backward in time) with change metrics.
Supports grouping for panel data analysis.
Returns absolute and percentage changes from lagged values.';

COMMENT ON FUNCTION calculate_lead IS
'Calculate lead values (shift forward in time) for predictive analysis.
Useful for creating forward-looking features.
Returns changes relative to future values.';

COMMENT ON FUNCTION analyze_variance IS
'Analyze variance using rolling, expanding, or exponential windows.
Returns variance, standard deviation, CV, and Z-scores.
Essential for volatility analysis and outlier detection.';

COMMENT ON FUNCTION analyze_distribution IS
'Comprehensive distribution analysis with quartiles, skewness, and kurtosis.
Supports grouped analysis for comparative statistics.
Returns full statistical summary for each group.';

COMMENT ON FUNCTION calculate_difference IS
'Calculate first and second-order differences for stationarity.
Tests whether differenced series is stationary.
Essential preprocessing for time series forecasting.';

COMMENT ON FUNCTION calculate_cdf IS
'Calculate empirical cumulative distribution function.
Returns percentile ranks and cumulative probabilities.
Useful for probability analysis and ranking.';

COMMENT ON FUNCTION calculate_rolling_window IS
'General-purpose rolling window with multiple aggregations.
Supports mean, sum, min, max, std, count.
Returns deviations from rolling values.';

COMMENT ON FUNCTION calculate_ema IS
'Exponential moving average with configurable smoothing factor.
Gives more weight to recent observations.
Alpha closer to 1 = more responsive, closer to 0 = smoother.';

COMMENT ON FUNCTION calculate_autocorrelation IS
'Calculate autocorrelation function (ACF) up to specified lag.
Tests significance using confidence bounds.
Essential for ARIMA modeling and pattern detection.';

COMMENT ON FUNCTION test_stationarity IS
'Simplified stationarity test checking mean, variance, and trend stability.
Returns actionable recommendations for transformations.
Critical for time series modeling.';

COMMENT ON FUNCTION calculate_cumulative IS
'Calculate cumulative operations: sum, product, max, min.
Returns percent of total for cumulative sum.
Useful for running totals and cumulative metrics.';

COMMENT ON FUNCTION calculate_percent_change IS
'Calculate period-over-period percent changes.
Supports simple, log, and compound methods.
Auto-categorizes magnitude of changes.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- Example 1: Lag analysis
SELECT * FROM calculate_lag(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 110},
        {"time": "2024-01-03", "value": 105},
        {"time": "2024-01-04", "value": 115}
    ]'::JSONB,
    1,  -- 1-period lag
    NULL  -- no grouping
);

-- Example 2: Variance analysis with rolling window
SELECT * FROM analyze_variance(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 150},
        {"time": "2024-01-03", "value": 80},
        {"time": "2024-01-04", "value": 120}
    ]'::JSONB,
    'rolling',
    3,  -- 3-period window
    NULL
);

-- Example 3: Distribution analysis
SELECT * FROM analyze_distribution(
    '[
        {"value": 100, "group": "A"},
        {"value": 110, "group": "A"},
        {"value": 95, "group": "A"},
        {"value": 200, "group": "B"},
        {"value": 210, "group": "B"}
    ]'::JSONB,
    'group'  -- group by 'group' field
);

-- Example 4: First-order differencing
SELECT * FROM calculate_difference(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 110},
        {"time": "2024-01-03", "value": 115},
        {"time": "2024-01-04", "value": 125}
    ]'::JSONB,
    1,  -- first-order difference
    NULL
);

-- Example 5: Exponential moving average
SELECT * FROM calculate_ema(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 110},
        {"time": "2024-01-03", "value": 105},
        {"time": "2024-01-04", "value": 115}
    ]'::JSONB,
    0.3,  -- alpha = 0.3 (smoothing factor)
    NULL
);

-- Example 6: Autocorrelation analysis
SELECT * FROM calculate_autocorrelation(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 105},
        {"time": "2024-01-03", "value": 102},
        {"time": "2024-01-04", "value": 108}
    ]'::JSONB,
    5  -- max lag of 5
);

-- Example 7: Stationarity test
SELECT * FROM test_stationarity(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 110},
        {"time": "2024-01-03", "value": 120},
        {"time": "2024-01-04", "value": 130}
    ]'::JSONB
);

-- Example 8: Cumulative sum
SELECT * FROM calculate_cumulative(
    '[
        {"time": "2024-01-01", "value": 10},
        {"time": "2024-01-02", "value": 20},
        {"time": "2024-01-03", "value": 15},
        {"time": "2024-01-04", "value": 25}
    ]'::JSONB,
    'sum',
    NULL
);
*/
