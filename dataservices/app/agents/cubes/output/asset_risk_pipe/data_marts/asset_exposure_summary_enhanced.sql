-- Enhanced Data Mart: asset_exposure_summary
-- Generated: 20251124_084146

CREATE TABLE asset_exposure_summary AS 
SELECT 
    a.asset_id, 
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations, 
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures 
FROM 
    assets a 
LEFT JOIN 
    vulnerabilities v ON v.asset_id = a.asset_id 
LEFT JOIN 
    misconfigurations m ON a.asset_id = m.asset_id 
LEFT JOIN 
    external_exposure e ON a.asset_id = e.asset_id 
GROUP BY 
    a.asset_id; 

-- Index suggestions for performance optimization
-- CREATE INDEX idx_asset_id ON assets(asset_id);
-- CREATE INDEX idx_vulnerability_asset_id ON vulnerabilities(asset_id);
-- CREATE INDEX idx_misconfiguration_asset_id ON misconfigurations(asset_id);
-- CREATE INDEX idx_external_exposure_asset_id ON external_exposure(asset_id);