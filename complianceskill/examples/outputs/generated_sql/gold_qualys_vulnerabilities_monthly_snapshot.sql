{{ config(materialized='table', unique_key='connection_id, month_start, host_id, os', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH monthly AS (
  SELECT
    src.connection_id AS connection_id,
    CAST(DATE_TRUNC('month', src.week_start) AS TIMESTAMP WITH TIME ZONE) AS month_start,
    src.host_id AS host_id,
    src.os AS os,
    SUM(src.critical_vuln_count_week) AS critical_vuln_count_month,
    SUM(src.open_vuln_count_week) AS open_vuln_count_month,
    CASE
      WHEN SUM(src.open_vuln_count_week) = 0 THEN NULL
      ELSE SUM(src.avg_days_open_week * src.open_vuln_count_week) / NULLIF(SUM(src.open_vuln_count_week), 0)
    END AS avg_days_open_month
  FROM {{ ref('gold_qualys_vulnerabilities_weekly_snapshot') }} AS src
  {% if is_incremental() %}
    WHERE src.week_start >= (
      SELECT COALESCE(MAX(month_start), '1970-01-01'::timestamp with time zone)
      FROM {{ this }}
    )
    AND src.connection_id = {{ var('connection_id') }}
  {% else %}
    WHERE src.connection_id = {{ var('connection_id') }}
  {% endif %}
  GROUP BY
    src.connection_id,
    CAST(DATE_TRUNC('month', src.week_start) AS TIMESTAMP WITH TIME ZONE),
    src.host_id,
    src.os
)

SELECT
  m.connection_id,
  m.month_start,
  m.host_id,
  m.os,
  m.critical_vuln_count_month,
  m.open_vuln_count_month,
  m.avg_days_open_month
FROM monthly AS m;