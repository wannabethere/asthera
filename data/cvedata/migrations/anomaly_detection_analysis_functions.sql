-- ============================================================================
-- Generic Anomaly Detection Framework
-- ============================================================================
-- Composable anomaly detection built on top of:
--   • moving_averages_functions.sql   (SMA, Bollinger, variance, quantiles)
--   • timeseries_analysis_functions.sql (z-scores, lag/lead, EMA)
--   • trend_analysis_functions.sql    (statistical trend, volatility, growth)
--
-- Design principles:
--   1. Every function accepts raw JSONB  → [{"time": "...", "value": ...}, ...]
--   2. Every detector is INDEPENDENT — call them solo or composed
--   3. A shared enrichment layer provides pre-computed context
--   4. A composite scorer fuses multiple signals into one confidence score
--
-- Pipeline:
--   Raw JSONB
--     └─► build_anomaly_context()             -- enrichment (trends, bands, z-scores)
--           ├─► detect_anomalies_zscore()     -- z-score method
--           ├─► detect_anomalies_bollinger()  -- Bollinger Band breach
--           ├─► detect_anomalies_iqr()        -- IQR / Tukey fence method
--           ├─► detect_anomalies_trend_break()-- breaks from local linear trend
--           └─► detect_anomalies_composite()  -- ensemble (calls all four)
--                   └─► anomaly_summary()     -- convenience: anomalies only
-- ============================================================================


-- ============================================================================
-- SHARED TYPE: Standard anomaly signal emitted by every detector
-- ============================================================================

CREATE TYPE IF NOT EXISTS anomaly_signal AS (
    row_number        INTEGER,
    time_period       TIMESTAMP,
    original_value    DECIMAL(15,4),
    is_anomaly        BOOLEAN,
    anomaly_direction TEXT,          -- 'high' | 'low' | 'none'
    anomaly_score     DECIMAL(10,4), -- 0-100, higher = more anomalous
    method            TEXT,
    context           JSONB          -- method-specific supporting numbers
);


-- ============================================================================
-- 1. ENRICHMENT LAYER — build_anomaly_context
-- ============================================================================
-- Computes all baseline statistics in one pass so downstream detectors
-- share the same window configuration.
--
-- Calls:
--   calculate_sma()              → sma_value, upper_band, lower_band
--   calculate_moving_variance()  → moving_mean, moving_std, z_score
--   calculate_moving_quantiles() → q1, q3, iqr
--   calculate_percent_change()   → pct_change (period-over-period)
--   calculate_moving_rank()      → window_percentile
-- ============================================================================

CREATE OR REPLACE FUNCTION build_anomaly_context(
    p_data        JSONB,
    p_window_size INTEGER DEFAULT 14,
    p_num_std     DECIMAL DEFAULT 2.0,
    p_group_by    TEXT    DEFAULT NULL
) RETURNS TABLE (
    row_number        INTEGER,
    time_period       TIMESTAMP,
    original_value    DECIMAL(15,4),
    sma               DECIMAL(15,4),
    upper_band        DECIMAL(15,4),
    lower_band        DECIMAL(15,4),
    moving_mean       DECIMAL(15,4),
    moving_std        DECIMAL(15,4),
    z_score           DECIMAL(10,4),
    q1                DECIMAL(15,4),
    q3                DECIMAL(15,4),
    iqr               DECIMAL(15,4),
    pct_change        DECIMAL(10,4),
    window_percentile DECIMAL(10,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH
    sma_data AS (
        SELECT s.row_number,
               s.time_period,
               s.original_value,
               s.sma_value,
               s.upper_band AS ub,
               s.lower_band AS lb
        FROM calculate_sma(p_data, p_window_size, p_group_by) s
    ),
    var_data AS (
        SELECT v.row_number,
               v.moving_mean,
               v.moving_std,
               v.z_score
        FROM calculate_moving_variance(p_data, p_window_size, p_group_by) v
    ),
    quant_data AS (
        SELECT q.row_number,
               q.q1,
               q.q3,
               q.iqr
        FROM calculate_moving_quantiles(
                 p_data, p_window_size, ARRAY[0.25, 0.50, 0.75], p_group_by
             ) q
    ),
    pct_data AS (
        SELECT p.row_number,
               p.percent_change
        FROM calculate_percent_change(p_data, 1, 'simple', p_group_by) p
    ),
    rank_data AS (
        SELECT r.row_number,
               r.window_percentile
        FROM calculate_moving_rank(p_data, p_window_size, p_group_by) r
    )
    SELECT
        s.row_number,
        s.time_period,
        s.original_value,
        s.sma_value     AS sma,
        s.ub            AS upper_band,
        s.lb            AS lower_band,
        v.moving_mean,
        v.moving_std,
        v.z_score,
        q.q1,
        q.q3,
        q.iqr,
        p.percent_change AS pct_change,
        r.window_percentile
    FROM      sma_data    s
    JOIN var_data         v ON v.row_number = s.row_number
    JOIN quant_data       q ON q.row_number = s.row_number
    JOIN pct_data         p ON p.row_number = s.row_number
    JOIN rank_data        r ON r.row_number = s.row_number
    ORDER BY s.row_number;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION build_anomaly_context IS
'Enrichment layer: computes SMA, Bollinger bands, rolling z-scores, IQR,
period change, and window percentile for every data point.
Designed to be called once and joined to any downstream detector.
Also useful standalone to inspect per-point context before picking thresholds.';


-- ============================================================================
-- 2. DETECTOR — detect_anomalies_zscore
-- ============================================================================
-- Flags points whose rolling z-score exceeds p_threshold.
-- Uses calculate_moving_variance() for clean isolation.
-- Score = min(|z_score| / threshold * 100, 100)
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_anomalies_zscore(
    p_data        JSONB,
    p_window_size INTEGER DEFAULT 14,
    p_threshold   DECIMAL DEFAULT 2.5,
    p_group_by    TEXT    DEFAULT NULL
) RETURNS SETOF anomaly_signal AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.row_number,
        v.time_period,
        v.original_value,
        ABS(COALESCE(v.z_score, 0)) > p_threshold                 AS is_anomaly,
        CASE
            WHEN v.z_score >  p_threshold THEN 'high'
            WHEN v.z_score < -p_threshold THEN 'low'
            ELSE 'none'
        END                                                        AS anomaly_direction,
        LEAST(ABS(COALESCE(v.z_score, 0)) / p_threshold * 100, 100) AS anomaly_score,
        'zscore'::TEXT                                             AS method,
        jsonb_build_object(
            'z_score',     v.z_score,
            'moving_mean', v.moving_mean,
            'moving_std',  v.moving_std,
            'threshold',   p_threshold,
            'window_size', p_window_size
        )                                                          AS context
    FROM calculate_moving_variance(p_data, p_window_size, p_group_by) v
    ORDER BY v.row_number;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_anomalies_zscore IS
'Z-score anomaly detector: flags points where |rolling z-score| > threshold.
Uses a rolling (not global) mean, so it adapts to gradual level shifts.
Score 0-100 (100 = 2x threshold). Pairs well with Bollinger for spike detection.
Accepts any JSONB series: [{"time": "...", "value": ...}].';


-- ============================================================================
-- 3. DETECTOR — detect_anomalies_bollinger
-- ============================================================================
-- Flags points that breach the upper or lower Bollinger band.
-- Uses calculate_bollinger_bands() directly.
-- %B < 0 = below lower band (low anomaly), %B > 1 = above upper band (high).
-- Score is proportional to how far outside [0,1] the %B value falls.
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_anomalies_bollinger(
    p_data        JSONB,
    p_window_size INTEGER DEFAULT 14,
    p_num_std     DECIMAL DEFAULT 2.0,
    p_group_by    TEXT    DEFAULT NULL
) RETURNS SETOF anomaly_signal AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.row_number,
        b.time_period,
        b.original_value,
        (b.percent_b > 1.0 OR b.percent_b < 0.0)               AS is_anomaly,
        CASE
            WHEN b.percent_b > 1.0 THEN 'high'
            WHEN b.percent_b < 0.0 THEN 'low'
            ELSE 'none'
        END                                                     AS anomaly_direction,
        LEAST(
            CASE
                WHEN b.percent_b > 1.0 THEN (b.percent_b - 1.0) * 100
                WHEN b.percent_b < 0.0 THEN ABS(b.percent_b)     * 100
                ELSE 0
            END,
            100
        )                                                       AS anomaly_score,
        'bollinger'::TEXT                                       AS method,
        jsonb_build_object(
            'percent_b',   b.percent_b,
            'upper_band',  b.upper_band,
            'lower_band',  b.lower_band,
            'middle_band', b.middle_band,
            'bandwidth',   b.bandwidth,
            'num_std',     p_num_std,
            'window_size', p_window_size
        )                                                       AS context
    FROM calculate_bollinger_bands(p_data, p_window_size, p_num_std) b
    ORDER BY b.row_number;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_anomalies_bollinger IS
'Bollinger Band anomaly detector: flags values that breach SMA ± N std devs.
Wider bands (higher p_num_std) = fewer but more severe anomalies flagged.
Score scales with how far the value sits outside the band.
Accepts any JSONB series: [{"time": "...", "value": ...}].';


-- ============================================================================
-- 4. DETECTOR — detect_anomalies_iqr
-- ============================================================================
-- IQR fence (Tukey): anomaly if value < Q1 - k*IQR or > Q3 + k*IQR.
-- Uses rolling IQR via calculate_moving_quantiles().
-- More robust than z-score for skewed or heavy-tailed distributions.
-- Default k=1.5 (moderate outliers); k=3.0 = extreme outliers only.
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_anomalies_iqr(
    p_data           JSONB,
    p_window_size    INTEGER DEFAULT 14,
    p_iqr_multiplier DECIMAL DEFAULT 1.5,
    p_group_by       TEXT    DEFAULT NULL
) RETURNS SETOF anomaly_signal AS $$
BEGIN
    RETURN QUERY
    WITH quant AS (
        SELECT q.row_number,
               q.time_period,
               q.original_value,
               q.q1,
               q.q3,
               q.iqr,
               q.q1 - (p_iqr_multiplier * q.iqr) AS fence_low,
               q.q3 + (p_iqr_multiplier * q.iqr) AS fence_high
        FROM calculate_moving_quantiles(
                 p_data, p_window_size, ARRAY[0.25, 0.50, 0.75], p_group_by
             ) q
    )
    SELECT
        q.row_number,
        q.time_period,
        q.original_value,
        (q.original_value > q.fence_high OR q.original_value < q.fence_low) AS is_anomaly,
        CASE
            WHEN q.original_value > q.fence_high THEN 'high'
            WHEN q.original_value < q.fence_low  THEN 'low'
            ELSE 'none'
        END                                                                  AS anomaly_direction,
        LEAST(
            CASE
                WHEN q.original_value > q.fence_high
                    THEN ((q.original_value - q.fence_high) / NULLIF(q.iqr, 0)) * 50
                WHEN q.original_value < q.fence_low
                    THEN ((q.fence_low - q.original_value) / NULLIF(q.iqr, 0)) * 50
                ELSE 0
            END,
            100
        )                                                                    AS anomaly_score,
        'iqr'::TEXT                                                          AS method,
        jsonb_build_object(
            'q1',             q.q1,
            'q3',             q.q3,
            'iqr',            q.iqr,
            'fence_low',      q.fence_low,
            'fence_high',     q.fence_high,
            'iqr_multiplier', p_iqr_multiplier,
            'window_size',    p_window_size
        )                                                                    AS context
    FROM quant q
    ORDER BY q.row_number;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_anomalies_iqr IS
'IQR fence anomaly detector: flags values outside Q1 - k*IQR or Q3 + k*IQR.
Uses rolling IQR so it adapts as the distribution shifts over time.
k=1.5 (Tukey inner fence, default) / k=3.0 (extreme outliers only).
More robust than z-score on skewed distributions.
Accepts any JSONB series: [{"time": "...", "value": ...}].';


-- ============================================================================
-- 5. DETECTOR — detect_anomalies_trend_break
-- ============================================================================
-- Detects sudden breaks from the local linear trend.
-- Fits a rolling OLS regression over the prior window, projects the expected
-- value at each point, then flags if |actual - expected| > threshold_pct% of
-- the expected value.
-- Catches anomalies that look normal in absolute terms but break pattern.
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_anomalies_trend_break(
    p_data          JSONB,
    p_window_size   INTEGER DEFAULT 14,
    p_threshold_pct DECIMAL DEFAULT 15.0,
    p_group_by      TEXT    DEFAULT NULL
) RETURNS SETOF anomaly_signal AS $$
BEGIN
    RETURN QUERY
    WITH
    parsed AS (
        SELECT
            ROW_NUMBER() OVER (ORDER BY (elem->>'time')::TIMESTAMP) AS rn,
            (elem->>'time')::TIMESTAMP                              AS ts,
            (elem->>'value')::DECIMAL                               AS val,
            COALESCE(elem->>'group', 'default')                     AS grp
        FROM jsonb_array_elements(p_data) AS elem
    ),
    -- Rolling OLS: slope = (N·Σxy - Σx·Σy) / (N·Σx² - (Σx)²)
    --              intercept = (Σy - slope·Σx) / N
    trend_calc AS (
        SELECT
            p.rn,
            p.ts,
            p.val,
            -- slope
            (
                COUNT(*)            OVER w * SUM(p.rn::DECIMAL * p.val) OVER w
              - SUM(p.rn::DECIMAL)  OVER w * SUM(p.val)                 OVER w
            ) / NULLIF(
                COUNT(*)            OVER w * SUM(p.rn::DECIMAL ^ 2)     OVER w
              - (SUM(p.rn::DECIMAL) OVER w) ^ 2,
                0
            )                                                            AS slope,
            -- intercept
            (
                SUM(p.val)         OVER w
              - (
                    (COUNT(*)            OVER w * SUM(p.rn::DECIMAL * p.val) OVER w
                   - SUM(p.rn::DECIMAL)  OVER w * SUM(p.val)                 OVER w)
                  / NULLIF(
                        COUNT(*)            OVER w * SUM(p.rn::DECIMAL ^ 2)     OVER w
                      - (SUM(p.rn::DECIMAL) OVER w) ^ 2,
                        0)
                ) * SUM(p.rn::DECIMAL) OVER w
            ) / NULLIF(COUNT(*) OVER w, 0)                               AS intercept
        FROM parsed p
        WINDOW w AS (
            PARTITION BY CASE WHEN p_group_by IS NOT NULL THEN p.grp END
            ORDER BY p.rn
            ROWS BETWEEN (p_window_size - 1) PRECEDING AND CURRENT ROW
        )
    ),
    deviation_calc AS (
        SELECT
            tc.rn,
            tc.ts,
            tc.val,
            tc.slope,
            tc.intercept,
            tc.slope * tc.rn + tc.intercept                AS expected,
            tc.val - (tc.slope * tc.rn + tc.intercept)     AS residual
        FROM trend_calc tc
    )
    SELECT
        dc.rn::INTEGER,
        dc.ts,
        dc.val,
        -- Flag if residual exceeds threshold_pct% of expected value
        ABS(dc.residual) > ABS(COALESCE(dc.expected, dc.val)) * (p_threshold_pct / 100.0)
                                                            AS is_anomaly,
        CASE
            WHEN dc.residual >  ABS(COALESCE(dc.expected, dc.val)) * (p_threshold_pct / 100.0) THEN 'high'
            WHEN dc.residual < -ABS(COALESCE(dc.expected, dc.val)) * (p_threshold_pct / 100.0) THEN 'low'
            ELSE 'none'
        END                                                 AS anomaly_direction,
        -- Score: 0 at threshold boundary, scales up from there (capped 100)
        GREATEST(0, LEAST(
            (ABS(dc.residual)
             / NULLIF(ABS(COALESCE(dc.expected, dc.val)) * (p_threshold_pct / 100.0), 0)
             - 1.0) * 50,
            100
        ))                                                  AS anomaly_score,
        'trend_break'::TEXT                                 AS method,
        jsonb_build_object(
            'trend_expected', dc.expected,
            'trend_residual', dc.residual,
            'slope',          dc.slope,
            'intercept',      dc.intercept,
            'threshold_pct',  p_threshold_pct,
            'window_size',    p_window_size
        )                                                   AS context
    FROM deviation_calc dc
    ORDER BY dc.rn;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_anomalies_trend_break IS
'Trend-break anomaly detector: fits a rolling OLS linear regression over
the lookback window and flags points where |actual - projected| > threshold_pct%
of the projected value. Catches anomalies that look normal in absolute terms
but break an established local trend — complements spike detectors.
Accepts any JSONB series: [{"time": "...", "value": ...}].';


-- ============================================================================
-- 6. COMPOSITE — detect_anomalies_composite
-- ============================================================================
-- Orchestrates all four detectors in parallel and merges into one row per point.
-- Each detector casts a weighted vote; ensemble_score is a weighted average.
-- A point is flagged when >= p_min_signals detectors agree (default = 2).
-- All four method scores AND the per-point enrichment context are included
-- for full drilldown capability.
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_anomalies_composite(
    p_data              JSONB,
    p_window_size       INTEGER  DEFAULT 14,
    -- Per-method thresholds
    p_zscore_threshold  DECIMAL  DEFAULT 2.5,
    p_bollinger_std     DECIMAL  DEFAULT 2.0,
    p_iqr_multiplier    DECIMAL  DEFAULT 1.5,
    p_trend_pct         DECIMAL  DEFAULT 15.0,
    -- Ensemble control
    p_min_signals       INTEGER  DEFAULT 2,
    -- Method weights (normalised internally, no need to sum to 1.0)
    p_w_zscore          DECIMAL  DEFAULT 0.30,
    p_w_bollinger       DECIMAL  DEFAULT 0.25,
    p_w_iqr             DECIMAL  DEFAULT 0.25,
    p_w_trend           DECIMAL  DEFAULT 0.20,
    p_group_by          TEXT     DEFAULT NULL
) RETURNS TABLE (
    row_number          INTEGER,
    time_period         TIMESTAMP,
    original_value      DECIMAL(15,4),
    -- Ensemble verdict
    is_anomaly          BOOLEAN,
    anomaly_direction   TEXT,          -- 'high' | 'low' | 'mixed' | 'none'
    ensemble_score      DECIMAL(10,4),
    signals_fired       INTEGER,
    confidence          TEXT,          -- 'high' | 'medium' | 'low' | 'none'
    -- Per-detector drilldown
    zscore_flag         BOOLEAN,
    zscore_score        DECIMAL(10,4),
    bollinger_flag      BOOLEAN,
    bollinger_score     DECIMAL(10,4),
    iqr_flag            BOOLEAN,
    iqr_score           DECIMAL(10,4),
    trend_break_flag    BOOLEAN,
    trend_break_score   DECIMAL(10,4),
    -- Enrichment context (from build_anomaly_context)
    sma                 DECIMAL(15,4),
    upper_band          DECIMAL(15,4),
    lower_band          DECIMAL(15,4),
    moving_mean         DECIMAL(15,4),
    moving_std          DECIMAL(15,4),
    z_score             DECIMAL(10,4),
    pct_change          DECIMAL(10,4)
) AS $$
DECLARE
    v_total_weight DECIMAL;
BEGIN
    v_total_weight := GREATEST(p_w_zscore + p_w_bollinger + p_w_iqr + p_w_trend, 0.0001);

    RETURN QUERY
    WITH
    zs  AS (SELECT * FROM detect_anomalies_zscore(
                p_data, p_window_size, p_zscore_threshold, p_group_by)),
    bb  AS (SELECT * FROM detect_anomalies_bollinger(
                p_data, p_window_size, p_bollinger_std, p_group_by)),
    iq  AS (SELECT * FROM detect_anomalies_iqr(
                p_data, p_window_size, p_iqr_multiplier, p_group_by)),
    tb  AS (SELECT * FROM detect_anomalies_trend_break(
                p_data, p_window_size, p_trend_pct, p_group_by)),
    ctx AS (SELECT * FROM build_anomaly_context(
                p_data, p_window_size, p_bollinger_std, p_group_by)),
    -- ── Merge all signals on row_number ──────────────────────────────
    merged AS (
        SELECT
            ctx.row_number,
            ctx.time_period,
            ctx.original_value,
            COALESCE(zs.is_anomaly,        FALSE) AS zs_flag,
            COALESCE(zs.anomaly_score,     0)     AS zs_score,
            COALESCE(zs.anomaly_direction, 'none')AS zs_dir,
            COALESCE(bb.is_anomaly,        FALSE) AS bb_flag,
            COALESCE(bb.anomaly_score,     0)     AS bb_score,
            COALESCE(bb.anomaly_direction, 'none')AS bb_dir,
            COALESCE(iq.is_anomaly,        FALSE) AS iq_flag,
            COALESCE(iq.anomaly_score,     0)     AS iq_score,
            COALESCE(iq.anomaly_direction, 'none')AS iq_dir,
            COALESCE(tb.is_anomaly,        FALSE) AS tb_flag,
            COALESCE(tb.anomaly_score,     0)     AS tb_score,
            COALESCE(tb.anomaly_direction, 'none')AS tb_dir,
            ctx.sma, ctx.upper_band, ctx.lower_band,
            ctx.moving_mean, ctx.moving_std, ctx.z_score, ctx.pct_change
        FROM ctx
        LEFT JOIN zs ON zs.row_number = ctx.row_number
        LEFT JOIN bb ON bb.row_number = ctx.row_number
        LEFT JOIN iq ON iq.row_number = ctx.row_number
        LEFT JOIN tb ON tb.row_number = ctx.row_number
    ),
    -- ── Ensemble score + direction vote ──────────────────────────────
    ensemble AS (
        SELECT
            m.*,
            (m.zs_flag::INT + m.bb_flag::INT + m.iq_flag::INT + m.tb_flag::INT) AS signals,
            ROUND(
                m.zs_score * (p_w_zscore    / v_total_weight)
              + m.bb_score * (p_w_bollinger / v_total_weight)
              + m.iq_score * (p_w_iqr       / v_total_weight)
              + m.tb_score * (p_w_trend     / v_total_weight),
                2
            ) AS ens_score,
            -- Direction: simple majority vote across methods that fired
            CASE
                WHEN (CASE WHEN m.zs_dir='high' THEN 1 ELSE 0 END
                    + CASE WHEN m.bb_dir='high' THEN 1 ELSE 0 END
                    + CASE WHEN m.iq_dir='high' THEN 1 ELSE 0 END
                    + CASE WHEN m.tb_dir='high' THEN 1 ELSE 0 END)
                   > (CASE WHEN m.zs_dir='low' THEN 1 ELSE 0 END
                    + CASE WHEN m.bb_dir='low' THEN 1 ELSE 0 END
                    + CASE WHEN m.iq_dir='low' THEN 1 ELSE 0 END
                    + CASE WHEN m.tb_dir='low' THEN 1 ELSE 0 END)
                    THEN 'high'
                WHEN (CASE WHEN m.zs_dir='low' THEN 1 ELSE 0 END
                    + CASE WHEN m.bb_dir='low' THEN 1 ELSE 0 END
                    + CASE WHEN m.iq_dir='low' THEN 1 ELSE 0 END
                    + CASE WHEN m.tb_dir='low' THEN 1 ELSE 0 END)
                   > (CASE WHEN m.zs_dir='high' THEN 1 ELSE 0 END
                    + CASE WHEN m.bb_dir='high' THEN 1 ELSE 0 END
                    + CASE WHEN m.iq_dir='high' THEN 1 ELSE 0 END
                    + CASE WHEN m.tb_dir='high' THEN 1 ELSE 0 END)
                    THEN 'low'
                WHEN (m.zs_flag OR m.bb_flag OR m.iq_flag OR m.tb_flag) THEN 'mixed'
                ELSE 'none'
            END AS dir_vote
        FROM merged m
    )
    SELECT
        e.row_number,
        e.time_period,
        e.original_value,
        (e.signals >= p_min_signals)                          AS is_anomaly,
        CASE WHEN e.signals < p_min_signals THEN 'none' ELSE e.dir_vote END
                                                              AS anomaly_direction,
        e.ens_score                                           AS ensemble_score,
        e.signals                                             AS signals_fired,
        CASE
            WHEN e.signals >= 3                               THEN 'high'
            WHEN e.signals = 2 AND e.ens_score >= 60         THEN 'medium'
            WHEN e.signals = 2                               THEN 'low'
            WHEN e.signals = 1 AND e.ens_score >= 75         THEN 'low'
            ELSE 'none'
        END                                                   AS confidence,
        e.zs_flag,  ROUND(e.zs_score, 2),
        e.bb_flag,  ROUND(e.bb_score, 2),
        e.iq_flag,  ROUND(e.iq_score, 2),
        e.tb_flag,  ROUND(e.tb_score, 2),
        e.sma, e.upper_band, e.lower_band,
        e.moving_mean, e.moving_std, e.z_score, e.pct_change
    FROM ensemble e
    ORDER BY e.row_number;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_anomalies_composite IS
'Ensemble anomaly detector: runs Z-score, Bollinger, IQR, and Trend-break
detectors in parallel, merges with a weighted score, and applies a
majority-vote threshold (p_min_signals, default=2).
Each method weight is normalised internally so they never need to sum to 1.
Every row is returned (anomalous or not) for full audit trails.
Use anomaly_summary() to get only the flagged rows ranked by severity.';


-- ============================================================================
-- 7. CONVENIENCE — anomaly_summary
-- ============================================================================
-- Thin wrapper over detect_anomalies_composite that:
--   • Returns ONLY anomalous rows
--   • Ranks them by ensemble_score DESC
--   • Adds a human-readable detectors_flagged column
-- Ideal for dashboards, alerting, and "top N anomalies" reports.
-- ============================================================================

CREATE OR REPLACE FUNCTION anomaly_summary(
    p_data              JSONB,
    p_window_size       INTEGER  DEFAULT 14,
    p_min_signals       INTEGER  DEFAULT 2,
    p_zscore_threshold  DECIMAL  DEFAULT 2.5,
    p_bollinger_std     DECIMAL  DEFAULT 2.0,
    p_iqr_multiplier    DECIMAL  DEFAULT 1.5,
    p_trend_pct         DECIMAL  DEFAULT 15.0,
    p_group_by          TEXT     DEFAULT NULL
) RETURNS TABLE (
    row_number         INTEGER,
    time_period        TIMESTAMP,
    original_value     DECIMAL(15,4),
    anomaly_direction  TEXT,
    ensemble_score     DECIMAL(10,4),
    confidence         TEXT,
    signals_fired      INTEGER,
    detectors_flagged  TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.row_number,
        c.time_period,
        c.original_value,
        c.anomaly_direction,
        c.ensemble_score,
        c.confidence,
        c.signals_fired,
        -- Build a readable list of which detectors fired
        TRIM(BOTH ', ' FROM
            CASE WHEN c.zscore_flag      THEN 'zscore, '      ELSE '' END ||
            CASE WHEN c.bollinger_flag   THEN 'bollinger, '   ELSE '' END ||
            CASE WHEN c.iqr_flag         THEN 'iqr, '         ELSE '' END ||
            CASE WHEN c.trend_break_flag THEN 'trend_break, ' ELSE '' END
        ) AS detectors_flagged
    FROM detect_anomalies_composite(
        p_data,
        p_window_size,
        p_zscore_threshold,
        p_bollinger_std,
        p_iqr_multiplier,
        p_trend_pct,
        p_min_signals,
        0.30, 0.25, 0.25, 0.20,
        p_group_by
    ) c
    WHERE c.is_anomaly
    ORDER BY c.ensemble_score DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION anomaly_summary IS
'Convenience wrapper: returns ONLY anomalous rows from the composite detector,
ranked by ensemble_score (most severe first). Includes a detectors_flagged
column listing which methods agreed. Best for dashboards and alerting.
Use detect_anomalies_composite() when you need every row for audit trails.';


-- ============================================================================
-- FUNCTION MAP — quick reference
-- ============================================================================
/*

  FUNCTION                       PURPOSE                           DEPENDENCIES
  ─────────────────────────────────────────────────────────────────────────────────────────────────
  build_anomaly_context()        Per-point enrichment baseline     calculate_sma
                                 (call once, join to detectors)    calculate_moving_variance
                                                                   calculate_moving_quantiles
                                                                   calculate_percent_change
                                                                   calculate_moving_rank

  detect_anomalies_zscore()      Rolling z-score > threshold       calculate_moving_variance

  detect_anomalies_bollinger()   Bollinger band breach (%B)        calculate_bollinger_bands

  detect_anomalies_iqr()         Tukey IQR fence breach            calculate_moving_quantiles

  detect_anomalies_trend_break() Breaks local OLS trend            (inline regression)

  detect_anomalies_composite()   Weighted ensemble of all four     all four detectors above +
                                 Returns every row                 build_anomaly_context

  anomaly_summary()              Anomalous rows only, ranked        detect_anomalies_composite
  ─────────────────────────────────────────────────────────────────────────────────────────────────

  STANDARD INPUT FORMAT (all functions):
    JSONB array of objects with "time" (TIMESTAMP-castable) and "value" (NUMERIC):
    '[{"time": "2024-01-01", "value": 100}, ...]'

  OPTIONAL GROUPING:
    Pass a p_group_by TEXT matching a JSON key (e.g. 'region') to partition
    all calculations per group: [{"time":"...", "value":100, "region":"EU"}]

*/


-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*

-- ── Test dataset: stable signal with two injected spikes ─────────────────
-- (Use \set in psql, or just paste the literal inline)

\set test_data '[
    {"time": "2024-01-01", "value": 100},
    {"time": "2024-01-02", "value": 102},
    {"time": "2024-01-03", "value": 101},
    {"time": "2024-01-04", "value": 99},
    {"time": "2024-01-05", "value": 103},
    {"time": "2024-01-06", "value": 104},
    {"time": "2024-01-07", "value": 102},
    {"time": "2024-01-08", "value": 280},
    {"time": "2024-01-09", "value": 101},
    {"time": "2024-01-10", "value": 100},
    {"time": "2024-01-11", "value": 98},
    {"time": "2024-01-12", "value": 103},
    {"time": "2024-01-13", "value": 99},
    {"time": "2024-01-14", "value": 102},
    {"time": "2024-01-15", "value": 15},
    {"time": "2024-01-16", "value": 104},
    {"time": "2024-01-17", "value": 105},
    {"time": "2024-01-18", "value": 107},
    {"time": "2024-01-19", "value": 109},
    {"time": "2024-01-20", "value": 250}
]'


-- ── 1. Inspect enriched context for every point ───────────────────────────
SELECT * FROM build_anomaly_context(:'test_data', 7);


-- ── 2. Single-method: Z-score ─────────────────────────────────────────────
SELECT time_period, original_value, is_anomaly, anomaly_score,
       (context->>'z_score')::DECIMAL     AS z_score,
       (context->>'moving_mean')::DECIMAL AS rolling_mean
FROM   detect_anomalies_zscore(:'test_data', 7, 2.5)
ORDER BY row_number;


-- ── 3. Single-method: Bollinger Band ─────────────────────────────────────
SELECT time_period, original_value, is_anomaly,
       (context->>'percent_b')::DECIMAL  AS percent_b,
       (context->>'upper_band')::DECIMAL AS upper_band,
       (context->>'lower_band')::DECIMAL AS lower_band
FROM   detect_anomalies_bollinger(:'test_data', 14, 2.0);


-- ── 4. Single-method: IQR fence (Tukey k=1.5) ────────────────────────────
SELECT time_period, original_value, is_anomaly,
       (context->>'fence_low')::DECIMAL  AS fence_low,
       (context->>'fence_high')::DECIMAL AS fence_high
FROM   detect_anomalies_iqr(:'test_data', 14, 1.5);


-- ── 5. Single-method: Trend break ────────────────────────────────────────
SELECT time_period, original_value, is_anomaly, anomaly_score,
       (context->>'trend_expected')::DECIMAL AS expected,
       (context->>'trend_residual')::DECIMAL AS residual
FROM   detect_anomalies_trend_break(:'test_data', 7, 15.0);


-- ── 6. Composite: all rows with full drilldown ───────────────────────────
SELECT time_period, original_value,
       is_anomaly, anomaly_direction, ensemble_score, confidence,
       signals_fired,
       zscore_flag, bollinger_flag, iqr_flag, trend_break_flag
FROM   detect_anomalies_composite(
           :'test_data',
           p_window_size      => 7,
           p_zscore_threshold => 2.5,
           p_bollinger_std    => 2.0,
           p_iqr_multiplier   => 1.5,
           p_trend_pct        => 15.0,
           p_min_signals      => 2
       );


-- ── 7. Dashboard view: anomalies only, ranked by severity ────────────────
SELECT * FROM anomaly_summary(:'test_data', p_window_size => 7, p_min_signals => 2);


-- ── 8. Strict mode: only flag when ALL four detectors agree ──────────────
SELECT time_period, original_value, ensemble_score, detectors_flagged
FROM   anomaly_summary(:'test_data', p_min_signals => 4);


-- ── 9. Trust trend analysis more (40% weight) ────────────────────────────
SELECT time_period, original_value, is_anomaly, ensemble_score
FROM   detect_anomalies_composite(
           :'test_data',
           p_w_zscore    => 0.20,
           p_w_bollinger => 0.20,
           p_w_iqr       => 0.20,
           p_w_trend     => 0.40
       )
WHERE  is_anomaly;


-- ── 10. Grouped data (multi-series) ──────────────────────────────────────
SELECT * FROM anomaly_summary(
    '[
        {"time": "2024-01-01", "value": 100, "region": "US"},
        {"time": "2024-01-01", "value": 200, "region": "EU"},
        {"time": "2024-01-02", "value": 102, "region": "US"},
        {"time": "2024-01-02", "value": 800, "region": "EU"},
        {"time": "2024-01-03", "value": 101, "region": "US"},
        {"time": "2024-01-03", "value": 205, "region": "EU"}
    ]'::JSONB,
    p_group_by => 'region'
);

*/