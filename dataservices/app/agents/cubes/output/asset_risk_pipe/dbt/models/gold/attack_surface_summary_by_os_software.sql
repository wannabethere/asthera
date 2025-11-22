{{ config(
    materialized='table'  -- Change to 'view' if you prefer a view instead of a table
) }}

-- This model summarizes the attack surface categorized by operating system, software stack, business unit, and environment.
SELECT 
    a.business_unit, 
    a.environment, 
    a.os, 
    a.software_stack, 
    COUNT(DISTINCT a.asset_id) AS total_assets, 
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations, 
    COUNT(DISTINCT e.exposure_id) AS total_exposures 
FROM 
    {{ ref('assets') }} a 
LEFT JOIN 
    {{ ref('vulnerabilities') }} v ON a.asset_id = v.asset_id 
LEFT JOIN 
    {{ ref('misconfigurations') }} m ON a.asset_id = m.asset_id 
LEFT JOIN 
    {{ ref('external_exposure') }} e ON a.asset_id = e.asset_id 
GROUP BY 
    a.business_unit, a.environment, a.os, a.software_stack