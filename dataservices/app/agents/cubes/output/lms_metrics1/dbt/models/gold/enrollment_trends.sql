{{ config(materialized='table') }}

-- This model captures trends in enrollments over time, including total enrollments and the number of courses offered on each date.
WITH enrollment_data AS (
    SELECT 
        DATE_TRUNC('day', e.enrollment_date) AS enrollment_date,  -- Truncate to day for grouping
        COUNT(e.user_id) AS total_enrollments,  -- Count total enrollments
        COUNT(DISTINCT e.course_id) AS total_courses_offered  -- Count distinct courses offered
    FROM 
        {{ ref('enrollments') }} e  -- Reference the enrollments table
    GROUP BY 
        DATE_TRUNC('day', e.enrollment_date)  -- Group by truncated date
)

SELECT 
    enrollment_date,
    COALESCE(total_enrollments, 0) AS total_enrollments,  -- Handle NULL values for total enrollments
    COALESCE(total_courses_offered, 0) AS total_courses_offered  -- Handle NULL values for total courses offered
FROM 
    enrollment_data
ORDER BY 
    enrollment_date;  -- Order by enrollment date

-- Indexes can be added on enrollment_date for performance optimization
-- CREATE INDEX idx_enrollment_date ON {{ this }}(enrollment_date);