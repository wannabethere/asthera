-- Transformation: silver_to_gold_gold_completion_count
-- Source: silver.gold_completion_count
-- Target: gold.gold_gold_completion_count
-- Description: Transform gold_completion_count from silver to gold

-- Metric: completion_count: Total number of completed enrollments in each course
INSERT INTO gold_completion_count (course_id, total_completed_enrollments)
SELECT 
    course_id,
    COUNT(*) AS total_completed_enrollments
FROM 
    enrollment_table
WHERE 
    completion_status = 'completed'  -- Only count completed enrollments
GROUP BY 
    course_id;