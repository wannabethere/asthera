-- Data Mart: attack_surface_summary_by_os_software
-- Goal: Show attack surface breakdown by OS/software stack, business unit, and environment
-- Question: What is the breakdown of the attack surface by OS/software stack, business unit, and environment?
-- Generated: 20251124_084146

CREATE TABLE attack_surface_summary_by_os_software AS SELECT a.business_unit, a.environment, a.os, a.software_stack, COUNT(DISTINCT a.asset_id) AS total_assets, COUNT(DISTINCT v.vulnerability_id) AS total_vulnerabilities, COUNT(DISTINCT m misconfiguration_id) AS total_misconfigurations FROM assets a LEFT JOIN vulnerabilities v ON a.asset_id = v.asset_id LEFT JOIN misconfigurations m ON a.asset_id = m.asset_id GROUP BY a.business_unit, a.environment, a.os, a.software_stack;