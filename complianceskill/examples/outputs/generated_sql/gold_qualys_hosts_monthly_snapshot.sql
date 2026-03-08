{{ config(materialized='table', unique_key='connection_id, month_start_date, organization_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH monthly_agg AS (
    SELECT
        src.connection_id AS connection_id,
        CAST(DATE_TRUNC('month', src.week_start_date) AS TIMESTAMP WITH TIME ZONE) AS month_start_date,
        src.organization_id AS organization_id,
        MAX(src.total_hosts) AS monthly_total_hosts,
        MAX(src.hosts_without_recent_detections) AS monthly_hosts_without_recent_detections
    FROM {{ ref('gold_qualys_hosts_weekly_snapshot') }} AS src
    WHERE src.connection_id = '{{ var("connection_id") }}'
    GROUP BY
        src.connection_id,
        CAST(DATE_TRUNC('month', src.week_start_date) AS TIMESTAMP WITH TIME ZONE),
        src.organization_id
)

SELECT
    connection_id,
    month_start_date,
    organization_id,
    monthly_total_hosts,
    monthly_hosts_without_recent_detections
FROM monthly_agg
