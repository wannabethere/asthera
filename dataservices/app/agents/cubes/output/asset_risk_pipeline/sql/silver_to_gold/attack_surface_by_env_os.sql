-- Attack Surface by Environment and OS/Software Stack
-- Enables drill-downs by environment (prod/non-prod) and software stack

CREATE TABLE IF NOT EXISTS gold.attack_surface_by_env_os AS
WITH software_os_mapping AS (
    SELECT 
        si.asset_id,
        si.software_name,
        CASE 
            WHEN LOWER(si.software_name) LIKE '%windows%' THEN 'Windows'
            WHEN LOWER(si.software_name) LIKE '%linux%' OR LOWER(si.software_name) LIKE '%ubuntu%' OR LOWER(si.software_name) LIKE '%centos%' THEN 'Linux'
            WHEN LOWER(si.software_name) LIKE '%macos%' OR LOWER(si.software_name) LIKE '%darwin%' THEN 'macOS'
            WHEN LOWER(si.software_name) LIKE '%oracle%' THEN 'Oracle'
            WHEN LOWER(si.software_name) LIKE '%sql server%' THEN 'SQL Server'
            WHEN LOWER(si.software_name) LIKE '%postgres%' THEN 'PostgreSQL'
            ELSE 'Other'
        END AS os_category,
        si.is_eol,
        si.is_unsupported
    FROM silver.software_inventory si
    WHERE si.software_name IS NOT NULL
),
asset_os AS (
    SELECT 
        asset_id,
        MAX(os_category) AS primary_os,  -- Take most common OS
        COUNT(DISTINCT os_category) AS os_count,
        SUM(CASE WHEN is_eol THEN 1 ELSE 0 END) AS eol_count,
        SUM(CASE WHEN is_unsupported THEN 1 ELSE 0 END) AS unsupported_count
    FROM software_os_mapping
    GROUP BY asset_id
)
SELECT 
    a.env,
    COALESCE(ao.primary_os, 'Unknown') AS os_category,
    COUNT(DISTINCT asi.asset_id) AS asset_count,
    AVG(asi.attack_surface_index) AS avg_asi,
    MAX(asi.attack_surface_index) AS max_asi,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY asi.attack_surface_index) AS median_asi,
    
    -- Component breakdown
    AVG(asi.external_exposure_score) AS avg_external_exposure,
    AVG(asi.vulnerability_exposure_score) AS avg_vulnerability_exposure,
    AVG(asi.misconfiguration_exposure_score) AS avg_misconfiguration_exposure,
    AVG(asi.identity_exposure_score) AS avg_identity_exposure,
    AVG(asi.software_exposure_score) AS avg_software_exposure,
    
    -- Risk distribution
    COUNT(CASE WHEN asi.attack_surface_index >= 70 THEN 1 END) AS high_risk_count,
    COUNT(CASE WHEN asi.attack_surface_index >= 50 AND asi.attack_surface_index < 70 THEN 1 END) AS medium_risk_count,
    COUNT(CASE WHEN asi.attack_surface_index < 50 THEN 1 END) AS low_risk_count,
    
    -- Software health metrics
    AVG(ao.eol_count) AS avg_eol_software_count,
    AVG(ao.unsupported_count) AS avg_unsupported_software_count,
    
    -- Total risk exposure
    SUM(asi.risk_weighted_asi) AS total_risk_exposure,
    (SUM(asi.risk_weighted_asi) * 100.0 / SUM(SUM(asi.risk_weighted_asi)) OVER (PARTITION BY a.env)) AS risk_contribution_pct_env,
    (SUM(asi.risk_weighted_asi) * 100.0 / SUM(SUM(asi.risk_weighted_asi)) OVER (PARTITION BY ao.primary_os)) AS risk_contribution_pct_os,
    
    CURRENT_TIMESTAMP AS calculated_at
    
FROM gold.attack_surface_index asi
JOIN silver.assets a ON asi.asset_id = a.asset_id
LEFT JOIN asset_os ao ON asi.asset_id = ao.asset_id
GROUP BY a.env, COALESCE(ao.primary_os, 'Unknown');

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_asi_env_os_env ON gold.attack_surface_by_env_os(env);
CREATE INDEX IF NOT EXISTS idx_asi_env_os_category ON gold.attack_surface_by_env_os(os_category);

