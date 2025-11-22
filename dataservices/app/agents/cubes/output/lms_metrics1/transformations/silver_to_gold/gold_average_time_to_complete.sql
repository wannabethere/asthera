-- Transformation: silver_to_gold_gold_average_time_to_complete
-- Source: silver.gold_average_time_to_complete
-- Target: gold.gold_gold_average_time_to_complete
-- Description: Transform gold_average_time_to_complete from silver to gold

-- Metric: average_time_to_complete: Average time taken by students to complete courses
INSERT INTO gold_average_time_to_complete (average_time)
SELECT 
    COALESCE(SUM(time_taken), 0) / NULLIF(COUNT(*), 0) AS average_time
FROM 
    course_completions
WHERE 
    course_status = 'completed';