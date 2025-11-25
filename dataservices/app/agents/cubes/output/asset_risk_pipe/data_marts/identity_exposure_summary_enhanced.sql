-- Enhanced Data Mart: identity_exposure_summary
-- Generated: 20251124_084146

CREATE TABLE identity_exposure_summary AS 
SELECT 
    ie.identity_id, 
    COUNT(ie.exposure_id) AS total_exposures,
    CASE 
        WHEN COUNT(ie.exposure_id) > 0 THEN COUNT(ie.exposure_id) 
        ELSE 0 
    END AS exposure_score -- Exposure score for dashboard visualizations
FROM 
    identity_exposure ie
GROUP BY 
    ie.identity_id; 

-- Index on identity_id for performance optimization
-- CREATE INDEX idx_identity_exposure_identity_id ON identity_exposure(identity_id);