-- Transformation: silver_to_gold_gold_exposure_score_sum
-- Source: silver.gold_exposure_score_sum
-- Target: gold.gold_gold_exposure_score_sum
-- Description: Transform gold_exposure_score_sum from silver to gold

-- Metric: exposure_score_sum: Total exposure score across all records
INSERT INTO gold_exposure_score_sum (total_exposure_score)
SELECT 
    COALESCE(SUM(exposure_score), 0) AS total_exposure_score
FROM 
    exposure_scores
WHERE 
    exposure_score IS NOT NULL;