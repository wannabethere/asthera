-- Transformation: silver_to_gold_gold_exposure_score_weekly_average
-- Source: silver.gold_exposure_score_weekly_average
-- Target: gold.gold_gold_exposure_score_weekly_average
-- Description: Transform gold_exposure_score_weekly_average from silver to gold

-- Metric: exposure_score_weekly_average: Average exposure score calculated on a weekly basis.
INSERT INTO gold_exposure_score_weekly_average (week_start, average_exposure_score)
SELECT 
    DATE_TRUNC('week', es."timestamp") AS week_start,  -- Truncate timestamp to week
    COALESCE(SUM(es.exposure_score), 0) / NULLIF(COUNT(es.exposure_score), 0) AS average_exposure_score  -- Calculate average, handle division by zero
FROM 
    exposure_scores es
WHERE 
    es.exposure_score IS NOT NULL  -- Only include records with valid exposure scores
GROUP BY 
    week_start
ORDER BY 
    week_start;  -- Order by week for clarity