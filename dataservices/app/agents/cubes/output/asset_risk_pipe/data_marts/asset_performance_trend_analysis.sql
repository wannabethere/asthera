-- Data Mart: asset_performance_trend_analysis
-- Goal: Generate 12-month trend analysis for likelihood and breach risk
-- Question: What is the trend of vulnerabilities, misconfigurations, and external exposures for each asset over the past 12 months?
-- Generated: 20251124_084146

CREATE TABLE asset_performance_trend_analysis AS SELECT
    a.asset_id,
    a.asset_name,
    a.asset_type,
    COUNT(v.vulnerability_id) AS total_vulnerabilities,
    COUNT(m.misconfiguration_id) AS total_misconfigurations,
    COUNT(e.exposure_id) AS total_external_exposures,
    AVG(CASE WHEN v.severity = 'High' THEN 1 ELSE 0 END) AS high_risk_vulnerability_ratio,
    AVG(CASE WHEN m.severity = 'Critical' THEN 1 ELSE 0 END) AS critical_misconfiguration_ratio,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM
    assets a
LEFT JOIN
    vulnerabilities v ON a.asset_id = v.asset_id
LEFT JOIN
    misconfigurations m ON a.asset_id = m.asset_id
LEFT JOIN
    external_exposure e ON a.asset_id = e.asset_id
CROSS JOIN
    generate_series(0, 11) n
WHERE
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY
    a.asset_id, a.asset_name, a.asset_type, month
ORDER BY
    month DESC;