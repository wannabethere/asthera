-- Transformation: silver_to_gold_gold_exposure_score_trend
-- Source: silver.gold_exposure_score_trend
-- Target: gold.gold_gold_exposure_score_trend
-- Description: Transform gold_exposure_score_trend from silver to gold

-- Metric: exposure_score_trend: Trend of exposure scores over time
INSERT INTO gold_exposure_score_trend (month, average_score)
SELECT 
    DATE_TRUNC('month', es."timestamp") AS month,  -- Truncate timestamp to month
    AVG(COALESCE(es.score, 0)) AS average_score    -- Calculate average score, handling NULLs
FROM 
    exposure_scores es
WHERE 
    es."timestamp" >= CURRENT_DATE - INTERVAL '12 months'  -- Filter for the last 12 months
GROUP BY 
    month
ORDER BY 
    month;  -- Order results by month for trend analysis