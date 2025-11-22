-- Transformation: silver_to_gold_gold_active_learners_by_user_type
-- Source: silver.gold_active_learners_by_user_type
-- Target: gold.gold_gold_active_learners_by_user_type
-- Description: Transform gold_active_learners_by_user_type from silver to gold

-- Metric: active_learners_by_user_type: Breakdown of active learners by user type.
INSERT INTO gold_active_learners_by_user_type (user_type, active_learners_count)
SELECT 
    user_type,
    COUNT(*) AS active_learners_count
FROM 
    learners_table
WHERE 
    learner_status = 'active'  -- Filter for active learners
    AND user_type IS NOT NULL   -- Ensure user_type is not NULL
GROUP BY 
    user_type
ORDER BY 
    user_type;  -- Optional: Order by user_type for better readability