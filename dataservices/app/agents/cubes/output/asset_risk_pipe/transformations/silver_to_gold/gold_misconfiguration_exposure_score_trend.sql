-- Transformation: silver_to_gold_gold_misconfiguration_exposure_score_trend
-- Source: silver.gold_misconfiguration_exposure_score_trend
-- Target: gold.gold_gold_misconfiguration_exposure_score_trend
-- Description: Transform gold_misconfiguration_exposure_score_trend from silver to gold

-- Metric: misconfiguration_exposure_score_trend: The trend of misconfiguration exposure scores over the last 6 months.
INSERT INTO gold_misconfiguration_exposure_score_trend (month, severity_category, total_exposure_score)
SELECT 
    DATE_TRUNC('month', ms.timestamp) AS month,  -- Truncate timestamp to month
    ms.severity_category,  -- Group by severity category
    SUM(COALESCE(ms.exposure_score, 0)) AS total_exposure_score  -- Sum exposure scores, handling NULLs
FROM 
    misconfiguration_scores ms
WHERE 
    ms.timestamp >= CURRENT_DATE - INTERVAL '6 months'  -- Filter for the last 6 months
GROUP BY 
    month, severity_category  -- Group by month and severity category
ORDER BY 
    month, severity_category;  -- Order results for better readability