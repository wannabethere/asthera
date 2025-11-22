-- Transformation: silver_to_gold_gold_active_learners_daily_trend
-- Source: silver.gold_active_learners_daily_trend
-- Target: gold.gold_gold_active_learners_daily_trend
-- Description: Transform gold_active_learners_daily_trend from silver to gold

-- Metric: active_learners_daily_trend: Daily trend of active learners over a specified time period.
INSERT INTO gold_active_learners_daily_trend (day, active_learners_count)
SELECT 
    DATE_TRUNC('day', l."last_active_date") AS day,
    COUNT(DISTINCT l."learner_id") AS active_learners_count
FROM 
    learners_table l
WHERE 
    l."last_active_date" IS NOT NULL
    AND l."last_active_date" >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 
    day
ORDER BY 
    day;