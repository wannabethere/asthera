-- Transformation: silver_to_gold_gold_average_progress_percentage_by_enrollment_status
-- Source: silver.gold_average_progress_percentage_by_enrollment_status
-- Target: gold.gold_gold_average_progress_percentage_by_enrollment_status
-- Description: Transform gold_average_progress_percentage_by_enrollment_status from silver to gold

-- Metric: average_progress_percentage_by_enrollment_status: The average progress percentage of enrollments, broken down by enrollment status.
INSERT INTO gold_average_progress_percentage_by_enrollment_status (enrollment_status, average_progress_percentage)
SELECT 
    enrollment_status,
    COALESCE(SUM(progress_percentage), 0) / NULLIF(COUNT(*), 0) AS average_progress_percentage
FROM 
    enrollments
WHERE 
    progress_percentage IS NOT NULL  -- Only include enrollments with a valid progress percentage
GROUP BY 
    enrollment_status;