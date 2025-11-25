{{ config(materialized='table') }}

-- This model summarizes software assets by department, including total software assets, total licenses, and average usage hours.
SELECT 
    s.department, 
    COUNT(DISTINCT s.id) AS total_software_assets,  -- Count distinct software assets
    COALESCE(SUM(s.license_count), 0) AS total_licenses,  -- Sum of licenses, default to 0 if NULL
    COALESCE(AVG(s.usage_hours), 0) AS avg_usage_hours  -- Average usage hours, default to 0 if NULL
FROM 
    {{ ref('software_inventory') }} s  -- Reference to the software_inventory table
GROUP BY 
    s.department  -- Grouping by department
ORDER BY 
    total_software_assets DESC  -- Order by total software assets in descending order
LIMIT 5;  -- Limit to top 5 departments

-- Index suggestion: CREATE INDEX idx_department ON software_inventory(department);