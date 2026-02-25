-- ============================================================================
-- Moving Averages & Aggregations SQL Functions
-- ============================================================================
-- Comprehensive moving window operations for time series analysis
-- Includes: MA (SMA/WMA/EMA), variance, correlation, quantiles, cumulative,
-- expanding windows, time-weighted, and custom aggregations
-- ============================================================================

-- ============================================================================
-- HELPER TYPE DEFINITIONS
-- ============================================================================

-- Moving average result type
CREATE TYPE ma_detailed_result AS (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    ma_value DECIMAL(15,4),
    ma_type TEXT,
    deviation DECIMAL(15,4),
    percent_deviation DECIMAL(10,4),
    upper_band DECIMAL(15,4),
    lower_band DECIMAL(15,4)
);

-- Moving statistics result
CREATE TYPE moving_stats_result AS (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    moving_mean DECIMAL(15,4),
    moving_std DECIMAL(15,4),
    moving_var DECIMAL(15,4),
    moving_min DECIMAL(15,4),
    moving_max DECIMAL(15,4),
    moving_range DECIMAL(15,4)
);

-- ============================================================================
-- 1. SIMPLE MOVING AVERAGE (SMA)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_sma(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    sma_value DECIMAL(15,4),
    deviation DECIMAL(15,4),
    percent_deviation DECIMAL(10,4),
    upper_band DECIMAL(15,4),  -- SMA + 2*std
    lower_band DECIMAL(15,4)   -- SMA - 2*std
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    sma_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            AVG(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS sma,
            STDDEV(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS std_dev
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        sma AS sma_value,
        val - sma AS deviation,
        CASE WHEN sma != 0 THEN ((val - sma) / sma) * 100 ELSE NULL END AS percent_deviation,
        sma + (2 * std_dev) AS upper_band,
        sma - (2 * std_dev) AS lower_band
    FROM sma_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. WEIGHTED MOVING AVERAGE (WMA)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_wma(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    wma_value DECIMAL(15,4),
    deviation DECIMAL(15,4),
    percent_deviation DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    weighted_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            -- WMA: more weight to recent values
            -- Weight = position in window (1, 2, 3, ..., n)
            -- WMA = (val1*1 + val2*2 + ... + valn*n) / (1+2+...+n)
            SUM(val * rn) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) / 
            NULLIF(SUM(rn) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ), 0) AS wma
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        wma AS wma_value,
        val - wma AS deviation,
        CASE WHEN wma != 0 THEN ((val - wma) / wma) * 100 ELSE NULL END AS percent_deviation
    FROM weighted_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. MOVING VARIANCE AND STANDARD DEVIATION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_variance(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    moving_mean DECIMAL(15,4),
    moving_variance DECIMAL(15,4),
    moving_std DECIMAL(15,4),
    coefficient_variation DECIMAL(10,4),
    z_score DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
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
            AVG(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS mean_val,
            VARIANCE(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS var_val,
            STDDEV(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS std_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        mean_val AS moving_mean,
        var_val AS moving_variance,
        std_val AS moving_std,
        CASE WHEN mean_val != 0 THEN (std_val / ABS(mean_val)) * 100 ELSE NULL END AS coefficient_variation,
        CASE WHEN std_val != 0 THEN (val - mean_val) / std_val ELSE NULL END AS z_score
    FROM variance_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. MOVING QUANTILES/PERCENTILES
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_quantiles(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_quantiles DECIMAL[] DEFAULT ARRAY[0.25, 0.50, 0.75],
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    q25 DECIMAL(15,4),
    q50_median DECIMAL(15,4),
    q75 DECIMAL(15,4),
    iqr DECIMAL(15,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    windowed_data AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            ARRAY_AGG(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS window_values
        FROM parsed_data
    ),
    quantile_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY unnest(window_values)) AS q25_val,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY unnest(window_values)) AS q50_val,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY unnest(window_values)) AS q75_val
        FROM windowed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        q25_val AS q25,
        q50_val AS q50_median,
        q75_val AS q75,
        q75_val - q25_val AS iqr
    FROM quantile_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. MOVING MIN/MAX
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_minmax(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    moving_min DECIMAL(15,4),
    moving_max DECIMAL(15,4),
    moving_range DECIMAL(15,4),
    position_in_range DECIMAL(10,4)  -- 0=at min, 1=at max
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    minmax_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            MIN(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS min_val,
            MAX(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS max_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        min_val AS moving_min,
        max_val AS moving_max,
        max_val - min_val AS moving_range,
        CASE 
            WHEN (max_val - min_val) != 0 
            THEN (val - min_val) / (max_val - min_val)
            ELSE 0.5
        END AS position_in_range
    FROM minmax_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. MOVING CORRELATION (Between two series)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_correlation(
    p_data_x JSONB,
    p_data_y JSONB,
    p_window_size INTEGER DEFAULT 7
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    value_x DECIMAL(15,4),
    value_y DECIMAL(15,4),
    correlation DECIMAL(10,6),
    correlation_strength TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_x AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val_x
        FROM jsonb_array_elements(p_data_x) AS elem
    ),
    parsed_y AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'value')::DECIMAL AS val_y
        FROM jsonb_array_elements(p_data_y) AS elem
    ),
    combined AS (
        SELECT
            px.rn,
            px.ts,
            px.val_x,
            py.val_y
        FROM parsed_x px
        JOIN parsed_y py ON px.rn = py.rn
    ),
    correlation_calc AS (
        SELECT
            rn,
            ts,
            val_x,
            val_y,
            CORR(val_x, val_y) OVER (
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS corr_val
        FROM combined
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val_x AS value_x,
        val_y AS value_y,
        corr_val AS correlation,
        CASE
            WHEN ABS(corr_val) > 0.8 THEN 'very_strong'
            WHEN ABS(corr_val) > 0.6 THEN 'strong'
            WHEN ABS(corr_val) > 0.4 THEN 'moderate'
            WHEN ABS(corr_val) > 0.2 THEN 'weak'
            ELSE 'very_weak'
        END AS correlation_strength
    FROM correlation_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. MOVING SUM
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_sum(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    moving_sum DECIMAL(15,4),
    contribution_pct DECIMAL(10,4)  -- Contribution to moving sum
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    sum_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            SUM(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS sum_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        sum_val AS moving_sum,
        CASE WHEN sum_val != 0 THEN (val / sum_val) * 100 ELSE NULL END AS contribution_pct
    FROM sum_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. EXPANDING WINDOW (All Prior Data)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_expanding_window(
    p_data JSONB,
    p_operation TEXT DEFAULT 'mean',  -- 'mean', 'sum', 'std', 'min', 'max', 'count'
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    expanding_value DECIMAL(15,4),
    window_size INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    expanding_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            CASE p_operation
                WHEN 'mean' THEN
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'sum' THEN
                    SUM(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'std' THEN
                    STDDEV(val) OVER (
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
                WHEN 'max' THEN
                    MAX(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                WHEN 'count' THEN
                    COUNT(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )::DECIMAL
                ELSE
                    AVG(val) OVER (
                        PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                        ORDER BY rn
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
            END AS exp_val,
            rn AS window_count
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        exp_val AS expanding_value,
        window_count::INTEGER AS window_size
    FROM expanding_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. CUMULATIVE OPERATIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_cumulative_operations(
    p_data JSONB,
    p_operations TEXT[] DEFAULT ARRAY['sum', 'product', 'max', 'min'],
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    cumsum DECIMAL(15,4),
    cumproduct DECIMAL(15,4),
    cummax DECIMAL(15,4),
    cummin DECIMAL(15,4),
    percent_of_total DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
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
            SUM(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_sum,
            EXP(SUM(LN(NULLIF(ABS(val), 0))) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )) AS cum_prod,
            MAX(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_max,
            MIN(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cum_min,
            SUM(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
            ) AS total_sum
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        cum_sum AS cumsum,
        cum_prod AS cumproduct,
        cum_max AS cummax,
        cum_min AS cummin,
        CASE WHEN total_sum != 0 THEN (cum_sum / total_sum) * 100 ELSE NULL END AS percent_of_total
    FROM cumulative_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. TIME-WEIGHTED MOVING AVERAGE
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_time_weighted_ma(
    p_data JSONB,
    p_decay_factor DECIMAL(5,3) DEFAULT 0.1,  -- Higher = more weight on recent
    p_window_size INTEGER DEFAULT 30
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    twma_value DECIMAL(15,4),
    deviation DECIMAL(15,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    weighted_calc AS (
        SELECT
            pd1.rn,
            pd1.ts,
            pd1.val,
            -- Time-weighted average: weight = exp(-decay_factor * age)
            SUM(pd2.val * EXP(-p_decay_factor * (pd1.rn - pd2.rn))) / 
            NULLIF(SUM(EXP(-p_decay_factor * (pd1.rn - pd2.rn))), 0) AS twma
        FROM parsed_data pd1
        JOIN parsed_data pd2 ON pd2.rn <= pd1.rn AND pd2.rn > (pd1.rn - p_window_size)
        GROUP BY pd1.rn, pd1.ts, pd1.val
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        twma AS twma_value,
        val - twma AS deviation
    FROM weighted_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 11. BOLLINGER BANDS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_bollinger_bands(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 20,
    p_num_std DECIMAL(5,2) DEFAULT 2.0
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    middle_band DECIMAL(15,4),  -- SMA
    upper_band DECIMAL(15,4),   -- SMA + num_std * std
    lower_band DECIMAL(15,4),   -- SMA - num_std * std
    bandwidth DECIMAL(15,4),
    percent_b DECIMAL(10,4)     -- Position within bands (0-1)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    bollinger_calc AS (
        SELECT
            rn,
            ts,
            val,
            AVG(val) OVER (
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS sma,
            STDDEV(val) OVER (
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS std_dev
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        sma AS middle_band,
        sma + (p_num_std * std_dev) AS upper_band,
        sma - (p_num_std * std_dev) AS lower_band,
        2 * p_num_std * std_dev AS bandwidth,
        CASE 
            WHEN (sma + (p_num_std * std_dev)) - (sma - (p_num_std * std_dev)) != 0
            THEN (val - (sma - (p_num_std * std_dev))) / 
                 ((sma + (p_num_std * std_dev)) - (sma - (p_num_std * std_dev)))
            ELSE 0.5
        END AS percent_b
    FROM bollinger_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 12. MOVING RANK/PERCENTILE RANK
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_rank(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_group_by TEXT DEFAULT NULL
) RETURNS TABLE (
    row_number INTEGER,
    time_period TIMESTAMP,
    original_value DECIMAL(15,4),
    window_rank INTEGER,
    window_percentile DECIMAL(10,4),
    is_highest BOOLEAN,
    is_lowest BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'value')::DECIMAL AS val,
            COALESCE(elem->>'group', 'default') AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    rank_calc AS (
        SELECT
            rn,
            ts,
            val,
            grp,
            RANK() OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                ORDER BY val DESC
            ) AS rnk,
            PERCENT_RANK() OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                ORDER BY val
            ) AS pct_rnk,
            MAX(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS max_val,
            MIN(val) OVER (
                PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN grp END
                ORDER BY rn
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS min_val
        FROM parsed_data
    )
    SELECT
        rn AS row_number,
        ts AS time_period,
        val AS original_value,
        rnk::INTEGER AS window_rank,
        (pct_rnk * 100) AS window_percentile,
        (val = max_val) AS is_highest,
        (val = min_val) AS is_lowest
    FROM rank_calc
    ORDER BY rn;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DOCUMENTATION AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION calculate_sma IS
'Calculate Simple Moving Average with Bollinger-style bands.
Returns SMA, deviation, and upper/lower bands (±2 std dev).
Essential for trend identification and volatility assessment.';

COMMENT ON FUNCTION calculate_wma IS
'Calculate Weighted Moving Average giving more weight to recent values.
More responsive to changes than SMA.
Useful for short-term trend analysis.';

COMMENT ON FUNCTION calculate_moving_variance IS
'Calculate moving variance, std dev, CV, and Z-scores.
Comprehensive volatility analysis with normalization.
Essential for risk assessment and anomaly detection.';

COMMENT ON FUNCTION calculate_moving_quantiles IS
'Calculate moving quartiles (Q1, median, Q3) and IQR.
Robust to outliers, provides distribution shape within window.
Useful for detecting distribution shifts.';

COMMENT ON FUNCTION calculate_moving_minmax IS
'Calculate moving min/max with range and position metrics.
Returns where current value sits within recent range (0-1).
Essential for support/resistance analysis.';

COMMENT ON FUNCTION calculate_moving_correlation IS
'Calculate moving correlation between two time series.
Identifies changing relationships over time.
Useful for portfolio analysis and dependency tracking.';

COMMENT ON FUNCTION calculate_moving_sum IS
'Calculate moving sum with contribution percentage.
Shows each value's contribution to recent total.
Essential for cumulative metrics and totals.';

COMMENT ON FUNCTION calculate_expanding_window IS
'Calculate metrics using all prior data (expanding window).
Window grows with each observation.
Useful for cumulative statistics and long-term trends.';

COMMENT ON FUNCTION calculate_cumulative_operations IS
'Calculate multiple cumulative operations: sum, product, max, min.
Returns percent of total for cumulative sum.
Essential for running totals and cumulative metrics.';

COMMENT ON FUNCTION calculate_time_weighted_ma IS
'Calculate time-weighted moving average with exponential decay.
More weight on recent observations, decay controlled by factor.
Superior for non-uniformly spaced time series.';

COMMENT ON FUNCTION calculate_bollinger_bands IS
'Calculate Bollinger Bands: SMA with ±N standard deviation bands.
Returns bandwidth and %B (position within bands).
Essential for volatility and overbought/oversold detection.';

COMMENT ON FUNCTION calculate_moving_rank IS
'Calculate moving rank and percentile rank within window.
Identifies relative position of values within recent history.
Useful for momentum and relative strength analysis.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- Example 1: Simple Moving Average
SELECT * FROM calculate_sma(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 105},
        {"time": "2024-01-03", "value": 102}
    ]'::JSONB,
    3,    -- 3-period SMA
    NULL  -- no grouping
);

-- Example 2: Moving Variance
SELECT * FROM calculate_moving_variance(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 150},
        {"time": "2024-01-03", "value": 80}
    ]'::JSONB,
    5,    -- 5-period window
    NULL
);

-- Example 3: Bollinger Bands
SELECT * FROM calculate_bollinger_bands(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 105},
        {"time": "2024-01-03", "value": 102}
    ]'::JSONB,
    20,   -- 20-period window
    2.0   -- 2 standard deviations
);

-- Example 4: Moving Correlation
SELECT * FROM calculate_moving_correlation(
    '[{"time": "2024-01-01", "value": 100}, {"time": "2024-01-02", "value": 105}]'::JSONB,
    '[{"time": "2024-01-01", "value": 200}, {"time": "2024-01-02", "value": 210}]'::JSONB,
    7     -- 7-period correlation
);

-- Example 5: Expanding Window
SELECT * FROM calculate_expanding_window(
    '[
        {"time": "2024-01-01", "value": 100},
        {"time": "2024-01-02", "value": 110},
        {"time": "2024-01-03", "value": 105}
    ]'::JSONB,
    'mean',  -- expanding mean
    NULL
);
*/
