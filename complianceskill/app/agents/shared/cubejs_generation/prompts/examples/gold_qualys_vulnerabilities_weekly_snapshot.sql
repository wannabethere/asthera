-- Example: gold_qualys_vulnerabilities_weekly_snapshot
-- Weekly snapshot of Qualys vulnerabilities by host
{{ config(materialized='incremental', unique_key='pk') }}
SELECT
  connection_id,
  host_id,
  week_start,
  critical_count,
  high_count,
  open_count,
  CONCAT(connection_id, '|', host_id, '|', week_start) AS pk
FROM {{ ref('silver_qualys_vulnerabilities') }}
WHERE week_start = DATE_TRUNC('week', detected_at)::date
