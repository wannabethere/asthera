-- Transformation: silver_to_gold_gold_breach_risk_trend
-- Source: silver.gold_breach_risk_trend
-- Target: gold.gold_gold_breach_risk_trend
-- Description: Transform gold_breach_risk_trend from silver to gold

-- Metric: breach_risk_trend: Measures the trend of breach risk scores over the past 12 months.
INSERT INTO gold_breach_risk_trend (month, average_breach_risk_score)
SELECT 
    DATE_TRUNC('month', br.timestamp) AS month,  -- Truncate timestamp to month
    AVG(COALESCE(br.breach_risk_score, 0)) AS average_breach_risk_score  -- Calculate average, handling NULLs
FROM 
    breach_risk_table br
WHERE 
    br.timestamp >= CURRENT_DATE - INTERVAL '12 months'  -- Filter for the last 12 months
GROUP BY 
    month  -- Group by the truncated month
ORDER BY 
    month;  -- Order by month for consistency