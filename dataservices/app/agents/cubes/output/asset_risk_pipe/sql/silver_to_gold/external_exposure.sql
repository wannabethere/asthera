-- Transformation: silver_to_gold
-- Table: external_exposure
-- Generated: 20251120_111506

-- Step: Daily Aggregation - external_exposure
-- Type: TransformationType.AGGREGATION
-- Description: Daily aggregated metrics


CREATE TABLE gold_external_exposure_daily AS
SELECT 
    DATE_TRUNC('day', updated_at) as date,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_devices,
    SUM(CASE WHEN is_stale THEN 1 ELSE 0 END) as stale_count
FROM silver_external_exposure
GROUP BY DATE_TRUNC('day', updated_at);


--------------------------------------------------------------------------------

