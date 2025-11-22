-- Transformation: silver_to_gold_gold_quarterly_trend_percentage_completed_courses
-- Source: silver.gold_quarterly_trend_percentage_completed_courses
-- Target: gold.gold_gold_quarterly_trend_percentage_completed_courses
-- Description: Transform gold_quarterly_trend_percentage_completed_courses from silver to gold

-- Metric: quarterly_trend_percentage_completed_courses: Quarterly trend of the percentage of students who completed courses taught by each instructor
INSERT INTO gold_quarterly_trend_percentage_completed_courses (instructor_id, quarter, percentage_completed_courses)
WITH course_completion AS (
    SELECT 
        c.instructor_id,
        DATE_TRUNC('quarter', c.start_date) AS quarter,
        COUNT(DISTINCT s.student_id) FILTER (WHERE s.completed = TRUE) AS completed_students,
        COUNT(DISTINCT s.student_id) AS total_students
    FROM 
        courses c
    LEFT JOIN 
        students s ON c.course_id = s.course_id
    GROUP BY 
        c.instructor_id, DATE_TRUNC('quarter', c.start_date)
),
percentage_calculation AS (
    SELECT 
        instructor_id,
        quarter,
        COALESCE(100.0 * completed_students / NULLIF(total_students, 0), 0) AS percentage_completed_courses
    FROM 
        course_completion
)
SELECT 
    instructor_id,
    quarter,
    percentage_completed_courses
FROM 
    percentage_calculation
ORDER BY 
    instructor_id, quarter;