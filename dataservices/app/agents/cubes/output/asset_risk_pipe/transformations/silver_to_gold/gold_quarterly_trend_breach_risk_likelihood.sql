-- Transformation: silver_to_gold_gold_quarterly_trend_breach_risk_likelihood
-- Source: silver.gold_quarterly_trend_breach_risk_likelihood
-- Target: gold.gold_gold_quarterly_trend_breach_risk_likelihood
-- Description: Transform gold_quarterly_trend_breach_risk_likelihood from silver to gold

-- Metric: quarterly_trend_breach_risk_likelihood: Quarterly trends of breach risk likelihood aggregated by business unit.
INSERT INTO gold_quarterly_trend_breach_risk_likelihood (quarter, business_unit, average_breach_risk_likelihood)
SELECT 
    DATE_TRUNC('quarter', br.timestamp) AS quarter,  -- Truncate timestamp to quarter
    br.business_unit,  -- Group by business unit
    AVG(COALESCE(br.breach_risk_likelihood, 0)) AS average_breach_risk_likelihood  -- Calculate average, handling NULLs
FROM 
    breach_risk_table br
GROUP BY 
    quarter, 
    br.business_unit  -- Group by quarter and business unit
ORDER BY 
    quarter, 
    br.business_unit;  -- Order results for better readability