{{ config(materialized='incremental', unique_key='connection_id,week_start,host_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH source_data AS (
  SELECT
    d.connection_id AS connection_id,
    DATE_TRUNC('week', CAST(d.snapshot_date AS TIMESTAMP WITH TIME ZONE)) AS week_start,
    d.host_id AS host_id,
    d.ip AS ip,
    d.os AS os,
    d.is_critical AS is_critical,
    d.is_open AS is_open,
    d.days_open AS days_open
  FROM {{ ref('gold_qualys_vulnerabilities_daily_snapshot') }} AS d
  WHERE d.connection_id = {{ var('connection_id') }}
  {% if is_incremental() %}
    AND DATE_TRUNC('week', CAST(d.snapshot_date AS TIMESTAMP WITH TIME ZONE)) >= (
      SELECT COALESCE(MAX(week_start), '1970-01-01'::timestamp AT TIME ZONE 'UTC')
      FROM {{ this }}
      WHERE connection_id = {{ var('connection_id') }}
    )
  {% endif %}
)

SELECT
  sd.connection_id AS connection_id,
  sd.week_start AS week_start,
  sd.host_id AS host_id,
  sd.ip AS ip,
  sd.os AS os,
  SUM(CASE WHEN sd.is_critical = TRUE THEN 1 ELSE 0 END) AS critical_vuln_count_week,
  SUM(CASE WHEN sd.is_open = TRUE THEN 1 ELSE 0 END) AS open_vuln_count_week,
  AVG(sd.days_open) AS avg_days_open_week
FROM source_data sd
GROUP BY
  sd.connection_id,
  sd.week_start,
  sd.host_id,
  sd.ip,
  sd.os