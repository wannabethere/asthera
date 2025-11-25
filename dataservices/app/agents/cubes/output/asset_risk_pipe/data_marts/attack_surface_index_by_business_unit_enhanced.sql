-- Enhanced Data Mart: attack_surface_index_by_business_unit
-- Generated: 20251124_084146

CREATE TABLE attack_surface_index_by_business_unit AS 
SELECT 
    a.business_unit, 
    COUNT(DISTINCT v.id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.id) AS total_misconfigurations, 
    COUNT(DISTINCT e.id) AS total_external_exposures, 
    COUNT(DISTINCT ie.id) AS total_identity_exposures 
FROM 
    assets a 
LEFT JOIN 
    vulnerabilities v ON a.id = v.asset_id 
LEFT JOIN 
    misconfigurations m ON a.id = m.asset_id 
LEFT JOIN 
    external_exposure e ON a.id = e.asset_id 
LEFT JOIN 
    identity_exposure ie ON a.id = ie.asset_id 
GROUP BY 
    a.business_unit 
ORDER BY 
    total_vulnerabilities DESC 
LIMIT 5; 

-- Indexes can be added on business_unit and asset_id columns for performance optimization
-- CREATE INDEX idx_business_unit ON attack_surface_index_by_business_unit (business_unit);
-- CREATE INDEX idx_asset_id ON vulnerabilities (asset_id);
-- CREATE INDEX idx_asset_id_misconfigurations ON misconfigurations (asset_id);
-- CREATE INDEX idx_asset_id_external_exposure ON external_exposure (asset_id);
-- CREATE INDEX idx_asset_id_identity_exposure ON identity_exposure (asset_id);