-- Transformation: silver_to_gold_gold_total_courses_offered
-- Source: silver.gold_total_courses_offered
-- Target: gold.gold_gold_total_courses_offered
-- Description: Transform gold_total_courses_offered from silver to gold

-- Metric: total_courses_offered: Total number of courses offered in the data mart
INSERT INTO gold_total_courses_offered (total_courses)
SELECT COUNT(*) AS total_courses
FROM courses
WHERE "active" = TRUE;