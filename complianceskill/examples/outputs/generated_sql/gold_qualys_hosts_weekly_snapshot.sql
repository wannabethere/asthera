{{ config(materialized='incremental', unique_key='connection_id, week_start_date, organization_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH hosts AS (
  SELECT
    h.connection_id AS connection_id,
    CAST(h.snapshot_date AS TIMESTAMP WITH TIME ZONE) AS week_start_date,
    h.organization_id AS organization_id,
    h.id AS host_id
  FROM {{ ref('gold_qualys_hosts_daily_snapshot') }} AS h
  WHERE 1 = 1
  {% if var('connection_id', none) is not none %}
    AND h.connection_id = {{ var('connection_id') }}
  {% endif %}
  {% if is_incremental() %}
    -- For incremental runs, only process snapshot_date on/after the latest week already in the target
    AND h.snapshot_date >= (
      SELECT COALESCE(MAX(week_start_date), '1970-01-01'::timestamp with time zone)
      FROM {{ this }}
    )
  {% endif %}
),

detections AS (
  SELECT
    d.connection_id AS connection_id,
    CAST(d.snapshot_date AS TIMESTAMP WITH TIME ZONE) AS week_start_date,
    d.id AS host_id,
    d.open_vulnerability_count AS open_vulnerability_count
  FROM {{ ref('gold_qualys_host_detections_weekly_snapshot') }} AS d
)

SELECT
  h.connection_id AS connection_id,
  h.week_start_date AS week_start_date,
  h.organization_id AS organization_id,
  COUNT(DISTINCT h.host_id) AS total_hosts,
  COUNT(DISTINCT CASE WHEN COALESCE(d.open_vulnerability_count, 0) > 0 THEN h.host_id END) AS hosts_with_recent_detections,
  (COUNT(DISTINCT h.host_id) - COUNT(DISTINCT CASE WHEN COALESCE(d.open_vulnerability_count, 0) > 0 THEN h.host_id END)) AS hosts_without_recent_detections
FROM hosts AS h
LEFT JOIN detections AS d
  ON d.connection_id = h.connection_id
  AND d.week_start_date = h.week_start_date
  AND d.host_id = h.host_id
GROUP BY
  h.connection_id,
  h.week_start_date,
  h.organization_id