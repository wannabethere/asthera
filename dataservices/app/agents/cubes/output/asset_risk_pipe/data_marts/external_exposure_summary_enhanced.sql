-- Enhanced Data Mart: external_exposure_summary
-- Generated: 20251124_084146

CREATE TABLE external_exposure_summary AS 
SELECT 
    e.business_unit, 
    e.environment, 
    e.exposure_type, 
    COUNT(DISTINCT e.exposure_id) AS total_exposures 
FROM 
    external_exposure e 
GROUP BY 
    e.business_unit, 
    e.environment, 
    e.exposure_type; 

-- Indexes can be added on business_unit, environment, and exposure_type for performance optimization
-- CREATE INDEX idx_business_unit ON external_exposure_summary (business_unit);
-- CREATE INDEX idx_environment ON external_exposure_summary (environment);
-- CREATE INDEX idx_exposure_type ON external_exposure_summary (exposure_type);