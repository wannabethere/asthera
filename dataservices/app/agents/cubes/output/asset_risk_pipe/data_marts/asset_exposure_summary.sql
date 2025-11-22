-- Data Mart: asset_exposure_summary
-- Goal: Create exposure score aggregations for dashboard visualizations
-- Question: What is the total vulnerability score and count of vulnerabilities for each asset?
-- Generated: 20251120_111506

CREATE TABLE asset_exposure_summary AS SELECT a.asset_id, a.asset_name, SUM(v.severity_score) AS total_vulnerability_score, COUNT(DISTINCT v.vulnerability_id) AS vulnerability_count, SUM(m.configuration_issues) AS total_misconfigurations, SUM(e.external_risk_score) AS total_external_exposure FROM assets a LEFT JOIN vulnerabilities v ON a.asset_id = v.asset_id LEFT JOIN misconfigurations m ON a.asset_id = m.asset_id LEFT JOIN external_exposure e ON a.asset_id = e.asset_id GROUP BY a.asset_id, a.asset_name;