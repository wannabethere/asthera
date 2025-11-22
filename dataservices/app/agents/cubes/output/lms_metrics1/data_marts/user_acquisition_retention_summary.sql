-- Data Mart: user_acquisition_retention_summary
-- Goal: Generate instructor analytics summary
-- Question: What is the total number of courses each user has enrolled in, and how many days have they engaged with the courses?
-- Generated: 20251121_132228

CREATE TABLE user_acquisition_retention_summary AS SELECT u.user_id, u.name AS user_name, COUNT(e.course_id) AS total_courses_enrolled, COUNT(DISTINCT e.enrollment_date) AS enrollment_days, SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed FROM users u LEFT JOIN enrollments e ON u.user_id = e.user_id GROUP BY u.user_id, u.name;