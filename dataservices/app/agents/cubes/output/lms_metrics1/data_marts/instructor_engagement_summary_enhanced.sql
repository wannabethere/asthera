-- Enhanced Data Mart: instructor_engagement_summary
-- Generated: 20251121_132228

CREATE TABLE instructor_engagement_summary AS 
SELECT 
    u.user_id, 
    u.name AS user_name, 
    COUNT(e.course_id) AS total_courses_enrolled, 
    COALESCE(AVG(c.duration), 0) AS avg_course_duration,  -- Handle NULL for average duration
    SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed 
FROM 
    users u 
JOIN 
    enrollments e ON u.user_id = e.user_id 
JOIN 
    courses c ON e.course_id = c.course_id 
GROUP BY 
    u.user_id, u.name; 

-- Index suggestions for performance optimization
-- CREATE INDEX idx_user_id ON instructor_engagement_summary(user_id);
-- CREATE INDEX idx_course_id ON enrollments(course_id);
-- CREATE INDEX idx_user_enrollment ON enrollments(user_id);