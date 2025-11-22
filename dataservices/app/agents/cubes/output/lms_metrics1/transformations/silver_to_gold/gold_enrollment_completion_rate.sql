-- Transformation: silver_to_gold_gold_enrollment_completion_rate
-- Source: silver.gold_enrollment_completion_rate
-- Target: gold.gold_gold_enrollment_completion_rate
-- Description: Transform gold_enrollment_completion_rate from silver to gold

-- Metric: enrollment_completion_rate: Rate of completion for enrollments in each course
INSERT INTO gold_enrollment_completion_rate (course_id, completion_rate)
SELECT 
    course_id,
    COALESCE((SUM(completion_count) * 100.0) / NULLIF(SUM(enrollment_count), 0), 0) AS completion_rate
FROM (
    SELECT 
        course_id,
        COUNT(*) AS enrollment_count,
        COUNT(CASE WHEN completed = TRUE THEN 1 END) AS completion_count
    FROM enrollment_table
    GROUP BY course_id
) AS enrollment_summary
GROUP BY course_id;