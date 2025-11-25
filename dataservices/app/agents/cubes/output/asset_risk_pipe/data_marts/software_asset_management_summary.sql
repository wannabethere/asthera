-- Data Mart: software_asset_management_summary
-- Goal: Create Attack Surface Index (ASI) datamart by business unit with top 5 rankings
-- Question: Which departments have the highest number of software assets and how are they utilizing them?
-- Generated: 20251124_084146

CREATE TABLE software_asset_management_summary AS SELECT s.department, COUNT(DISTINCT s.id) AS total_software_assets, SUM(s.license_count) AS total_licenses, AVG(s.usage_hours) AS avg_usage_hours FROM software_inventory s GROUP BY s.department ORDER BY total_software_assets DESC LIMIT 5;