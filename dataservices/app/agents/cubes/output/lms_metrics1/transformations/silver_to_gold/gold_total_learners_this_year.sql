-- Transformation: silver_to_gold_gold_total_learners_this_year
-- Source: silver.gold_total_learners_this_year
-- Target: gold.gold_gold_total_learners_this_year
-- Description: Transform gold_total_learners_this_year from silver to gold

-- Metric: total_learners_this_year: Total number of learners who consumed more than one activity this year.
WITH activity_counts AS (
    SELECT 
        "learner_id", 
        COUNT(*) AS activity_count
    FROM 
        "learners_activities"
    WHERE 
        DATE_TRUNC('year', "activity_date") = DATE_TRUNC('year', CURRENT_DATE)  -- Filter for current year
    GROUP BY 
        "learner_id"
)
SELECT 
    COUNT(DISTINCT "learner_id") AS total_learners
FROM 
    activity_counts
WHERE 
    activity_count > 1;  -- Only count learners with more than one activity