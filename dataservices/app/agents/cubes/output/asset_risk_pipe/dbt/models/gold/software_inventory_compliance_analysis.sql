{{ config(materialized='table') }}

WITH month_series AS (
    SELECT 
        DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * n AS month
    FROM 
        generate_series(0, 11) AS n
),
software_compliance AS (
    SELECT
        si.software_id,
        si.software_name,
        COUNT(si.license_id) AS total_licenses,
        AVG(CASE WHEN si.compliance_status = 'Non-Compliant' THEN 1.0 ELSE 0.0 END) AS non_compliance_ratio,
        ms.month
    FROM
        software_inventory si
    JOIN 
        month_series ms ON ms.month >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
    GROUP BY
        si.software_id, si.software_name, ms.month
)

SELECT 
    software_id,
    software_name,
    COALESCE(total_licenses, 0) AS total_licenses,
    COALESCE(non_compliance_ratio, 0) AS non_compliance_ratio,
    month
FROM 
    software_compliance
ORDER BY 
    month DESC; 

-- Indexes can be added on software_id and month for performance optimization
-- CREATE INDEX idx_software_id ON software_inventory(software_id);
-- CREATE INDEX idx_month ON software_inventory_compliance_analysis(month);