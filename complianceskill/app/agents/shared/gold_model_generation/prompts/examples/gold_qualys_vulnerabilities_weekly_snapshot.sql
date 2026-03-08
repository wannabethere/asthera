-- Example: gold_qualys_vulnerabilities_weekly_snapshot
-- Weekly snapshot of Qualys vulnerabilities by host for dashboard metrics
{{
  config(
    materialized='incremental',
    unique_key='pk',
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
  )
}}
WITH base AS (
  SELECT
    connection_id,
    host_id,
    qid,
    severity,
    status,
    first_found_dt,
    last_found_dt,
    DATE_TRUNC('week', first_found_dt)::date AS week_start
  FROM {{ source('silver', 'qualys_vulnerability_findings') }}
  WHERE connection_id IS NOT NULL
  {% if is_incremental() %}
    AND DATE_TRUNC('week', first_found_dt)::date >= (SELECT MAX(week_start) - INTERVAL '2 weeks' FROM {{ this }})
  {% endif %}
),
aggregated AS (
  SELECT
    connection_id,
    host_id,
    week_start,
    COUNT(*) FILTER (WHERE severity = 'Critical') AS critical_count,
    COUNT(*) FILTER (WHERE severity = 'High') AS high_count,
    COUNT(*) FILTER (WHERE status = 'Open') AS open_count,
    AVG((last_found_dt::date - first_found_dt::date)) FILTER (WHERE status = 'Fixed') AS avg_days_open
  FROM base
  GROUP BY connection_id, host_id, week_start
)
SELECT
  connection_id,
  host_id,
  week_start,
  critical_count,
  high_count,
  open_count,
  avg_days_open,
  CONCAT(connection_id, '|', host_id, '|', week_start) AS pk
FROM aggregated
