-- Transformation: silver_to_gold_gold_average_progress_percentage_by_course
-- Source: silver.gold_average_progress_percentage_by_course
-- Target: gold.gold_gold_average_progress_percentage_by_course
-- Description: Transform gold_average_progress_percentage_by_course from silver to gold

-- Metric: average_progress_percentage_by_course: The average progress percentage of enrollments, broken down by course.
INSERT INTO gold_average_progress_percentage_by_course (course, average_progress_percentage)
SELECT 
    course,
    COALESCE(SUM(progress_percentage) / NULLIF(COUNT(*), 0), 0) AS average_progress_percentage
FROM 
    enrollments
WHERE 
    progress_percentage IS NOT NULL  -- Only include valid progress percentages
GROUP BY 
    course;