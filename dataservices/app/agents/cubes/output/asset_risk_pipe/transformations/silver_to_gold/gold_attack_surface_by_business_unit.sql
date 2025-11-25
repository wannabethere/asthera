-- Transformation: silver_to_gold_gold_attack_surface_by_business_unit
-- Source: silver.gold_attack_surface_by_business_unit
-- Target: gold.gold_gold_attack_surface_by_business_unit
-- Description: Transform gold_attack_surface_by_business_unit from silver to gold

-- Metric: attack_surface_by_business_unit: Breakdown of attack surfaces by business unit
INSERT INTO gold_attack_surface_by_business_unit (business_unit, attack_surface_count)
SELECT 
    COALESCE(business_unit, 'Unknown') AS business_unit,  -- Handle NULL business units
    COUNT(*) AS attack_surface_count
FROM 
    attack_surface_table
GROUP BY 
    business_unit
ORDER BY 
    business_unit;  -- Optional: Order by business unit for better readability