-- Data Mart: identity_exposure_risk_analysis
-- Goal: Generate 12-month trend analysis for likelihood and breach risk
-- Question: What is the trend of identity exposures and their severity over the past 12 months?
-- Generated: 20251124_084146

CREATE TABLE identity_exposure_risk_analysis AS SELECT
    ie.identity_id,
    COUNT(ie.exposure_id) AS total_exposures,
    AVG(CASE WHEN ie.severity = 'High' THEN 1 ELSE 0 END) AS high_risk_exposure_ratio,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) AS month
FROM
    identity_exposure ie
CROSS JOIN
    generate_series(0, 11) n
WHERE
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' * (n.n) >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY
    ie.identity_id, month
ORDER BY
    month DESC;