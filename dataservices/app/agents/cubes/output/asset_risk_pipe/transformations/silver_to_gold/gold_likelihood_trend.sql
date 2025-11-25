-- Transformation: silver_to_gold_gold_likelihood_trend
-- Source: silver.gold_likelihood_trend
-- Target: gold.gold_gold_likelihood_trend
-- Description: Transform gold_likelihood_trend from silver to gold

-- Metric: likelihood_trend: Measures the trend of likelihood scores over the past 12 months.
INSERT INTO gold_likelihood_trend (month, average_likelihood_score)
SELECT 
    DATE_TRUNC('month', likelihood_date) AS month,
    AVG(COALESCE(likelihood_score, 0)) AS average_likelihood_score
FROM 
    likelihood_table
WHERE 
    likelihood_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY 
    month
ORDER BY 
    month;