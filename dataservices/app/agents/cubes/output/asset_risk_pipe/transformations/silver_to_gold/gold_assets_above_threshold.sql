-- Transformation: silver_to_gold_gold_assets_above_threshold
-- Source: silver.gold_assets_above_threshold
-- Target: gold.gold_gold_assets_above_threshold
-- Description: Transform gold_assets_above_threshold from silver to gold

-- Metric: assets_above_threshold: Count of assets with a vulnerability exposure score greater than 0.5.
INSERT INTO gold_assets_above_threshold (asset_count)
SELECT COUNT(*) AS asset_count
FROM assets_table
WHERE COALESCE(vulnerability_exposure_score, 0) > 0.5;