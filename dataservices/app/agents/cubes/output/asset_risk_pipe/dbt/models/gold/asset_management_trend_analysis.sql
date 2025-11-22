{{ config(materialized='table') }}

-- This model contains a 12-month trend analysis of asset management, including risk scores, vulnerabilities, misconfigurations, and exposures related to each asset.
SELECT
    a.asset_id,
    a.asset_type,
    a.acquisition_date,
    a.depreciation_value,
    SUM(v.risk_score) AS total_risk_score,
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities,
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    COUNT(DISTINCT i.identity_exposure_id) AS total_identity_exposures,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month,
    SUM(v.risk_score) / NULLIF(COUNT(DISTINCT v.vulnerability_id), 0) AS risk_breach_likelihood,
    SUM(v.risk_score) * 0.1 AS risk_breach_score
FROM {{ ref('assets') }} a
LEFT JOIN {{ ref('vulnerabilities') }} v ON a.asset_id = v.asset_id
LEFT JOIN {{ ref('misconfigurations') }} m ON a.asset_id = m.asset_id
LEFT JOIN {{ ref('external_exposure') }} e ON a.asset_id = e.asset_id
LEFT JOIN {{ ref('identity_exposure') }} i ON a.asset_id = i.asset_id
JOIN generate_series(0, 11) n ON TRUE
WHERE a.acquisition_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY a.asset_id, a.asset_type, a.acquisition_date, a.depreciation_value, month
ORDER BY month;