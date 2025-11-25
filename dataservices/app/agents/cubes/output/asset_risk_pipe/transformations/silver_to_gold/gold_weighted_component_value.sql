-- Transformation: silver_to_gold_gold_weighted_component_value
-- Source: silver.gold_weighted_component_value
-- Target: gold.gold_gold_weighted_component_value
-- Description: Transform gold_weighted_component_value from silver to gold

-- Metric: weighted_component_value: The value of each component weighted according to its importance.
INSERT INTO gold_weighted_component_value (asset, component, weighted_value)
SELECT 
    asset,
    component,
    SUM(COALESCE(value, 0) * COALESCE(weight, 0)) AS weighted_value
FROM (
    SELECT 
        asset,
        component,
        value,
        weight,
        SUM(weight) OVER (PARTITION BY asset) AS total_weight
    FROM 
        silver_attack_surface_components
) AS subquery
WHERE 
    total_weight > 0  -- Ensure weights are normalized
GROUP BY 
    asset, component;