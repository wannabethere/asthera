-- Transformation: silver_to_gold_gold_breach_risk_likelihood
-- Source: silver.gold_breach_risk_likelihood
-- Target: gold.gold_gold_breach_risk_likelihood
-- Description: Transform gold_breach_risk_likelihood from silver to gold

-- Metric: breach_risk_likelihood: The likelihood of breach risk aggregated by business unit.
INSERT INTO gold_breach_risk_likelihood (business_unit, average_breach_risk_likelihood)
SELECT 
    business_unit,
    AVG(COALESCE(breach_risk_value, 0)) AS average_breach_risk_likelihood
FROM 
    breach_risk_table
WHERE 
    breach_risk_value IS NOT NULL  -- Filter out NULL values to ensure accurate average calculation
GROUP BY 
    business_unit;