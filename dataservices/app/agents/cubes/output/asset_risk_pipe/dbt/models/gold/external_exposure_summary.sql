{{ config(materialized='table') }}

-- This mart summarizes external exposures categorized by business unit, environment, and type of exposure.
SELECT 
    e.business_unit, 
    e.environment, 
    e.exposure_type, 
    COUNT(DISTINCT e.exposure_id) AS total_exposures 
FROM 
    {{ ref('external_exposure') }} e 
GROUP BY 
    e.business_unit, 
    e.environment, 
    e.exposure_type;

-- Indexes can be added on business_unit, environment, and exposure_type for performance optimization
-- CREATE INDEX idx_business_unit ON {{ this }} (business_unit);
-- CREATE INDEX idx_environment ON {{ this }} (environment);
-- CREATE INDEX idx_exposure_type ON {{ this }} (exposure_type);