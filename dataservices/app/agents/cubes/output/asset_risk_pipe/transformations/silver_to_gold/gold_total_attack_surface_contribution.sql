-- Transformation: silver_to_gold_gold_total_attack_surface_contribution
-- Source: silver.gold_total_attack_surface_contribution
-- Target: gold.gold_gold_total_attack_surface_contribution
-- Description: Transform gold_total_attack_surface_contribution from silver to gold

-- Metric: total_attack_surface_contribution: Total contribution to the attack surface by the OS/software stack.
INSERT INTO gold_total_attack_surface_contribution (os_stack, software_stack, total_contribution)
SELECT 
    COALESCE(s.os_stack, 'Unknown') AS os_stack,  -- Handle NULL OS stack
    COALESCE(s.software_stack, 'Unknown') AS software_stack,  -- Handle NULL software stack
    SUM(COALESCE(s.contribution, 0)) AS total_contribution  -- Sum contributions, treating NULL as 0
FROM 
    silver_attack_surface s
JOIN 
    gold_attack_surface g ON s.id = g.id  -- Assuming a common identifier for joining
GROUP BY 
    s.os_stack, s.software_stack  -- Group by OS and software stack
HAVING 
    SUM(COALESCE(s.contribution, 0)) > 0;  -- Only include groups with positive contributions