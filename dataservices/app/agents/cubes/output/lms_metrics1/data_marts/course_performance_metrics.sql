-- Data Mart: course_performance_metrics
-- Goal: Build course performance metrics data mart
-- Question: What are the performance metrics for each course, including total enrollments and average completion rates?
-- Generated: 20251121_132228

CREATE TABLE course_performance_metrics AS SELECT c.course_id, c.title, c.description, COUNT(e.user_id) AS total_enrollments, AVG(e.completion_rate) AS average_completion_rate, SUM(e.duration) AS total_duration FROM courses c LEFT JOIN enrollments e ON c.course_id = e.course_id GROUP BY c.course_id, c.title, c.description;