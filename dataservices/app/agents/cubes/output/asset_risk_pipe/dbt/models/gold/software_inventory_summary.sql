{{ config(materialized='table') }}

WITH software_data AS (
    SELECT 
        si.software_id,
        COUNT(si.license_id) AS total_licenses,
        SUM(COALESCE(si.usage_hours, 0)) AS total_usage_hours
    FROM 
        {{ ref('software_inventory') }} si
    GROUP BY 
        si.software_id
)

SELECT 
    software_id,
    total_licenses,
    total_usage_hours,
    CASE 
        WHEN total_licenses > 0 THEN total_usage_hours / NULLIF(total_licenses, 0) 
        ELSE 0 
    END AS exposure_score -- Calculating exposure score as total usage hours per license
FROM 
    software_data;

-- Index on software_id for performance optimization
-- CREATE INDEX idx_software_inventory_summary_software_id ON {{ this }}(software_id);