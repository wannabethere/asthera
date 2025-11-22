-- Transformation: silver_to_gold_gold_instructor_feedback_count
-- Source: silver.gold_instructor_feedback_count
-- Target: gold.gold_gold_instructor_feedback_count
-- Description: Transform gold_instructor_feedback_count from silver to gold

-- Metric: instructor_feedback_count: Total number of feedback submissions for instructors
INSERT INTO gold_instructor_feedback_count (instructor_id, feedback_count)
SELECT 
    instructor_id,
    COUNT(*) AS feedback_count
FROM 
    instructor_feedback
WHERE 
    feedback_date >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year' 
    AND feedback_date < DATE_TRUNC('year', CURRENT_DATE)
GROUP BY 
    instructor_id;