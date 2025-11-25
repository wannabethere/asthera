-- Transformation: silver_to_gold_gold_external_exposure_score_by_environment
-- Source: silver.gold_external_exposure_score_by_environment
-- Target: gold.gold_gold_external_exposure_score_by_environment
-- Description: Transform gold_external_exposure_score_by_environment from silver to gold

-- Metric: external_exposure_score_by_environment: The breakdown of total external exposure score by environment (prod vs non-prod).
INSERT INTO gold_external_exposure_score_by_environment (environment, total_external_exposure_score)
SELECT 
    COALESCE(environment, 'Unknown') AS environment,  -- Handle NULL environments
    SUM(external_exposure_score) AS total_external_exposure_score
FROM 
    assets_table
WHERE 
    environment IS NOT NULL  -- Only consider assets with an assigned environment
GROUP BY 
    environment
ORDER BY 
    environment;  -- Optional: Order by environment for better readability