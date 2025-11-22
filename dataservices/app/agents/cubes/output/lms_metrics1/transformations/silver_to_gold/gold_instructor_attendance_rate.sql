-- Transformation: silver_to_gold_gold_instructor_attendance_rate
-- Source: silver.gold_instructor_attendance_rate
-- Target: gold.gold_gold_instructor_attendance_rate
-- Description: Transform gold_instructor_attendance_rate from silver to gold

-- Metric: instructor_attendance_rate: Average attendance rate of students in classes taught by instructors
INSERT INTO gold_instructor_attendance_rate (instructor_id, average_attendance_rate)
SELECT 
    a.instructor_id,
    COALESCE(SUM(a.attendance_rate), 0) / NULLIF(COUNT(a.class_id), 0) AS average_attendance_rate
FROM 
    attendance a
WHERE 
    a.class_date >= DATE_TRUNC('semester', CURRENT_DATE)  -- Filter for current semester classes
GROUP BY 
    a.instructor_id;