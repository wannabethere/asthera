{{ config(materialized='incremental', unique_key='connection_id,organization_id,issue_package,publication_time', incremental_strategy='merge', on_schema_change='append_new_columns') }}

WITH source_data AS (
    SELECT
        src."connection_id" AS connection_id,
        src."organization_id" AS organization_id,
        -- normalize publication time to day-level snapshot (timestamp with time zone)
        CAST(date_trunc('day', CAST(src."v1.issue.publicationTime" AS TIMESTAMP WITH TIME ZONE)) AS TIMESTAMP WITH TIME ZONE) AS snapshot_date,
        src."v1.issue.package" AS issue_package,
        src."v1.issue.language" AS issue_language,
        -- cast CVSS score to numeric when it is a numeric-looking string
        CASE
            WHEN src."v1.issue.cvssScore" ~ '^[0-9]+(\.[0-9]+)?$' THEN CAST(src."v1.issue.cvssScore" AS NUMERIC)
            ELSE NULL
        END AS cvss_score,
        -- derive high CVSS flag
        CASE
            WHEN src."v1.issue.cvssScore" ~ '^[0-9]+(\.[0-9]+)?$' AND CAST(src."v1.issue.cvssScore" AS NUMERIC) >= 7.0 THEN TRUE
            ELSE FALSE
        END AS is_high_cvss,
        CAST(src."v1.issue.publicationTime" AS TIMESTAMP WITH TIME ZONE) AS publication_time,
        src."v1.issue.semver.vulnerable" AS vulnerable_semver_ranges
    FROM {{ source('silver', 'snyk_issues') }} AS src
    {% if is_incremental() %}
    WHERE src."connection_id" = '{{ var("connection_id") }}'
    {% else %}
    WHERE src."connection_id" = '{{ var("connection_id") }}'
    {% endif %}
)

SELECT
    sd.connection_id,
    sd.organization_id,
    sd.snapshot_date,
    sd.issue_package,
    sd.issue_language,
    sd.cvss_score,
    sd.is_high_cvss,
    sd.publication_time,
    sd.vulnerable_semver_ranges
FROM source_data AS sd