-- Transformation: silver_to_gold_gold_engagement_by_category
-- Source: silver.gold_engagement_by_category
-- Target: gold.gold_gold_engagement_by_category
-- Description: Transform gold_engagement_by_category from silver to gold

-- Metric: engagement_by_category: Engagement metrics segmented by course category
INSERT INTO gold_engagement_by_category (course_category, engagement_count, month)
SELECT 
    cc."category_name" AS course_category,
    COUNT(le."engagement_id") AS engagement_count,
    DATE_TRUNC('month', le."engagement_timestamp") AS month
FROM 
    learner_engagement le
JOIN 
    course_categories cc ON le."course_id" = cc."course_id"
WHERE 
    cc."is_active" = TRUE  -- Only include active courses
GROUP BY 
    cc."category_name", DATE_TRUNC('month', le."engagement_timestamp")
ORDER BY 
    month, course_category;