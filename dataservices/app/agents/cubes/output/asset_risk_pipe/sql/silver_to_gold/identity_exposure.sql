-- Transformation: silver_to_gold
-- Table: identity_exposure
-- Generated: 20251120_111506

-- Step: Daily Aggregation - identity_exposure
-- Type: TransformationType.AGGREGATION
-- Description: Daily aggregated metrics


CREATE TABLE gold_identity_exposure_daily AS
SELECT 
    DATE_TRUNC('day', updated_at) as date,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_devices,
    SUM(CASE WHEN is_stale THEN 1 ELSE 0 END) as stale_count
FROM silver_identity_exposure
GROUP BY DATE_TRUNC('day', updated_at);


--------------------------------------------------------------------------------

