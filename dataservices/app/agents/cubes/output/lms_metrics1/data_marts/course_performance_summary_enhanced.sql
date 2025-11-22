-- Enhanced Data Mart: course_performance_summary
-- Generated: 20251121_132228

CREATE TABLE course_performance_summary AS 
SELECT 
    c.course_id, 
    c.title, 
    COUNT(e.user_id) AS total_enrollments, 
    COALESCE(AVG(CASE WHEN e.completed = TRUE THEN 1.0 ELSE 0.0 END), 0) AS completion_rate -- Handle NULL case for completion rate
FROM 
    courses c 
LEFT JOIN 
    enrollments e ON c.course_id = e.course_id 
GROUP BY 
    c.course_id, c.title; 

-- Indexes can be added on course_id in both tables for performance optimization
-- CREATE INDEX idx_courses_course_id ON courses(course_id);
-- CREATE INDEX idx_enrollments_course_id ON enrollments(course_id);