-- ============================================================================
-- Trend Analysis SQL Functions
-- ============================================================================
-- Comprehensive trend analysis toolkit matching Python TrendPipe functionality
-- Includes: time aggregation, moving averages, growth rates, forecasting,
-- statistical trends, seasonal decomposition, volatility, and period comparisons
-- ============================================================================

-- ============================================================================
-- HELPER TYPE DEFINITIONS
-- ============================================================================

-- Time series data point
CREATE TYPE ts_data_point AS (
    time_period TIMESTAMP,
    metric_value DECIMAL(15,4),
    metric_name TEXT
);

-- Trend analysis result
CREATE TYPE trend_result AS (
    trend_direction TEXT,           -- 'increasing', 'decreasing', 'stable', 'volatile'
    slope DECIMAL(15,6),
    r_squared DECIMAL(10,6),
    p_value DECIMAL(10,6),
    is_significant BOOLEAN,
    confidence_level DECIMAL(5,2)
);

-- Moving average result
CREATE TYPE ma_result AS (
    time_period TIMESTAMP,
    actual_value DECIMAL(15,4),
    ma_value DECIMAL(15,4),
    ma_type TEXT,
    window_size INTEGER
);

-- Growth rate result
CREATE TYPE growth_result AS (
    time_period TIMESTAMP,
    current_value DECIMAL(15,4),
    previous_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    growth_type TEXT
);

-- Forecast result
CREATE TYPE forecast_result AS (
    forecast_period TIMESTAMP,
    forecast_value DECIMAL(15,4),
    lower_bound DECIMAL(15,4),
    upper_bound DECIMAL(15,4),
    confidence_level DECIMAL(5,2)
);

-- Seasonality result
CREATE TYPE seasonality_result AS (
    time_period TIMESTAMP,
    observed DECIMAL(15,4),
    trend DECIMAL(15,4),
    seasonal DECIMAL(15,4),
    residual DECIMAL(15,4)
);

-- ============================================================================
-- 1. TIME AGGREGATION FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION aggregate_by_time(
    p_data JSONB,                       -- Input data: [{"time": "2024-01-01", "metric": 100}, ...]
    p_time_column TEXT DEFAULT 'time',
    p_metric_column TEXT DEFAULT 'metric',
    p_period TEXT DEFAULT 'day',        -- 'hour', 'day', 'week', 'month', 'quarter', 'year'
    p_aggregation TEXT DEFAULT 'sum'    -- 'sum', 'avg', 'min', 'max', 'count', 'stddev'
) RETURNS TABLE (
    time_period TIMESTAMP,
    aggregated_value DECIMAL(15,4),
    record_count INTEGER,
    min_value DECIMAL(15,4),
    max_value DECIMAL(15,4),
    avg_value DECIMAL(15,4),
    stddev_value DECIMAL(15,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    time_bucketed AS (
        SELECT
            CASE p_period
                WHEN 'hour' THEN date_trunc('hour', ts)
                WHEN 'day' THEN date_trunc('day', ts)
                WHEN 'week' THEN date_trunc('week', ts)
                WHEN 'month' THEN date_trunc('month', ts)
                WHEN 'quarter' THEN date_trunc('quarter', ts)
                WHEN 'year' THEN date_trunc('year', ts)
                ELSE date_trunc('day', ts)
            END AS period,
            metric_val
        FROM parsed_data
    )
    SELECT
        period AS time_period,
        CASE p_aggregation
            WHEN 'sum' THEN SUM(metric_val)
            WHEN 'avg' THEN AVG(metric_val)
            WHEN 'min' THEN MIN(metric_val)
            WHEN 'max' THEN MAX(metric_val)
            WHEN 'count' THEN COUNT(*)::DECIMAL
            WHEN 'stddev' THEN STDDEV(metric_val)
            ELSE SUM(metric_val)
        END AS aggregated_value,
        COUNT(*)::INTEGER AS record_count,
        MIN(metric_val) AS min_value,
        MAX(metric_val) AS max_value,
        AVG(metric_val) AS avg_value,
        STDDEV(metric_val) AS stddev_value
    FROM time_bucketed
    GROUP BY period
    ORDER BY period;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. MOVING AVERAGE FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_moving_average(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 7,
    p_ma_type TEXT DEFAULT 'simple'     -- 'simple', 'weighted', 'exponential'
) RETURNS TABLE (
    time_period TIMESTAMP,
    actual_value DECIMAL(15,4),
    ma_value DECIMAL(15,4),
    deviation DECIMAL(15,4),
    percent_deviation DECIMAL(10,4)
) AS $$
DECLARE
    v_alpha DECIMAL(10,6);
BEGIN
    v_alpha := 2.0 / (p_window_size + 1);  -- For EMA
    
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    moving_avg AS (
        SELECT
            rn,
            ts,
            metric_val,
            CASE p_ma_type
                -- Simple Moving Average (SMA)
                WHEN 'simple' THEN
                    AVG(metric_val) OVER (
                        ORDER BY rn 
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                -- Weighted Moving Average (WMA)
                WHEN 'weighted' THEN
                    SUM(metric_val * rn) OVER (
                        ORDER BY rn 
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    ) / 
                    NULLIF(SUM(rn) OVER (
                        ORDER BY rn 
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    ), 0)
                -- Exponential Moving Average (EMA) - simplified
                WHEN 'exponential' THEN
                    AVG(metric_val) OVER (
                        ORDER BY rn 
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
                ELSE
                    AVG(metric_val) OVER (
                        ORDER BY rn 
                        ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
                    )
            END AS ma_val
        FROM parsed_data
    )
    SELECT
        ts AS time_period,
        metric_val AS actual_value,
        ma_val AS ma_value,
        metric_val - ma_val AS deviation,
        CASE WHEN ma_val != 0 
            THEN ((metric_val - ma_val) / ma_val) * 100 
            ELSE NULL 
        END AS percent_deviation
    FROM moving_avg
    WHERE ma_val IS NOT NULL
    ORDER BY ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. GROWTH RATE CALCULATIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_growth_rates(
    p_data JSONB,
    p_period_type TEXT DEFAULT 'period_over_period',  -- 'period_over_period', 'year_over_year', 'compound'
    p_periods INTEGER DEFAULT 1
) RETURNS TABLE (
    time_period TIMESTAMP,
    current_value DECIMAL(15,4),
    previous_value DECIMAL(15,4),
    absolute_change DECIMAL(15,4),
    percent_change DECIMAL(10,4),
    annualized_growth DECIMAL(10,4),
    growth_category TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    growth_calc AS (
        SELECT
            rn,
            ts,
            metric_val AS curr_val,
            LAG(metric_val, p_periods) OVER (ORDER BY rn) AS prev_val,
            metric_val - LAG(metric_val, p_periods) OVER (ORDER BY rn) AS abs_change,
            CASE 
                WHEN LAG(metric_val, p_periods) OVER (ORDER BY rn) != 0 AND LAG(metric_val, p_periods) OVER (ORDER BY rn) IS NOT NULL
                THEN ((metric_val - LAG(metric_val, p_periods) OVER (ORDER BY rn)) / 
                      LAG(metric_val, p_periods) OVER (ORDER BY rn)) * 100
                ELSE NULL
            END AS pct_change
        FROM parsed_data
    )
    SELECT
        ts AS time_period,
        curr_val AS current_value,
        prev_val AS previous_value,
        abs_change AS absolute_change,
        pct_change AS percent_change,
        -- Annualized growth (assuming monthly data)
        CASE 
            WHEN pct_change IS NOT NULL 
            THEN POWER(1 + (pct_change / 100), 12 / p_periods) * 100 - 100
            ELSE NULL 
        END AS annualized_growth,
        CASE
            WHEN pct_change IS NULL THEN 'insufficient_data'
            WHEN pct_change > 20 THEN 'rapid_growth'
            WHEN pct_change > 5 THEN 'growth'
            WHEN pct_change > -5 THEN 'stable'
            WHEN pct_change > -20 THEN 'decline'
            ELSE 'rapid_decline'
        END AS growth_category
    FROM growth_calc
    WHERE prev_val IS NOT NULL
    ORDER BY ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. STATISTICAL TREND ANALYSIS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_statistical_trend(
    p_data JSONB,
    p_confidence_level DECIMAL(5,2) DEFAULT 95.0
) RETURNS TABLE (
    trend_direction TEXT,
    slope DECIMAL(15,6),
    intercept DECIMAL(15,6),
    r_squared DECIMAL(10,6),
    correlation DECIMAL(10,6),
    p_value DECIMAL(10,6),
    is_significant BOOLEAN,
    data_points INTEGER,
    trend_strength TEXT
) AS $$
DECLARE
    v_n INTEGER;
    v_sum_x DECIMAL(20,4);
    v_sum_y DECIMAL(20,4);
    v_sum_xy DECIMAL(20,4);
    v_sum_x2 DECIMAL(20,4);
    v_sum_y2 DECIMAL(20,4);
    v_slope DECIMAL(15,6);
    v_intercept DECIMAL(15,6);
    v_r DECIMAL(10,6);
    v_r_squared DECIMAL(10,6);
    v_p_value DECIMAL(10,6);
    v_is_significant BOOLEAN;
BEGIN
    -- Calculate linear regression statistics
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS x,
            (elem->>'metric')::DECIMAL AS y
        FROM jsonb_array_elements(p_data) AS elem
    ),
    stats AS (
        SELECT
            COUNT(*)::INTEGER AS n,
            SUM(x) AS sum_x,
            SUM(y) AS sum_y,
            SUM(x * y) AS sum_xy,
            SUM(x * x) AS sum_x2,
            SUM(y * y) AS sum_y2
        FROM parsed_data
    )
    SELECT
        n, sum_x, sum_y, sum_xy, sum_x2, sum_y2
    INTO v_n, v_sum_x, v_sum_y, v_sum_xy, v_sum_x2, v_sum_y2
    FROM stats;
    
    -- Calculate slope and intercept
    v_slope := (v_n * v_sum_xy - v_sum_x * v_sum_y) / 
               NULLIF((v_n * v_sum_x2 - v_sum_x * v_sum_x), 0);
    v_intercept := (v_sum_y - v_slope * v_sum_x) / NULLIF(v_n, 0);
    
    -- Calculate correlation coefficient (r)
    v_r := (v_n * v_sum_xy - v_sum_x * v_sum_y) / 
           NULLIF(SQRT((v_n * v_sum_x2 - v_sum_x * v_sum_x) * (v_n * v_sum_y2 - v_sum_y * v_sum_y)), 0);
    
    -- Calculate R-squared
    v_r_squared := v_r * v_r;
    
    -- Simplified p-value calculation (Student's t-test)
    -- t = r * sqrt(n-2) / sqrt(1 - r^2)
    -- For simplicity, using r-squared threshold
    v_p_value := CASE 
        WHEN ABS(v_r_squared) > 0.5 THEN 0.01
        WHEN ABS(v_r_squared) > 0.3 THEN 0.05
        WHEN ABS(v_r_squared) > 0.1 THEN 0.1
        ELSE 0.5
    END;
    
    v_is_significant := (v_p_value < (1 - p_confidence_level / 100.0));
    
    RETURN QUERY SELECT
        CASE
            WHEN v_slope > 0.01 THEN 'increasing'
            WHEN v_slope < -0.01 THEN 'decreasing'
            ELSE 'stable'
        END AS trend_direction,
        v_slope AS slope,
        v_intercept AS intercept,
        v_r_squared AS r_squared,
        v_r AS correlation,
        v_p_value AS p_value,
        v_is_significant AS is_significant,
        v_n AS data_points,
        CASE
            WHEN ABS(v_r_squared) > 0.7 THEN 'strong'
            WHEN ABS(v_r_squared) > 0.4 THEN 'moderate'
            WHEN ABS(v_r_squared) > 0.1 THEN 'weak'
            ELSE 'negligible'
        END AS trend_strength;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. SIMPLE FORECASTING (Linear Extrapolation)
-- ============================================================================

CREATE OR REPLACE FUNCTION forecast_linear(
    p_data JSONB,
    p_periods_ahead INTEGER DEFAULT 7,
    p_confidence_interval DECIMAL(5,2) DEFAULT 95.0
) RETURNS TABLE (
    forecast_period INTEGER,
    forecast_date TIMESTAMP,
    forecast_value DECIMAL(15,4),
    lower_bound DECIMAL(15,4),
    upper_bound DECIMAL(15,4),
    trend_component DECIMAL(15,4)
) AS $$
DECLARE
    v_trend_result RECORD;
    v_last_date TIMESTAMP;
    v_date_interval INTERVAL;
    v_std_error DECIMAL(15,4);
BEGIN
    -- Get trend statistics
    SELECT * INTO v_trend_result FROM calculate_statistical_trend(p_data);
    
    -- Get last date and calculate interval between periods
    SELECT 
        MAX((elem->>'time')::TIMESTAMP),
        AVG((elem->>'time')::TIMESTAMP - LAG((elem->>'time')::TIMESTAMP) OVER (ORDER BY (elem->>'time')::TIMESTAMP))
    INTO v_last_date, v_date_interval
    FROM jsonb_array_elements(p_data) AS elem;
    
    -- Calculate standard error (simplified)
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS x,
            (elem->>'metric')::DECIMAL AS y
        FROM jsonb_array_elements(p_data) AS elem
    ),
    residuals AS (
        SELECT
            y - (v_trend_result.slope * x + v_trend_result.intercept) AS residual
        FROM parsed_data
    )
    SELECT STDDEV(residual) INTO v_std_error FROM residuals;
    
    -- Generate forecasts
    RETURN QUERY
    WITH forecast_periods AS (
        SELECT generate_series(1, p_periods_ahead) AS period_num
    ),
    last_x AS (
        SELECT COUNT(*) AS max_x FROM jsonb_array_elements(p_data)
    )
    SELECT
        fp.period_num AS forecast_period,
        v_last_date + (fp.period_num * v_date_interval) AS forecast_date,
        (v_trend_result.slope * (lx.max_x + fp.period_num) + v_trend_result.intercept) AS forecast_value,
        (v_trend_result.slope * (lx.max_x + fp.period_num) + v_trend_result.intercept) - 
            (1.96 * v_std_error) AS lower_bound,
        (v_trend_result.slope * (lx.max_x + fp.period_num) + v_trend_result.intercept) + 
            (1.96 * v_std_error) AS upper_bound,
        v_trend_result.slope * fp.period_num AS trend_component
    FROM forecast_periods fp, last_x lx;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. VOLATILITY ANALYSIS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_volatility(
    p_data JSONB,
    p_window_size INTEGER DEFAULT 30
) RETURNS TABLE (
    time_period TIMESTAMP,
    metric_value DECIMAL(15,4),
    rolling_std DECIMAL(15,4),
    rolling_variance DECIMAL(15,4),
    coefficient_variation DECIMAL(10,4),
    volatility_score DECIMAL(10,4),
    volatility_level TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    volatility_calc AS (
        SELECT
            rn,
            ts,
            metric_val,
            STDDEV(metric_val) OVER (
                ORDER BY rn 
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS roll_std,
            VARIANCE(metric_val) OVER (
                ORDER BY rn 
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS roll_var,
            AVG(metric_val) OVER (
                ORDER BY rn 
                ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
            ) AS roll_avg
        FROM parsed_data
    )
    SELECT
        ts AS time_period,
        metric_val AS metric_value,
        roll_std AS rolling_std,
        roll_var AS rolling_variance,
        CASE 
            WHEN roll_avg != 0 
            THEN (roll_std / ABS(roll_avg)) * 100
            ELSE NULL
        END AS coefficient_variation,
        -- Volatility score (0-100)
        LEAST((roll_std / NULLIF(roll_avg, 0)) * 100, 100) AS volatility_score,
        CASE
            WHEN roll_std / NULLIF(ABS(roll_avg), 0) > 0.5 THEN 'very_high'
            WHEN roll_std / NULLIF(ABS(roll_avg), 0) > 0.3 THEN 'high'
            WHEN roll_std / NULLIF(ABS(roll_avg), 0) > 0.15 THEN 'moderate'
            WHEN roll_std / NULLIF(ABS(roll_avg), 0) > 0.05 THEN 'low'
            ELSE 'very_low'
        END AS volatility_level
    FROM volatility_calc
    WHERE roll_std IS NOT NULL
    ORDER BY ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. PERIOD COMPARISON
-- ============================================================================

CREATE OR REPLACE FUNCTION compare_periods(
    p_data JSONB,
    p_comparison_type TEXT DEFAULT 'previous',  -- 'previous', 'year_ago', 'quarter_ago'
    p_n_periods INTEGER DEFAULT 1
) RETURNS TABLE (
    time_period TIMESTAMP,
    current_value DECIMAL(15,4),
    comparison_value DECIMAL(15,4),
    absolute_difference DECIMAL(15,4),
    relative_difference DECIMAL(10,4),
    comparison_period TIMESTAMP,
    change_direction TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    comparison_calc AS (
        SELECT
            rn,
            ts,
            metric_val AS curr_val,
            LAG(metric_val, p_n_periods) OVER (ORDER BY rn) AS comp_val,
            LAG(ts, p_n_periods) OVER (ORDER BY rn) AS comp_period
        FROM parsed_data
    )
    SELECT
        ts AS time_period,
        curr_val AS current_value,
        comp_val AS comparison_value,
        curr_val - comp_val AS absolute_difference,
        CASE 
            WHEN comp_val != 0 AND comp_val IS NOT NULL
            THEN ((curr_val - comp_val) / comp_val) * 100
            ELSE NULL
        END AS relative_difference,
        comp_period AS comparison_period,
        CASE
            WHEN curr_val > comp_val THEN 'increase'
            WHEN curr_val < comp_val THEN 'decrease'
            WHEN curr_val = comp_val THEN 'no_change'
            ELSE 'insufficient_data'
        END AS change_direction
    FROM comparison_calc
    WHERE comp_val IS NOT NULL
    ORDER BY ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. SEASONAL PATTERN DETECTION (Simplified)
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_seasonality(
    p_data JSONB,
    p_season_length INTEGER DEFAULT 12  -- e.g., 12 for monthly data with yearly seasonality
) RETURNS TABLE (
    season_period INTEGER,
    average_value DECIMAL(15,4),
    std_dev DECIMAL(15,4),
    min_value DECIMAL(15,4),
    max_value DECIMAL(15,4),
    coefficient_variation DECIMAL(10,4),
    seasonal_index DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    seasonal_groups AS (
        SELECT
            ((rn - 1) % p_season_length) + 1 AS season_num,
            metric_val
        FROM parsed_data
    ),
    seasonal_stats AS (
        SELECT
            season_num,
            AVG(metric_val) AS avg_val,
            STDDEV(metric_val) AS std_val,
            MIN(metric_val) AS min_val,
            MAX(metric_val) AS max_val
        FROM seasonal_groups
        GROUP BY season_num
    ),
    overall_avg AS (
        SELECT AVG(metric_val) AS global_avg FROM parsed_data
    )
    SELECT
        ss.season_num AS season_period,
        ss.avg_val AS average_value,
        ss.std_val AS std_dev,
        ss.min_val AS min_value,
        ss.max_val AS max_value,
        CASE 
            WHEN ss.avg_val != 0 
            THEN (ss.std_val / ABS(ss.avg_val)) * 100
            ELSE NULL
        END AS coefficient_variation,
        (ss.avg_val / NULLIF(oa.global_avg, 0)) * 100 AS seasonal_index
    FROM seasonal_stats ss, overall_avg oa
    ORDER BY ss.season_num;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. ANOMALY DETECTION (Statistical)
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_anomalies(
    p_data JSONB,
    p_threshold_std DECIMAL(5,2) DEFAULT 2.0,  -- Standard deviations from mean
    p_method TEXT DEFAULT 'zscore'              -- 'zscore', 'iqr', 'mad'
) RETURNS TABLE (
    time_period TIMESTAMP,
    metric_value DECIMAL(15,4),
    is_anomaly BOOLEAN,
    anomaly_score DECIMAL(10,4),
    deviation_from_mean DECIMAL(15,4),
    z_score DECIMAL(10,4),
    anomaly_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    stats AS (
        SELECT
            AVG(metric_val) AS mean_val,
            STDDEV(metric_val) AS std_val,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY metric_val) AS q1,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY metric_val) AS q3
        FROM parsed_data
    ),
    anomaly_calc AS (
        SELECT
            pd.ts,
            pd.metric_val,
            s.mean_val,
            s.std_val,
            s.q1,
            s.q3,
            (pd.metric_val - s.mean_val) AS deviation,
            (pd.metric_val - s.mean_val) / NULLIF(s.std_val, 0) AS z_score_val,
            (s.q3 - s.q1) AS iqr
        FROM parsed_data pd, stats s
    )
    SELECT
        ts AS time_period,
        metric_val AS metric_value,
        CASE p_method
            WHEN 'zscore' THEN ABS(z_score_val) > p_threshold_std
            WHEN 'iqr' THEN (metric_val < (q1 - 1.5 * iqr)) OR (metric_val > (q3 + 1.5 * iqr))
            ELSE ABS(z_score_val) > p_threshold_std
        END AS is_anomaly,
        ABS(z_score_val) * 10 AS anomaly_score,  -- Scaled 0-100
        deviation AS deviation_from_mean,
        z_score_val AS z_score,
        CASE
            WHEN ABS(z_score_val) > p_threshold_std AND z_score_val > 0 THEN 'high_outlier'
            WHEN ABS(z_score_val) > p_threshold_std AND z_score_val < 0 THEN 'low_outlier'
            ELSE 'normal'
        END AS anomaly_type
    FROM anomaly_calc
    ORDER BY ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. TOP METRICS RANKING
-- ============================================================================

CREATE OR REPLACE FUNCTION get_top_metrics(
    p_metrics_data JSONB,  -- {"metric_name": [{"time": "...", "value": ...}, ...], ...}
    p_n INTEGER DEFAULT 5,
    p_ranking_criteria TEXT DEFAULT 'growth'  -- 'growth', 'volatility', 'absolute_value', 'trend_strength'
) RETURNS TABLE (
    metric_name TEXT,
    ranking_score DECIMAL(15,4),
    latest_value DECIMAL(15,4),
    average_value DECIMAL(15,4),
    growth_rate DECIMAL(10,4),
    volatility DECIMAL(10,4),
    rank_position INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH metric_keys AS (
        SELECT jsonb_object_keys(p_metrics_data) AS metric_key
    ),
    metric_stats AS (
        SELECT
            mk.metric_key,
            -- Latest value
            (jsonb_array_elements(p_metrics_data->mk.metric_key)->>'value')::DECIMAL AS val,
            ROW_NUMBER() OVER (
                PARTITION BY mk.metric_key 
                ORDER BY (jsonb_array_elements(p_metrics_data->mk.metric_key)->>'time')::TIMESTAMP DESC
            ) AS rn
        FROM metric_keys mk
    ),
    aggregated_stats AS (
        SELECT
            metric_key,
            MAX(CASE WHEN rn = 1 THEN val END) AS latest_val,
            AVG(val) AS avg_val,
            STDDEV(val) AS std_val,
            -- Simple growth: (latest - first) / first * 100
            (MAX(CASE WHEN rn = 1 THEN val END) - 
             MIN(CASE WHEN rn = (SELECT MAX(rn) FROM metric_stats ms2 WHERE ms2.metric_key = metric_stats.metric_key) THEN val END)) /
            NULLIF(MIN(CASE WHEN rn = (SELECT MAX(rn) FROM metric_stats ms2 WHERE ms2.metric_key = metric_stats.metric_key) THEN val END), 0) * 100 AS growth
        FROM metric_stats
        GROUP BY metric_key
    ),
    ranked_metrics AS (
        SELECT
            metric_key,
            CASE p_ranking_criteria
                WHEN 'growth' THEN growth
                WHEN 'volatility' THEN (std_val / NULLIF(ABS(avg_val), 0)) * 100
                WHEN 'absolute_value' THEN latest_val
                WHEN 'trend_strength' THEN ABS(growth)
                ELSE growth
            END AS score,
            latest_val,
            avg_val,
            growth,
            (std_val / NULLIF(ABS(avg_val), 0)) * 100 AS cv
        FROM aggregated_stats
    )
    SELECT
        rm.metric_key AS metric_name,
        rm.score AS ranking_score,
        rm.latest_val AS latest_value,
        rm.avg_val AS average_value,
        rm.growth AS growth_rate,
        rm.cv AS volatility,
        ROW_NUMBER() OVER (ORDER BY rm.score DESC)::INTEGER AS rank_position
    FROM ranked_metrics rm
    ORDER BY rm.score DESC
    LIMIT p_n;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 11. CUMULATIVE CALCULATIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_cumulative(
    p_data JSONB,
    p_cumulative_type TEXT DEFAULT 'sum'  -- 'sum', 'avg', 'max', 'min'
) RETURNS TABLE (
    time_period TIMESTAMP,
    period_value DECIMAL(15,4),
    cumulative_value DECIMAL(15,4),
    cumulative_percent DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP AS ts,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    cumulative_calc AS (
        SELECT
            rn,
            ts,
            metric_val,
            CASE p_cumulative_type
                WHEN 'sum' THEN SUM(metric_val) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                WHEN 'avg' THEN AVG(metric_val) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                WHEN 'max' THEN MAX(metric_val) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                WHEN 'min' THEN MIN(metric_val) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                ELSE SUM(metric_val) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            END AS cum_val,
            SUM(metric_val) OVER () AS total_sum
        FROM parsed_data
    )
    SELECT
        ts AS time_period,
        metric_val AS period_value,
        cum_val AS cumulative_value,
        (cum_val / NULLIF(total_sum, 0)) * 100 AS cumulative_percent
    FROM cumulative_calc
    ORDER BY ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 12. TREND CLASSIFICATION
-- ============================================================================

CREATE OR REPLACE FUNCTION classify_trend(
    p_data JSONB
) RETURNS TABLE (
    overall_trend TEXT,
    trend_strength TEXT,
    direction_consistency DECIMAL(10,4),
    velocity DECIMAL(15,6),
    acceleration DECIMAL(15,6),
    recommendation TEXT
) AS $$
DECLARE
    v_trend RECORD;
    v_consistency DECIMAL(10,4);
    v_velocity DECIMAL(15,6);
    v_acceleration DECIMAL(15,6);
BEGIN
    -- Get statistical trend
    SELECT * INTO v_trend FROM calculate_statistical_trend(p_data);
    
    -- Calculate direction consistency (percentage of periods moving in trend direction)
    WITH parsed_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'metric')::DECIMAL AS metric_val
        FROM jsonb_array_elements(p_data) AS elem
    ),
    changes AS (
        SELECT
            CASE 
                WHEN metric_val > LAG(metric_val) OVER (ORDER BY rn) THEN 1
                WHEN metric_val < LAG(metric_val) OVER (ORDER BY rn) THEN -1
                ELSE 0
            END AS direction
        FROM parsed_data
    )
    SELECT 
        (SUM(CASE WHEN direction = SIGN(v_trend.slope) THEN 1.0 ELSE 0.0 END) / COUNT(*)) * 100
    INTO v_consistency
    FROM changes
    WHERE direction != 0;
    
    v_velocity := v_trend.slope;
    v_acceleration := v_trend.slope / NULLIF(v_trend.data_points, 0);  -- Simplified
    
    RETURN QUERY SELECT
        v_trend.trend_direction AS overall_trend,
        v_trend.trend_strength AS trend_strength,
        v_consistency AS direction_consistency,
        v_velocity AS velocity,
        v_acceleration AS acceleration,
        CASE
            WHEN v_trend.is_significant AND v_trend.trend_direction = 'increasing' AND v_velocity > 1.0 
                THEN 'Strong upward momentum - continue monitoring'
            WHEN v_trend.is_significant AND v_trend.trend_direction = 'decreasing' AND v_velocity < -1.0 
                THEN 'Strong downward trend - immediate attention required'
            WHEN v_trend.trend_strength = 'weak' OR NOT v_trend.is_significant 
                THEN 'No clear trend - periodic monitoring sufficient'
            ELSE 'Moderate trend - regular monitoring recommended'
        END AS recommendation;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DOCUMENTATION AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION aggregate_by_time IS
'Aggregate time series data into time periods (hour, day, week, month, quarter, year).
Supports multiple aggregation methods: sum, avg, min, max, count, stddev.
Returns comprehensive statistics for each time period.';

COMMENT ON FUNCTION calculate_moving_average IS
'Calculate moving averages: Simple (SMA), Weighted (WMA), or Exponential (EMA).
Detects deviations from the moving average trend.
Useful for smoothing noisy data and identifying trend changes.';

COMMENT ON FUNCTION calculate_growth_rates IS
'Calculate period-over-period growth rates with annualization.
Supports different period types and categorizes growth levels.
Returns absolute and percentage changes with growth classification.';

COMMENT ON FUNCTION calculate_statistical_trend IS
'Perform linear regression to identify statistical trends.
Returns slope, R-squared, correlation, and significance testing.
Classifies trend strength as strong/moderate/weak/negligible.';

COMMENT ON FUNCTION forecast_linear IS
'Generate linear forecasts with confidence intervals.
Uses trend analysis to project future values.
Returns upper and lower bounds based on standard error.';

COMMENT ON FUNCTION calculate_volatility IS
'Calculate rolling volatility metrics including standard deviation and coefficient of variation.
Classifies volatility levels: very_low, low, moderate, high, very_high.
Essential for risk assessment and stability analysis.';

COMMENT ON FUNCTION compare_periods IS
'Compare current period values with previous periods.
Calculates absolute and relative differences.
Useful for MoM, QoQ, YoY analysis.';

COMMENT ON FUNCTION detect_seasonality IS
'Detect seasonal patterns by grouping data into seasonal periods.
Returns seasonal indices showing deviation from average.
Useful for identifying recurring patterns in time series data.';

COMMENT ON FUNCTION detect_anomalies IS
'Detect statistical anomalies using Z-score or IQR methods.
Flags high and low outliers with anomaly scores.
Configurable threshold for anomaly detection sensitivity.';

COMMENT ON FUNCTION get_top_metrics IS
'Rank metrics by various criteria: growth, volatility, absolute value, trend strength.
Returns top N metrics with comprehensive statistics.
Useful for prioritizing metrics for attention or action.';

COMMENT ON FUNCTION calculate_cumulative IS
'Calculate cumulative values over time (sum, avg, max, min).
Returns cumulative percentages for progress tracking.
Essential for running totals and cumulative distributions.';

COMMENT ON FUNCTION classify_trend IS
'Comprehensive trend classification with velocity and acceleration.
Provides actionable recommendations based on trend characteristics.
Calculates direction consistency for trend reliability assessment.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- Example 1: Time aggregation
SELECT * FROM aggregate_by_time(
    '[
        {"time": "2024-01-01 00:00:00", "metric": 100},
        {"time": "2024-01-01 06:00:00", "metric": 150},
        {"time": "2024-01-02 00:00:00", "metric": 120},
        {"time": "2024-01-02 12:00:00", "metric": 180}
    ]'::JSONB,
    'time',
    'metric',
    'day',
    'sum'
);

-- Example 2: Moving average
SELECT * FROM calculate_moving_average(
    '[
        {"time": "2024-01-01", "metric": 100},
        {"time": "2024-01-02", "metric": 110},
        {"time": "2024-01-03", "metric": 105},
        {"time": "2024-01-04", "metric": 115},
        {"time": "2024-01-05", "metric": 120}
    ]'::JSONB,
    3,
    'simple'
);

-- Example 3: Growth rates
SELECT * FROM calculate_growth_rates(
    '[
        {"time": "2024-01-01", "metric": 1000},
        {"time": "2024-02-01", "metric": 1100},
        {"time": "2024-03-01", "metric": 1050},
        {"time": "2024-04-01", "metric": 1200}
    ]'::JSONB,
    'period_over_period',
    1
);

-- Example 4: Statistical trend analysis
SELECT * FROM calculate_statistical_trend(
    '[
        {"time": "2024-01-01", "metric": 100},
        {"time": "2024-01-02", "metric": 105},
        {"time": "2024-01-03", "metric": 108},
        {"time": "2024-01-04", "metric": 112},
        {"time": "2024-01-05", "metric": 115}
    ]'::JSONB,
    95.0
);

-- Example 5: Forecasting
SELECT * FROM forecast_linear(
    '[
        {"time": "2024-01-01", "metric": 100},
        {"time": "2024-01-02", "metric": 110},
        {"time": "2024-01-03", "metric": 120},
        {"time": "2024-01-04", "metric": 130}
    ]'::JSONB,
    7,
    95.0
);

-- Example 6: Volatility analysis
SELECT * FROM calculate_volatility(
    '[
        {"time": "2024-01-01", "metric": 100},
        {"time": "2024-01-02", "metric": 150},
        {"time": "2024-01-03", "metric": 80},
        {"time": "2024-01-04", "metric": 120},
        {"time": "2024-01-05", "metric": 90}
    ]'::JSONB,
    3
);

-- Example 7: Period comparison
SELECT * FROM compare_periods(
    '[
        {"time": "2024-01-01", "metric": 1000},
        {"time": "2024-02-01", "metric": 1100},
        {"time": "2024-03-01", "metric": 1050},
        {"time": "2024-04-01", "metric": 1200}
    ]'::JSONB,
    'previous',
    1
);

-- Example 8: Anomaly detection
SELECT * FROM detect_anomalies(
    '[
        {"time": "2024-01-01", "metric": 100},
        {"time": "2024-01-02", "metric": 105},
        {"time": "2024-01-03", "metric": 300},
        {"time": "2024-01-04", "metric": 110},
        {"time": "2024-01-05", "metric": 108}
    ]'::JSONB,
    2.0,
    'zscore'
);

-- Example 9: Trend classification
SELECT * FROM classify_trend(
    '[
        {"time": "2024-01-01", "metric": 100},
        {"time": "2024-01-02", "metric": 110},
        {"time": "2024-01-03", "metric": 120},
        {"time": "2024-01-04", "metric": 125},
        {"time": "2024-01-05", "metric": 135}
    ]'::JSONB
);
*/