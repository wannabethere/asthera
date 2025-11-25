{{ config(materialized='table') }}

-- This mart contains a summary of the attack surface categorized by operating system, software stack, business unit, and environment.
SELECT 
    a.business_unit, 
    a.environment, 
    a.os, 
    a.software_stack, 
    COUNT(DISTINCT a.asset_id) AS total_assets, 
    COUNT(DISTINCT COALESCE(v.vulnerability_id, NULL)) AS total_vulnerabilities, 
    COUNT(DISTINCT COALESCE(m.misconfiguration_id, NULL)) AS total_misconfigurations 
FROM 
    {{ ref('assets') }} a 
LEFT JOIN 
    {{ ref('vulnerabilities') }} v ON a.asset_id = v.asset_id 
LEFT JOIN 
    {{ ref('misconfigurations') }} m ON a.asset_id = m.asset_id 
GROUP BY 
    a.business_unit, 
    a.environment, 
    a.os, 
    a.software_stack;

-- Index suggestions for performance optimization
-- CREATE INDEX idx_assets_business_unit ON assets(business_unit);
-- CREATE INDEX idx_assets_environment ON assets(environment);
-- CREATE INDEX idx_assets_os ON assets(os);
-- CREATE INDEX idx_assets_software_stack ON assets(software_stack);
-- CREATE INDEX idx_vulnerabilities_asset_id ON vulnerabilities(asset_id);
-- CREATE INDEX idx_misconfigurations_asset_id ON misconfigurations(asset_id);