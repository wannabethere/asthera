{{ config(materialized='incremental', unique_key='connection_id,snapshot_date,host_id,name,version', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH source_data AS (
  SELECT
    a.connection_id AS connection_id,
    CAST(date_trunc('day', now()) AS TIMESTAMP WITH TIME ZONE) AS snapshot_date,
    a.host_id AS host_id,
    a.name AS name,
    a.version AS version,
    h.ip AS ip,
    h.os AS os,
    a.organization_id AS organization_id
  FROM {{ source('silver', 'qualys_applications') }} AS a
  LEFT JOIN {{ source('silver', 'qualys_hosts') }} AS h
    ON a.host_id = h.id
    AND a.connection_id = h.connection_id
  WHERE a.connection_id = {{ var('connection_id') }}
  {% if is_incremental() %}
    AND is_incremental()
  {% endif %}
)

SELECT
  sd.connection_id,
  sd.snapshot_date,
  sd.host_id,
  sd.name,
  sd.version,
  sd.ip,
  sd.os,
  sd.organization_id
FROM source_data AS sd
GROUP BY
  sd.connection_id,
  sd.snapshot_date,
  sd.host_id,
  sd.name,
  sd.version,
  sd.ip,
  sd.os,
  sd.organization_id;