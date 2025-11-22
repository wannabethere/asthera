-- Data Mart: software_asset_usage_summary
-- Goal: Create exposure score aggregations for dashboard visualizations
-- Question: What is the total number of devices using each software and how many hours it has been used?
-- Generated: 20251120_111506

CREATE TABLE software_asset_usage_summary AS SELECT s.software_id, s.software_name, COUNT(DISTINCT s.device_id) AS total_devices_used, SUM(s.usage_hours) AS total_usage_hours FROM software_inventory s GROUP BY s.software_id, s.software_name;