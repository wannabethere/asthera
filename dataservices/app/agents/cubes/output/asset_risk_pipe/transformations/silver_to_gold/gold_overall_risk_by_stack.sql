-- Transformation: silver_to_gold_gold_overall_risk_by_stack
-- Source: silver.gold_overall_risk_by_stack
-- Target: gold.gold_gold_overall_risk_by_stack
-- Description: Transform gold_overall_risk_by_stack from silver to gold

-- Metric: overall_risk_by_stack: Overall risk associated with each OS/software stack.
INSERT INTO gold_overall_risk_by_stack (os_stack, software_stack, total_risk_score)
SELECT 
    COALESCE(sra.os_stack, 'Unknown OS') AS os_stack,  -- Handle NULL OS stack
    COALESCE(sra.software_stack, 'Unknown Software') AS software_stack,  -- Handle NULL software stack
    SUM(COALESCE(gra.risk_score, 0)) AS total_risk_score  -- Sum risk scores, treating NULL as 0
FROM 
    silver_risk_assessment sra
LEFT JOIN 
    gold_risk_assessment gra ON sra.id = gra.assessment_id  -- Assuming a join condition based on assessment ID
GROUP BY 
    sra.os_stack, 
    sra.software_stack
ORDER BY 
    os_stack, 
    software_stack;  -- Order by OS and software stack for better readability