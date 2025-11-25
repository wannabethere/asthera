-- Transformation: silver_to_gold_gold_distribution_of_attack_surface_index
-- Source: silver.gold_distribution_of_attack_surface_index
-- Target: gold.gold_gold_distribution_of_attack_surface_index
-- Description: Transform gold_distribution_of_attack_surface_index from silver to gold

-- Metric: distribution_of_attack_surface_index: The distribution of Attack Surface Index values across all assets.
INSERT INTO gold_distribution_of_attack_surface_index (attack_surface_index, asset_count)
SELECT 
    attack_surface_index,
    COUNT(*) AS asset_count
FROM 
    assets_table
WHERE 
    attack_surface_index IS NOT NULL  -- Ensure only valid ASI values are considered
GROUP BY 
    attack_surface_index
ORDER BY 
    attack_surface_index;  -- Optional: Order by ASI for better readability