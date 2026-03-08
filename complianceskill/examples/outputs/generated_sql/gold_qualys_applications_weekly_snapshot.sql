{{ config(materialized='incremental', unique_key='connection_id,week_start_date,host_id,name,version', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH daily AS (
  SELECT
    d.connection_id AS connection_id,
    CAST(date_trunc('week', d.snapshot_date) AS TIMESTAMP WITH TIME ZONE) AS week_start_date,
    d.host_id AS host_id,
    d.name AS name,
    d.version AS version,
    CAST(d.snapshot_date AS TIMESTAMP WITH TIME ZONE) AS snapshot_ts
  FROM {{ ref('gold_qualys_applications_daily_snapshot') }} AS d
  WHERE
    d.connection_id IS NOT NULL
    AND (
      NOT is_incremental()
      OR (is_incremental() AND d.snapshot_date >= date_trunc('week', current_date) - INTERVAL '7 days')
    )
),

-- Deduplicate to one row per host/software/version per week
weekly_presence AS (
  SELECT
    d.connection_id AS connection_id,
    d.week_start_date AS week_start_date,
    d.host_id AS host_id,
    d.name AS name,
    d.version AS version,
    MIN(d.snapshot_ts) AS first_seen_ts
  FROM daily AS d
  GROUP BY
    d.connection_id,
    d.week_start_date,
    d.host_id,
    d.name,
    d.version
)

SELECT
  w.connection_id,
  w.week_start_date,
  w.host_id,
  w.name,
  w.version,
  -- number of unique hosts in the connection/week that reported this name+version
  COUNT(DISTINCT w.host_id) OVER (PARTITION BY w.connection_id, w.week_start_date, w.name, w.version) AS unique_software_count,
  -- flag if there is no record for this host/name/version prior to the week_start_date -> new install within the last 7 days
  CASE
    WHEN NOT EXISTS (
      SELECT 1
      FROM {{ ref('gold_qualys_applications_daily_snapshot') }} AS e
      WHERE
        e.connection_id = w.connection_id
        AND e.host_id = w.host_id
        AND e.name = w.name
        AND e.version = w.version
        AND CAST(e.snapshot_date AS TIMESTAMP WITH TIME ZONE) < w.week_start_date
    ) THEN 1 ELSE 0 END AS new_installs_last_7_days_flag
FROM weekly_presence AS w
