-- dbt model: Attack Surface by Business Unit
-- Aggregates ASI metrics at business unit level

{{ config(
    materialized='table',
    indexes=[
        {'columns': ['business_unit'], 'unique': True}
    ]
) }}

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
    
FROM {{ ref('attack_surface_index') }}
WHERE business_unit IS NOT NULL
GROUP BY business_unit

