-- Transformation: silver_to_gold_gold_percentage_change_learners
-- Source: silver.gold_percentage_change_learners
-- Target: gold.gold_gold_percentage_change_learners
-- Description: Transform gold_percentage_change_learners from silver to gold

-- Metric: percentage_change_learners: Percentage change in the number of learners who consumed more than one activity from last year to this year.
WITH learner_activity AS (
    SELECT 
        COUNT(DISTINCT learner_id) AS total_learners,
        EXTRACT(YEAR FROM activity_date) AS activity_year
    FROM 
        activities
    WHERE 
        activity_count > 1  -- Filter for learners who consumed more than one activity
    GROUP BY 
        activity_year
)

SELECT 
    COALESCE(
        ((current_year.total_learners - last_year.total_learners) / NULLIF(last_year.total_learners, 0)) * 100, 
        0
    ) AS percentage_change
FROM 
    (SELECT total_learners FROM learner_activity WHERE activity_year = EXTRACT(YEAR FROM CURRENT_DATE)) AS current_year,
    (SELECT total_learners FROM learner_activity WHERE activity_year = EXTRACT(YEAR FROM CURRENT_DATE) - 1) AS last_year;