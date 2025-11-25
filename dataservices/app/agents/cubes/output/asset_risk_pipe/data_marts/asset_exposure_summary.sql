-- Data Mart: asset_exposure_summary
-- Goal: Create exposure score aggregations for dashboard visualizations
-- Question: What is the total number of vulnerabilities, misconfigurations, and external exposures for each asset?
-- Generated: 20251124_084146

CREATE TABLE asset_exposure_summary AS SELECT a.asset_id, COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, COUNT(DISTINCT m misconfiguration_id) AS total_misconfigurations, COUNT(DISTINCT e.exposure_id) AS total_external_exposures FROM vulnerabilities v JOIN assets a ON v.asset_id = a.asset_id LEFT JOIN misconfigurations m ON a.asset_id = m.asset_id LEFT JOIN external_exposure e ON a.asset_id = e.asset_id GROUP BY a.asset_id;