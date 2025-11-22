-- Transformation: silver_to_gold_gold_enrollment_count
-- Source: silver.gold_enrollment_count
-- Target: gold.gold_gold_enrollment_count
-- Description: Transform gold_enrollment_count from silver to gold

-- Metric: enrollment_count: Total number of enrollments in each course
INSERT INTO gold_enrollment_count (course_id, total_enrollments)
SELECT 
    course_id,
    COUNT(*) AS total_enrollments
FROM 
    enrollment_table
GROUP BY 
    course_id;