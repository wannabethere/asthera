{{ config(
    materialized='table'  -- Change to 'view' if you prefer a view instead of a table
) }}

-- This model summarizes external exposure risks categorized by risk type,
-- including the total number of exposures and their potential impact.
SELECT 
    e.risk_category, 
    COUNT(DISTINCT e.exposure_id) AS total_exposures, 
    SUM(e.potential_impact) AS total_potential_impact,
    e.os_software_stack,
    e.business_unit,
    e.environment,
    CURRENT_TIMESTAMP AS created_at,  -- Capture the creation timestamp
    CURRENT_TIMESTAMP AS updated_at   -- Capture the update timestamp
FROM 
    {{ ref('external_exposure') }} e  -- Reference to the external_exposure model/table
GROUP BY 
    e.risk_category, 
    e.os_software_stack, 
    e.business_unit, 
    e.environment