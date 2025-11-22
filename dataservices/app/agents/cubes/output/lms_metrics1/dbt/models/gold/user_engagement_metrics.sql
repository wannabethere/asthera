{{ config(materialized='table') }}

-- This mart contains metrics related to user engagement, including total courses enrolled, average completion rates, and total time spent by users.
SELECT 
    u.user_id, 
    COUNT(e.course_id) AS total_courses_enrolled, 
    COALESCE(AVG(NULLIF(e.completion_rate, 0)), 0) AS average_completion_rate,  -- Handle NULL and avoid division by zero
    COALESCE(SUM(e.duration), 0) AS total_time_spent  -- Handle NULL for total time spent
FROM 
    {{ ref('users') }} u 
LEFT JOIN 
    {{ ref('enrollments') }} e ON u.user_id = e.user_id 
GROUP BY 
    u.user_id; 

-- Indexes can be added on user_id in both users and enrollments tables for performance optimization
-- CREATE INDEX idx_users_user_id ON users(user_id);
-- CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);