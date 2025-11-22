-- Transformation: silver_to_gold_gold_average_time_to_completion_last_year
-- Source: silver.gold_average_time_to_completion_last_year
-- Target: gold.gold_gold_average_time_to_completion_last_year
-- Description: Transform gold_average_time_to_completion_last_year from silver to gold

-- Metric: average_time_to_completion_last_year: The average time taken to complete each course for the previous year.
INSERT INTO gold_average_time_to_completion_last_year (course_id, average_time_to_completion)
SELECT 
    cr.course_id,
    COALESCE(SUM(cr.completion_time), 0) / NULLIF(COUNT(cr.id), 0) AS average_time_to_completion
FROM 
    completion_records cr
JOIN 
    courses c ON cr.course_id = c.id
WHERE 
    cr.completed = TRUE
    AND DATE_TRUNC('year', cr.completion_date) = DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')
GROUP BY 
    cr.course_id;