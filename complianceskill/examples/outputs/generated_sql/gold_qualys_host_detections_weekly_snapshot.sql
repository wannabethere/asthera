{{ config(materialized='incremental', unique_key=['connection_id','week_start_date','host_id','os','severity'], incremental_strategy='merge', on_schema_change='append_new_columns') }}

with daily_source as (
  select
    d.snapshot_date,
    d.host_id,
    d.os,
    d.severity,
    d.status,
    d.days_since_last_found,
    d.connection_id
  from {{ ref('gold_qualys_host_detections_daily_snapshot') }} as d
  where d.connection_id = {{ var('connection_id') }}
    and d.severity = 'CRITICAL'
    {% if is_incremental() %}
      and DATE_TRUNC('week', d.snapshot_date) >= (
        select coalesce(max(t.week_start_date), '1970-01-01'::timestamp with time zone)
        from {{ this }} as t
      )
    {% endif %}
)

select
  daily_source.connection_id as connection_id,
  CAST(DATE_TRUNC('week', daily_source.snapshot_date) AS TIMESTAMP WITH TIME ZONE) as week_start_date,
  daily_source.host_id as host_id,
  daily_source.os as os,
  daily_source.severity as severity,
  COUNT(CASE WHEN daily_source.status = 'OPEN' THEN 1 END) as open_vulnerability_count,
  AVG(CASE WHEN daily_source.status = 'OPEN' THEN daily_source.days_since_last_found END) as average_days_open
from daily_source
group by
  daily_source.connection_id,
  CAST(DATE_TRUNC('week', daily_source.snapshot_date) AS TIMESTAMP WITH TIME ZONE),
  daily_source.host_id,
  daily_source.os,
  daily_source.severity;