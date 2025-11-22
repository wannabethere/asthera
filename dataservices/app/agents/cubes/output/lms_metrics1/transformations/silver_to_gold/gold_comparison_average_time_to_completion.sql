-- Transformation: silver_to_gold_gold_comparison_average_time_to_completion
-- Source: silver.gold_comparison_average_time_to_completion
-- Target: gold.gold_gold_comparison_average_time_to_completion
-- Description: Transform gold_comparison_average_time_to_completion from silver to gold

-- Metric: comparison_average_time_to_completion: Comparison of average time to completion for each course between this year and last year.
INSERT INTO gold_comparison_average_time_to_completion (course_id, avg_time_this_year, avg_time_last_year)
WITH completion_data AS (
    SELECT 
        cr.course_id,
        DATE_TRUNC('year', cr.completion_date) AS completion_year,
        AVG(cr.completion_time) AS avg_completion_time
    FROM 
        completion_records cr
    WHERE 
        cr.completion_date >= CURRENT_DATE - INTERVAL '2 years'  -- Filter for the last two years
    GROUP BY 
        cr.course_id, DATE_TRUNC('year', cr.completion_date)
),
yearly_averages AS (
    SELECT 
        cd.course_id,
        MAX(CASE WHEN cd.completion_year = DATE_TRUNC('year', CURRENT_DATE) THEN cd.avg_completion_time END) AS avg_time_this_year,
        MAX(CASE WHEN cd.completion_year = DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year' THEN cd.avg_completion_time END) AS avg_time_last_year
    FROM 
        completion_data cd
    GROUP BY 
        cd.course_id
)
SELECT 
    ya.course_id,
    ya.avg_time_this_year,
    ya.avg_time_last_year
FROM 
    yearly_averages ya
WHERE 
    COALESCE(ya.avg_time_this_year, 0) > 0 AND COALESCE(ya.avg_time_last_year, 0) > 0;  -- Ensure both years have valid data for comparison