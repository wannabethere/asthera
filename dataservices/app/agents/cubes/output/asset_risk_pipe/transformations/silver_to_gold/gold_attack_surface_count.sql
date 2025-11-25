-- Transformation: silver_to_gold_gold_attack_surface_count
-- Source: silver.gold_attack_surface_count
-- Target: gold.gold_gold_attack_surface_count
-- Description: Transform gold_attack_surface_count from silver to gold

-- Metric: attack_surface_count: Total number of attack surfaces identified
INSERT INTO gold_attack_surface_count (os_software_stack, business_unit, environment, total_attack_surfaces)
SELECT 
    COALESCE(os_software_stack, 'Unknown') AS os_software_stack,  -- Handle NULL values for os_software_stack
    COALESCE(business_unit, 'Unknown') AS business_unit,        -- Handle NULL values for business_unit
    COALESCE(environment, 'Unknown') AS environment,            -- Handle NULL values for environment
    COUNT(*) AS total_attack_surfaces                            -- Count of all attack surfaces
FROM 
    attack_surface_table
GROUP BY 
    os_software_stack, 
    business_unit, 
    environment;