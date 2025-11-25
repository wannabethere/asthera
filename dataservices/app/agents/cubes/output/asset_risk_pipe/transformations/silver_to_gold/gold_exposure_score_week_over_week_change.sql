-- Transformation: silver_to_gold_gold_exposure_score_week_over_week_change
-- Source: silver.gold_exposure_score_week_over_week_change
-- Target: gold.gold_gold_exposure_score_week_over_week_change
-- Description: Transform gold_exposure_score_week_over_week_change from silver to gold

-- Metric: exposure_score_week_over_week_change: The change in average exposure scores from one week to the next.
INSERT INTO gold_exposure_score_week_over_week_change (week_start_date, percentage_change)
WITH weekly_averages AS (
    SELECT 
        DATE_TRUNC('week', "timestamp") AS week_start,
        AVG(exposure_score) AS avg_exposure_score
    FROM 
        exposure_scores
    GROUP BY 
        DATE_TRUNC('week', "timestamp")
),
current_previous_weeks AS (
    SELECT 
        current.week_start AS current_week,
        previous.avg_exposure_score AS previous_week_avg,
        current.avg_exposure_score AS current_week_avg
    FROM 
        weekly_averages AS current
    LEFT JOIN 
        weekly_averages AS previous 
    ON 
        current.week_start = current_previous_weeks.current_week + INTERVAL '1 week'
)
SELECT 
    current_week,
    CASE 
        WHEN NULLIF(previous_week_avg, 0) IS NOT NULL THEN 
            ((current_week_avg - previous_week_avg) / NULLIF(previous_week_avg, 0)) * 100
        ELSE 
            NULL 
    END AS percentage_change
FROM 
    current_previous_weeks
WHERE 
    previous_week_avg IS NOT NULL;