-- Transformation: silver_to_gold_gold_percentage_contribution_to_risk
-- Source: silver.gold_percentage_contribution_to_risk
-- Target: gold.gold_gold_percentage_contribution_to_risk
-- Description: Transform gold_percentage_contribution_to_risk from silver to gold

-- Metric: percentage_contribution_to_risk: Percentage contribution of each OS/software stack to the overall risk.
INSERT INTO gold_percentage_contribution_to_risk (os_stack, software_stack, percentage_contribution)
WITH risk_data AS (
    SELECT 
        s.os_stack,
        s.software_stack,
        SUM(COALESCE(r.risk_score, 0)) AS total_risk_contribution
    FROM 
        silver_attack_surface s
    JOIN 
        silver_risk_assessment r ON s.id = r.attack_surface_id
    GROUP BY 
        s.os_stack, s.software_stack
),
overall_risk AS (
    SELECT 
        SUM(total_risk_contribution) AS total_overall_risk
    FROM 
        risk_data
)
SELECT 
    rd.os_stack,
    rd.software_stack,
    CASE 
        WHEN o.total_overall_risk IS NULL OR o.total_overall_risk = 0 THEN 0
        ELSE (rd.total_risk_contribution / NULLIF(o.total_overall_risk, 0)) * 100
    END AS percentage_contribution
FROM 
    risk_data rd,
    overall_risk o;