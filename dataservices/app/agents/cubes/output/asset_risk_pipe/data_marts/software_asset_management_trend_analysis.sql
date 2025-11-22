-- Data Mart: software_asset_management_trend_analysis
-- Goal: Generate 12-month trend analysis for likelihood and breach risk
-- Question: What is the 12-month trend of software usage and compliance across devices?
-- Generated: 20251120_111506

CREATE TABLE software_asset_management_trend_analysis AS SELECT
    s.software_id,
    s.software_name,
    s.license_type,
    COUNT(DISTINCT s.device_id) AS total_devices,
    SUM(m.misconfiguration_count) AS total_misconfigurations,
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM software_inventory s
LEFT JOIN misconfigurations m ON s.software_id = m.software_id
LEFT JOIN external_exposure e ON s.software_id = e.software_id
JOIN generate_series(0, 11) n ON TRUE
WHERE s.installation_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY s.software_id, s.software_name, s.license_type, month
ORDER BY month;