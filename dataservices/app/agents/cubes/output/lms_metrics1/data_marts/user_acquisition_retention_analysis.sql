-- Data Mart: user_acquisition_retention_analysis
-- Goal: Create learner engagement analytics dashboard
-- Question: How many courses have users enrolled in since their registration, and how long have they been registered?
-- Generated: 20251121_132228

CREATE TABLE user_acquisition_retention_analysis AS SELECT u.user_id, COUNT(e.course_id) AS total_courses_enrolled, COUNT(DISTINCT e.enrollment_date) AS enrollment_days, DATEDIFF(CURRENT_DATE, u.registration_date) AS days_since_registration FROM users u LEFT JOIN enrollments e ON u.user_id = e.user_id GROUP BY u.user_id;