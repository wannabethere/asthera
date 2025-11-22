-- Transformation: silver_to_gold_gold_average_instructor_rating
-- Source: silver.gold_average_instructor_rating
-- Target: gold.gold_gold_average_instructor_rating
-- Description: Transform gold_average_instructor_rating from silver to gold

-- Metric: average_instructor_rating: Average rating of instructors based on student feedback
INSERT INTO gold_average_instructor_rating (average_rating)
SELECT 
    COALESCE(SUM(rating), 0) / NULLIF(COUNT(rating), 0) AS average_rating
FROM 
    instructor_feedback
WHERE 
    feedback_date >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year'
    AND feedback_date < DATE_TRUNC('year', CURRENT_DATE);