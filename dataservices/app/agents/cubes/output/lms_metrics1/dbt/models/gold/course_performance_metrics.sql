{{ config(materialized='table') }}

-- This model contains metrics related to course performance, including total enrollments, average completion rates, and total duration of courses.
SELECT 
    c.course_id, 
    c.title, 
    c.description, 
    COUNT(e.user_id) AS total_enrollments, 
    COALESCE(AVG(NULLIF(e.completion_rate, 0)), 0) AS average_completion_rate,  -- Handle NULL and avoid division by zero
    COALESCE(SUM(e.duration), 0) AS total_duration  -- Handle NULL for total duration
FROM 
    {{ ref('courses') }} c  -- Reference to the courses table
LEFT JOIN 
    {{ ref('enrollments') }} e ON c.course_id = e.course_id  -- Join with enrollments table
GROUP BY 
    c.course_id, c.title, c.description; 

-- Index suggestions:
-- CREATE INDEX idx_course_id ON course_performance_metrics(course_id);
-- CREATE INDEX idx_title ON course_performance_metrics(title);