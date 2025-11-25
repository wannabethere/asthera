-- Transformation: silver_to_gold_gold_exposure_score_count
-- Source: silver.gold_exposure_score_count
-- Target: gold.gold_gold_exposure_score_count
-- Description: Transform gold_exposure_score_count from silver to gold

-- Metric: exposure_score_count: Count of records with exposure scores
INSERT INTO gold_exposure_score_count (record_count)
SELECT COUNT(*) AS record_count
FROM exposure_scores
WHERE exposure_score IS NOT NULL;