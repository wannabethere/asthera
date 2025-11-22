-- Enhanced Data Mart: enrollment_trends
-- Generated: 20251121_132228

CREATE TABLE enrollment_trends AS 
SELECT 
    DATE_TRUNC('day', e.enrollment_date) AS enrollment_date,  -- Truncate to day for grouping
    COUNT(e.user_id) AS total_enrollments,  -- Count total enrollments
    COUNT(DISTINCT e.course_id) AS total_courses_offered  -- Count distinct courses offered
FROM 
    enrollments e
GROUP BY 
    DATE_TRUNC('day', e.enrollment_date)  -- Group by truncated date
ORDER BY 
    enrollment_date;  -- Order by enrollment date

-- Indexes can be added on enrollment_date for performance optimization
-- CREATE INDEX idx_enrollment_date ON enrollment_trends(enrollment_date);