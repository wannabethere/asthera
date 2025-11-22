-- Transformation: silver_to_gold_gold_percentage_completed_courses
-- Source: silver.gold_percentage_completed_courses
-- Target: gold.gold_gold_percentage_completed_courses
-- Description: Transform gold_percentage_completed_courses from silver to gold

-- Metric: percentage_completed_courses: Percentage of students who completed courses taught by each instructor
INSERT INTO gold_percentage_completed_courses (instructor_id, percentage_completed)
SELECT 
    c.instructor_id,
    COALESCE(
        (COUNT(DISTINCT CASE WHEN s.completed = TRUE THEN s.student_id END) * 100.0) / 
        NULLIF(COUNT(DISTINCT s.student_id), 0), 0) AS percentage_completed
FROM 
    courses c
JOIN 
    students s ON c.course_id = s.course_id
GROUP BY 
    c.instructor_id
HAVING 
    COUNT(DISTINCT s.student_id) > 0;