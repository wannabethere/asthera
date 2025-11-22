-- Transformation: silver_to_gold_gold_percentage_of_active_learners
-- Source: silver.gold_percentage_of_active_learners
-- Target: gold.gold_gold_percentage_of_active_learners
-- Description: Transform gold_percentage_of_active_learners from silver to gold

-- Metric: percentage_of_active_learners: Percentage of learners actively engaging with the platform
INSERT INTO gold_percentage_of_active_learners (percentage_active_learners)
SELECT 
    COALESCE(
        (COUNT(DISTINCT CASE WHEN le.engagement_date >= CURRENT_DATE - INTERVAL '30 days' THEN le.learner_id END) * 100.0) / 
        NULLIF(COUNT(DISTINCT l.learner_id), 0), 
    0) AS percentage_active_learners
FROM 
    learners l
LEFT JOIN 
    learner_engagement le ON l.learner_id = le.learner_id;