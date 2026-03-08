-- Example: gold_snyk_issues_daily_snapshot
-- Daily snapshot of Snyk vulnerability issues for MTTR and open count metrics
{{
  config(
    materialized='incremental',
    unique_key='pk',
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
  )
}}
SELECT
  connection_id,
  id AS issue_id,
  severity,
  state,
  created_at,
  fixed_at,
  project_id,
  DATE_TRUNC('day', created_at)::date AS snapshot_date,
  CONCAT(connection_id, '|', id, '|', DATE_TRUNC('day', created_at)::date) AS pk
FROM {{ source('silver', 'snyk_issues') }}
WHERE connection_id IS NOT NULL
{% if is_incremental() %}
  AND DATE_TRUNC('day', created_at)::date >= (SELECT MAX(snapshot_date) - INTERVAL '3 days' FROM {{ this }})
{% endif %}
