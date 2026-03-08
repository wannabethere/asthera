{{ config(materialized='table', unique_key='connection_id,month_start,issue_language,issue_package', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH monthly_counts AS (
  SELECT
    ws.connection_id AS connection_id,
    CAST(date_trunc('month', ws.week_start) AS TIMESTAMP WITH TIME ZONE) AS month_start,
    ws.issue_language AS issue_language,
    ws.issue_package AS issue_package,
    SUM(ws.count_high_cvss_week) AS monthly_high_cvss_count
  FROM {{ ref('gold_snyk_issues_weekly_snapshot') }} AS ws
  WHERE ws.connection_id = {{ var('connection_id') }}
  GROUP BY ws.connection_id, CAST(date_trunc('month', ws.week_start) AS TIMESTAMP WITH TIME ZONE), ws.issue_language, ws.issue_package
),
monthly_cvss_buckets AS (
  -- Unnest weekly JSON distributions into key/value rows, sum per month/language/package/key,
  -- then re-aggregate into a single JSON object per month/language/package
  SELECT
    sub.connection_id,
    sub.month_start,
    sub.issue_language,
    sub.issue_package,
    jsonb_object_agg(sub.cvss_key, sub.bucket_sum) AS monthly_cvss_distribution
  FROM (
    SELECT
      ws2.connection_id AS connection_id,
      CAST(date_trunc('month', ws2.week_start) AS TIMESTAMP WITH TIME ZONE) AS month_start,
      ws2.issue_language AS issue_language,
      ws2.issue_package AS issue_package,
      pd.key AS cvss_key,
      SUM((pd.value)::bigint) AS bucket_sum
    FROM {{ ref('gold_snyk_issues_weekly_snapshot') }} AS ws2
    CROSS JOIN LATERAL jsonb_each_text(ws2.cvss_distribution_week) AS pd(key, value)
    WHERE ws2.connection_id = {{ var('connection_id') }}
    GROUP BY ws2.connection_id, CAST(date_trunc('month', ws2.week_start) AS TIMESTAMP WITH TIME ZONE), ws2.issue_language, ws2.issue_package, pd.key
  ) AS sub
  GROUP BY sub.connection_id, sub.month_start, sub.issue_language, sub.issue_package
)

SELECT
  mc.connection_id AS connection_id,
  mc.month_start AS month_start,
  mc.issue_language AS issue_language,
  mc.issue_package AS issue_package,
  mc.monthly_high_cvss_count AS monthly_high_cvss_count,
  COALESCE(mcv.monthly_cvss_distribution, '{}'::jsonb) AS monthly_cvss_distribution
FROM monthly_counts AS mc
LEFT JOIN monthly_cvss_buckets AS mcv
  ON mcv.connection_id = mc.connection_id
  AND mcv.month_start = mc.month_start
  AND mcv.issue_language = mc.issue_language
  AND mcv.issue_package = mc.issue_package
