-- Attack Surface by Business Unit
-- Aggregates ASI metrics at business unit level for dashboard visualization
-- Includes top 5 rankings and contribution analysis

CREATE TABLE IF NOT EXISTS gold.attack_surface_by_bu AS
WITH bu_aggregates AS (
    SELECT 
        business_unit,
        COUNT(DISTINCT asset_id) AS total_assets,
        AVG(attack_surface_index) AS avg_asi,
        MAX(attack_surface_index) AS max_asi,
        MIN(attack_surface_index) AS min_asi,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY attack_surface_index) AS median_asi,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY attack_surface_index) AS p75_asi,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY attack_surface_index) AS p95_asi,
        
        -- Component scores
        AVG(external_exposure_score) AS avg_external_exposure,
        AVG(vulnerability_exposure_score) AS avg_vulnerability_exposure,
        AVG(misconfiguration_exposure_score) AS avg_misconfiguration_exposure,
        AVG(identity_exposure_score) AS avg_identity_exposure,
        AVG(software_exposure_score) AS avg_software_exposure,
        
        -- Risk-weighted metrics
        AVG(risk_weighted_asi) AS avg_risk_weighted_asi,
        SUM(risk_weighted_asi) AS total_risk_exposure,
        
        -- High-risk asset counts
        COUNT(CASE WHEN attack_surface_index >= 70 THEN 1 END) AS high_risk_assets,
        COUNT(CASE WHEN attack_surface_index >= 50 AND attack_surface_index < 70 THEN 1 END) AS medium_risk_assets,
        COUNT(CASE WHEN attack_surface_index < 50 THEN 1 END) AS low_risk_assets,
        
        -- Criticality distribution
        AVG(criticality) AS avg_criticality,
        COUNT(CASE WHEN criticality >= 80 THEN 1 END) AS critical_assets,
        
        CURRENT_TIMESTAMP AS calculated_at
        
    FROM gold.attack_surface_index
    WHERE business_unit IS NOT NULL
    GROUP BY business_unit
),
bu_rankings AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (ORDER BY avg_asi DESC) AS rank_by_avg_asi,
        ROW_NUMBER() OVER (ORDER BY total_risk_exposure DESC) AS rank_by_total_risk,
        ROW_NUMBER() OVER (ORDER BY high_risk_assets DESC) AS rank_by_high_risk_count,
        -- Contribution percentage
        (total_risk_exposure * 100.0 / SUM(total_risk_exposure) OVER ()) AS risk_contribution_pct
    FROM bu_aggregates
)
SELECT 
    business_unit,
    total_assets,
    avg_asi,
    max_asi,
    min_asi,
    median_asi,
    p75_asi,
    p95_asi,
    avg_external_exposure,
    avg_vulnerability_exposure,
    avg_misconfiguration_exposure,
    avg_identity_exposure,
    avg_software_exposure,
    avg_risk_weighted_asi,
    total_risk_exposure,
    risk_contribution_pct,
    high_risk_assets,
    medium_risk_assets,
    low_risk_assets,
    avg_criticality,
    critical_assets,
    rank_by_avg_asi,
    rank_by_total_risk,
    rank_by_high_risk_count,
    CASE 
        WHEN rank_by_avg_asi <= 5 THEN TRUE 
        ELSE FALSE 
    END AS is_top_5_by_exposure,
    calculated_at
FROM bu_rankings;

-- Create index
CREATE INDEX IF NOT EXISTS idx_asi_bu_business_unit ON gold.attack_surface_by_bu(business_unit);

