-- Transformation: silver_to_gold_gold_stale_account_count
-- Source: silver.gold_stale_account_count
-- Target: gold.gold_gold_stale_account_count
-- Description: Transform gold_stale_account_count from silver to gold

-- Metric: stale_account_count: Count of stale accounts associated with each asset.
INSERT INTO gold_stale_account_count (asset_id, stale_account_count)
SELECT 
    asset_id,
    COUNT(DISTINCT account_id) AS stale_account_count
FROM 
    stale_accounts
WHERE 
    account_status = 'stale'  -- Assuming there is a status column to identify stale accounts
GROUP BY 
    asset_id;