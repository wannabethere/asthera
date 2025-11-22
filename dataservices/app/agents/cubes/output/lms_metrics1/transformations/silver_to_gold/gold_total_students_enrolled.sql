-- Transformation: silver_to_gold_gold_total_students_enrolled
-- Source: silver.gold_total_students_enrolled
-- Target: gold.gold_gold_total_students_enrolled
-- Description: Transform gold_total_students_enrolled from silver to gold

-- Metric: total_students_enrolled: Count of total students enrolled in courses taught by each instructor
INSERT INTO gold_total_students_enrolled (instructor_id, total_students_enrolled)
SELECT 
    c.instructor_id,
    COUNT(DISTINCT s.student_id) AS total_students_enrolled
FROM 
    courses c
LEFT JOIN 
    students s ON s.course_id = c.course_id
GROUP BY 
    c.instructor_id;