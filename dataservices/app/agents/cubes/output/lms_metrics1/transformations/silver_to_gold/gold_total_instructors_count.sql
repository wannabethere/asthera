-- Transformation: silver_to_gold_gold_total_instructors_count
-- Source: silver.gold_total_instructors_count
-- Target: gold.gold_gold_total_instructors_count
-- Description: Transform gold_total_instructors_count from silver to gold

-- Metric: total_instructors_count: Total number of instructors in the system
INSERT INTO gold_total_instructors_count (total_instructors_count)
SELECT COUNT(*) AS total_instructors_count
FROM instructors
WHERE "active" = TRUE;