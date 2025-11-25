-- Transformation: silver_to_gold_gold_top_10_highest_risk_assets
-- Source: silver.gold_top_10_highest_risk_assets
-- Target: gold.gold_gold_top_10_highest_risk_assets
-- Description: Transform gold_top_10_highest_risk_assets from silver to gold

-- Metric: top_10_highest_risk_assets: The top 10 assets with the highest Attack Surface Index values.
INSERT INTO gold_top_10_highest_risk_assets (asset_id, asi_value)
SELECT asset_id, asi_value
FROM assets_table
WHERE asi_value IS NOT NULL  -- Ensure ASI is valid
ORDER BY asi_value DESC  -- Sort by ASI in descending order
LIMIT 10;  -- Select top 10 assets