-- Data Mart: enrollment_trends
-- Goal: Build course performance metrics data mart
-- Question: What are the trends in course enrollments over time?
-- Generated: 20251121_132228

CREATE TABLE enrollment_trends AS SELECT DATE(e.enrollment_date) AS enrollment_date, COUNT(e.user_id) AS total_enrollments, COUNT(DISTINCT e.course_id) AS total_courses_offered FROM enrollments e GROUP BY DATE(e.enrollment_date) ORDER BY enrollment_date;