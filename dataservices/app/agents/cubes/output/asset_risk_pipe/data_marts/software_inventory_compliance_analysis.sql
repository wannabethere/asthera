-- Data Mart: software_inventory_compliance_analysis
-- Goal: Generate 12-month trend analysis for likelihood and breach risk
-- Question: What is the trend of software compliance and license management over the past 12 months?
-- Generated: 20251124_084146

CREATE TABLE software_inventory_compliance_analysis AS SELECT
    si.software_id,
    si.software_name,
    COUNT(si.license_id) AS total_licenses,
    AVG(CASE WHEN si.compliance_status = 'Non-Compliant' THEN 1 ELSE 0 END) AS non_compliance_ratio,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM
    software_inventory si
CROSS JOIN
    generate_series(0, 11) n
WHERE
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY
    si.software_id, si.software_name, month
ORDER BY
    month DESC;