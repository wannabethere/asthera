-- Transformation: silver_to_gold_gold_software_exposure_score_per_asset
-- Source: silver.gold_software_exposure_score_per_asset
-- Target: gold.gold_gold_software_exposure_score_per_asset
-- Description: Transform gold_software_exposure_score_per_asset from silver to gold

-- Metric: software_exposure_score_per_asset: The average exposure score of software per asset based on EOL and unsupported software.
WITH latest_software AS (
    SELECT 
        s."asset_id",
        MAX(s."exposure_score") AS "latest_exposure_score"
    FROM 
        software_table s
    WHERE 
        s."status" IN ('EOL', 'unsupported')  -- Filter for EOL or unsupported software
    GROUP BY 
        s."asset_id"
),
asset_exposure AS (
    SELECT 
        a."business_unit",
        COALESCE(SUM(ls."latest_exposure_score"), 0) AS "total_exposure_score"
    FROM 
        assets_table a
    LEFT JOIN 
        latest_software ls ON a."id" = ls."asset_id"
    WHERE 
        ls."latest_exposure_score" IS NOT NULL  -- Only include assets with exposure scores
    GROUP BY 
        a."business_unit"
)
SELECT 
    "business_unit",
    COALESCE(AVG("total_exposure_score"), 0) AS "average_exposure_score"
FROM 
    asset_exposure
GROUP BY 
    "business_unit";