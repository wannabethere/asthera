{{ config(materialized='table', unique_key='connection_id, month_start_date, name, version', incremental_strategy='merge', on_schema_change='append_new_columns') }}

SELECT
  w.connection_id AS connection_id,
  CAST(date_trunc('month', w.week_start_date) AS TIMESTAMP WITH TIME ZONE) AS month_start_date,
  w.name AS name,
  w.version AS version,
  SUM(w.unique_software_count) AS monthly_unique_software_count,
  SUM(CASE WHEN w.version IS NOT NULL THEN w.unique_software_count ELSE 0 END) AS monthly_eol_software_count
FROM {{ ref('gold_qualys_applications_weekly_snapshot') }} AS w
WHERE w.connection_id = {{ var('connection_id') }}
GROUP BY
  w.connection_id,
  CAST(date_trunc('month', w.week_start_date) AS TIMESTAMP WITH TIME ZONE),
  w.name,
  w.version;