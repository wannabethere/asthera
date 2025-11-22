-- Transformation: silver_to_gold_gold_average_time_to_completion
-- Source: silver.gold_average_time_to_completion
-- Target: gold.gold_gold_average_time_to_completion
-- Description: Transform gold_average_time_to_completion from silver to gold

-- Metric: average_time_to_completion: The average time taken to complete each course.
INSERT INTO gold_average_time_to_completion (course_id, average_time_to_completion)
SELECT 
    c.course_id,
    COALESCE(SUM(cr.completion_time) / NULLIF(COUNT(cr.id), 0), 0) AS average_time_to_completion
FROM 
    courses c
JOIN 
    completion_records cr ON c.id = cr.course_id
WHERE 
    cr.status = 'completed'  -- Only include completed courses
GROUP BY 
    c.course_id;