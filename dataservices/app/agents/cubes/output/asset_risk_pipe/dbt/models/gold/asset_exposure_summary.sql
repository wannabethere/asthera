{{ config(materialized='table') }}

-- This mart aggregates exposure scores related to assets by counting vulnerabilities, misconfigurations, and external exposures.
SELECT 
    a.asset_id, 
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations, 
    COUNT(DISTINCT e.exposure_id) AS total_external_exposures 
FROM 
    {{ ref('assets') }} a 
LEFT JOIN 
    {{ ref('vulnerabilities') }} v ON v.asset_id = a.asset_id 
LEFT JOIN 
    {{ ref('misconfigurations') }} m ON a.asset_id = m.asset_id 
LEFT JOIN 
    {{ ref('external_exposure') }} e ON a.asset_id = e.asset_id 
GROUP BY 
    a.asset_id; 

-- Index suggestions for performance optimization
-- CREATE INDEX idx_asset_id ON assets(asset_id);
-- CREATE INDEX idx_vulnerability_asset_id ON vulnerabilities(asset_id);
-- CREATE INDEX idx_misconfiguration_asset_id ON misconfigurations(asset_id);
-- CREATE INDEX idx_external_exposure_asset_id ON external_exposure(asset_id);