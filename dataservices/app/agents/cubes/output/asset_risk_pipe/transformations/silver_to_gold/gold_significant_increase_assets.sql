-- Transformation: silver_to_gold_gold_significant_increase_assets
-- Source: silver.gold_significant_increase_assets
-- Target: gold.gold_gold_significant_increase_assets
-- Description: Transform gold_significant_increase_assets from silver to gold

-- Metric: significant_increase_assets: List of assets that have shown a significant increase in exposure scores week-over-week.
INSERT INTO gold_significant_increase_assets (asset_id, week_start, exposure_score_previous, exposure_score_current, percentage_increase)
WITH weekly_scores AS (
    SELECT 
        asset_id,
        DATE_TRUNC('week', score_date) AS week_start,
        AVG(exposure_score) AS avg_exposure_score
    FROM 
        exposure_scores
    GROUP BY 
        asset_id, DATE_TRUNC('week', score_date)
),
week_over_week AS (
    SELECT 
        current.asset_id,
        current.week_start,
        COALESCE(previous.avg_exposure_score, 0) AS exposure_score_previous,
        current.avg_exposure_score AS exposure_score_current,
        CASE 
            WHEN NULLIF(previous.avg_exposure_score, 0) IS NOT NULL THEN 
                (current.avg_exposure_score - previous.avg_exposure_score) / NULLIF(previous.avg_exposure_score, 0) * 100
            ELSE 
                NULL 
        END AS percentage_increase
    FROM 
        weekly_scores current
    LEFT JOIN 
        weekly_scores previous 
    ON 
        current.asset_id = previous.asset_id 
        AND current.week_start = previous.week_start + INTERVAL '1 week'
)
SELECT 
    asset_id,
    week_start,
    exposure_score_previous,
    exposure_score_current,
    percentage_increase
FROM 
    week_over_week
WHERE 
    percentage_increase > 10;