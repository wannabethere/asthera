{{ config(materialized='incremental', unique_key='connection_id, snapshot_date, host_id, qid', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH source_data AS (
  SELECT
    hd.connection_id AS connection_id,
    date_trunc('day', CAST(hd.last_found_datetime AS TIMESTAMP WITH TIME ZONE)) AS snapshot_date,
    hd.host_id AS host_id,
    h.ip AS ip,
    h.os AS os,
    hd.severity AS severity,
    CASE
      WHEN lower(CAST(hd.severity AS TEXT)) IN ('5','critical','crit') THEN 'critical'
      WHEN lower(CAST(hd.severity AS TEXT)) IN ('4','high') THEN 'high'
      WHEN lower(CAST(hd.severity AS TEXT)) IN ('3','medium','med') THEN 'medium'
      WHEN lower(CAST(hd.severity AS TEXT)) IN ('2','low') THEN 'low'
      WHEN lower(CAST(hd.severity AS TEXT)) IN ('1','info','informational') THEN 'info'
      ELSE lower(CAST(hd.severity AS TEXT))
    END AS severity_label,
    CASE
      WHEN lower(CAST(hd.severity AS TEXT)) IN ('5','critical','crit','4','high') THEN true
      ELSE false
    END AS is_critical,
    hd.status AS status,
    CASE
      WHEN lower(CAST(hd.status AS TEXT)) IN ('open','opened') THEN true
      ELSE false
    END AS is_open,
    CAST(hd.last_found_datetime AS TIMESTAMP WITH TIME ZONE) AS last_found_datetime,
    CAST( (CURRENT_TIMESTAMP - CAST(hd.last_found_datetime AS TIMESTAMP WITH TIME ZONE)) / INTERVAL '1 day' AS INTEGER) AS days_open,
    hd.qid AS qid,
    app.name AS application_name,
    app.version AS application_version
  FROM
    {{ source('silver','qualys_host_detections') }} AS hd
  JOIN
    {{ source('silver','qualys_hosts') }} AS h
    ON hd.host_id = h.id
    AND hd.connection_id = h.connection_id
  LEFT JOIN
    {{ source('silver','qualys_applications') }} AS app
    ON hd.host_id = app.host_id
    AND hd.connection_id = app.connection_id
  WHERE
    hd.connection_id = {{ var('connection_id') }}
    {% if is_incremental() %}
      AND CAST(hd.last_found_datetime AS TIMESTAMP WITH TIME ZONE) >= (CURRENT_DATE - INTERVAL '1 day')
    {% endif %}
)

SELECT
  sd.connection_id AS connection_id,
  sd.snapshot_date AS snapshot_date,
  sd.host_id AS host_id,
  sd.ip AS ip,
  sd.os AS os,
  sd.severity AS severity,
  sd.severity_label AS severity_label,
  sd.is_critical AS is_critical,
  sd.status AS status,
  sd.is_open AS is_open,
  sd.last_found_datetime AS last_found_datetime,
  sd.days_open AS days_open,
  sd.qid AS qid,
  sd.application_name AS application_name,
  sd.application_version AS application_version
FROM source_data AS sd
GROUP BY
  sd.connection_id,
  sd.snapshot_date,
  sd.host_id,
  sd.ip,
  sd.os,
  sd.severity,
  sd.severity_label,
  sd.is_critical,
  sd.status,
  sd.is_open,
  sd.last_found_datetime,
  sd.days_open,
  sd.qid,
  sd.application_name,
  sd.application_version;