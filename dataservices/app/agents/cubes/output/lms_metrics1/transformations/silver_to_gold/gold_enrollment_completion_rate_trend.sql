-- Transformation: silver_to_gold_gold_enrollment_completion_rate_trend
-- Source: silver.gold_enrollment_completion_rate_trend
-- Target: gold.gold_gold_enrollment_completion_rate_trend
-- Description: Transform gold_enrollment_completion_rate_trend from silver to gold

-- Metric: enrollment_completion_rate_trend: Trend of enrollment completion rate over the last 6 months for each course
INSERT INTO gold_enrollment_completion_rate_trend (course_id, month, enrollment_completion_rate)
WITH monthly_enrollment AS (
    SELECT 
        course_id,
        DATE_TRUNC('month', enrollment_date) AS month,
        COUNT(*) AS total_enrollments,
        SUM(CASE WHEN completion_status = 'completed' THEN 1 ELSE 0 END) AS completed_enrollments
    FROM 
        enrollment_table
    WHERE 
        enrollment_date >= CURRENT_DATE - INTERVAL '6 months'  -- Filter for the last 6 months
    GROUP BY 
        course_id, DATE_TRUNC('month', enrollment_date)
),
enrollment_rate AS (
    SELECT 
        course_id,
        month,
        COALESCE(SUM(completed_enrollments) / NULLIF(SUM(total_enrollments), 0), 0) AS enrollment_completion_rate
    FROM 
        monthly_enrollment
    GROUP BY 
        course_id, month
)
SELECT 
    course_id,
    month,
    enrollment_completion_rate
FROM 
    enrollment_rate
ORDER BY 
    course_id, month;