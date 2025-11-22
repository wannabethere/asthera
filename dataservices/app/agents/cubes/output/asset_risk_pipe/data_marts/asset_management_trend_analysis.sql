-- Data Mart: asset_management_trend_analysis
-- Goal: Generate 12-month trend analysis for likelihood and breach risk
-- Question: What is the 12-month trend of risk scores and vulnerabilities for each asset?
-- Generated: 20251120_111506

CREATE TABLE asset_management_trend_analysis AS SELECT
    a.asset_id,
    a.asset_type,
    a.acquisition_date,
    a.depreciation_value,
    SUM(v.risk_score) AS total_risk_score,
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities,
    COUNT(DISTINCT m misconfiguration_id) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    COUNT(DISTINCT i.identity_exposure_id) AS total_identity_exposures,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM assets a
LEFT JOIN vulnerabilities v ON a.asset_id = v.asset_id
LEFT JOIN misconfigurations m ON a.asset_id = m.asset_id
LEFT JOIN external_exposure e ON a.asset_id = e.asset_id
LEFT JOIN identity_exposure i ON a.asset_id = i.asset_id
JOIN generate_series(0, 11) n ON TRUE
WHERE a.acquisition_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY a.asset_id, a.asset_type, a.acquisition_date, a.depreciation_value, month
ORDER BY month;