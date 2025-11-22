-- Enhanced Data Mart: user_acquisition_retention_summary
-- Generated: 20251121_132228

CREATE TABLE user_acquisition_retention_summary AS 
SELECT 
    u.user_id, 
    u.name AS user_name, 
    COUNT(e.course_id) AS total_courses_enrolled, 
    COUNT(DISTINCT DATE_TRUNC('day', e.enrollment_date)) AS enrollment_days, 
    SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed 
FROM 
    users u 
LEFT JOIN 
    enrollments e ON u.user_id = e.user_id 
GROUP BY 
    u.user_id, u.name; 

-- Indexes can be added on user_id in users and enrollments for performance optimization
-- CREATE INDEX idx_users_user_id ON users(user_id);
-- CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);