-- Data Mart: instructor_engagement_summary
-- Goal: Generate instructor analytics summary
-- Question: What is the total number of courses each user has enrolled in, along with the average duration of those courses and the number of courses they have completed?
-- Generated: 20251121_132228

CREATE TABLE instructor_engagement_summary AS SELECT u.user_id, u.name AS user_name, COUNT(e.course_id) AS total_courses_enrolled, AVG(c.duration) AS avg_course_duration, SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed FROM users u JOIN enrollments e ON u.user_id = e.user_id JOIN courses c ON e.course_id = c.course_id GROUP BY u.user_id, u.name;