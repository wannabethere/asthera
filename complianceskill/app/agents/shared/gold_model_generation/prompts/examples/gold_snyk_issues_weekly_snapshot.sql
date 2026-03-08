-- Example: gold_snyk_issues_weekly_snapshot
-- Weekly aggregation of Snyk issues for severity counts and MTTR
{{
  config(
    materialized='incremental',
    unique_key='pk',
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
  )
}}
WITH daily AS (
  SELECT
    connection_id,
    project_id,
    severity,
    state,
    created_at,
    fixed_at,
    DATE_TRUNC('week', created_at)::date AS week_start
  FROM {{ source('silver', 'snyk_issues') }}
  WHERE connection_id IS NOT NULL
  {% if is_incremental() %}
    AND DATE_TRUNC('week', created_at)::date >= (SELECT MAX(week_start) - INTERVAL '2 weeks' FROM {{ this }})
  {% endif %}
)
SELECT
  connection_id,
  project_id,
  week_start,
  severity,
  COUNT(*) AS issue_count,
  COUNT(*) FILTER (WHERE state = 'open') AS open_count,
  AVG((fixed_at::date - created_at::date)) FILTER (WHERE state = 'fixed') AS avg_days_to_fix,
  CONCAT(connection_id, '|', project_id, '|', week_start, '|', severity) AS pk
FROM daily
GROUP BY connection_id, project_id, week_start, severity
