-- Transformation: silver_to_gold_gold_count_high_identity_risk_assets
-- Source: silver.gold_count_high_identity_risk_assets
-- Target: gold.gold_gold_count_high_identity_risk_assets
-- Description: Transform gold_count_high_identity_risk_assets from silver to gold

-- Metric: count_high_identity_risk_assets: Count of assets that are identified as having high identity risk based on the exposure score.
INSERT INTO gold_count_high_identity_risk_assets (asset_count)
SELECT COUNT(*) AS asset_count
FROM assets
WHERE COALESCE(identity_exposure_score, 0) > :high_risk_threshold;