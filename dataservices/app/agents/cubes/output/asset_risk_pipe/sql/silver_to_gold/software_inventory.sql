-- Transformation: silver_to_gold
-- Table: software_inventory
-- Generated: 20251120_111506

-- Step: Daily Aggregation - software_inventory
-- Type: TransformationType.AGGREGATION
-- Description: Daily aggregated metrics


CREATE TABLE gold_software_inventory_daily AS
SELECT 
    DATE_TRUNC('day', updated_at) as date,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_devices,
    SUM(CASE WHEN is_stale THEN 1 ELSE 0 END) as stale_count
FROM silver_software_inventory
GROUP BY DATE_TRUNC('day', updated_at);


--------------------------------------------------------------------------------

