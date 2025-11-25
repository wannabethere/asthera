-- Transformation: silver_to_gold_gold_identity_exposure_score_per_asset
-- Source: silver.gold_identity_exposure_score_per_asset
-- Target: gold.gold_gold_identity_exposure_score_per_asset
-- Description: Transform gold_identity_exposure_score_per_asset from silver to gold

-- Metric: identity_exposure_score_per_asset: The calculated identity exposure score for each asset based on the status of admin accounts, stale accounts, and MFA.
INSERT INTO gold_identity_exposure_score_per_asset (asset_id, exposure_score)
SELECT 
    a.asset_id,
    COALESCE(SUM(
        CASE 
            WHEN aa.admin_account_id IS NOT NULL THEN 1 
            ELSE 0 
        END +
        CASE 
            WHEN sa.stale_account_id IS NOT NULL THEN 1 
            ELSE 0 
        END +
        CASE 
            WHEN mfa.mfa_enabled = TRUE THEN 1 
            ELSE 0 
        END
    ), 0) AS identity_exposure_score
FROM 
    assets a
LEFT JOIN 
    admin_accounts aa ON a.asset_id = aa.asset_id
LEFT JOIN 
    stale_accounts sa ON a.asset_id = sa.asset_id
LEFT JOIN 
    mfa_status mfa ON a.asset_id = mfa.asset_id
GROUP BY 
    a.asset_id;