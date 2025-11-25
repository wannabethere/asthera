-- Transformation: silver_to_gold_gold_attack_surface_index
-- Source: silver.gold_attack_surface_index
-- Target: gold.gold_gold_attack_surface_index
-- Description: Transform gold_attack_surface_index from silver to gold

-- Metric: attack_surface_index: The composite Attack Surface Index (ASI) calculated using weighted components.
INSERT INTO gold_attack_surface_index (asset, asi)
SELECT 
    asset,
    SUM(weight * COALESCE(component_value, 0)) AS asi
FROM 
    silver_attack_surface_components
GROUP BY 
    asset;