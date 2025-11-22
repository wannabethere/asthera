-- Transformation: silver_to_gold_gold_course_performance_trend
-- Source: silver.gold_course_performance_trend
-- Target: gold.gold_gold_course_performance_trend
-- Description: Transform gold_course_performance_trend from silver to gold

-- Metric: course_performance_trend: Trend of course performance metrics over time
INSERT INTO gold_course_performance_trend (course_id, month, average_score, total_enrollments)
SELECT 
    course_id,
    DATE_TRUNC('month', performance_date) AS month,
    AVG(score) AS average_score,  -- Calculate average score for the month
    COUNT(*) AS total_enrollments   -- Count total enrollments for the month
FROM 
    course_performance
WHERE 
    performance_date >= CURRENT_DATE - INTERVAL '12 months'  -- Filter for the last 12 months
GROUP BY 
    course_id, month
ORDER BY 
    course_id, month;  -- Order by course_id and month for better readability