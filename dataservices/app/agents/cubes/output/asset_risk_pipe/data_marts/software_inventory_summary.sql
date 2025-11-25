-- Data Mart: software_inventory_summary
-- Goal: Create exposure score aggregations for dashboard visualizations
-- Question: What is the total number of licenses and usage hours for each software asset?
-- Generated: 20251124_084146

CREATE TABLE software_inventory_summary AS SELECT si.software_id, COUNT(si.license_id) AS total_licenses, SUM(si.usage_hours) AS total_usage_hours FROM software_inventory si GROUP BY si.software_id;