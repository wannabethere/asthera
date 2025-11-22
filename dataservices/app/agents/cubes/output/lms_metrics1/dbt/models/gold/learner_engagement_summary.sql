{{ config(materialized='table') }}

-- This model summarizes learner engagement metrics, including total courses enrolled, average course duration, and total courses completed per user.
SELECT 
    u.user_id, 
    u.registration_date, 
    COUNT(e.course_id) AS total_courses_enrolled, 
    COALESCE(AVG(c.duration), 0) AS average_course_duration,  -- Handle NULL for average duration
    SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed 
FROM 
    {{ ref('users') }} u 
LEFT JOIN 
    {{ ref('enrollments') }} e ON u.user_id = e.user_id 
LEFT JOIN 
    {{ ref('courses') }} c ON e.course_id = c.course_id 
GROUP BY 
    u.user_id, 
    u.registration_date; 

-- Index suggestions for performance optimization
-- CREATE INDEX idx_user_id ON users(user_id);
-- CREATE INDEX idx_enrollment_user_id ON enrollments(user_id);
-- CREATE INDEX idx_enrollment_course_id ON enrollments(course_id);
-- CREATE INDEX idx_course_id ON courses(course_id);