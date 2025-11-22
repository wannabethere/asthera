-- Transformation: silver_to_gold_gold_course_completion_rate
-- Source: silver.gold_course_completion_rate
-- Target: gold.gold_gold_course_completion_rate
-- Description: Transform gold_course_completion_rate from silver to gold

-- Metric: course_completion_rate: Percentage of students who completed the courses they enrolled in
INSERT INTO gold_course_completion_rate (completion_rate)
SELECT 
    COALESCE(
        (COUNT(DISTINCT cc.course_id) * 100.0) / NULLIF(COUNT(DISTINCT e.course_id), 0), 
        0) AS completion_rate
FROM 
    enrollments e
LEFT JOIN 
    course_completions cc ON e.course_id = cc.course_id
WHERE 
    e.course_id IS NOT NULL
GROUP BY 
    e.course_id
HAVING 
    COUNT(e.student_id) > 0;