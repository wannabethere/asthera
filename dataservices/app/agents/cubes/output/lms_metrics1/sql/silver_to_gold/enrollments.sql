-- Transformation: silver_to_gold
-- Table: enrollments
-- Generated: 20251121_132228

-- Step: Daily Aggregation - enrollments
-- Type: TransformationType.AGGREGATION
-- Description: Daily aggregated metrics


CREATE TABLE gold_enrollments_daily AS
SELECT 
    DATE_TRUNC('day', updated_at) as date,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_devices,
    SUM(CASE WHEN is_stale THEN 1 ELSE 0 END) as stale_count
FROM silver_enrollments
GROUP BY DATE_TRUNC('day', updated_at);


--------------------------------------------------------------------------------

