-- Transformation: silver_to_gold_gold_engagement_growth_rate
-- Source: silver.gold_engagement_growth_rate
-- Target: gold.gold_gold_engagement_growth_rate
-- Description: Transform gold_engagement_growth_rate from silver to gold

-- Metric: engagement_growth_rate: Growth rate of learner engagement over time
WITH monthly_engagement AS (
    SELECT 
        DATE_TRUNC('month', "timestamp") AS month,
        COUNT(*) AS total_engagement
    FROM 
        learner_engagement
    GROUP BY 
        month
),
engagement_growth AS (
    SELECT 
        current.month AS current_month,
        current.total_engagement AS current_engagement,
        COALESCE(previous.total_engagement, 0) AS previous_engagement
    FROM 
        monthly_engagement current
    LEFT JOIN 
        monthly_engagement previous 
    ON 
        current.month = previous.month + INTERVAL '1 month'
)
INSERT INTO gold_engagement_growth_rate (month, growth_rate)
SELECT 
    current_month,
    CASE 
        WHEN NULLIF(previous_engagement, 0) IS NOT NULL THEN 
            ((current_engagement - previous_engagement) / NULLIF(previous_engagement, 0)) * 100
        ELSE 
            NULL 
    END AS growth_rate
FROM 
    engagement_growth
WHERE 
    current_engagement IS NOT NULL 
    AND previous_engagement IS NOT NULL;