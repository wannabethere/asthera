{{ config(materialized='table') }}

-- This model contains a 12-month trend analysis of software asset management,
-- including device counts, misconfigurations, and external exposures related to each software application.

SELECT
    s.software_id,
    s.software_name,
    s.license_type,
    COUNT(DISTINCT s.device_id) AS total_devices,
    SUM(m.misconfiguration_count) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month,
    CASE 
        WHEN SUM(m.misconfiguration_count) > 10 THEN 1.0
        WHEN COUNT(DISTINCT e.exposure_id) > 5 THEN 0.75
        ELSE 0.5
    END AS breach_risk_score,
    CASE 
        WHEN COUNT(DISTINCT s.device_id) > 100 THEN 0.9
        WHEN COUNT(DISTINCT s.device_id) BETWEEN 50 AND 100 THEN 0.7
        ELSE 0.3
    END AS likelihood_score
FROM {{ ref('software_inventory') }} s
LEFT JOIN {{ ref('misconfigurations') }} m ON s.software_id = m.software_id
LEFT JOIN {{ ref('external_exposure') }} e ON s.software_id = e.software_id
JOIN generate_series(0, 11) n ON TRUE
WHERE s.installation_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY s.software_id, s.software_name, s.license_type, month
ORDER BY month;