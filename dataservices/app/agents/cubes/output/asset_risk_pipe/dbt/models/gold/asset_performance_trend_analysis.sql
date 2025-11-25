{{ config(materialized='table') }}

-- This mart contains a 12-month trend analysis of asset performance, including vulnerabilities, misconfigurations, and external exposures.
SELECT
    a.asset_id,
    a.asset_name,
    a.asset_type,
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities,
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    AVG(CASE WHEN v.severity = 'High' THEN 1.0 ELSE 0.0 END) AS high_risk_vulnerability_ratio,
    AVG(CASE WHEN m.severity = 'Critical' THEN 1.0 ELSE 0.0 END) AS critical_misconfiguration_ratio,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * n.n AS month
FROM
    {{ ref('assets') }} a
LEFT JOIN
    {{ ref('vulnerabilities') }} v ON a.asset_id = v.asset_id
LEFT JOIN
    {{ ref('misconfigurations') }} m ON a.asset_id = m.asset_id
LEFT JOIN
    {{ ref('external_exposure') }} e ON a.asset_id = e.asset_id
CROSS JOIN
    generate_series(0, 11) n
WHERE
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * n.n >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY
    a.asset_id, a.asset_name, a.asset_type, month
ORDER BY
    month DESC;