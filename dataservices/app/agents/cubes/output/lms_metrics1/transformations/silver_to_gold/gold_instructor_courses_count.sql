-- Transformation: silver_to_gold_gold_instructor_courses_count
-- Source: silver.gold_instructor_courses_count
-- Target: gold.gold_gold_instructor_courses_count
-- Description: Transform gold_instructor_courses_count from silver to gold

-- Metric: instructor_courses_count: Total number of courses taught by instructors
INSERT INTO gold_instructor_courses_count (instructor_id, total_courses)
SELECT 
    instructor_id,
    COUNT(*) AS total_courses
FROM 
    courses
WHERE 
    semester = (SELECT current_semester FROM semesters WHERE CURRENT_DATE BETWEEN start_date AND end_date)
GROUP BY 
    instructor_id;