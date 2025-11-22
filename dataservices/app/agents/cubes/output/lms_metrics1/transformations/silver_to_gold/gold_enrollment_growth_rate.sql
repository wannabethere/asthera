-- Transformation: silver_to_gold_gold_enrollment_growth_rate
-- Source: silver.gold_enrollment_growth_rate
-- Target: gold.gold_gold_enrollment_growth_rate
-- Description: Transform gold_enrollment_growth_rate from silver to gold

-- Metric: enrollment_growth_rate: Growth rate of enrollments compared to the previous period
INSERT INTO gold_enrollment_growth_rate (month, growth_rate)
SELECT 
    DATE_TRUNC('month', e.current_month) AS month,
    CASE 
        WHEN previous_month.enrollment_count IS NULL THEN NULL
        ELSE 
            COALESCE(((e.enrollment_count - previous_month.enrollment_count) / NULLIF(previous_month.enrollment_count, 0)) * 100, 0)
    END AS growth_rate
FROM 
    (SELECT 
         DATE_TRUNC('month', enrollment_date) AS current_month,
         COUNT(*) AS enrollment_count
     FROM 
         enrollments
     WHERE 
         enrollment_date >= CURRENT_DATE - INTERVAL '2 months'
     GROUP BY 
         DATE_TRUNC('month', enrollment_date)
    ) e
LEFT JOIN 
    (SELECT 
         DATE_TRUNC('month', enrollment_date) AS previous_month,
         COUNT(*) AS enrollment_count
     FROM 
         enrollments
     WHERE 
         enrollment_date >= CURRENT_DATE - INTERVAL '3 months' AND 
         enrollment_date < CURRENT_DATE - INTERVAL '2 months'
     GROUP BY 
         DATE_TRUNC('month', enrollment_date)
    ) previous_month 
ON 
    DATE_TRUNC('month', e.current_month) = DATE_TRUNC('month', previous_month.previous_month) + INTERVAL '1 month'
ORDER BY 
    month;