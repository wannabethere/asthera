-- Enhanced Data Mart: user_acquisition_retention_analysis
-- Generated: 20251121_132228

CREATE TABLE user_acquisition_retention_analysis AS 
SELECT 
    u.user_id, 
    COUNT(COALESCE(e.course_id, NULL)) AS total_courses_enrolled,  -- Count of courses enrolled, handling NULLs
    COUNT(DISTINCT DATE_TRUNC('day', e.enrollment_date)) AS enrollment_days,  -- Count of distinct enrollment days
    COALESCE(DATE_PART('day', CURRENT_DATE - u.registration_date), 0) AS days_since_registration  -- Days since registration, default to 0 if NULL
FROM 
    users u 
LEFT JOIN 
    enrollments e ON u.user_id = e.user_id 
GROUP BY 
    u.user_id;  -- Grouping by user_id to aggregate metrics per user

-- Indexes can be added on user_id in both users and enrollments tables for performance optimization
-- CREATE INDEX idx_users_user_id ON users(user_id);
-- CREATE INDEX idx_enrollments_user_id ON enrollments(user_id);