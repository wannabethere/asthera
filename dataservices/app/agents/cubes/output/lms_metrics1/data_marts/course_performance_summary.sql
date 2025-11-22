-- Data Mart: course_performance_summary
-- Goal: Generate instructor analytics summary
-- Question: How many students are enrolled in each course, and what is the completion rate for those courses?
-- Generated: 20251121_132228

CREATE TABLE course_performance_summary AS SELECT c.course_id, c.title, COUNT(e.user_id) AS total_enrollments, AVG(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS completion_rate FROM courses c LEFT JOIN enrollments e ON c.course_id = e.course_id GROUP BY c.course_id, c.title;