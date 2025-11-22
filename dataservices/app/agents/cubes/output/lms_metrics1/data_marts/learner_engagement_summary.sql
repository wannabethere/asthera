-- Data Mart: learner_engagement_summary
-- Goal: Create learner engagement analytics dashboard
-- Question: How many courses has each user enrolled in, and what is their average course duration and completion rate?
-- Generated: 20251121_132228

CREATE TABLE learner_engagement_summary AS SELECT u.user_id, u.registration_date, COUNT(e.course_id) AS total_courses_enrolled, AVG(c.duration) AS average_course_duration, SUM(CASE WHEN e.completed = TRUE THEN 1 ELSE 0 END) AS total_courses_completed FROM users u LEFT JOIN enrollments e ON u.user_id = e.user_id LEFT JOIN courses c ON e.course_id = c.course_id GROUP BY u.user_id, u.registration_date;