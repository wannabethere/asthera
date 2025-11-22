{{ config(
    materialized='table'  -- Change to 'view' if you prefer a view instead of a table
) }}

-- This model aggregates exposure scores for each asset, including vulnerabilities, misconfigurations, and external risks.
SELECT 
    a.asset_id, 
    a.asset_name, 
    COALESCE(SUM(v.severity_score), 0) AS total_vulnerability_score, 
    COUNT(DISTINCT v.vulnerability_id) AS vulnerability_count, 
    COALESCE(SUM(m.configuration_issues), 0) AS total_misconfigurations, 
    COALESCE(SUM(e.external_risk_score), 0) AS total_external_exposure,
    (COALESCE(SUM(v.severity_score), 0) + 
     COALESCE(SUM(m.configuration_issues), 0) + 
     COALESCE(SUM(e.external_risk_score), 0)) AS exposure_score,
    CURRENT_TIMESTAMP AS last_updated
FROM 
    {{ ref('assets') }} a 
LEFT JOIN 
    {{ ref('vulnerabilities') }} v ON a.asset_id = v.asset_id 
LEFT JOIN 
    {{ ref('misconfigurations') }} m ON a.asset_id = m.asset_id 
LEFT JOIN 
    {{ ref('external_exposure') }} e ON a.asset_id = e.asset_id 
GROUP BY 
    a.asset_id, a.asset_name;