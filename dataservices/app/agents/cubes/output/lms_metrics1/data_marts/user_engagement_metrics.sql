-- Data Mart: user_engagement_metrics
-- Goal: Build course performance metrics data mart
-- Question: How engaged are users based on their course enrollments and completion rates?
-- Generated: 20251121_132228

CREATE TABLE user_engagement_metrics AS SELECT u.user_id, COUNT(e.course_id) AS total_courses_enrolled, AVG(e.completion_rate) AS average_completion_rate, SUM(e.duration) AS total_time_spent FROM users u LEFT JOIN enrollments e ON u.user_id = e.user_id GROUP BY u.user_id;