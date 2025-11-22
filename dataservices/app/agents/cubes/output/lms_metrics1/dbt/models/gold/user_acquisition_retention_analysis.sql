{{ config(materialized='table') }}

-- This mart contains metrics related to user acquisition and retention, including the number of courses enrolled and the number of days since registration.
WITH user_metrics AS (
    SELECT 
        u.user_id,
        COUNT(COALESCE(e.course_id, NULL)) AS total_courses_enrolled,  -- Count of courses enrolled, handling NULLs
        COUNT(DISTINCT DATE_TRUNC('day', e.enrollment_date)) AS enrollment_days,  -- Count of distinct enrollment days
        COALESCE(DATE_PART('day', CURRENT_DATE - u.registration_date), 0) AS days_since_registration  -- Days since registration, default to 0 if NULL
    FROM 
        {{ ref('users') }} u  -- Reference to users table
    LEFT JOIN 
        {{ ref('enrollments') }} e ON u.user_id = e.user_id  -- Left join to include users with no enrollments
    GROUP BY 
        u.user_id  -- Grouping by user_id to aggregate metrics per user
)

SELECT 
    user_id,
    total_courses_enrolled,
    enrollment_days,
    days_since_registration
FROM 
    user_metrics;  -- Final selection from the CTE

-- Indexes can be added on user_id in both users and enrollments tables for performance optimization
-- CREATE INDEX idx_users_user_id ON users(user_id);
-- CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);