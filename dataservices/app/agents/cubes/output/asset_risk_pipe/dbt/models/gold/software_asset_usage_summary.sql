{{ config(
    materialized='table'  -- Change to 'view' if you prefer a view instead of a table
) }}

-- This model aggregates usage data for software assets, including the number of devices using each software and total usage hours.
SELECT 
    s.software_id, 
    s.software_name, 
    COUNT(DISTINCT s.device_id) AS total_devices_used, 
    SUM(s.usage_hours) AS total_usage_hours,
    CASE 
        WHEN SUM(s.usage_hours) > 0 THEN COUNT(DISTINCT s.device_id) / SUM(s.usage_hours) 
        ELSE 0 
    END AS exposure_score,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM 
    {{ ref('software_inventory') }} s  -- Reference to the software_inventory model
GROUP BY 
    s.software_id, 
    s.software_name
HAVING 
    SUM(s.usage_hours) >= 0 AND COUNT(DISTINCT s.device_id) >= 0;  -- Ensuring constraints on usage hours and devices used