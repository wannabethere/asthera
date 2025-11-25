{{ config(materialized='table') }}

-- This mart summarizes the exposure of sensitive identity information by counting instances of exposure per identity.
SELECT 
    ie.identity_id, 
    COUNT(ie.exposure_id) AS total_exposures,
    COALESCE(COUNT(ie.exposure_id), 0) AS exposure_score -- Exposure score for dashboard visualizations
FROM 
    {{ ref('identity_exposure') }} ie
GROUP BY 
    ie.identity_id;

-- Index on identity_id for performance optimization
-- CREATE INDEX idx_identity_exposure_identity_id ON identity_exposure(identity_id);