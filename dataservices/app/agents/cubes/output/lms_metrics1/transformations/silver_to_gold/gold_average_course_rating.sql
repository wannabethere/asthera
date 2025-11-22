-- Transformation: silver_to_gold_gold_average_course_rating
-- Source: silver.gold_average_course_rating
-- Target: gold.gold_gold_average_course_rating
-- Description: Transform gold_average_course_rating from silver to gold

-- Metric: average_course_rating: Average rating of all courses offered
INSERT INTO gold_average_course_rating (average_rating)
SELECT 
    COALESCE(SUM(rating), 0) / NULLIF(COUNT(rating), 0) AS average_rating
FROM 
    course_ratings
WHERE 
    course_status = 'completed';  -- Only include ratings from completed courses