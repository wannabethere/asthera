-- Transformation: silver_to_gold_gold_increasing_risk_assets
-- Source: silver.gold_increasing_risk_assets
-- Target: gold.gold_gold_increasing_risk_assets
-- Description: Transform gold_increasing_risk_assets from silver to gold

-- Metric: increasing_risk_assets: Assets that have shown an increase in exploitability likelihood over the last 12 months.
INSERT INTO gold_increasing_risk_assets (asset_id, current_month_score, previous_month_score, score_increase)
WITH monthly_scores AS (
    SELECT 
        asset_id,
        DATE_TRUNC('month', score_date) AS month,
        AVG(exploitability_likelihood) AS avg_score
    FROM 
        assets_table
    WHERE 
        score_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY 
        asset_id, DATE_TRUNC('month', score_date)
),
score_comparison AS (
    SELECT 
        current.asset_id,
        current.avg_score AS current_month_score,
        previous.avg_score AS previous_month_score
    FROM 
        monthly_scores AS current
    LEFT JOIN 
        monthly_scores AS previous 
    ON 
        current.asset_id = previous.asset_id 
        AND current.month = previous.month + INTERVAL '1 month'
)
SELECT 
    asset_id,
    current_month_score,
    previous_month_score,
    CASE 
        WHEN current_month_score > COALESCE(previous_month_score, 0) THEN TRUE 
        ELSE FALSE 
    END AS score_increase
FROM 
    score_comparison
WHERE 
    current_month_score > COALESCE(previous_month_score, 0);