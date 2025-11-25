-- Transformation: silver_to_gold_gold_component_weight
-- Source: silver.gold_component_weight
-- Target: gold.gold_gold_component_weight
-- Description: Transform gold_component_weight from silver to gold

-- Metric: component_weight: The weight assigned to each component in the ASI calculation.
INSERT INTO gold_component_weight (component, weight)
SELECT 
    component,
    COALESCE(weight, 0) AS weight -- Handle NULL values by replacing with 0
FROM 
    gold_component_weights
WHERE 
    weight IS NOT NULL; -- Ensure only relevant weights are considered