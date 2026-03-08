{{ config(materialized='table', unique_key='connection_id,month_start_date,host_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH monthly_agg AS (
  SELECT
    ws.connection_id AS connection_id,
    CAST(DATE_TRUNC('month', ws.week_start_date) AS TIMESTAMP WITH TIME ZONE) AS month_start_date,
    ws.host_id AS host_id,
    ws.os AS os,
    SUM(ws.open_vulnerability_count) AS monthly_open_vulnerability_count,
    CASE
      WHEN SUM(ws.open_vulnerability_count) = 0 THEN NULL
      ELSE SUM(ws.average_days_open * ws.open_vulnerability_count) / NULLIF(SUM(ws.open_vulnerability_count), 0)
    END AS monthly_average_days_open
  FROM {{ ref('gold_qualys_host_detections_weekly_snapshot') }} AS ws
  WHERE ws.connection_id = {{ var('connection_id') }}
  GROUP BY
    ws.connection_id,
    CAST(DATE_TRUNC('month', ws.week_start_date) AS TIMESTAMP WITH TIME ZONE),
    ws.host_id,
    ws.os
)

SELECT
  ma.connection_id,
  ma.month_start_date,
  ma.host_id,
  ma.os,
  ma.monthly_open_vulnerability_count,
  ma.monthly_average_days_open
FROM monthly_agg AS ma
ORDER BY ma.connection_id, ma.month_start_date, ma.host_id, ma.os;