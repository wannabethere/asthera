-- Transformation: silver_to_gold_gold_attack_surface_by_environment
-- Source: silver.gold_attack_surface_by_environment
-- Target: gold.gold_gold_attack_surface_by_environment
-- Description: Transform gold_attack_surface_by_environment from silver to gold

-- Metric: attack_surface_by_environment: Breakdown of attack surfaces by environment
INSERT INTO gold_attack_surface_by_environment (environment, attack_surface_count)
SELECT 
    COALESCE(environment, 'Unknown') AS environment,  -- Handle NULL values by replacing with 'Unknown'
    COUNT(*) AS attack_surface_count  -- Count of records for each environment
FROM 
    attack_surface_table
GROUP BY 
    environment  -- Group by distinct environment values
ORDER BY 
    environment;  -- Order by environment for better readability