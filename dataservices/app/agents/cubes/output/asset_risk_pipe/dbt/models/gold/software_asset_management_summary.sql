{{ config(materialized='table') }}

-- This model provides a summary of software assets, including their usage 
-- and associated vulnerabilities and misconfigurations.
SELECT 
    s.software_name, 
    s.version, 
    COUNT(DISTINCT s.device_id) AS total_devices, 
    COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, 
    COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations,
    s.business_unit,
    s.environment,
    CURRENT_TIMESTAMP AS last_updated
FROM 
    {{ ref('software_inventory') }} s 
LEFT JOIN 
    {{ ref('vulnerabilities') }} v ON s.software_id = v.software_id 
LEFT JOIN 
    {{ ref('misconfigurations') }} m ON s.software_id = m.software_id 
GROUP BY 
    s.software_name, s.version, s.business_unit, s.environment