-- Transformation: silver_to_gold_gold_total_attack_surface
-- Source: silver.gold_total_attack_surface
-- Target: gold.gold_gold_total_attack_surface
-- Description: Transform gold_total_attack_surface from silver to gold

-- Metric: total_attack_surface: Total number of attack surface elements identified per business unit
INSERT INTO gold_total_attack_surface (business_unit, total_attack_surface_elements)
SELECT 
    business_unit,
    COUNT(DISTINCT attack_surface_element) AS total_attack_surface_elements
FROM 
    attack_surface_table
WHERE 
    business_unit IS NOT NULL  -- Ensure business unit is not NULL
    AND is_active = TRUE        -- Only include active business units
GROUP BY 
    business_unit;