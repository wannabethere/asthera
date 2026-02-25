-- ============================================================================
-- Sample Data: SaaS Platform Metrics
-- ============================================================================
-- Scenario: E-commerce / SaaS checkout platform
--
-- Metrics tracked daily:
--   revenue            — daily transaction revenue ($)
--   api_error_rate     — % of API calls returning errors
--   p99_latency_ms     — 99th percentile API response time (ms)
--   cart_abandonment   — % of carts abandoned before checkout
--   conversion_rate    — % of sessions converting to purchase
--
-- Dimensions:
--   region      — US | EU | APAC
--   product_tier — pro | enterprise
--
-- Injected anomaly sequence (causal chain):
--   Jan 13 → p99_latency spikes in EU (infrastructure issue begins)
--   Jan 14 → api_error_rate climbs (cascade from latency)
--   Jan 14 → cart_abandonment rises (users giving up on slow checkout)
--   Jan 15 → revenue drops 58% (the visible anomaly the user sees)
--   Jan 16 → gradual recovery begins
--
-- The pipeline should discover:
--   WHAT:  Revenue dropped 58% on Jan 15
--   WHERE: 79% of the impact from EU / Enterprise segment
--   WHY:   p99_latency led by 2 days → api_error_rate led by 1 day
--          → cart_abandonment coincident → revenue crash
-- ============================================================================

-- ── Schema ──────────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS metrics_daily CASCADE;
DROP TABLE IF EXISTS metric_definitions CASCADE;

CREATE TABLE metric_definitions (
    metric_name     TEXT PRIMARY KEY,
    display_name    TEXT,
    unit            TEXT,
    direction       TEXT,   -- 'higher_better' | 'lower_better'
    base_value      DECIMAL(15,4),
    description     TEXT
);

CREATE TABLE metrics_daily (
    id              SERIAL PRIMARY KEY,
    metric_date     DATE         NOT NULL,
    metric_name     TEXT         NOT NULL REFERENCES metric_definitions(metric_name),
    region          TEXT         NOT NULL,
    product_tier    TEXT         NOT NULL,
    metric_value    DECIMAL(15,4) NOT NULL,
    is_injected     BOOLEAN      DEFAULT FALSE  -- marks deliberately injected anomaly rows
);

CREATE INDEX idx_metrics_daily_date   ON metrics_daily(metric_date);
CREATE INDEX idx_metrics_daily_metric ON metrics_daily(metric_name);
CREATE INDEX idx_metrics_daily_segment ON metrics_daily(region, product_tier);

-- ── Metric definitions ───────────────────────────────────────────────────────

INSERT INTO metric_definitions VALUES
    ('revenue',          'Daily Revenue',            'USD',  'higher_better', 10000, 'Daily transaction revenue per segment'),
    ('api_error_rate',   'API Error Rate',            '%',    'lower_better',  0.5,  'Percentage of API calls returning 4xx/5xx'),
    ('p99_latency_ms',   'P99 API Latency',           'ms',   'lower_better',  200,  '99th percentile API response time in milliseconds'),
    ('cart_abandonment', 'Cart Abandonment Rate',     '%',    'lower_better',  30,   'Percentage of shopping carts abandoned before purchase'),
    ('conversion_rate',  'Session Conversion Rate',   '%',    'higher_better', 3.2,  'Percentage of sessions that result in a completed purchase');


-- ── Helper: generate normally-distributed noise ──────────────────────────────
-- (used inline via RANDOM() approximation — Box-Muller not needed for demo)

-- ── Seed data: 20 days × 5 metrics × 3 regions × 2 tiers = 600 rows ─────────
-- Normal baseline: Jan 1-12 and Jan 16-20
-- Anomaly window:  Jan 13-15

INSERT INTO metrics_daily (metric_date, metric_name, region, product_tier, metric_value, is_injected)
WITH
-- date spine
dates AS (
    SELECT generate_series(
        '2024-01-01'::DATE,
        '2024-01-20'::DATE,
        '1 day'::INTERVAL
    )::DATE AS d
),
segments AS (
    SELECT * FROM (VALUES
        ('US',   'pro'),
        ('US',   'enterprise'),
        ('EU',   'pro'),
        ('EU',   'enterprise'),
        ('APAC', 'pro'),
        ('APAC', 'enterprise')
    ) AS t(region, product_tier)
),
-- base multipliers per segment (enterprise pays ~3x pro)
segment_base AS (
    SELECT
        region,
        product_tier,
        CASE region
            WHEN 'US'   THEN 1.0
            WHEN 'EU'   THEN 0.85
            WHEN 'APAC' THEN 0.60
        END *
        CASE product_tier
            WHEN 'enterprise' THEN 3.2
            WHEN 'pro'        THEN 1.0
        END AS revenue_mult,
        CASE region
            WHEN 'US'   THEN 1.0
            WHEN 'EU'   THEN 0.95
            WHEN 'APAC' THEN 1.05
        END AS latency_mult
    FROM segments
),
-- ── REVENUE (normal + anomaly) ────────────────────────────────────────────
rev AS (
    SELECT
        d.d AS metric_date,
        'revenue' AS metric_name,
        sb.region,
        sb.product_tier,
        -- Base: $10,000 × segment multiplier + small daily noise + weekend dip
        10000 * sb.revenue_mult
        * CASE WHEN EXTRACT(DOW FROM d.d) IN (0,6) THEN 0.75 ELSE 1.0 END
        * (1 + (RANDOM() - 0.5) * 0.06)
        -- Anomaly: Jan 14 EU starts dropping, Jan 15 is the crash
        * CASE
            WHEN d.d = '2024-01-14' AND sb.region = 'EU' THEN 0.72
            WHEN d.d = '2024-01-15' AND sb.region = 'EU' AND sb.product_tier = 'enterprise' THEN 0.38
            WHEN d.d = '2024-01-15' AND sb.region = 'EU' AND sb.product_tier = 'pro'        THEN 0.45
            WHEN d.d = '2024-01-15' AND sb.region = 'US'   THEN 0.91  -- mild spillover
            WHEN d.d = '2024-01-16' AND sb.region = 'EU'   THEN 0.68  -- partial recovery
            WHEN d.d = '2024-01-17' AND sb.region = 'EU'   THEN 0.84
            ELSE 1.0
          END AS metric_value,
        (d.d BETWEEN '2024-01-14' AND '2024-01-17' AND sb.region = 'EU') AS is_injected
    FROM dates d CROSS JOIN segment_base sb
),
-- ── P99 LATENCY (spikes Jan 13 EU — the leading indicator) ────────────────
lat AS (
    SELECT
        d.d,
        'p99_latency_ms',
        sb.region,
        sb.product_tier,
        200 * sb.latency_mult
        * (1 + (RANDOM() - 0.5) * 0.08)
        * CASE
            WHEN d.d = '2024-01-13' AND sb.region = 'EU' THEN 3.8   -- first spike
            WHEN d.d = '2024-01-14' AND sb.region = 'EU' THEN 4.5   -- worsening
            WHEN d.d = '2024-01-15' AND sb.region = 'EU' THEN 3.2   -- still high
            WHEN d.d = '2024-01-16' AND sb.region = 'EU' THEN 2.1   -- recovering
            WHEN d.d = '2024-01-17' AND sb.region = 'EU' THEN 1.4
            ELSE 1.0
          END,
        (d.d BETWEEN '2024-01-13' AND '2024-01-17' AND sb.region = 'EU')
    FROM dates d CROSS JOIN segment_base sb
),
-- ── API ERROR RATE (spikes Jan 14 EU — one day after latency) ─────────────
err AS (
    SELECT
        d.d,
        'api_error_rate',
        sb.region,
        sb.product_tier,
        0.5
        * (1 + (RANDOM() - 0.5) * 0.15)
        * CASE
            WHEN d.d = '2024-01-13' AND sb.region = 'EU' THEN 1.8   -- small rise
            WHEN d.d = '2024-01-14' AND sb.region = 'EU' THEN 9.2   -- spike
            WHEN d.d = '2024-01-15' AND sb.region = 'EU' THEN 7.6
            WHEN d.d = '2024-01-16' AND sb.region = 'EU' THEN 3.1
            WHEN d.d = '2024-01-17' AND sb.region = 'EU' THEN 1.5
            ELSE 1.0
          END,
        (d.d BETWEEN '2024-01-13' AND '2024-01-17' AND sb.region = 'EU')
    FROM dates d CROSS JOIN segment_base sb
),
-- ── CART ABANDONMENT (spikes Jan 14 EU — coincident with errors) ──────────
cart AS (
    SELECT
        d.d,
        'cart_abandonment',
        sb.region,
        sb.product_tier,
        30.0
        * (1 + (RANDOM() - 0.5) * 0.05)
        * CASE
            WHEN d.d = '2024-01-14' AND sb.region = 'EU' THEN 2.1
            WHEN d.d = '2024-01-15' AND sb.region = 'EU' THEN 2.4
            WHEN d.d = '2024-01-16' AND sb.region = 'EU' THEN 1.8
            WHEN d.d = '2024-01-17' AND sb.region = 'EU' THEN 1.3
            ELSE 1.0
          END,
        (d.d BETWEEN '2024-01-14' AND '2024-01-17' AND sb.region = 'EU')
    FROM dates d CROSS JOIN segment_base sb
),
-- ── CONVERSION RATE (drops Jan 14-15 EU) ──────────────────────────────────
conv AS (
    SELECT
        d.d,
        'conversion_rate',
        sb.region,
        sb.product_tier,
        3.2
        * (1 + (RANDOM() - 0.5) * 0.06)
        * CASE
            WHEN d.d = '2024-01-14' AND sb.region = 'EU' THEN 0.52
            WHEN d.d = '2024-01-15' AND sb.region = 'EU' THEN 0.41
            WHEN d.d = '2024-01-16' AND sb.region = 'EU' THEN 0.65
            WHEN d.d = '2024-01-17' AND sb.region = 'EU' THEN 0.82
            ELSE 1.0
          END,
        (d.d BETWEEN '2024-01-14' AND '2024-01-17' AND sb.region = 'EU')
    FROM dates d CROSS JOIN segment_base sb
)
SELECT * FROM rev
UNION ALL SELECT * FROM lat
UNION ALL SELECT * FROM err
UNION ALL SELECT * FROM cart
UNION ALL SELECT * FROM conv;


-- ── Verification queries ─────────────────────────────────────────────────────

/*
-- Check row count (expect 600)
SELECT COUNT(*) FROM metrics_daily;

-- Spot check the anomaly window
SELECT metric_date, metric_name, region, product_tier,
       ROUND(metric_value, 2) AS value, is_injected
FROM   metrics_daily
WHERE  metric_date BETWEEN '2024-01-12' AND '2024-01-17'
  AND  region = 'EU'
ORDER  BY metric_name, metric_date, product_tier;

-- Aggregated daily revenue to see the drop
SELECT metric_date,
       ROUND(SUM(CASE WHEN metric_name = 'revenue' THEN metric_value END), 0) AS total_revenue,
       ROUND(AVG(CASE WHEN metric_name = 'p99_latency_ms' THEN metric_value END), 0) AS avg_latency,
       ROUND(AVG(CASE WHEN metric_name = 'api_error_rate' THEN metric_value END), 2) AS avg_errors
FROM   metrics_daily
GROUP  BY metric_date
ORDER  BY metric_date;
*/
