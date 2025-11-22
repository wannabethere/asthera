-- Transformation: silver_to_gold_gold_engagement_trend
-- Source: silver.gold_engagement_trend
-- Target: gold.gold_gold_engagement_trend
-- Description: Transform gold_engagement_trend from silver to gold

-- Metric: engagement_trend: Trend of learner engagement over time
INSERT INTO gold_engagement_trend (month, total_engagements)
SELECT 
    DATE_TRUNC('month', engagement_date) AS month,
    COUNT(*) AS total_engagements
FROM 
    learner_engagement
WHERE 
    engagement_date >= CURRENT_DATE - INTERVAL '6 months'  -- Ensure at least 6 months of data
GROUP BY 
    month
HAVING 
    COUNT(*) > 0  -- Only include months with engagements
ORDER BY 
    month;