{{ config(materialized='incremental', unique_key=['connection_id','week_start','issue_language','issue_package'], incremental_strategy='merge', on_schema_change='append_new_columns') }}

select
  daily.connection_id,
  CAST(DATE_TRUNC('week', daily.snapshot_date) AS TIMESTAMP WITH TIME ZONE) AS week_start,
  daily.issue_language,
  daily.issue_package,
  SUM(CASE WHEN daily.is_high_cvss = TRUE THEN 1 ELSE 0 END) AS count_high_cvss_week,
  json_build_object(
    'min', MIN(daily.cvss_score),
    'p25', percentile_disc(0.25) WITHIN GROUP (ORDER BY daily.cvss_score),
    'p50', percentile_disc(0.50) WITHIN GROUP (ORDER BY daily.cvss_score),
    'p75', percentile_disc(0.75) WITHIN GROUP (ORDER BY daily.cvss_score),
    'max', MAX(daily.cvss_score),
    'avg', AVG(daily.cvss_score)
  ) AS cvss_distribution_week
from {{ ref('gold_snyk_issues_daily_snapshot') }} as daily
where daily.connection_id = {{ var('connection_id') }}
{% if is_incremental() %}
  -- incremental runs only process recent snapshots (by snapshot_date -> week_start)
  AND daily.snapshot_date >= (
    select coalesce(max(week_start), '1970-01-01'::timestamp) from {{ this }}
  )
{% endif %}
group by
  daily.connection_id,
  CAST(DATE_TRUNC('week', daily.snapshot_date) AS TIMESTAMP WITH TIME ZONE),
  daily.issue_language,
  daily.issue_package;