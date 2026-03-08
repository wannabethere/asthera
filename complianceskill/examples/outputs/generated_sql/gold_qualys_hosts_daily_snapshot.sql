{{ config(materialized='incremental', unique_key='id,snapshot_date,connection_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

SELECT
  qh.connection_id AS connection_id,
  CAST(DATE_TRUNC('day', COALESCE(qh.first_found_date, CURRENT_TIMESTAMP)) AS TIMESTAMP WITH TIME ZONE) AS snapshot_date,
  qh.id AS id,
  qh.ip AS ip,
  qh.os AS os,
  CAST(qh.first_found_date AS TIMESTAMP WITH TIME ZONE) AS first_found_date,
  qh.organization_id AS organization_id
FROM {{ source('silver', 'qualys_hosts') }} AS qh
{% if is_incremental() %}
WHERE qh.connection_id = {{ var('connection_id') }}
  AND qh.first_found_date >= (
    SELECT MAX(snapshot_date) FROM {{ this }} WHERE connection_id = {{ var('connection_id') }}
  )
{% else %}
WHERE qh.connection_id = {{ var('connection_id') }}
{% endif %}
GROUP BY
  qh.connection_id,
  CAST(DATE_TRUNC('day', COALESCE(qh.first_found_date, CURRENT_TIMESTAMP)) AS TIMESTAMP WITH TIME ZONE),
  qh.id,
  qh.ip,
  qh.os,
  CAST(qh.first_found_date AS TIMESTAMP WITH TIME ZONE),
  qh.organization_id;