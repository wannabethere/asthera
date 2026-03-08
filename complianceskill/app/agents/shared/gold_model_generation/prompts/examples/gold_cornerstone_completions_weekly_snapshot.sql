-- Example: gold_cornerstone_completions_weekly_snapshot
-- Weekly completion metrics for Cornerstone/CSOD LMS training compliance
{{
  config(
    materialized='table',
    unique_key='pk'
  )
}}
SELECT
  connection_id,
  user_id,
  learning_id,
  completion_status,
  completed_at,
  DATE_TRUNC('week', completed_at)::date AS week_start,
  CONCAT(connection_id, '|', user_id, '|', learning_id, '|', week_start) AS pk
FROM {{ source('silver', 'cornerstone_learning_completions') }}
WHERE connection_id IS NOT NULL
  AND completed_at IS NOT NULL
