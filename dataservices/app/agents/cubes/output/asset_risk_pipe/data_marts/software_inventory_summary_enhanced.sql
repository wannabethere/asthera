-- Enhanced Data Mart: software_inventory_summary
-- Generated: 20251124_084146

CREATE TABLE software_inventory_summary AS 
SELECT 
    si.software_id, 
    COUNT(si.license_id) AS total_licenses, 
    SUM(COALESCE(si.usage_hours, 0)) AS total_usage_hours, 
    CASE 
        WHEN COUNT(si.license_id) > 0 THEN SUM(COALESCE(si.usage_hours, 0)) / NULLIF(COUNT(si.license_id), 0) 
        ELSE 0 
    END AS exposure_score -- Calculating exposure score as total usage hours per license
FROM 
    software_inventory si 
GROUP BY 
    si.software_id; 

-- Index on software_id for performance optimization
-- CREATE INDEX idx_software_inventory_summary_software_id ON software_inventory_summary(software_id);