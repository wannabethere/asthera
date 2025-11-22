-- Monthly Exposure Trends
-- Creates time-series snapshots for 12-month trend analysis
-- Supports likelihood and breach risk trend visualization

CREATE TABLE IF NOT EXISTS gold.exposure_trends_monthly AS
WITH monthly_snapshots AS (
    SELECT 
        DATE_TRUNC('month', asi.calculated_at) AS snapshot_month,
        a.business_unit,
        a.env,
        
        -- Asset counts
        COUNT(DISTINCT asi.asset_id) AS asset_count,
        
        -- ASI metrics
        AVG(asi.attack_surface_index) AS avg_asi,
        MAX(asi.attack_surface_index) AS max_asi,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY asi.attack_surface_index) AS median_asi,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY asi.attack_surface_index) AS p95_asi,
        
        -- Risk distribution
        COUNT(CASE WHEN asi.attack_surface_index >= 70 THEN 1 END) AS high_risk_assets,
        COUNT(CASE WHEN asi.attack_surface_index >= 50 AND asi.attack_surface_index < 70 THEN 1 END) AS medium_risk_assets,
        COUNT(CASE WHEN asi.attack_surface_index < 50 THEN 1 END) AS low_risk_assets,
        
        -- Component scores
        AVG(asi.external_exposure_score) AS avg_external_exposure,
        AVG(asi.vulnerability_exposure_score) AS avg_vulnerability_exposure,
        AVG(asi.misconfiguration_exposure_score) AS avg_misconfiguration_exposure,
        AVG(asi.identity_exposure_score) AS avg_identity_exposure,
        AVG(asi.software_exposure_score) AS avg_software_exposure,
        
        -- Total risk exposure
        SUM(asi.risk_weighted_asi) AS total_risk_exposure,
        
        -- Likelihood metrics (if available)
        AVG(el.asset_exploitability_likelihood) AS avg_likelihood,
        COUNT(CASE WHEN el.asset_exploitability_likelihood >= 0.7 THEN 1 END) AS very_high_likelihood_assets,
        COUNT(CASE WHEN el.asset_exploitability_likelihood >= 0.5 AND el.asset_exploitability_likelihood < 0.7 THEN 1 END) AS high_likelihood_assets,
        
        -- Breach risk indicator (high ASI + high likelihood)
        COUNT(CASE 
            WHEN asi.attack_surface_index >= 70 AND el.asset_exploitability_likelihood >= 0.5 
            THEN 1 
        END) AS high_breach_risk_assets,
        
        CURRENT_TIMESTAMP AS calculated_at
        
    FROM gold.attack_surface_index asi
    JOIN silver.assets a ON asi.asset_id = a.asset_id
    LEFT JOIN gold.exploitability_likelihood el ON asi.asset_id = el.asset_id
    WHERE asi.calculated_at >= DATEADD('month', -12, CURRENT_DATE)
    GROUP BY DATE_TRUNC('month', asi.calculated_at), a.business_unit, a.env
)
SELECT 
    snapshot_month,
    business_unit,
    env,
    asset_count,
    avg_asi,
    max_asi,
    median_asi,
    p95_asi,
    high_risk_assets,
    medium_risk_assets,
    low_risk_assets,
    avg_external_exposure,
    avg_vulnerability_exposure,
    avg_misconfiguration_exposure,
    avg_identity_exposure,
    avg_software_exposure,
    total_risk_exposure,
    avg_likelihood,
    very_high_likelihood_assets,
    high_likelihood_assets,
    high_breach_risk_assets,
    -- Trend indicators (compared to previous month)
    LAG(avg_asi) OVER (PARTITION BY business_unit, env ORDER BY snapshot_month) AS prev_month_avg_asi,
    avg_asi - LAG(avg_asi) OVER (PARTITION BY business_unit, env ORDER BY snapshot_month) AS asi_change,
    LAG(high_breach_risk_assets) OVER (PARTITION BY business_unit, env ORDER BY snapshot_month) AS prev_month_breach_risk,
    high_breach_risk_assets - LAG(high_breach_risk_assets) OVER (PARTITION BY business_unit, env ORDER BY snapshot_month) AS breach_risk_change,
    calculated_at
FROM monthly_snapshots
ORDER BY snapshot_month DESC, business_unit, env;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_trends_month ON gold.exposure_trends_monthly(snapshot_month);
CREATE INDEX IF NOT EXISTS idx_trends_bu ON gold.exposure_trends_monthly(business_unit);
CREATE INDEX IF NOT EXISTS idx_trends_env ON gold.exposure_trends_monthly(env);

