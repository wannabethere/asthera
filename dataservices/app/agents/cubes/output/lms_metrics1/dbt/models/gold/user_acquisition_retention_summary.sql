{{ config(materialized='table') }}

-- This model summarizes user acquisition and retention metrics
-- including total courses enrolled and the number of days users have engaged with courses.

SELECT 
    u.user_id, 
    u.name AS user_name, 
    COUNT(e.course_id) AS total_courses_enrolled, 
    COUNT(DISTINCT DATE_TRUNC('day', e.enrollment_date)) AS enrollment_days, 
    SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed 
FROM 
    {{ ref('users') }} u 
LEFT JOIN 
    {{ ref('enrollments') }} e ON u.user_id = e.user_id 
GROUP BY 
    u.user_id, u.name; 

-- Indexes can be added on user_id in users and enrollments for performance optimization
-- CREATE INDEX idx_users_user_id ON users(user_id);
-- CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);