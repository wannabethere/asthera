-- Transformation: silver_to_gold_gold_average_engagement_time
-- Source: silver.gold_average_engagement_time
-- Target: gold.gold_gold_average_engagement_time
-- Description: Transform gold_average_engagement_time from silver to gold

-- Metric: average_engagement_time: Average time spent by learners on the platform
INSERT INTO gold_average_engagement_time (month, average_time_spent)
SELECT 
    DATE_TRUNC('month', engagement_timestamp) AS month,
    COALESCE(SUM(engagement_time) / NULLIF(COUNT(*), 0), 0) AS average_time_spent
FROM 
    learner_engagement
WHERE 
    engagement_time > 1 -- Only include sessions longer than 1 minute
GROUP BY 
    DATE_TRUNC('month', engagement_timestamp)
ORDER BY 
    month;