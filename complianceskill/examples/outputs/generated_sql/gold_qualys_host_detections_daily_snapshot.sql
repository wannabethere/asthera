{{ config(materialized='incremental', unique_key='connection_id,snapshot_date,host_id,qid', incremental_strategy='merge', on_schema_change='append_new_columns') }}

SELECT
  det.connection_id AS connection_id,
  CAST(date_trunc('day', CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE)) AS TIMESTAMP WITH TIME ZONE) AS snapshot_date,
  det.host_id AS host_id,
  h.ip AS ip,
  h.os AS os,
  det.qid AS qid,
  det.severity AS severity,
  det.status AS status,
  CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE) AS last_found_datetime,
  det.organization_id AS organization_id,
  (CURRENT_DATE - CAST(CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE) AS DATE))::integer AS days_since_last_found

FROM {{ source('silver', 'qualys_host_detections') }} AS det
LEFT JOIN {{ source('silver', 'qualys_hosts') }} AS h
  ON det.host_id = h.id
  AND det.connection_id = h.connection_id

WHERE det.connection_id = {{ var('connection_id') }}
{% if is_incremental() %}
  AND CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE) >= (CURRENT_DATE - INTERVAL '1 day')
{% endif %}

GROUP BY
  det.connection_id,
  CAST(date_trunc('day', CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE)) AS TIMESTAMP WITH TIME ZONE),
  det.host_id,
  h.ip,
  h.os,
  det.qid,
  det.severity,
  det.status,
  CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE),
  det.organization_id,
  (CURRENT_DATE - CAST(CAST(det.last_found_datetime AS TIMESTAMP WITH TIME ZONE) AS DATE))::integer;