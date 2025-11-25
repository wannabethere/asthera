-- Transformation: silver_to_gold_gold_top_contributing_stacks
-- Source: silver.gold_top_contributing_stacks
-- Target: gold.gold_gold_top_contributing_stacks
-- Description: Transform gold_top_contributing_stacks from silver to gold

-- Metric: top_contributing_stacks: Identify the top OS/software stacks contributing to the overall risk.
INSERT INTO gold_top_contributing_stacks (os_stack, software_stack, total_risk_score)
WITH risk_contributions AS (
    SELECT 
        s.os_stack,
        s.software_stack,
        SUM(COALESCE(gra.risk_score, 0)) AS total_risk_score
    FROM 
        silver_attack_surface s
    JOIN 
        gold_attack_surface ga ON s.id = ga.attack_surface_id
    JOIN 
        silver_risk_assessment sra ON ga.id = sra.attack_surface_id
    JOIN 
        gold_risk_assessment gra ON sra.id = gra.risk_assessment_id
    GROUP BY 
        s.os_stack, s.software_stack
)
SELECT 
    os_stack,
    software_stack,
    total_risk_score
FROM 
    risk_contributions
ORDER BY 
    total_risk_score DESC
LIMIT 10;