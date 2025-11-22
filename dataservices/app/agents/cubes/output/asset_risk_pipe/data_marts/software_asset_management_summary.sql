-- Data Mart: software_asset_management_summary
-- Goal: Show attack surface breakdown by OS/software stack, business unit, and environment
-- Question: How many devices are using each software application, and what are the associated vulnerabilities and misconfigurations?
-- Generated: 20251120_111506

CREATE TABLE software_asset_management_summary AS SELECT s.software_name, s.version, COUNT(DISTINCT s.device_id) AS total_devices, COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, COUNT(DISTINCT m.misconfiguration_id) AS total_misconfigurations FROM software_inventory s LEFT JOIN vulnerabilities v ON s.software_id = v.software_id LEFT JOIN misconfigurations m ON s.software_id = m.software_id GROUP BY s.software_name, s.version;