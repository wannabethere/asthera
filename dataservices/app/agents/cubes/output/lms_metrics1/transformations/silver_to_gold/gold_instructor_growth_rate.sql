-- Transformation: silver_to_gold_gold_instructor_growth_rate
-- Source: silver.gold_instructor_growth_rate
-- Target: gold.gold_gold_instructor_growth_rate
-- Description: Transform gold_instructor_growth_rate from silver to gold

-- Metric: instructor_growth_rate: Growth rate of the number of instructors over the last year
INSERT INTO gold_instructor_growth_rate (growth_rate, year)
SELECT 
    CASE 
        WHEN COUNT(instructors_current.year) = 0 THEN NULL  -- Handle division by zero
        ELSE (COUNT(instructors_current.year) - COUNT(instructors_previous.year))::DECIMAL / NULLIF(COUNT(instructors_previous.year), 0) 
    END AS growth_rate,
    EXTRACT(YEAR FROM CURRENT_DATE) AS year
FROM 
    (SELECT 
        DATE_TRUNC('year', created_at) AS year, 
        COUNT(*) AS instructor_count 
     FROM instructors 
     WHERE created_at >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year' 
     GROUP BY DATE_TRUNC('year', created_at)
    ) AS instructors_current
FULL OUTER JOIN 
    (SELECT 
        DATE_TRUNC('year', created_at) AS year, 
        COUNT(*) AS instructor_count 
     FROM instructors 
     WHERE created_at >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '2 years' 
     AND created_at < DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year' 
     GROUP BY DATE_TRUNC('year', created_at)
    ) AS instructors_previous
ON instructors_current.year = instructors_previous.year + INTERVAL '1 year'
WHERE 
    instructors_current.year = DATE_TRUNC('year', CURRENT_DATE);