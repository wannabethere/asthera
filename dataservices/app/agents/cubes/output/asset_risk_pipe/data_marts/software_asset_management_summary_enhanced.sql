-- Enhanced Data Mart: software_asset_management_summary
-- Generated: 20251124_084146

CREATE TABLE software_asset_management_summary AS 
SELECT 
    s.department, 
    COUNT(DISTINCT s.id) AS total_software_assets, 
    COALESCE(SUM(s.license_count), 0) AS total_licenses, 
    COALESCE(AVG(s.usage_hours), 0) AS avg_usage_hours 
FROM 
    software_inventory s 
GROUP BY 
    s.department 
ORDER BY 
    total_software_assets DESC 
LIMIT 5; 

-- Index suggestion: CREATE INDEX idx_department ON software_inventory(department);