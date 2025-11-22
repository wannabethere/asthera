-- Transformation: silver_to_gold_gold_students_completed_courses
-- Source: silver.gold_students_completed_courses
-- Target: gold.gold_gold_students_completed_courses
-- Description: Transform gold_students_completed_courses from silver to gold

-- Metric: students_completed_courses: Count of students who completed courses taught by each instructor
SELECT 
    c."instructor_id",
    COUNT(DISTINCT s."student_id") AS "completed_students_count"
FROM 
    "courses" c
JOIN 
    "gold_students_completed_courses" g ON c."course_id" = g."course_id"
JOIN 
    "students" s ON g."student_id" = s."student_id"
WHERE 
    COALESCE(g."completion_status", '') = 'completed'  -- Only include completed courses
GROUP BY 
    c."instructor_id"
ORDER BY 
    c."instructor_id";