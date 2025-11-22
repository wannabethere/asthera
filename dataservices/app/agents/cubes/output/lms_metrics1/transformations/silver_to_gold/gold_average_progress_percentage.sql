-- Transformation: silver_to_gold_gold_average_progress_percentage
-- Source: silver.gold_average_progress_percentage
-- Target: gold.gold_gold_average_progress_percentage
-- Description: Transform gold_average_progress_percentage from silver to gold

-- Metric: average_progress_percentage: The average progress percentage of all enrollments.
INSERT INTO gold_average_progress_percentage (average_progress_percentage)
SELECT 
    COALESCE(SUM(CASE 
        WHEN total_required_progress > 0 THEN (current_progress::DECIMAL / total_required_progress) * 100 
        ELSE NULL 
    END) / NULLIF(COUNT(*), 0), 0) AS average_progress_percentage
FROM 
    enrollments;