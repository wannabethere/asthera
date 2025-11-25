-- Transformation: silver_to_gold_gold_attack_surface_by_os_software_stack
-- Source: silver.gold_attack_surface_by_os_software_stack
-- Target: gold.gold_gold_attack_surface_by_os_software_stack
-- Description: Transform gold_attack_surface_by_os_software_stack from silver to gold

-- Metric: attack_surface_by_os_software_stack: Breakdown of attack surfaces by operating system/software stack
INSERT INTO gold_attack_surface_by_os_software_stack (os_software_stack, record_count)
SELECT 
    COALESCE(os_software_stack, 'Unknown') AS os_software_stack,  -- Handle NULL values by replacing with 'Unknown'
    COUNT(*) AS record_count
FROM 
    attack_surface_table
GROUP BY 
    os_software_stack  -- Group by distinct OS/software stack values
ORDER BY 
    os_software_stack;  -- Order results for better readability