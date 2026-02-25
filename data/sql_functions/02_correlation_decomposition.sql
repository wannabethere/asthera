-- ============================================================================
-- Correlation, Lag Analysis & Dimensional Decomposition Functions
-- ============================================================================
-- Extends the anomaly detection framework with three new capabilities:
--
--   1. find_correlated_metrics()        — rank all metric pairs by correlation
--                                         strength around an anomaly window
--   2. calculate_lag_correlation()      — sweep lag 0..N for a metric pair,
--                                         find which metric LEADS the other
--   3. decompose_impact_by_dimension()  — break an anomaly into segment
--                                         contributions (region, tier, etc.)
--
-- All functions accept the same tall-format metrics table and return
-- structured results ready for the Python orchestration layer.
-- ============================================================================


-- ============================================================================
-- 1. FIND CORRELATED METRICS
-- ============================================================================
-- Given a primary metric and an anomaly timestamp, scan all other metrics
-- in the same window and rank by Pearson correlation strength.
--
-- Logic:
--   • Pull a lookback window (p_lookback_days) ending at p_anomaly_date
--   • For each (primary, other_metric) pair compute corr()
--   • Return ranked by ABS(correlation) DESC
--
-- This answers: "Which other metrics moved with the anomaly?"
-- ============================================================================

CREATE OR REPLACE FUNCTION find_correlated_metrics(
    p_primary_metric    TEXT,
    p_anomaly_date      DATE,
    p_lookback_days     INTEGER DEFAULT 14,
    p_min_correlation   DECIMAL DEFAULT 0.60,   -- filter weak correlations
    p_region            TEXT    DEFAULT NULL,    -- NULL = all regions combined
    p_product_tier      TEXT    DEFAULT NULL
) RETURNS TABLE (
    metric_pair         TEXT,
    primary_metric      TEXT,
    correlated_metric   TEXT,
    correlation         DECIMAL(10,4),
    abs_correlation     DECIMAL(10,4),
    direction           TEXT,     -- 'positive' | 'negative'
    data_points         INTEGER,
    window_start        DATE,
    window_end          DATE
) AS $$
BEGIN
    RETURN QUERY
    WITH
    -- ── Aggregate across dimensions (or filter to specific segment) ───────
    primary_series AS (
        SELECT
            metric_date AS d,
            AVG(metric_value) AS val
        FROM metrics_daily
        WHERE metric_name = p_primary_metric
          AND metric_date BETWEEN p_anomaly_date - p_lookback_days AND p_anomaly_date
          AND (p_region       IS NULL OR region       = p_region)
          AND (p_product_tier IS NULL OR product_tier = p_product_tier)
        GROUP BY metric_date
    ),
    -- ── All OTHER metrics in the same window ──────────────────────────────
    other_metrics AS (
        SELECT
            metric_name AS other_metric,
            metric_date AS d,
            AVG(metric_value) AS val
        FROM metrics_daily
        WHERE metric_name != p_primary_metric
          AND metric_date BETWEEN p_anomaly_date - p_lookback_days AND p_anomaly_date
          AND (p_region       IS NULL OR region       = p_region)
          AND (p_product_tier IS NULL OR product_tier = p_product_tier)
        GROUP BY metric_name, metric_date
    ),
    -- ── Compute Pearson correlation for each pair ─────────────────────────
    correlations AS (
        SELECT
            o.other_metric,
            CORR(p.val, o.val)::DECIMAL(10,4) AS corr_val,
            COUNT(*)::INTEGER                  AS n_points
        FROM primary_series p
        JOIN other_metrics o ON o.d = p.d
        GROUP BY o.other_metric
    )
    SELECT
        p_primary_metric || ' ↔ ' || c.other_metric         AS metric_pair,
        p_primary_metric                                     AS primary_metric,
        c.other_metric                                       AS correlated_metric,
        c.corr_val                                           AS correlation,
        ABS(c.corr_val)                                      AS abs_correlation,
        CASE WHEN c.corr_val >= 0 THEN 'positive' ELSE 'negative' END AS direction,
        c.n_points                                           AS data_points,
        (p_anomaly_date - p_lookback_days)                   AS window_start,
        p_anomaly_date                                       AS window_end
    FROM correlations c
    WHERE ABS(c.corr_val) >= p_min_correlation
    ORDER BY ABS(c.corr_val) DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_correlated_metrics IS
'Scans all metrics in the database and ranks by Pearson correlation strength
against the primary metric within a lookback window ending at the anomaly date.
Answers: "Which other metrics moved with the anomaly?"
Filter p_min_correlation to control noise (default 0.60).';


-- ============================================================================
-- 2. CALCULATE LAG CORRELATION
-- ============================================================================
-- For a specific metric pair, sweep through lags 0..p_max_lag.
-- At each lag, compute corr(primary[t], other[t - lag]).
--
-- Negative lag = other_metric LEADS primary (it moved first — causal candidate)
-- Positive lag = other_metric LAGS primary  (it moved after — effect, not cause)
--
-- This answers: "Which metrics preceded the anomaly? By how many days?"
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_lag_correlation(
    p_primary_metric    TEXT,
    p_other_metric      TEXT,
    p_anomaly_date      DATE,
    p_lookback_days     INTEGER DEFAULT 14,
    p_max_lag           INTEGER DEFAULT 5,   -- sweep -N to +N periods
    p_region            TEXT    DEFAULT NULL,
    p_product_tier      TEXT    DEFAULT NULL
) RETURNS TABLE (
    lag_periods         INTEGER,
    lag_direction       TEXT,    -- 'other_leads' | 'concurrent' | 'other_lags'
    correlation         DECIMAL(10,4),
    abs_correlation     DECIMAL(10,4),
    interpretation      TEXT
) AS $$
DECLARE
    v_lag INTEGER;
BEGIN
    -- Sweep from -p_max_lag to +p_max_lag
    FOR v_lag IN -p_max_lag .. p_max_lag LOOP
        RETURN QUERY
        WITH
        primary_series AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY metric_date) AS rn,
                metric_date AS d,
                AVG(metric_value) AS val
            FROM metrics_daily
            WHERE metric_name = p_primary_metric
              AND metric_date BETWEEN p_anomaly_date - p_lookback_days AND p_anomaly_date
              AND (p_region       IS NULL OR region       = p_region)
              AND (p_product_tier IS NULL OR product_tier = p_product_tier)
            GROUP BY metric_date
        ),
        other_series AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY metric_date) AS rn,
                metric_date AS d,
                AVG(metric_value) AS val
            FROM metrics_daily
            WHERE metric_name = p_other_metric
              AND metric_date BETWEEN p_anomaly_date - p_lookback_days AND p_anomaly_date
              AND (p_region       IS NULL OR region       = p_region)
              AND (p_product_tier IS NULL OR product_tier = p_product_tier)
            GROUP BY metric_date
        ),
        -- Shift other series by lag
        lagged AS (
            SELECT
                p.val AS primary_val,
                LAG(o.val, v_lag) OVER (ORDER BY o.rn) AS other_lagged
            FROM primary_series p
            JOIN other_series o ON o.rn = p.rn
        )
        SELECT
            v_lag,
            CASE
                WHEN v_lag < 0 THEN 'other_leads'
                WHEN v_lag = 0 THEN 'concurrent'
                ELSE 'other_lags'
            END,
            CORR(primary_val, other_lagged)::DECIMAL(10,4),
            ABS(CORR(primary_val, other_lagged))::DECIMAL(10,4),
            CASE
                WHEN v_lag < 0 THEN
                    p_other_metric || ' leads ' || p_primary_metric || ' by ' || ABS(v_lag) || ' day(s)'
                WHEN v_lag = 0 THEN
                    'Metrics move concurrently'
                ELSE
                    p_other_metric || ' lags ' || p_primary_metric || ' by ' || v_lag || ' day(s)'
            END
        FROM lagged
        WHERE other_lagged IS NOT NULL
        HAVING CORR(primary_val, other_lagged) IS NOT NULL;
    END LOOP;

    RETURN;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_lag_correlation IS
'Sweeps lag -N to +N for a metric pair and computes Pearson correlation at
each lag. Negative lag = other_metric LEADS primary (causal candidate).
Positive lag = other_metric LAGS primary (downstream effect).
Answers: "Which metrics moved BEFORE the anomaly, and by how many days?"';


-- ============================================================================
-- 3. DECOMPOSE IMPACT BY DIMENSION
-- ============================================================================
-- Breaks the total anomaly delta into segment-level contributions.
-- Compares actual values in the anomaly period against expected (baseline avg).
--
-- Contribution = (actual_segment - expected_segment) × weight
-- Weight       = segment's share of baseline total
--
-- This answers: "Which region/tier/etc. was responsible for the anomaly?"
-- ============================================================================

CREATE OR REPLACE FUNCTION decompose_impact_by_dimension(
    p_metric_name       TEXT,
    p_anomaly_date      DATE,
    p_dimension         TEXT,        -- 'region' | 'product_tier' | 'region_tier'
    p_baseline_days     INTEGER DEFAULT 7,   -- days before anomaly for expected value
    p_comparison_days   INTEGER DEFAULT 1    -- anomaly window width (1 = single day)
) RETURNS TABLE (
    dimension_value     TEXT,
    baseline_avg        DECIMAL(15,4),
    anomaly_actual      DECIMAL(15,4),
    absolute_delta      DECIMAL(15,4),
    pct_delta           DECIMAL(10,4),
    segment_weight      DECIMAL(10,4),   -- segment's share of baseline total
    contribution_to_total DECIMAL(10,4), -- segment's contribution to overall delta (%)
    impact_rank         INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH
    -- ── Baseline: N days before anomaly ───────────────────────────────────
    baseline AS (
        SELECT
            CASE p_dimension
                WHEN 'region'       THEN region
                WHEN 'product_tier' THEN product_tier
                WHEN 'region_tier'  THEN region || ' / ' || product_tier
                ELSE region
            END AS dim_val,
            AVG(metric_value) AS avg_val,
            SUM(metric_value) AS sum_val
        FROM metrics_daily
        WHERE metric_name = p_metric_name
          AND metric_date BETWEEN
              p_anomaly_date - p_baseline_days - p_comparison_days
              AND p_anomaly_date - 1
        GROUP BY 1
    ),
    -- ── Anomaly period ────────────────────────────────────────────────────
    anomaly_period AS (
        SELECT
            CASE p_dimension
                WHEN 'region'       THEN region
                WHEN 'product_tier' THEN product_tier
                WHEN 'region_tier'  THEN region || ' / ' || product_tier
                ELSE region
            END AS dim_val,
            AVG(metric_value) AS avg_val
        FROM metrics_daily
        WHERE metric_name = p_metric_name
          AND metric_date BETWEEN p_anomaly_date AND p_anomaly_date + p_comparison_days - 1
        GROUP BY 1
    ),
    -- ── Total delta (for contribution %) ──────────────────────────────────
    totals AS (
        SELECT
            SUM(b.sum_val) AS total_baseline_sum,
            SUM(ap.avg_val - b.avg_val) AS total_delta
        FROM baseline b
        JOIN anomaly_period ap ON ap.dim_val = b.dim_val
    ),
    -- ── Per-segment calculation ───────────────────────────────────────────
    deltas AS (
        SELECT
            b.dim_val,
            b.avg_val                                      AS baseline_avg,
            ap.avg_val                                     AS anomaly_actual,
            ap.avg_val - b.avg_val                         AS abs_delta,
            CASE WHEN b.avg_val != 0
                THEN ((ap.avg_val - b.avg_val) / b.avg_val) * 100
                ELSE NULL
            END                                            AS pct_delta,
            b.sum_val / NULLIF(t.total_baseline_sum, 0)   AS seg_weight,
            (ap.avg_val - b.avg_val) / NULLIF(t.total_delta, 0) * 100 AS contribution
        FROM baseline b
        JOIN anomaly_period ap ON ap.dim_val = b.dim_val
        CROSS JOIN totals t
    )
    SELECT
        d.dim_val             AS dimension_value,
        d.baseline_avg,
        d.anomaly_actual,
        d.abs_delta,
        d.pct_delta,
        ROUND(d.seg_weight * 100, 2)  AS segment_weight,
        ROUND(d.contribution, 2)       AS contribution_to_total,
        RANK() OVER (
            ORDER BY ABS(d.contribution) DESC
        )::INTEGER             AS impact_rank
    FROM deltas d
    ORDER BY ABS(d.contribution) DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION decompose_impact_by_dimension IS
'Breaks total anomaly impact into segment-level contributions.
Compares anomaly period values against baseline average.
contribution_to_total shows each segment as % of total delta.
Answers: "Which segment drove most of the anomaly impact?"
Use p_dimension = region_tier for combined breakdown.';


-- ============================================================================
-- 4. BUILD FULL ANOMALY CONTEXT (for LLM payload)
-- ============================================================================
-- Convenience function that assembles the complete structured context
-- for a detected anomaly: stats, top correlations, leading indicators,
-- and dimensional decomposition — all in one call.
-- Returns a single JSONB object ready to send to the explanation layer.
-- ============================================================================

CREATE OR REPLACE FUNCTION build_anomaly_explanation_payload(
    p_primary_metric    TEXT,
    p_anomaly_date      DATE,
    p_lookback_days     INTEGER DEFAULT 14,
    p_region            TEXT    DEFAULT NULL,
    p_product_tier      TEXT    DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_payload       JSONB;
    v_anomaly_val   DECIMAL;
    v_baseline_val  DECIMAL;
    v_pct_change    DECIMAL;
    v_correlations  JSONB;
    v_lag_leaders   JSONB;
    v_decomp        JSONB;
    v_metric_def    RECORD;
BEGIN
    -- ── Anomaly stats ─────────────────────────────────────────────────────
    SELECT AVG(metric_value) INTO v_anomaly_val
    FROM metrics_daily
    WHERE metric_name = p_primary_metric
      AND metric_date = p_anomaly_date
      AND (p_region       IS NULL OR region       = p_region)
      AND (p_product_tier IS NULL OR product_tier = p_product_tier);

    SELECT AVG(metric_value) INTO v_baseline_val
    FROM metrics_daily
    WHERE metric_name = p_primary_metric
      AND metric_date BETWEEN p_anomaly_date - p_lookback_days AND p_anomaly_date - 1
      AND (p_region       IS NULL OR region       = p_region)
      AND (p_product_tier IS NULL OR product_tier = p_product_tier);

    v_pct_change := ((v_anomaly_val - v_baseline_val) / NULLIF(v_baseline_val, 0)) * 100;

    SELECT * INTO v_metric_def FROM metric_definitions WHERE metric_name = p_primary_metric;

    -- ── Correlated metrics ────────────────────────────────────────────────
    SELECT jsonb_agg(
        jsonb_build_object(
            'metric',      correlated_metric,
            'correlation', correlation,
            'direction',   direction
        ) ORDER BY abs_correlation DESC
    ) INTO v_correlations
    FROM find_correlated_metrics(
        p_primary_metric, p_anomaly_date, p_lookback_days,
        0.60, p_region, p_product_tier
    );

    -- ── Leading indicators (lag < 0 = other metric moved first) ───────────
    -- Find the best lag for each correlated metric
    SELECT jsonb_agg(leading ORDER BY abs_corr DESC) INTO v_lag_leaders
    FROM (
        SELECT DISTINCT ON (metric_name)
            jsonb_build_object(
                'metric',         lc.correlated_metric,
                'lag_days',       ABS(lc_detail.lag_periods),
                'correlation',    lc_detail.correlation,
                'interpretation', lc_detail.interpretation
            ) AS leading,
            ABS(lc_detail.correlation) AS abs_corr,
            lc.correlated_metric AS metric_name
        FROM find_correlated_metrics(
            p_primary_metric, p_anomaly_date, p_lookback_days,
            0.60, p_region, p_product_tier
        ) lc
        CROSS JOIN LATERAL (
            SELECT *
            FROM calculate_lag_correlation(
                p_primary_metric, lc.correlated_metric,
                p_anomaly_date, p_lookback_days, 5, p_region, p_product_tier
            )
            WHERE lag_direction = 'other_leads'   -- only care about leading metrics
            ORDER BY abs_correlation DESC
            LIMIT 1
        ) lc_detail
        ORDER BY metric_name, abs_corr DESC
    ) sub;

    -- ── Dimensional decomposition ─────────────────────────────────────────
    SELECT jsonb_agg(
        jsonb_build_object(
            'segment',            dimension_value,
            'baseline',           baseline_avg,
            'actual',             anomaly_actual,
            'pct_change',         pct_delta,
            'contribution_pct',   contribution_to_total,
            'rank',               impact_rank
        ) ORDER BY impact_rank
    ) INTO v_decomp
    FROM decompose_impact_by_dimension(
        p_primary_metric, p_anomaly_date, 'region_tier', p_lookback_days
    );

    -- ── Assemble payload ──────────────────────────────────────────────────
    v_payload := jsonb_build_object(
        'anomaly', jsonb_build_object(
            'metric',           p_primary_metric,
            'display_name',     v_metric_def.display_name,
            'unit',             v_metric_def.unit,
            'direction',        v_metric_def.direction,
            'anomaly_date',     p_anomaly_date,
            'actual_value',     ROUND(v_anomaly_val, 2),
            'baseline_value',   ROUND(v_baseline_val, 2),
            'pct_change',       ROUND(v_pct_change, 1),
            'lookback_days',    p_lookback_days,
            'region_filter',    COALESCE(p_region, 'all'),
            'tier_filter',      COALESCE(p_product_tier, 'all')
        ),
        'correlations',       COALESCE(v_correlations, '[]'::JSONB),
        'leading_indicators', COALESCE(v_lag_leaders, '[]'::JSONB),
        'impact_by_segment',  COALESCE(v_decomp, '[]'::JSONB)
    );

    RETURN v_payload;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION build_anomaly_explanation_payload IS
'Master aggregation function: assembles a complete structured JSONB payload
for a detected anomaly including stats, correlated metrics, leading indicators
(lag analysis), and dimensional decomposition. Feed the result directly to
the Python LLM explanation layer.';


-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- 1. Find what correlated with the revenue anomaly on Jan 15
SELECT * FROM find_correlated_metrics(
    'revenue', '2024-01-15'::DATE, 14, 0.60
);

-- 2. Check if p99_latency led revenue (expect strong lead at lag -2)
SELECT * FROM calculate_lag_correlation(
    'revenue', 'p99_latency_ms', '2024-01-15'::DATE, 14, 5
) ORDER BY abs_correlation DESC;

-- 3. Decompose impact by region × tier
SELECT * FROM decompose_impact_by_dimension(
    'revenue', '2024-01-15'::DATE, 'region_tier', 7
);

-- 4. Build the full payload for the LLM explanation layer
SELECT build_anomaly_explanation_payload(
    'revenue', '2024-01-15'::DATE, 14
);
*/
