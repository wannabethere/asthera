{{ config(materialized='table') }}

WITH exposure_months AS (
    SELECT 
        ie.identity_id,
        COUNT(ie.exposure_id) AS total_exposures,
        AVG(CASE WHEN ie.severity = 'High' THEN 1.0 ELSE 0.0 END) AS high_risk_exposure_ratio,
        DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * n.n AS month
    FROM 
        identity_exposure ie
    CROSS JOIN 
        generate_series(0, 11) n
    WHERE 
        DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * n.n >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
    GROUP BY 
        ie.identity_id, month
)

SELECT 
    identity_id,
    COALESCE(total_exposures, 0) AS total_exposures,
    COALESCE(high_risk_exposure_ratio, 0) AS high_risk_exposure_ratio,
    month
FROM 
    exposure_months
ORDER BY 
    month DESC;