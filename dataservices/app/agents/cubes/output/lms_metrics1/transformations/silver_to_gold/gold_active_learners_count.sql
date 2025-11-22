-- Transformation: silver_to_gold_gold_active_learners_count
-- Source: silver.gold_active_learners_count
-- Target: gold.gold_gold_active_learners_count
-- Description: Transform gold_active_learners_count from silver to gold

-- Metric: active_learners_count: Total number of active learners in the system.
INSERT INTO gold_active_learners_count (active_learners_count)
SELECT COUNT(*) AS active_learners_count
FROM learners_table
WHERE "status" = 'active'
  AND "last_activity_date" >= CURRENT_DATE - INTERVAL '30 days';