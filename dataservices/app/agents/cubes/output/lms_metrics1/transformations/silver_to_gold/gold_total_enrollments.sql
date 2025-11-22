-- Transformation: silver_to_gold_gold_total_enrollments
-- Source: silver.gold_total_enrollments
-- Target: gold.gold_gold_total_enrollments
-- Description: Transform gold_total_enrollments from silver to gold

-- Metric: total_enrollments: Total number of enrollments across all courses
INSERT INTO gold_total_enrollments (total_enrollments)
SELECT COUNT(*) AS total_enrollments
FROM enrollments
WHERE enrollment_status = 'active';  -- Assuming 'enrollment_status' is the column indicating active enrollments