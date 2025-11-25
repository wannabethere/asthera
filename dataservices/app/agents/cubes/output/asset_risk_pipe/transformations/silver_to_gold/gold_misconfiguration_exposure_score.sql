-- Transformation: silver_to_gold_gold_misconfiguration_exposure_score
-- Source: silver.gold_misconfiguration_exposure_score
-- Target: gold.gold_gold_misconfiguration_exposure_score
-- Description: Transform gold_misconfiguration_exposure_score from silver to gold

-- Metric: misconfiguration_exposure_score: The total misconfiguration exposure score calculated based on severity categories.
SELECT 
    "severity_category",
    DATE_TRUNC('month', "created_at") AS "month",
    COALESCE(SUM("exposure_score"), 0) AS "total_exposure_score"
FROM 
    "misconfiguration_scores"
GROUP BY 
    "severity_category", 
    DATE_TRUNC('month', "created_at")
ORDER BY 
    "month" DESC, 
    "severity_category";