-- Transformation: silver_to_gold_gold_admin_account_count
-- Source: silver.gold_admin_account_count
-- Target: gold.gold_gold_admin_account_count
-- Description: Transform gold_admin_account_count from silver to gold

-- Metric: admin_account_count: Count of admin accounts associated with each asset.
INSERT INTO gold_admin_account_count (asset_id, admin_account_count)
SELECT 
    asset_id,
    COUNT(DISTINCT id) AS admin_account_count  -- Count of distinct active admin accounts
FROM 
    admin_accounts
WHERE 
    status = 'active'  -- Only consider active admin accounts
GROUP BY 
    asset_id;  -- Group by asset_id to get counts per asset