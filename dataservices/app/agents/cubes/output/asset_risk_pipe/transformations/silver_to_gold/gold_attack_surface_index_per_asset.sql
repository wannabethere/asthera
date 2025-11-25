-- Transformation: silver_to_gold_gold_attack_surface_index_per_asset
-- Source: silver.gold_attack_surface_index_per_asset
-- Target: gold.gold_gold_attack_surface_index_per_asset
-- Description: Transform gold_attack_surface_index_per_asset from silver to gold

-- Metric: attack_surface_index_per_asset: The Attack Surface Index (ASI) calculated for each asset.
INSERT INTO gold_attack_surface_index_per_asset (asset_id, attack_surface_index)
SELECT 
    a.asset_id,
    COALESCE(SUM(asi.value), 0) / NULLIF(COUNT(ass.id), 0) AS attack_surface_index
FROM 
    assets_table a
LEFT JOIN 
    assessments_table ass ON a.asset_id = ass.asset_id
LEFT JOIN 
    attack_surface_index_table asi ON ass.id = asi.assessment_id
WHERE 
    ass.timestamp = (SELECT MAX(timestamp) FROM assessments_table WHERE asset_id = a.asset_id)
GROUP BY 
    a.asset_id;