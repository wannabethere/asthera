-- Transformation: silver_to_gold
-- Table: assets
-- Generated: 20251124_084146

-- Step: Daily Aggregation - assets
-- Type: TransformationType.AGGREGATION
-- Description: Daily aggregated metrics


CREATE TABLE gold_assets_daily AS
SELECT 
    DATE_TRUNC('day', updated_at) as date,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_devices,
    SUM(CASE WHEN is_stale THEN 1 ELSE 0 END) as stale_count
FROM silver_assets
GROUP BY DATE_TRUNC('day', updated_at);


--------------------------------------------------------------------------------

