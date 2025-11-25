-- Transformation: silver_to_gold_gold_total_external_exposure_score
-- Source: silver.gold_total_external_exposure_score
-- Target: gold.gold_gold_total_external_exposure_score
-- Description: Transform gold_total_external_exposure_score from silver to gold

-- Metric: total_external_exposure_score: The total score representing external exposure across all assets.
INSERT INTO gold_total_external_exposure_score (environment, total_external_exposure_score)
SELECT 
    environment,
    COALESCE(SUM(external_exposure_score), 0) AS total_external_exposure_score
FROM 
    assets_table
GROUP BY 
    environment;