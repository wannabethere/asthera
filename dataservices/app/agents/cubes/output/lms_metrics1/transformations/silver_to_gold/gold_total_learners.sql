-- Transformation: silver_to_gold_gold_total_learners
-- Source: silver.gold_total_learners
-- Target: gold.gold_gold_total_learners
-- Description: Transform gold_total_learners from silver to gold

-- Metric: total_learners: Total number of learners engaged in the platform
INSERT INTO gold_total_learners (total_learners)
SELECT COUNT(DISTINCT learner_id) AS total_learners
FROM learner_engagement
WHERE active = TRUE  -- Only count active learners
  AND deleted = FALSE;  -- Exclude deleted accounts