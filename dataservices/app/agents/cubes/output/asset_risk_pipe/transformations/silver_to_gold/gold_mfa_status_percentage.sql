-- Transformation: silver_to_gold_gold_mfa_status_percentage
-- Source: silver.gold_mfa_status_percentage
-- Target: gold.gold_gold_mfa_status_percentage
-- Description: Transform gold_mfa_status_percentage from silver to gold

-- Metric: mfa_status_percentage: Percentage of assets that have Multi-Factor Authentication (MFA) enabled.
INSERT INTO gold_mfa_status_percentage (asset_id, mfa_enabled_percentage)
SELECT 
    asset_id,
    COALESCE(
        (COUNT(CASE WHEN mfa_configured THEN 1 END) * 100.0) / NULLIF(COUNT(*), 0), 
        0) AS mfa_enabled_percentage
FROM 
    mfa_status
GROUP BY 
    asset_id;