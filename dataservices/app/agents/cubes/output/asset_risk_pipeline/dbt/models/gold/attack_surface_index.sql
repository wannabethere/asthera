-- dbt model: Attack Surface Index
-- Combines all exposure components into a single 0-100 score per asset

{{ config(
    materialized='table',
    indexes=[
        {'columns': ['asset_id'], 'unique': True},
        {'columns': ['business_unit']},
        {'columns': ['env']}
    ]
) }}

WITH asset_exposures AS (
    SELECT 
        a.asset_id,
        a.hostname,
        a.business_unit,
        a.env,
        a.criticality,
        
        -- External Exposure Score (0-30 points)
        CASE 
            WHEN ee.is_public_ip THEN 10 ELSE 0 END +
        CASE 
            WHEN ee.open_ports > 10 THEN 10
            WHEN ee.open_ports > 5 THEN 5
            WHEN ee.open_ports > 0 THEN 2
            ELSE 0 END +
        CASE WHEN ee.weak_tls THEN 5 ELSE 0 END +
        CASE WHEN ee.geo_risky THEN 5 ELSE 0 END
        AS external_exposure_score,
        
        -- Vulnerability Exposure Score (0-25 points)
        COALESCE(
            CASE 
                WHEN SUM(CASE WHEN v.is_kev THEN 1 ELSE 0 END) > 0 THEN 10 ELSE 0 END +
                CASE 
                    WHEN AVG(v.cvss_score * v.epss_score * CASE WHEN v.is_internet_facing THEN 1.5 ELSE 1.0 END) > 8.0 THEN 10
                    WHEN AVG(v.cvss_score * v.epss_score * CASE WHEN v.is_internet_facing THEN 1.5 ELSE 1.0 END) > 6.0 THEN 7
                    WHEN AVG(v.cvss_score * v.epss_score * CASE WHEN v.is_internet_facing THEN 1.5 ELSE 1.0 END) > 4.0 THEN 4
                    ELSE 0 END +
                CASE 
                    WHEN COUNT(DISTINCT v.cve_id) > 50 THEN 5
                    WHEN COUNT(DISTINCT v.cve_id) > 20 THEN 3
                    WHEN COUNT(DISTINCT v.cve_id) > 5 THEN 1
                    ELSE 0 END,
            0
        ) AS vulnerability_exposure_score,
        
        -- Misconfiguration Exposure Score (0-20 points)
        COALESCE(
            SUM(
                CASE m.severity
                    WHEN 'critical' THEN 5
                    WHEN 'high' THEN 3
                    WHEN 'med' THEN 2
                    WHEN 'low' THEN 1
                    ELSE 0
                END
            ),
            0
        ) AS misconfiguration_exposure_score,
        
        -- Identity Exposure Score (0-15 points)
        CASE 
            WHEN ie.num_admin_accounts > 10 THEN 5
            WHEN ie.num_admin_accounts > 5 THEN 3
            WHEN ie.num_admin_accounts > 0 THEN 1
            ELSE 0 END +
        CASE 
            WHEN ie.num_stale_accounts > 20 THEN 4
            WHEN ie.num_stale_accounts > 10 THEN 2
            WHEN ie.num_stale_accounts > 0 THEN 1
            ELSE 0 END +
        CASE WHEN ie.has_password_reuse THEN 3 ELSE 0 END +
        CASE WHEN ie.has_mfa_disabled THEN 3 ELSE 0 END
        AS identity_exposure_score,
        
        -- Software Exposure Score (0-10 points)
        COALESCE(
            CASE 
                WHEN SUM(CASE WHEN si.is_eol THEN 1 ELSE 0 END) > 5 THEN 5
                WHEN SUM(CASE WHEN si.is_eol THEN 1 ELSE 0 END) > 2 THEN 3
                WHEN SUM(CASE WHEN si.is_eol THEN 1 ELSE 0 END) > 0 THEN 1
                ELSE 0 END +
            CASE 
                WHEN SUM(CASE WHEN si.is_unsupported THEN 1 ELSE 0 END) > 5 THEN 5
                WHEN SUM(CASE WHEN si.is_unsupported THEN 1 ELSE 0 END) > 2 THEN 3
                WHEN SUM(CASE WHEN si.is_unsupported THEN 1 ELSE 0 END) > 0 THEN 1
                ELSE 0 END,
            0
        ) AS software_exposure_score
        
    FROM {{ ref('silver_assets') }} a
    LEFT JOIN {{ ref('silver_external_exposure') }} ee ON a.asset_id = ee.asset_id
    LEFT JOIN {{ ref('silver_vulnerabilities') }} v ON a.asset_id = v.asset_id
    LEFT JOIN {{ ref('silver_misconfigurations') }} m ON a.asset_id = m.asset_id
    LEFT JOIN {{ ref('silver_identity_exposure') }} ie ON a.asset_id = ie.asset_id
    LEFT JOIN {{ ref('silver_software_inventory') }} si ON a.asset_id = si.asset_id
    GROUP BY 
        a.asset_id, a.hostname, a.business_unit, a.env, a.criticality,
        ee.is_public_ip, ee.open_ports, ee.weak_tls, ee.geo_risky,
        ie.num_admin_accounts, ie.num_stale_accounts, ie.has_password_reuse, ie.has_mfa_disabled
)
SELECT 
    asset_id,
    hostname,
    business_unit,
    env,
    criticality,
    external_exposure_score,
    vulnerability_exposure_score,
    misconfiguration_exposure_score,
    identity_exposure_score,
    software_exposure_score,
    -- Total ASI (0-100 scale)
    LEAST(100, 
        external_exposure_score + 
        vulnerability_exposure_score + 
        misconfiguration_exposure_score + 
        identity_exposure_score + 
        software_exposure_score
    ) AS attack_surface_index,
    -- Risk-weighted ASI (ASI × criticality / 100)
    LEAST(100, 
        (external_exposure_score + 
         vulnerability_exposure_score + 
         misconfiguration_exposure_score + 
         identity_exposure_score + 
         software_exposure_score) * criticality / 100.0
    ) AS risk_weighted_asi,
    CURRENT_TIMESTAMP AS calculated_at
FROM asset_exposures

