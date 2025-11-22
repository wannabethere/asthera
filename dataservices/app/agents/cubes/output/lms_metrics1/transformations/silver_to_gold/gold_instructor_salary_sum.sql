-- Transformation: silver_to_gold_gold_instructor_salary_sum
-- Source: silver.gold_instructor_salary_sum
-- Target: gold.gold_gold_instructor_salary_sum
-- Description: Transform gold_instructor_salary_sum from silver to gold

-- Metric: instructor_salary_sum: Total salary paid to instructors
INSERT INTO gold_instructor_salary_sum (total_salary)
SELECT COALESCE(SUM(salary), 0) AS total_salary
FROM instructors
WHERE active = TRUE;