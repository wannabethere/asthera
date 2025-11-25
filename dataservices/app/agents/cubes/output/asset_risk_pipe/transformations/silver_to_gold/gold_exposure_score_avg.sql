-- Transformation: silver_to_gold_gold_exposure_score_avg
-- Source: silver.gold_exposure_score_avg
-- Target: gold.gold_gold_exposure_score_avg
-- Description: Transform gold_exposure_score_avg from silver to gold

-- Metric: exposure_score_avg: Average exposure score across all records
INSERT INTO gold_exposure_score_avg (average_exposure_score)
SELECT AVG(COALESCE(exposure_score, 0)) AS average_exposure_score
FROM exposure_scores
WHERE exposure_score IS NOT NULL;