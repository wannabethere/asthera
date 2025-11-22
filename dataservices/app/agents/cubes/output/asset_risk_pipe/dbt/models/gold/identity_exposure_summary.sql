{{ config(
    materialized='table'  -- Change to 'view' if you prefer a view instead of a table
) }}

-- This model aggregates data on identity exposure incidents, including total incidents and average severity levels.
SELECT 
    i.identity_id, 
    COUNT(i.exposure_id) AS total_exposure_incidents, 
    AVG(i.severity_level) AS average_severity, 
    CURRENT_TIMESTAMP AS last_updated  -- Adding last_updated as the current timestamp
FROM 
    {{ ref('identity_exposure') }} AS i  -- Reference to the identity_exposure table
GROUP BY 
    i.identity_id