-- Transformation: silver_to_gold_gold_exposure_score_comparison_by_category
-- Source: silver.gold_exposure_score_comparison_by_category
-- Target: gold.gold_gold_exposure_score_comparison_by_category
-- Description: Transform gold_exposure_score_comparison_by_category from silver to gold

-- Metric: exposure_score_comparison_by_category: Comparison of average exposure scores by category
INSERT INTO gold_exposure_score_comparison_by_category (category, average_exposure_score)
SELECT 
    category,
    AVG(COALESCE(exposure_score, 0)) AS average_exposure_score
FROM 
    exposure_scores
WHERE 
    exposure_score IS NOT NULL  -- Include only valid exposure scores
GROUP BY 
    category
ORDER BY 
    category;