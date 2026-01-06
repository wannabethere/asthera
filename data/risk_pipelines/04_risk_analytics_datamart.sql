-- ============================================================================
-- UNIVERSAL RISK ANALYTICS DATA MARTS
-- ============================================================================
-- Dimensional models for risk analytics with survival analysis
-- Supports: Trend analysis, survival curves, risk scoring, impact tracking
-- ============================================================================

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- ============================================================================
-- Date Dimension (comprehensive calendar table)
-- ============================================================================
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    date_actual DATE NOT NULL UNIQUE,
    
    -- Date components
    day_of_week INTEGER,
    day_name VARCHAR(10),
    day_of_month INTEGER,
    day_of_year INTEGER,
    
    -- Week attributes
    week_of_year INTEGER,
    iso_week INTEGER,
    week_start_date DATE,
    week_end_date DATE,
    
    -- Month attributes
    month_number INTEGER,
    month_name VARCHAR(10),
    month_start_date DATE,
    month_end_date DATE,
    
    -- Quarter attributes
    quarter_number INTEGER,
    quarter_name VARCHAR(2),
    quarter_start_date DATE,
    quarter_end_date DATE,
    
    -- Year attributes
    year_number INTEGER,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    
    -- Flags
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    is_business_day BOOLEAN,
    
    -- Special periods
    is_month_end BOOLEAN,
    is_quarter_end BOOLEAN,
    is_year_end BOOLEAN
);

-- Generate date dimension for 10 years
INSERT INTO dim_date
SELECT 
    TO_CHAR(date_actual, 'YYYYMMDD')::INTEGER as date_key,
    date_actual,
    EXTRACT(DOW FROM date_actual) as day_of_week,
    TO_CHAR(date_actual, 'Day') as day_name,
    EXTRACT(DAY FROM date_actual) as day_of_month,
    EXTRACT(DOY FROM date_actual) as day_of_year,
    EXTRACT(WEEK FROM date_actual) as week_of_year,
    EXTRACT(ISOYEAR FROM date_actual) * 100 + EXTRACT(WEEK FROM date_actual) as iso_week,
    DATE_TRUNC('week', date_actual)::DATE as week_start_date,
    (DATE_TRUNC('week', date_actual) + INTERVAL '6 days')::DATE as week_end_date,
    EXTRACT(MONTH FROM date_actual) as month_number,
    TO_CHAR(date_actual, 'Month') as month_name,
    DATE_TRUNC('month', date_actual)::DATE as month_start_date,
    (DATE_TRUNC('month', date_actual) + INTERVAL '1 month - 1 day')::DATE as month_end_date,
    EXTRACT(QUARTER FROM date_actual) as quarter_number,
    'Q' || EXTRACT(QUARTER FROM date_actual) as quarter_name,
    DATE_TRUNC('quarter', date_actual)::DATE as quarter_start_date,
    (DATE_TRUNC('quarter', date_actual) + INTERVAL '3 months - 1 day')::DATE as quarter_end_date,
    EXTRACT(YEAR FROM date_actual) as year_number,
    CASE 
        WHEN EXTRACT(MONTH FROM date_actual) >= 7 THEN EXTRACT(YEAR FROM date_actual) + 1
        ELSE EXTRACT(YEAR FROM date_actual)
    END as fiscal_year,
    CASE 
        WHEN EXTRACT(MONTH FROM date_actual) >= 7 THEN EXTRACT(QUARTER FROM date_actual) - 2
        ELSE EXTRACT(QUARTER FROM date_actual) + 2
    END as fiscal_quarter,
    EXTRACT(DOW FROM date_actual) IN (0, 6) as is_weekend,
    FALSE as is_holiday,
    EXTRACT(DOW FROM date_actual) NOT IN (0, 6) as is_business_day,
    date_actual = (DATE_TRUNC('month', date_actual) + INTERVAL '1 month - 1 day')::DATE as is_month_end,
    date_actual = (DATE_TRUNC('quarter', date_actual) + INTERVAL '3 months - 1 day')::DATE as is_quarter_end,
    date_actual = (DATE_TRUNC('year', date_actual) + INTERVAL '1 year - 1 day')::DATE as is_year_end
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL) as date_actual;

CREATE INDEX idx_dim_date_actual ON dim_date(date_actual);
CREATE INDEX idx_dim_date_month ON dim_date(year_number, month_number);
CREATE INDEX idx_dim_date_quarter ON dim_date(year_number, quarter_number);

-- ============================================================================
-- Entity Dimension (SCD Type 2 - slowly changing dimension)
-- ============================================================================
CREATE TABLE dim_entity (
    entity_key SERIAL PRIMARY KEY,
    entity_id VARCHAR(200) NOT NULL,  -- Natural key
    
    -- Entity attributes
    entity_type VARCHAR(50),  -- 'employee', 'customer', 'asset', 'vendor', etc.
    entity_name VARCHAR(500),
    entity_category VARCHAR(100),
    entity_subcategory VARCHAR(100),
    
    -- Hierarchy (for drill-down)
    level_1 VARCHAR(200),  -- Department, Business Unit, etc.
    level_2 VARCHAR(200),
    level_3 VARCHAR(200),
    level_4 VARCHAR(200),
    
    -- Business attributes
    business_criticality VARCHAR(20),  -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    risk_classification VARCHAR(50),
    
    -- Geographic attributes
    region VARCHAR(100),
    country VARCHAR(100),
    state_province VARCHAR(100),
    city VARCHAR(100),
    
    -- SCD Type 2 fields
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (entity_id, effective_start_date)
);

CREATE INDEX idx_dim_entity_id ON dim_entity(entity_id);
CREATE INDEX idx_dim_entity_current ON dim_entity(entity_id, is_current) WHERE is_current = TRUE;
CREATE INDEX idx_dim_entity_type ON dim_entity(entity_type);
CREATE INDEX idx_dim_entity_hierarchy ON dim_entity(level_1, level_2, level_3);

-- ============================================================================
-- Risk Domain Dimension
-- ============================================================================
CREATE TABLE dim_risk_domain (
    domain_key SERIAL PRIMARY KEY,
    domain_code VARCHAR(50) NOT NULL UNIQUE,
    domain_name VARCHAR(200) NOT NULL,
    domain_category VARCHAR(50),  -- 'operational', 'financial', 'compliance', etc.
    
    -- Risk framework alignment
    risk_framework VARCHAR(50),  -- 'COSO', 'ISO31000', 'NIST', etc.
    regulatory_requirement VARCHAR(200),
    
    -- Metadata
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed data
INSERT INTO dim_risk_domain (domain_code, domain_name, domain_category, risk_framework) VALUES
('hr_attrition', 'Employee Attrition', 'operational', 'COSO'),
('security_vuln', 'Vulnerability Exploitation', 'operational', 'NIST'),
('customer_churn', 'Customer Churn', 'financial', 'COSO'),
('supply_chain', 'Supply Chain Disruption', 'operational', 'ISO31000'),
('compliance', 'Regulatory Compliance', 'compliance', 'SOX'),
('fraud', 'Fraud Detection', 'financial', 'COSO'),
('cyber_threat', 'Cybersecurity Threat', 'operational', 'NIST');

-- ============================================================================
-- Risk Factor Dimension
-- ============================================================================
CREATE TABLE dim_risk_factor (
    factor_key SERIAL PRIMARY KEY,
    factor_code VARCHAR(100) NOT NULL,
    factor_name VARCHAR(200) NOT NULL,
    factor_category VARCHAR(50),  -- 'likelihood', 'impact', 'temporal'
    
    -- Factor properties
    data_source VARCHAR(200),
    measurement_unit VARCHAR(50),
    normal_range_min DECIMAL(10,2),
    normal_range_max DECIMAL(10,2),
    
    -- Metadata
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE (factor_code)
);

-- ============================================================================
-- FACT TABLES
-- ============================================================================

-- ============================================================================
-- Fact Risk Assessment (grain: one row per entity per assessment date)
-- ============================================================================
CREATE TABLE fact_risk_assessment (
    assessment_key BIGSERIAL PRIMARY KEY,
    
    -- Dimension foreign keys
    entity_key INTEGER NOT NULL REFERENCES dim_entity(entity_key),
    assessment_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    domain_key INTEGER NOT NULL REFERENCES dim_risk_domain(domain_key),
    
    -- Risk scores (the measures)
    overall_risk_score DECIMAL(10,2) NOT NULL,
    likelihood_score DECIMAL(10,2) NOT NULL,
    impact_score DECIMAL(10,2) NOT NULL,
    
    -- Risk categorization
    risk_level VARCHAR(20),  -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    risk_level_numeric INTEGER,  -- 5, 4, 3, 2, 1 for easy sorting
    
    -- Detailed impact breakdown
    direct_impact DECIMAL(10,2),
    indirect_impact DECIMAL(10,2),
    cascading_impact DECIMAL(10,2),
    
    -- Confidence and quality metrics
    transfer_confidence DECIMAL(5,2),
    data_quality_score DECIMAL(5,2),
    model_version VARCHAR(20),
    
    -- Survival analysis fields
    days_since_first_at_risk INTEGER,  -- Tenure in risk state
    is_censored BOOLEAN DEFAULT FALSE,  -- Has event occurred yet?
    
    -- Change detection
    risk_score_change DECIMAL(10,2),  -- Change from previous assessment
    risk_level_change VARCHAR(20),  -- 'INCREASED', 'DECREASED', 'STABLE'
    days_since_last_assessment INTEGER,
    
    -- Audit
    assessment_id VARCHAR(100),  -- Reference to source assessment
    assessed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_fact_risk_entity ON fact_risk_assessment(entity_key, assessment_date_key);
CREATE INDEX idx_fact_risk_domain ON fact_risk_assessment(domain_key);
CREATE INDEX idx_fact_risk_date ON fact_risk_assessment(assessment_date_key);
CREATE INDEX idx_fact_risk_level ON fact_risk_assessment(risk_level, domain_key);
CREATE INDEX idx_fact_risk_score ON fact_risk_assessment(overall_risk_score DESC);

-- Partitioning by date for large-scale deployments
-- CREATE TABLE fact_risk_assessment_2026_q1 PARTITION OF fact_risk_assessment
--     FOR VALUES FROM ('20260101') TO ('20260401');

-- ============================================================================
-- Fact Risk Factor Detail (grain: one row per factor per assessment)
-- ============================================================================
CREATE TABLE fact_risk_factor_detail (
    factor_detail_key BIGSERIAL PRIMARY KEY,
    
    -- Foreign keys
    assessment_key BIGINT NOT NULL REFERENCES fact_risk_assessment(assessment_key),
    factor_key INTEGER NOT NULL REFERENCES dim_risk_factor(factor_key),
    
    -- Factor measurements
    raw_value DECIMAL(10,2),
    normalized_value DECIMAL(10,2),  -- 0-100 scale
    decayed_value DECIMAL(10,2),  -- After applying decay function
    weighted_score DECIMAL(10,2),  -- Contribution to overall risk
    
    -- Configuration used
    weight_applied DECIMAL(5,3),
    decay_function VARCHAR(50),
    decay_rate DECIMAL(5,3),
    time_delta DECIMAL(10,2),
    
    -- Contribution analysis
    contribution_percentage DECIMAL(5,2),  -- % of total risk from this factor
    is_primary_driver BOOLEAN,  -- Top 3 factors
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fact_factor_assessment ON fact_risk_factor_detail(assessment_key);
CREATE INDEX idx_fact_factor_key ON fact_risk_factor_detail(factor_key);
CREATE INDEX idx_fact_factor_contribution ON fact_risk_factor_detail(contribution_percentage DESC);

-- ============================================================================
-- Fact Survival Events (for survival analysis)
-- ============================================================================
CREATE TABLE fact_survival_events (
    event_key BIGSERIAL PRIMARY KEY,
    
    -- Dimension foreign keys
    entity_key INTEGER NOT NULL REFERENCES dim_entity(entity_key),
    event_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    domain_key INTEGER NOT NULL REFERENCES dim_risk_domain(domain_key),
    
    -- Event identification
    event_type VARCHAR(50) NOT NULL,  -- 'attrition', 'exploitation', 'churn', etc.
    event_occurred BOOLEAN NOT NULL,  -- TRUE = event happened, FALSE = censored
    
    -- Survival analysis variables
    entry_date DATE NOT NULL,  -- When entity entered risk cohort
    exit_date DATE,  -- When event occurred or censoring happened
    survival_time_days INTEGER NOT NULL,  -- Days from entry to event/censoring
    
    -- Risk scores at key timepoints
    risk_score_at_entry DECIMAL(10,2),
    risk_score_at_30_days DECIMAL(10,2),
    risk_score_at_60_days DECIMAL(10,2),
    risk_score_at_90_days DECIMAL(10,2),
    risk_score_at_event DECIMAL(10,2),
    
    -- Trajectory metrics
    risk_trend VARCHAR(20),  -- 'INCREASING', 'DECREASING', 'STABLE'
    peak_risk_score DECIMAL(10,2),
    days_to_peak_risk INTEGER,
    
    -- Intervention tracking
    intervention_applied BOOLEAN,
    intervention_type VARCHAR(100),
    days_to_intervention INTEGER,
    
    -- Cohort analysis
    cohort_month DATE,  -- Month when entity entered at-risk state
    cohort_quarter DATE,
    cohort_fiscal_year INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fact_survival_entity ON fact_survival_events(entity_key);
CREATE INDEX idx_fact_survival_domain ON fact_survival_events(domain_key);
CREATE INDEX idx_fact_survival_cohort ON fact_survival_events(cohort_month, domain_key);
CREATE INDEX idx_fact_survival_time ON fact_survival_events(survival_time_days);
CREATE INDEX idx_fact_survival_event ON fact_survival_events(event_occurred, domain_key);

-- ============================================================================
-- Fact Risk Trends (aggregated snapshots for performance)
-- ============================================================================
CREATE TABLE fact_risk_trends (
    trend_key BIGSERIAL PRIMARY KEY,
    
    -- Grain: domain + date + aggregation level
    domain_key INTEGER NOT NULL REFERENCES dim_risk_domain(domain_key),
    snapshot_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    aggregation_level VARCHAR(50) NOT NULL,  -- 'daily', 'weekly', 'monthly'
    
    -- Aggregation dimensions (optional)
    entity_type VARCHAR(50),
    level_1 VARCHAR(200),
    risk_level VARCHAR(20),
    
    -- Aggregated measures
    total_entities INTEGER,
    total_assessments INTEGER,
    
    -- Risk score statistics
    avg_risk_score DECIMAL(10,2),
    median_risk_score DECIMAL(10,2),
    stddev_risk_score DECIMAL(10,2),
    min_risk_score DECIMAL(10,2),
    max_risk_score DECIMAL(10,2),
    p95_risk_score DECIMAL(10,2),
    
    -- Distribution counts
    count_critical INTEGER,
    count_high INTEGER,
    count_medium INTEGER,
    count_low INTEGER,
    
    -- Change metrics
    avg_risk_change DECIMAL(10,2),
    entities_increased INTEGER,
    entities_decreased INTEGER,
    entities_stable INTEGER,
    
    -- Event statistics (if available)
    events_occurred INTEGER,
    event_rate DECIMAL(5,4),
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (domain_key, snapshot_date_key, aggregation_level, entity_type, level_1, risk_level)
);

CREATE INDEX idx_fact_trends_domain_date ON fact_risk_trends(domain_key, snapshot_date_key);
CREATE INDEX idx_fact_trends_level ON fact_risk_trends(aggregation_level);

-- ============================================================================
-- BRIDGE TABLES (for many-to-many relationships)
-- ============================================================================

-- ============================================================================
-- Bridge: Assessment to Recommendations
-- ============================================================================
CREATE TABLE bridge_assessment_recommendations (
    assessment_key BIGINT NOT NULL REFERENCES fact_risk_assessment(assessment_key),
    recommendation_sequence INTEGER NOT NULL,
    recommendation_text TEXT NOT NULL,
    recommendation_priority VARCHAR(20),  -- 'URGENT', 'HIGH', 'MEDIUM', 'LOW'
    recommendation_category VARCHAR(50),  -- 'PREVENTIVE', 'DETECTIVE', 'CORRECTIVE'
    
    PRIMARY KEY (assessment_key, recommendation_sequence)
);

-- ============================================================================
-- ANALYTICS VIEWS
-- ============================================================================

-- ============================================================================
-- Current Risk Snapshot (Latest assessment per entity)
-- ============================================================================
CREATE VIEW v_current_risk_snapshot AS
WITH latest_assessments AS (
    SELECT 
        entity_key,
        domain_key,
        MAX(assessment_date_key) as latest_date_key
    FROM fact_risk_assessment
    GROUP BY entity_key, domain_key
)
SELECT 
    e.entity_id,
    e.entity_name,
    e.entity_type,
    e.level_1,
    d.domain_name,
    f.overall_risk_score,
    f.likelihood_score,
    f.impact_score,
    f.risk_level,
    f.risk_score_change,
    f.days_since_last_assessment,
    dt.date_actual as assessment_date
FROM latest_assessments la
JOIN fact_risk_assessment f ON la.entity_key = f.entity_key 
    AND la.domain_key = f.domain_key 
    AND la.latest_date_key = f.assessment_date_key
JOIN dim_entity e ON f.entity_key = e.entity_key AND e.is_current = TRUE
JOIN dim_risk_domain d ON f.domain_key = d.domain_key
JOIN dim_date dt ON f.assessment_date_key = dt.date_key;

-- ============================================================================
-- Risk Trend Analysis (30-day moving average)
-- ============================================================================
CREATE VIEW v_risk_trends_30day AS
SELECT 
    e.entity_id,
    e.entity_name,
    d.domain_name,
    dt.date_actual,
    f.overall_risk_score,
    AVG(f.overall_risk_score) OVER (
        PARTITION BY f.entity_key, f.domain_key 
        ORDER BY f.assessment_date_key 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as moving_avg_30day,
    f.overall_risk_score - LAG(f.overall_risk_score, 1) OVER (
        PARTITION BY f.entity_key, f.domain_key 
        ORDER BY f.assessment_date_key
    ) as day_over_day_change,
    f.overall_risk_score - LAG(f.overall_risk_score, 7) OVER (
        PARTITION BY f.entity_key, f.domain_key 
        ORDER BY f.assessment_date_key
    ) as week_over_week_change
FROM fact_risk_assessment f
JOIN dim_entity e ON f.entity_key = e.entity_key
JOIN dim_risk_domain d ON f.domain_key = d.domain_key
JOIN dim_date dt ON f.assessment_date_key = dt.date_key;

-- ============================================================================
-- Survival Cohort Analysis
-- ============================================================================
CREATE VIEW v_survival_cohorts AS
SELECT 
    d.domain_name,
    s.cohort_month,
    s.event_occurred,
    COUNT(*) as cohort_size,
    AVG(s.survival_time_days) as avg_survival_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY s.survival_time_days) as median_survival_days,
    AVG(s.risk_score_at_entry) as avg_entry_risk,
    AVG(CASE WHEN s.event_occurred THEN s.risk_score_at_event END) as avg_event_risk,
    SUM(CASE WHEN s.intervention_applied THEN 1 ELSE 0 END) as interventions_count,
    AVG(CASE WHEN s.intervention_applied THEN s.survival_time_days END) as avg_survival_with_intervention
FROM fact_survival_events s
JOIN dim_risk_domain d ON s.domain_key = d.domain_key
GROUP BY d.domain_name, s.cohort_month, s.event_occurred;

-- ============================================================================
-- Top Risk Drivers (by contribution)
-- ============================================================================
CREATE VIEW v_top_risk_drivers AS
WITH ranked_factors AS (
    SELECT 
        e.entity_id,
        e.entity_name,
        d.domain_name,
        rf.factor_name,
        frd.weighted_score,
        frd.contribution_percentage,
        dt.date_actual,
        ROW_NUMBER() OVER (
            PARTITION BY fra.entity_key, fra.domain_key, fra.assessment_date_key 
            ORDER BY frd.contribution_percentage DESC
        ) as factor_rank
    FROM fact_risk_factor_detail frd
    JOIN fact_risk_assessment fra ON frd.assessment_key = fra.assessment_key
    JOIN dim_entity e ON fra.entity_key = e.entity_key
    JOIN dim_risk_domain d ON fra.domain_key = d.domain_key
    JOIN dim_risk_factor rf ON frd.factor_key = rf.factor_key
    JOIN dim_date dt ON fra.assessment_date_key = dt.date_key
)
SELECT * FROM ranked_factors WHERE factor_rank <= 5;

-- ============================================================================
-- MATERIALIZED VIEWS (for performance)
-- ============================================================================

-- ============================================================================
-- Daily Risk Summary (refresh nightly)
-- ============================================================================
CREATE MATERIALIZED VIEW mv_daily_risk_summary AS
SELECT 
    d.domain_key,
    d.domain_name,
    dt.date_key,
    dt.date_actual,
    COUNT(DISTINCT f.entity_key) as total_entities,
    AVG(f.overall_risk_score) as avg_risk_score,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.overall_risk_score) as median_risk_score,
    COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') as critical_count,
    COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') as high_count,
    COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') as medium_count,
    COUNT(*) FILTER (WHERE f.risk_level = 'LOW') as low_count,
    AVG(f.transfer_confidence) as avg_confidence
FROM fact_risk_assessment f
JOIN dim_risk_domain d ON f.domain_key = d.domain_key
JOIN dim_date dt ON f.assessment_date_key = dt.date_key
GROUP BY d.domain_key, d.domain_name, dt.date_key, dt.date_actual;

CREATE UNIQUE INDEX idx_mv_daily_risk ON mv_daily_risk_summary(domain_key, date_key);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_risk_analytics_marts()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_risk_summary;
    -- Add other materialized views here
    
    -- Update fact_risk_trends
    INSERT INTO fact_risk_trends (
        domain_key,
        snapshot_date_key,
        aggregation_level,
        total_entities,
        total_assessments,
        avg_risk_score,
        median_risk_score,
        count_critical,
        count_high,
        count_medium,
        count_low
    )
    SELECT 
        domain_key,
        date_key,
        'daily',
        total_entities,
        total_entities,  -- Same as count for daily
        avg_risk_score,
        median_risk_score,
        critical_count,
        high_count,
        medium_count,
        low_count
    FROM mv_daily_risk_summary
    WHERE date_key = TO_CHAR(CURRENT_DATE, 'YYYYMMDD')::INTEGER
    ON CONFLICT DO NOTHING;
    
    RAISE NOTICE 'Risk analytics marts refreshed successfully';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS & DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE fact_risk_assessment IS 'Core fact table containing risk assessments with likelihood, impact, and overall scores';
COMMENT ON TABLE fact_survival_events IS 'Survival analysis events tracking time-to-event with censoring';
COMMENT ON TABLE fact_risk_factor_detail IS 'Detailed breakdown of risk factors contributing to each assessment';
COMMENT ON TABLE fact_risk_trends IS 'Pre-aggregated risk trends for fast dashboard queries';
COMMENT ON TABLE dim_entity IS 'Slowly changing dimension for entities being assessed (Type 2 SCD)';
COMMENT ON TABLE dim_date IS 'Calendar dimension for time-based analysis';
COMMENT ON TABLE dim_risk_domain IS 'Risk domain classification (HR, Security, Finance, etc.)';
COMMENT ON TABLE dim_risk_factor IS 'Individual risk factors that contribute to overall risk';

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

/*
-- Query 1: Current high-risk entities
SELECT * FROM v_current_risk_snapshot
WHERE risk_level IN ('CRITICAL', 'HIGH')
ORDER BY overall_risk_score DESC
LIMIT 100;

-- Query 2: Risk trend for specific entity
SELECT 
    date_actual,
    overall_risk_score,
    moving_avg_30day,
    week_over_week_change
FROM v_risk_trends_30day
WHERE entity_id = 'USR12345'
    AND domain_name = 'Employee Attrition'
ORDER BY date_actual DESC;

-- Query 3: Survival analysis - Kaplan-Meier estimation
WITH survival_data AS (
    SELECT 
        domain_name,
        survival_time_days,
        event_occurred::INTEGER as event
    FROM fact_survival_events s
    JOIN dim_risk_domain d ON s.domain_key = d.domain_key
    WHERE domain_name = 'Employee Attrition'
)
SELECT 
    survival_time_days,
    COUNT(*) as at_risk,
    SUM(event) as events,
    1.0 - (SUM(SUM(event)) OVER (ORDER BY survival_time_days) * 1.0 / 
           SUM(COUNT(*)) OVER ()) as survival_probability
FROM survival_data
GROUP BY survival_time_days
ORDER BY survival_time_days;

-- Query 4: Top risk drivers across organization
SELECT 
    domain_name,
    factor_name,
    AVG(contribution_percentage) as avg_contribution,
    COUNT(*) as frequency
FROM v_top_risk_drivers
WHERE factor_rank = 1
GROUP BY domain_name, factor_name
ORDER BY avg_contribution DESC;

-- Query 5: Risk score distribution
SELECT 
    domain_name,
    date_actual,
    avg_risk_score,
    median_risk_score,
    critical_count,
    high_count,
    medium_count,
    low_count
FROM mv_daily_risk_summary
WHERE date_actual >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY domain_name, date_actual;
*/
