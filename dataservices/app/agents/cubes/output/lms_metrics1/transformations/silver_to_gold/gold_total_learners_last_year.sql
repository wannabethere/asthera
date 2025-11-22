-- Transformation: silver_to_gold_gold_total_learners_last_year
-- Source: silver.gold_total_learners_last_year
-- Target: gold.gold_gold_total_learners_last_year
-- Description: Transform gold_total_learners_last_year from silver to gold

-- Metric: total_learners_last_year: Total number of learners who consumed more than one activity last year.
INSERT INTO gold_total_learners_last_year (total_learners)
SELECT COUNT(DISTINCT learner_id) AS total_learners
FROM learners_activities
WHERE DATE_TRUNC('year', activity_date) = DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year'
GROUP BY learner_id
HAVING COUNT(activity_id) > 1;