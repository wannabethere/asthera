#!/usr/bin/env python3
"""
Script to add advanced SQL examples with percentiles, CTEs, window functions,
and other sophisticated SQL features to sql_pairs.json
"""

import json

def add_advanced_sql_examples():
    """Add advanced SQL examples with percentiles, CTEs, and window functions"""
    
    # Read existing sql_pairs.json
    with open('data/sql_meta/cve_data/sql_pairs.json', 'r') as f:
        existing_pairs = json.load(f)
    
    # Advanced SQL examples with percentiles, CTEs, window functions
    advanced_examples = [
        {
            "categories": ["vulnerability_management", "advanced_analytics"],
            "question": "What are the percentile distributions of CVSS scores for 2024-2025 CVEs using advanced aggregation?",
            "sql": "WITH cve_cvss_stats AS (SELECT cve_id, CAST(cvss AS DECIMAL) as cvss_score FROM cve WHERE cve_id LIKE 'CVE-2024%' OR cve_id LIKE 'CVE-2025%' AND cvss IS NOT NULL) SELECT 'P25' as percentile, PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY cvss_score) as value FROM cve_cvss_stats UNION ALL SELECT 'P50' as percentile, PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY cvss_score) as value FROM cve_cvss_stats UNION ALL SELECT 'P75' as percentile, PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY cvss_score) as value FROM cve_cvss_stats UNION ALL SELECT 'P90' as percentile, PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY cvss_score) as value FROM cve_cvss_stats UNION ALL SELECT 'P95' as percentile, PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY cvss_score) as value FROM cve_cvss_stats UNION ALL SELECT 'P99' as percentile, PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY cvss_score) as value FROM cve_cvss_stats ORDER BY value",
            "context": "Maths/Analytics - Percentile Analysis. Shows CVSS score distribution using advanced percentile functions for risk assessment.",
            "document": "mdl_cve.json - cvss_percentile_analysis",
            "samples": [],
            "instructions": "Calculate percentile distributions of CVSS scores to understand vulnerability severity distribution patterns."
        },
        {
            "categories": ["vulnerability_management", "advanced_analytics", "composite_key_analysis"],
            "question": "Using CTEs and window functions, rank devices by vulnerability count and show running totals by NUID.",
            "sql": "WITH device_vuln_counts AS (SELECT nuid, dev_id, COUNT(vi.instance_id) as vuln_count, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_count FROM assets a LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id GROUP BY nuid, dev_id), ranked_devices AS (SELECT nuid, dev_id, vuln_count, critical_count, ROW_NUMBER() OVER (PARTITION BY nuid ORDER BY vuln_count DESC) as device_rank, RANK() OVER (ORDER BY vuln_count DESC) as global_rank, DENSE_RANK() OVER (ORDER BY vuln_count DESC) as global_dense_rank FROM device_vuln_counts), running_totals AS (SELECT nuid, dev_id, vuln_count, critical_count, device_rank, global_rank, SUM(vuln_count) OVER (PARTITION BY nuid ORDER BY device_rank ROWS UNBOUNDED PRECEDING) as running_total_nuid, SUM(vuln_count) OVER (ORDER BY global_rank ROWS UNBOUNDED PRECEDING) as running_total_global FROM ranked_devices) SELECT * FROM running_totals WHERE device_rank <= 5 ORDER BY nuid, device_rank",
            "context": "Direct Visualization - Advanced Ranking Table. Shows device vulnerability rankings with running totals using window functions.",
            "document": "Multiple models - Advanced Device Ranking",
            "samples": [],
            "instructions": "Use CTEs and window functions to rank devices by vulnerability count and calculate running totals for comprehensive analysis."
        },
        {
            "categories": ["vulnerability_management", "temporal_analysis", "advanced_analytics"],
            "question": "Using CTEs, calculate the moving average of CVE publications and detect trend changes for 2024-2025 CVEs.",
            "sql": "WITH monthly_cve_counts AS (SELECT DATE_FORMAT(pub_date, '%Y-%m') as month, COUNT(DISTINCT cve_id) as cve_count, AVG(CAST(cvss AS DECIMAL)) as avg_cvss FROM cve WHERE cve_id LIKE 'CVE-2024%' OR cve_id LIKE 'CVE-2025%' GROUP BY DATE_FORMAT(pub_date, '%Y-%m')), moving_averages AS (SELECT month, cve_count, avg_cvss, AVG(cve_count) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as moving_avg_3m, AVG(cve_count) OVER (ORDER BY month ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as moving_avg_6m, LAG(cve_count, 1) OVER (ORDER BY month) as prev_month_count, LAG(cve_count, 12) OVER (ORDER BY month) as prev_year_count FROM monthly_cve_counts), trend_analysis AS (SELECT month, cve_count, moving_avg_3m, moving_avg_6m, prev_month_count, prev_year_count, CASE WHEN cve_count > moving_avg_3m * 1.2 THEN 'Spike' WHEN cve_count < moving_avg_3m * 0.8 THEN 'Drop' ELSE 'Normal' END as trend_status, ROUND((cve_count - prev_month_count) * 100.0 / prev_month_count, 2) as month_over_month_pct, ROUND((cve_count - prev_year_count) * 100.0 / prev_year_count, 2) as year_over_year_pct FROM moving_averages) SELECT * FROM trend_analysis ORDER BY month",
            "context": "Direct Visualization - Time Series Analysis. Shows CVE publication trends with moving averages and trend detection.",
            "document": "mdl_cve.json - temporal_trend_analysis",
            "samples": [],
            "instructions": "Use CTEs and window functions to calculate moving averages and detect trend changes in CVE publications."
        },
        {
            "categories": ["software_asset_management", "advanced_analytics", "composite_key_analysis"],
            "question": "Using window functions and CTEs, identify software vendors with the highest vulnerability density and their risk progression.",
            "sql": "WITH vendor_vuln_stats AS (SELECT si.vendor, COUNT(DISTINCT si.key) as total_installations, COUNT(vi.instance_id) as total_vulnerabilities, COUNT(DISTINCT vi.cve_id) as unique_cves, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns FROM software_instances si LEFT JOIN vulnerability_instances vi ON si.nuid = vi.nuid AND si.dev_id = vi.dev_id WHERE si.product_state = 'VULNERABLE' GROUP BY si.vendor), vendor_metrics AS (SELECT vendor, total_installations, total_vulnerabilities, unique_cves, avg_cvss, critical_vulns, ROUND(total_vulnerabilities * 100.0 / total_installations, 2) as vuln_density, ROUND(critical_vulns * 100.0 / total_vulnerabilities, 2) as critical_percentage FROM vendor_vuln_stats WHERE total_installations >= 10), ranked_vendors AS (SELECT *, ROW_NUMBER() OVER (ORDER BY vuln_density DESC) as density_rank, RANK() OVER (ORDER BY avg_cvss DESC) as severity_rank, NTILE(4) OVER (ORDER BY vuln_density) as risk_quartile FROM vendor_metrics), vendor_progression AS (SELECT vendor, total_installations, vuln_density, critical_percentage, density_rank, severity_rank, risk_quartile, LAG(vuln_density, 1) OVER (ORDER BY density_rank) as prev_vendor_density, CASE WHEN risk_quartile = 1 THEN 'High Risk' WHEN risk_quartile = 2 THEN 'Medium-High Risk' WHEN risk_quartile = 3 THEN 'Medium-Low Risk' ELSE 'Low Risk' END as risk_category FROM ranked_vendors) SELECT * FROM vendor_progression WHERE density_rank <= 20 ORDER BY density_rank",
            "context": "Direct Visualization - Advanced Vendor Analysis. Shows vendor vulnerability density with risk quartiles and progression analysis.",
            "document": "mdl_software_instances.json - advanced_vendor_analysis",
            "samples": [],
            "instructions": "Use CTEs and window functions to analyze vendor vulnerability density, risk quartiles, and progression patterns."
        },
        {
            "categories": ["vulnerability_management", "composite_key_analysis", "advanced_analytics"],
            "question": "Using recursive CTEs, find the vulnerability propagation path through connected assets in the same subnet.",
            "sql": "WITH RECURSIVE subnet_assets AS (SELECT DISTINCT i.subnet, i.nuid, i.dev_id, i.ip, i.manufacturer FROM interfaces i WHERE i.subnet IS NOT NULL), asset_vulnerabilities AS (SELECT sa.subnet, sa.nuid, sa.dev_id, sa.ip, COUNT(vi.instance_id) as vuln_count, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss FROM subnet_assets sa LEFT JOIN vulnerability_instances vi ON sa.nuid = vi.nuid AND sa.dev_id = vi.dev_id GROUP BY sa.subnet, sa.nuid, sa.dev_id, sa.ip), vulnerability_propagation AS (SELECT subnet, nuid, dev_id, ip, vuln_count, critical_vulns, avg_cvss, 0 as propagation_level, CAST(CONCAT(nuid, '-', dev_id) AS CHAR(1000)) as propagation_path FROM asset_vulnerabilities WHERE critical_vulns > 0 UNION ALL SELECT av.subnet, av.nuid, av.dev_id, av.ip, av.vuln_count, av.critical_vulns, av.avg_cvss, vp.propagation_level + 1, CONCAT(vp.propagation_path, ' -> ', av.nuid, '-', av.dev_id) FROM vulnerability_propagation vp JOIN asset_vulnerabilities av ON vp.subnet = av.subnet AND vp.nuid != av.nuid WHERE vp.propagation_level < 3 AND av.critical_vulns > 0) SELECT subnet, propagation_level, COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as affected_devices, AVG(vuln_count) as avg_vuln_count, AVG(critical_vulns) as avg_critical_vulns, GROUP_CONCAT(DISTINCT CONCAT(nuid, '-', dev_id) ORDER BY nuid, dev_id SEPARATOR ', ') as device_list FROM vulnerability_propagation GROUP BY subnet, propagation_level ORDER BY subnet, propagation_level",
            "context": "Maths/Analytics - Vulnerability Propagation Analysis. Shows how vulnerabilities spread through connected assets using recursive CTEs.",
            "document": "Multiple models - Vulnerability Propagation Analysis",
            "samples": [],
            "instructions": "Use recursive CTEs to analyze vulnerability propagation paths through connected assets in the same subnet."
        },
        {
            "categories": ["vulnerability_management", "temporal_analysis", "advanced_analytics"],
            "question": "Using window functions and CTEs, calculate the vulnerability detection lag percentiles and identify detection performance outliers.",
            "sql": "WITH detection_lag_data AS (SELECT vi.cve_id, vi.nuid, vi.dev_id, vi.detected_time, c.pub_date, DATEDIFF(vi.detected_time, c.pub_date) as detection_lag_days, vi.severity, CAST(vi.cvssv3_basescore AS DECIMAL) as cvss_score FROM vulnerability_instances vi JOIN cve c ON vi.cve_id = c.cve_id WHERE vi.detected_time IS NOT NULL AND c.pub_date IS NOT NULL AND vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%'), lag_percentiles AS (SELECT PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY detection_lag_days) as p10, PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY detection_lag_days) as p25, PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY detection_lag_days) as p50, PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY detection_lag_days) as p75, PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY detection_lag_days) as p90, PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY detection_lag_days) as p95, PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY detection_lag_days) as p99 FROM detection_lag_data), detection_performance AS (SELECT cve_id, nuid, dev_id, detection_lag_days, severity, cvss_score, ROW_NUMBER() OVER (PARTITION BY severity ORDER BY detection_lag_days) as severity_rank, ROW_NUMBER() OVER (ORDER BY detection_lag_days) as global_rank, NTILE(10) OVER (ORDER BY detection_lag_days) as performance_decile FROM detection_lag_data), outlier_analysis AS (SELECT dp.*, lp.p50, lp.p90, CASE WHEN dp.detection_lag_days > lp.p90 THEN 'Slow Detector' WHEN dp.detection_lag_days < lp.p10 THEN 'Fast Detector' ELSE 'Normal' END as performance_category, CASE WHEN dp.detection_lag_days > lp.p95 THEN 'Outlier' ELSE 'Normal' END as outlier_status FROM detection_performance dp CROSS JOIN lag_percentiles lp) SELECT performance_category, COUNT(*) as device_count, AVG(detection_lag_days) as avg_lag_days, AVG(cvss_score) as avg_cvss, COUNT(CASE WHEN outlier_status = 'Outlier' THEN 1 END) as outlier_count FROM outlier_analysis GROUP BY performance_category ORDER BY avg_lag_days",
            "context": "Maths/Analytics - Detection Performance Analysis. Shows vulnerability detection lag percentiles and identifies performance outliers.",
            "document": "mdl_vuln_instance.json - detection_performance_analysis",
            "samples": [],
            "instructions": "Use window functions and CTEs to calculate detection lag percentiles and identify performance outliers."
        },
        {
            "categories": ["comprehensive_security", "composite_key_analysis", "advanced_analytics"],
            "question": "Using CTEs and window functions, create a comprehensive security risk score for each NUID with weighted factors and trend analysis.",
            "sql": "WITH nuid_metrics AS (SELECT a.nuid, COUNT(DISTINCT a.dev_id) as total_devices, COUNT(vi.instance_id) as total_vulnerabilities, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns, COUNT(CASE WHEN vi.severity = 'HIGH' THEN 1 END) as high_vulns, COUNT(CASE WHEN si.product_state = 'VULNERABLE' THEN 1 END) as vulnerable_software, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss, COUNT(CASE WHEN ag.is_stale = 'True' THEN 1 END) as stale_agents FROM assets a LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id LEFT JOIN agents ag ON a.nuid = ag.nuid AND a.dev_id = ag.dev_id GROUP BY a.nuid), risk_calculations AS (SELECT nuid, total_devices, total_vulnerabilities, critical_vulns, high_vulns, vulnerable_software, avg_cvss, stale_agents, ROUND(total_vulnerabilities * 100.0 / total_devices, 2) as vuln_density, ROUND(critical_vulns * 100.0 / total_vulnerabilities, 2) as critical_percentage, ROUND(vulnerable_software * 100.0 / total_devices, 2) as vulnerable_software_percentage, ROUND(stale_agents * 100.0 / total_devices, 2) as stale_agent_percentage FROM nuid_metrics), weighted_scores AS (SELECT *, (vuln_density * 0.3 + critical_percentage * 0.25 + avg_cvss * 10 * 0.2 + vulnerable_software_percentage * 0.15 + stale_agent_percentage * 0.1) as raw_risk_score FROM risk_calculations), normalized_scores AS (SELECT *, ROUND(raw_risk_score, 2) as risk_score, ROW_NUMBER() OVER (ORDER BY raw_risk_score DESC) as risk_rank, RANK() OVER (ORDER BY raw_risk_score DESC) as risk_rank_tied, NTILE(5) OVER (ORDER BY raw_risk_score DESC) as risk_quintile, LAG(raw_risk_score, 1) OVER (ORDER BY risk_rank) as prev_nuid_score FROM weighted_scores), risk_trends AS (SELECT *, CASE WHEN prev_nuid_score IS NULL THEN 'Baseline' WHEN raw_risk_score > prev_nuid_score * 1.1 THEN 'Increasing' WHEN raw_risk_score < prev_nuid_score * 0.9 THEN 'Decreasing' ELSE 'Stable' END as risk_trend, CASE WHEN risk_quintile = 1 THEN 'Very High Risk' WHEN risk_quintile = 2 THEN 'High Risk' WHEN risk_quintile = 3 THEN 'Medium Risk' WHEN risk_quintile = 4 THEN 'Low Risk' ELSE 'Very Low Risk' END as risk_category FROM normalized_scores) SELECT nuid, total_devices, risk_score, risk_rank, risk_category, risk_trend, vuln_density, critical_percentage, avg_cvss, vulnerable_software_percentage, stale_agent_percentage FROM risk_trends ORDER BY risk_rank",
            "context": "Dashboard Widget - Advanced Risk Analysis. Shows comprehensive security risk scores with weighted factors and trend analysis.",
            "document": "Multiple models - Advanced Risk Analysis",
            "samples": [],
            "instructions": "Use CTEs and window functions to create comprehensive security risk scores with weighted factors and trend analysis."
        },
        {
            "categories": ["vulnerability_management", "temporal_analysis", "advanced_analytics"],
            "question": "Using window functions and CTEs, identify vulnerability clusters and their temporal patterns across different NUIDs.",
            "sql": "WITH vulnerability_timeline AS (SELECT vi.cve_id, vi.nuid, vi.detected_time, vi.severity, CAST(vi.cvssv3_basescore AS DECIMAL) as cvss_score, DATE_FORMAT(vi.detected_time, '%Y-%m-%d') as detection_date, ROW_NUMBER() OVER (PARTITION BY vi.cve_id ORDER BY vi.detected_time) as detection_sequence FROM vulnerability_instances vi WHERE vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%'), cve_clusters AS (SELECT cve_id, COUNT(DISTINCT nuid) as affected_nuids, COUNT(*) as total_instances, MIN(detected_time) as first_detection, MAX(detected_time) as last_detection, DATEDIFF(MAX(detected_time), MIN(detected_time)) as cluster_duration_days, AVG(cvss_score) as avg_cvss, COUNT(CASE WHEN severity = 'CRITICAL' THEN 1 END) as critical_count FROM vulnerability_timeline GROUP BY cve_id HAVING COUNT(DISTINCT nuid) > 1), cluster_analysis AS (SELECT cve_id, affected_nuids, total_instances, first_detection, last_detection, cluster_duration_days, avg_cvss, critical_count, ROW_NUMBER() OVER (ORDER BY affected_nuids DESC, total_instances DESC) as cluster_rank, RANK() OVER (ORDER BY cluster_duration_days DESC) as duration_rank, NTILE(4) OVER (ORDER BY affected_nuids) as spread_quartile FROM cve_clusters), temporal_patterns AS (SELECT ca.*, vt.detection_date, vt.detection_sequence, vt.nuid, vt.severity, LAG(vt.detection_date, 1) OVER (PARTITION BY ca.cve_id ORDER BY vt.detection_sequence) as prev_detection_date, DATEDIFF(vt.detection_date, LAG(vt.detection_date, 1) OVER (PARTITION BY ca.cve_id ORDER BY vt.detection_sequence)) as days_since_prev_detection FROM cluster_analysis ca JOIN vulnerability_timeline vt ON ca.cve_id = vt.cve_id), pattern_summary AS (SELECT cve_id, affected_nuids, cluster_duration_days, avg_cvss, spread_quartile, AVG(days_since_prev_detection) as avg_detection_interval, STDDEV(days_since_prev_detection) as detection_interval_stddev, COUNT(CASE WHEN days_since_prev_detection <= 1 THEN 1 END) as same_day_detections, COUNT(CASE WHEN days_since_prev_detection > 7 THEN 1 END) as delayed_detections FROM temporal_patterns WHERE days_since_prev_detection IS NOT NULL GROUP BY cve_id, affected_nuids, cluster_duration_days, avg_cvss, spread_quartile) SELECT cve_id, affected_nuids, cluster_duration_days, ROUND(avg_cvss, 2) as avg_cvss, CASE WHEN spread_quartile = 1 THEN 'Wide Spread' WHEN spread_quartile = 2 THEN 'Medium Spread' WHEN spread_quartile = 3 THEN 'Limited Spread' ELSE 'Localized' END as spread_category, ROUND(avg_detection_interval, 1) as avg_detection_interval, same_day_detections, delayed_detections FROM pattern_summary WHERE cluster_rank <= 20 ORDER BY cluster_rank",
            "context": "Maths/Analytics - Vulnerability Cluster Analysis. Shows vulnerability clusters and their temporal patterns across NUIDs.",
            "document": "mdl_vuln_instance.json - vulnerability_cluster_analysis",
            "samples": [],
            "instructions": "Use window functions and CTEs to identify vulnerability clusters and analyze their temporal patterns across different NUIDs."
        },
        {
            "categories": ["software_asset_management", "composite_key_analysis", "advanced_analytics"],
            "question": "Using window functions and CTEs, analyze software installation patterns and identify anomalous installations across NUIDs.",
            "sql": "WITH software_installations AS (SELECT si.nuid, si.dev_id, si.vendor, si.product, si.version, si.install_time, si.product_state, DATE_FORMAT(si.install_time, '%Y-%m') as install_month, ROW_NUMBER() OVER (PARTITION BY si.nuid, si.vendor, si.product ORDER BY si.install_time) as install_sequence FROM software_instances si), vendor_install_patterns AS (SELECT vendor, product, COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as total_installations, COUNT(DISTINCT nuid) as affected_nuids, MIN(install_time) as first_installation, MAX(install_time) as last_installation, DATEDIFF(MAX(install_time), MIN(install_time)) as installation_span_days, COUNT(CASE WHEN product_state = 'VULNERABLE' THEN 1 END) as vulnerable_installations FROM software_installations GROUP BY vendor, product), installation_metrics AS (SELECT vp.*, ROUND(vp.vulnerable_installations * 100.0 / vp.total_installations, 2) as vulnerability_rate, ROW_NUMBER() OVER (ORDER BY vp.total_installations DESC) as popularity_rank, RANK() OVER (ORDER BY vp.vulnerability_rate DESC) as risk_rank, NTILE(5) OVER (ORDER BY vp.total_installations) as popularity_quintile FROM vendor_install_patterns WHERE vp.total_installations >= 5), nuid_software_diversity AS (SELECT nuid, COUNT(DISTINCT vendor) as vendor_diversity, COUNT(DISTINCT product) as product_diversity, COUNT(*) as total_installations, AVG(CASE WHEN product_state = 'VULNERABLE' THEN 1.0 ELSE 0.0 END) as vulnerability_rate FROM software_installations GROUP BY nuid), anomalous_installations AS (SELECT si.nuid, si.dev_id, si.vendor, si.product, si.version, si.install_time, si.product_state, nsd.vendor_diversity, nsd.product_diversity, nsd.vulnerability_rate, im.popularity_rank, im.risk_rank, im.popularity_quintile, CASE WHEN im.popularity_quintile = 5 AND nsd.vendor_diversity < 3 THEN 'Rare Software' WHEN im.risk_rank <= 10 AND nsd.vulnerability_rate > 0.5 THEN 'High Risk Software' WHEN nsd.vendor_diversity > 10 AND nsd.product_diversity > 50 THEN 'Diverse Environment' ELSE 'Normal' END as installation_category FROM software_installations si JOIN nuid_software_diversity nsd ON si.nuid = nsd.nuid JOIN installation_metrics im ON si.vendor = im.vendor AND si.product = im.product) SELECT installation_category, COUNT(*) as installation_count, COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as affected_devices, COUNT(DISTINCT nuid) as affected_nuids, AVG(vendor_diversity) as avg_vendor_diversity, AVG(product_diversity) as avg_product_diversity, AVG(vulnerability_rate) as avg_vulnerability_rate FROM anomalous_installations GROUP BY installation_category ORDER BY installation_count DESC",
            "context": "Maths/Analytics - Software Installation Pattern Analysis. Shows software installation patterns and identifies anomalous installations.",
            "document": "mdl_software_instances.json - installation_pattern_analysis",
            "samples": [],
            "instructions": "Use window functions and CTEs to analyze software installation patterns and identify anomalous installations across NUIDs."
        },
        {
            "categories": ["vulnerability_management", "composite_key_analysis", "advanced_analytics"],
            "question": "Using advanced window functions and CTEs, calculate the vulnerability exposure index for each device and identify high-risk device clusters.",
            "sql": "WITH device_vulnerability_metrics AS (SELECT a.nuid, a.dev_id, a.host_name, a.os_name, COUNT(vi.instance_id) as total_vulnerabilities, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns, COUNT(CASE WHEN vi.severity = 'HIGH' THEN 1 END) as high_vulns, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss, MAX(CAST(vi.cvssv3_basescore AS DECIMAL)) as max_cvss, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN si.product_state = 'VULNERABLE' THEN 1 END) as vulnerable_software FROM assets a LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id GROUP BY a.nuid, a.dev_id, a.host_name, a.os_name), exposure_calculations AS (SELECT *, (critical_vulns * 4 + high_vulns * 2 + total_vulnerabilities * 1) as raw_exposure_score, (avg_cvss * 10) as cvss_weight, (vulnerable_software * 0.5) as software_weight FROM device_vulnerability_metrics), normalized_exposure AS (SELECT *, (raw_exposure_score + cvss_weight + software_weight) as exposure_index, ROW_NUMBER() OVER (ORDER BY (raw_exposure_score + cvss_weight + software_weight) DESC) as exposure_rank, RANK() OVER (ORDER BY (raw_exposure_score + cvss_weight + software_weight) DESC) as exposure_rank_tied, NTILE(10) OVER (ORDER BY (raw_exposure_score + cvss_weight + software_weight) DESC) as exposure_decile, PERCENT_RANK() OVER (ORDER BY (raw_exposure_score + cvss_weight + software_weight)) as exposure_percentile FROM exposure_calculations), device_clusters AS (SELECT nuid, COUNT(*) as device_count, AVG(exposure_index) as avg_exposure, MAX(exposure_index) as max_exposure, MIN(exposure_index) as min_exposure, STDDEV(exposure_index) as exposure_stddev, COUNT(CASE WHEN exposure_decile <= 3 THEN 1 END) as high_risk_devices FROM normalized_exposure GROUP BY nuid HAVING COUNT(*) >= 5), cluster_analysis AS (SELECT dc.nuid, dc.device_count, ROUND(dc.avg_exposure, 2) as avg_exposure, ROUND(dc.max_exposure, 2) as max_exposure, ROUND(dc.exposure_stddev, 2) as exposure_stddev, dc.high_risk_devices, ROUND(dc.high_risk_devices * 100.0 / dc.device_count, 2) as high_risk_percentage, ROW_NUMBER() OVER (ORDER BY dc.avg_exposure DESC) as cluster_risk_rank, CASE WHEN dc.avg_exposure > (SELECT AVG(avg_exposure) + STDDEV(avg_exposure) FROM device_clusters) THEN 'High Risk Cluster' WHEN dc.avg_exposure < (SELECT AVG(avg_exposure) - STDDEV(avg_exposure) FROM device_clusters) THEN 'Low Risk Cluster' ELSE 'Normal Risk Cluster' END as cluster_risk_category FROM device_clusters) SELECT ca.nuid, ca.device_count, ca.avg_exposure, ca.max_exposure, ca.exposure_stddev, ca.high_risk_devices, ca.high_risk_percentage, ca.cluster_risk_rank, ca.cluster_risk_category FROM cluster_analysis ca ORDER BY ca.cluster_risk_rank",
            "context": "Maths/Analytics - Device Vulnerability Exposure Analysis. Shows vulnerability exposure index and identifies high-risk device clusters.",
            "document": "Multiple models - Device Exposure Analysis",
            "samples": [],
            "instructions": "Use advanced window functions and CTEs to calculate vulnerability exposure index and identify high-risk device clusters."
        }
    ]
    
    # Combine existing and new examples
    all_examples = existing_pairs + advanced_examples
    
    # Write updated sql_pairs.json
    with open('data/sql_meta/cve_data/sql_pairs.json', 'w') as f:
        json.dump(all_examples, f, indent=2)
    
    print(f"Added {len(advanced_examples)} advanced SQL examples to sql_pairs.json")
    print("Advanced examples include:")
    print("- Percentile analysis with PERCENTILE_CONT")
    print("- CTE expressions for complex data processing")
    print("- Window functions (ROW_NUMBER, RANK, DENSE_RANK, NTILE)")
    print("- Recursive CTEs for vulnerability propagation")
    print("- Moving averages and trend analysis")
    print("- Advanced ranking and clustering algorithms")
    print("- Risk scoring with weighted factors")
    print("- Temporal pattern analysis")
    print("- Anomaly detection algorithms")

def main():
    """Main function to add advanced SQL examples"""
    print("Adding advanced SQL examples with percentiles, CTEs, and window functions...")
    add_advanced_sql_examples()
    print("✅ Advanced SQL examples update completed!")

if __name__ == "__main__":
    main()
