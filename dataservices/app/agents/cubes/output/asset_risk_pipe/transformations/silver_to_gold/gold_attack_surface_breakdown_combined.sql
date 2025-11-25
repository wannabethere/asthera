-- Transformation: silver_to_gold_gold_attack_surface_breakdown_combined
-- Source: silver.gold_attack_surface_breakdown_combined
-- Target: gold.gold_gold_attack_surface_breakdown_combined
-- Description: Transform gold_attack_surface_breakdown_combined from silver to gold

-- Metric: attack_surface_breakdown_combined: Combined breakdown of attack surfaces by OS/software stack, business unit, and environment
INSERT INTO gold_attack_surface_breakdown_combined (os_software_stack, business_unit, environment, record_count)
SELECT 
    COALESCE(os_software_stack, 'Unknown') AS os_software_stack,  -- Handle NULL values for OS/software stack
    COALESCE(business_unit, 'Unknown') AS business_unit,          -- Handle NULL values for business unit
    COALESCE(environment, 'Unknown') AS environment,              -- Handle NULL values for environment
    COUNT(*) AS record_count                                       -- Count of records
FROM 
    attack_surface_table
GROUP BY 
    os_software_stack, 
    business_unit, 
    environment
ORDER BY 
    os_software_stack, 
    business_unit, 
    environment;  -- Order by dimensions for better readability