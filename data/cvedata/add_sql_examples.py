#!/usr/bin/env python3
"""
Script to add more comprehensive SQL examples to sql_pairs.json
focusing on 2024-2025 CVEs and composite key system
"""

import json

def add_new_sql_examples():
    """Add new SQL examples to sql_pairs.json"""
    
    # Read existing sql_pairs.json
    with open('data/sql_meta/cve_data/sql_pairs.json', 'r') as f:
        existing_pairs = json.load(f)
    
    # New SQL examples focusing on 2024-2025 CVEs and composite key system
    new_examples = [
        {
            "categories": ["vulnerability_management", "composite_key_analysis"],
            "question": "What are the most critical 2024-2025 CVEs affecting our assets and how many devices are impacted?",
            "sql": "SELECT vi.cve_id, c.cvss, c.cwe_name, COUNT(DISTINCT CONCAT(vi.nuid, '-', vi.dev_id)) as affected_assets, COUNT(vi.instance_id) as total_instances, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss FROM vulnerability_instances vi JOIN cve c ON vi.cve_id = c.cve_id WHERE vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%' GROUP BY vi.cve_id, c.cvss, c.cwe_name ORDER BY avg_cvss DESC, affected_assets DESC LIMIT 20",
            "context": "Direct Visualization - Top N. Identifies most critical recent CVEs with asset impact for emergency response prioritization.",
            "document": "mdl_vuln_instance.json - recent_critical_cves",
            "samples": [],
            "instructions": "Rank 2024-2025 CVEs by severity and asset impact to prioritize emergency response and resource allocation."
        },
        {
            "categories": ["composite_key_analysis", "asset_management"],
            "question": "For each NUID, show the total number of devices, vulnerabilities, and software instances using the composite key system.",
            "sql": "SELECT a.nuid, COUNT(DISTINCT a.dev_id) as total_devices, COUNT(DISTINCT vi.instance_id) as total_vulnerabilities, COUNT(DISTINCT si.key) as total_software_instances, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns FROM assets a LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id GROUP BY a.nuid ORDER BY critical_vulns DESC, total_vulnerabilities DESC",
            "context": "Direct Visualization - Table. Shows comprehensive asset inventory and security posture by organizational unit.",
            "document": "Multiple models - NUID Security Overview",
            "samples": [],
            "instructions": "Analyze security posture by NUID using composite keys to understand organizational risk distribution."
        },
        {
            "categories": ["vulnerability_management", "software_asset_management"],
            "question": "Which software products are most vulnerable to 2024-2025 CVEs and on how many devices?",
            "sql": "SELECT si.vendor, si.product, si.version, COUNT(DISTINCT CONCAT(si.nuid, '-', si.dev_id)) as affected_devices, COUNT(DISTINCT vi.cve_id) as unique_cves, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss FROM software_instances si JOIN vulnerability_instances vi ON si.nuid = vi.nuid AND si.dev_id = vi.dev_id WHERE vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%' AND si.product_state = 'VULNERABLE' GROUP BY si.vendor, si.product, si.version ORDER BY affected_devices DESC, avg_cvss DESC LIMIT 15",
            "context": "Direct Visualization - Top N. Identifies most vulnerable software products affected by recent CVEs.",
            "document": "mdl_software_instances.json - vulnerable_software_analysis",
            "samples": [],
            "instructions": "Rank software products by vulnerability to recent CVEs to prioritize patch management and vendor coordination."
        },
        {
            "categories": ["composite_key_analysis", "vulnerability_management"],
            "question": "Find all data for a specific asset using composite key (nuid + dev_id) - show agent, software, and vulnerability details.",
            "sql": "SELECT a.nuid, a.dev_id, a.host_name, a.ip, a.os_name, ag.agent, ag.first_seen, ag.last_seen, COUNT(DISTINCT si.key) as software_count, COUNT(vi.instance_id) as vulnerability_count, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns FROM assets a LEFT JOIN agents ag ON a.nuid = ag.nuid AND a.dev_id = ag.dev_id LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id WHERE a.nuid = 87 AND a.dev_id = 2000000 GROUP BY a.nuid, a.dev_id, a.host_name, a.ip, a.os_name, ag.agent, ag.first_seen, ag.last_seen",
            "context": "Direct Visualization - Asset Detail View. Comprehensive asset information using composite key lookup.",
            "document": "Multiple models - Asset Comprehensive View",
            "samples": [],
            "instructions": "Demonstrate composite key usage to retrieve complete asset information across all related datasets."
        },
        {
            "categories": ["vulnerability_management", "temporal_analysis"],
            "question": "How many 2024-2025 CVEs were published each month and what's the trend?",
            "sql": "SELECT DATE_FORMAT(pub_date, '%Y-%m') as publication_month, COUNT(DISTINCT cve_id) as new_cves, AVG(CAST(cvss AS DECIMAL)) as avg_cvss, COUNT(CASE WHEN CAST(cvss AS DECIMAL) >= 7.0 THEN 1 END) as high_severity_cves FROM cve WHERE cve_id LIKE 'CVE-2024%' OR cve_id LIKE 'CVE-2025%' GROUP BY DATE_FORMAT(pub_date, '%Y-%m') ORDER BY publication_month",
            "context": "Direct Visualization - Line Chart. Shows monthly CVE publication trends for threat landscape analysis.",
            "document": "mdl_cve.json - cve_publication_trends",
            "samples": [],
            "instructions": "Track monthly CVE publication trends to understand threat landscape evolution and resource planning."
        },
        {
            "categories": ["composite_key_analysis", "network_infrastructure"],
            "question": "Show network interfaces for NUID 87 devices and their associated vulnerabilities.",
            "sql": "SELECT i.nuid, i.dev_id, i.ip, i.subnet, i.manufacturer, COUNT(vi.instance_id) as vulnerability_count, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns FROM interfaces i LEFT JOIN vulnerability_instances vi ON i.nuid = vi.nuid AND i.dev_id = vi.dev_id WHERE i.nuid = 87 GROUP BY i.nuid, i.dev_id, i.ip, i.subnet, i.manufacturer ORDER BY vulnerability_count DESC",
            "context": "Direct Visualization - Table. Shows network interface security status for NUID 87 devices.",
            "document": "mdl_interfaces.json - interface_security_analysis",
            "samples": [],
            "instructions": "Analyze network interface security using composite keys to identify vulnerable network segments."
        },
        {
            "categories": ["vulnerability_management", "software_asset_management"],
            "question": "Which devices have the most vulnerable software installations and what are the associated CVEs?",
            "sql": "SELECT a.nuid, a.dev_id, a.host_name, COUNT(DISTINCT si.key) as vulnerable_software_count, COUNT(vi.instance_id) as vulnerability_instances, COUNT(DISTINCT vi.cve_id) as unique_cves, GROUP_CONCAT(DISTINCT si.product ORDER BY si.product SEPARATOR ', ') as vulnerable_products FROM assets a JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id WHERE si.product_state = 'VULNERABLE' AND (vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%') GROUP BY a.nuid, a.dev_id, a.host_name ORDER BY vulnerable_software_count DESC, vulnerability_instances DESC LIMIT 15",
            "context": "Direct Visualization - Top N. Identifies devices with highest vulnerable software exposure.",
            "document": "Multiple models - Device Vulnerability Exposure",
            "samples": [],
            "instructions": "Rank devices by vulnerable software count to prioritize patch management and security hardening efforts."
        },
        {
            "categories": ["composite_key_analysis", "vulnerability_management"],
            "question": "Find all 2024-2025 vulnerabilities for a specific software product across all devices.",
            "sql": "SELECT si.vendor, si.product, si.version, a.nuid, a.dev_id, a.host_name, vi.cve_id, vi.severity, vi.cvssv3_basescore, vi.state FROM software_instances si JOIN assets a ON si.nuid = a.nuid AND si.dev_id = a.dev_id JOIN vulnerability_instances vi ON si.nuid = vi.nuid AND si.dev_id = vi.dev_id WHERE si.product = 'Windows 10' AND (vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%') ORDER BY a.nuid, a.dev_id, vi.severity DESC",
            "context": "Direct Visualization - Table. Shows specific software vulnerability details across all devices.",
            "document": "Multiple models - Software Vulnerability Mapping",
            "samples": [],
            "instructions": "Map specific software vulnerabilities across all devices using composite keys for targeted remediation."
        },
        {
            "categories": ["vulnerability_management", "temporal_analysis"],
            "question": "What is the average time between CVE publication and detection for 2024-2025 CVEs?",
            "sql": "SELECT AVG(DATEDIFF(vi.detected_time, c.pub_date)) as avg_detection_days, MIN(DATEDIFF(vi.detected_time, c.pub_date)) as fastest_detection, MAX(DATEDIFF(vi.detected_time, c.pub_date)) as slowest_detection, COUNT(CASE WHEN DATEDIFF(vi.detected_time, c.pub_date) <= 1 THEN 1 END) as same_day_detections FROM vulnerability_instances vi JOIN cve c ON vi.cve_id = c.cve_id WHERE vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%' AND vi.detected_time IS NOT NULL AND c.pub_date IS NOT NULL",
            "context": "Maths/Analytics - Detection Performance. Measures detection timeliness for recent CVEs.",
            "document": "mdl_vuln_instance.json - detection_performance_metrics",
            "samples": [],
            "instructions": "Calculate detection timeliness for 2024-2025 CVEs to assess vulnerability scanning effectiveness."
        },
        {
            "categories": ["comprehensive_security", "composite_key_analysis"],
            "question": "Show comprehensive security posture for NUID 87 devices including all metrics.",
            "sql": "SELECT a.nuid, COUNT(DISTINCT a.dev_id) as total_devices, COUNT(DISTINCT ag.agent) as agent_types, COUNT(DISTINCT si.key) as software_installations, COUNT(vi.instance_id) as vulnerability_instances, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns, COUNT(CASE WHEN si.product_state = 'VULNERABLE' THEN 1 END) as vulnerable_software, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss FROM assets a LEFT JOIN agents ag ON a.nuid = ag.nuid AND a.dev_id = ag.dev_id LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id WHERE a.nuid = 87 GROUP BY a.nuid",
            "context": "Dashboard Widget - NUID Security Posture. Comprehensive security metrics for specific organizational unit.",
            "document": "Multiple models - NUID Security Dashboard",
            "samples": [],
            "instructions": "Calculate comprehensive security metrics for NUID 87 using composite keys for organizational risk assessment."
        },
        {
            "categories": ["vulnerability_management", "software_asset_management"],
            "question": "Which software vendors have the most 2024-2025 CVE exposures and what are the affected products?",
            "sql": "SELECT si.vendor, COUNT(DISTINCT si.product) as affected_products, COUNT(DISTINCT CONCAT(si.nuid, '-', si.dev_id)) as affected_devices, COUNT(vi.instance_id) as vulnerability_instances, COUNT(DISTINCT vi.cve_id) as unique_cves, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss FROM software_instances si JOIN vulnerability_instances vi ON si.nuid = vi.nuid AND si.dev_id = vi.dev_id WHERE (vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%') AND si.product_state = 'VULNERABLE' GROUP BY si.vendor ORDER BY affected_devices DESC, vulnerability_instances DESC LIMIT 10",
            "context": "Direct Visualization - Top N. Identifies vendors with highest 2024-2025 CVE exposure.",
            "document": "mdl_software_instances.json - vendor_cve_exposure",
            "samples": [],
            "instructions": "Rank software vendors by 2024-2025 CVE exposure to prioritize vendor risk management and patch coordination."
        },
        {
            "categories": ["composite_key_analysis", "vulnerability_management"],
            "question": "Find all critical vulnerabilities affecting Windows systems across all NUIDs.",
            "sql": "SELECT a.nuid, a.dev_id, a.host_name, a.os_name, vi.cve_id, vi.severity, vi.cvssv3_basescore, vi.state, c.cwe_name, c.summary FROM assets a JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id JOIN cve c ON vi.cve_id = c.cve_id WHERE a.os_name LIKE '%Windows%' AND vi.severity = 'CRITICAL' AND (vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%') ORDER BY a.nuid, a.dev_id, vi.cvssv3_basescore DESC",
            "context": "Direct Visualization - Table. Shows critical Windows vulnerabilities across all organizational units.",
            "document": "Multiple models - Windows Critical Vulnerabilities",
            "samples": [],
            "instructions": "Identify critical Windows vulnerabilities across all NUIDs for prioritized remediation efforts."
        },
        {
            "categories": ["vulnerability_management", "temporal_analysis"],
            "question": "Show the distribution of 2024-2025 CVEs by CWE category and their average CVSS scores.",
            "sql": "SELECT c.cwe_name, COUNT(DISTINCT c.cve_id) as unique_cves, COUNT(vi.instance_id) as total_instances, COUNT(DISTINCT CONCAT(vi.nuid, '-', vi.dev_id)) as affected_assets, AVG(CAST(c.cvss AS DECIMAL)) as avg_cvss, COUNT(CASE WHEN CAST(c.cvss AS DECIMAL) >= 7.0 THEN 1 END) as high_severity_cves FROM cve c JOIN vulnerability_instances vi ON c.cve_id = vi.cve_id WHERE c.cve_id LIKE 'CVE-2024%' OR c.cve_id LIKE 'CVE-2025%' GROUP BY c.cwe_name ORDER BY unique_cves DESC, avg_cvss DESC",
            "context": "Direct Visualization - Bar Chart. Shows CWE distribution for 2024-2025 CVEs with severity analysis.",
            "document": "mdl_cve.json - cwe_analysis_2024_2025",
            "samples": [],
            "instructions": "Analyze CWE distribution for recent CVEs to understand vulnerability patterns and focus areas."
        },
        {
            "categories": ["composite_key_analysis", "network_infrastructure"],
            "question": "Show network topology security status by analyzing interfaces and their associated vulnerabilities.",
            "sql": "SELECT i.subnet, i.site, COUNT(DISTINCT CONCAT(i.nuid, '-', i.dev_id)) as devices_in_subnet, COUNT(vi.instance_id) as vulnerability_count, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns, AVG(CAST(vi.cvssv3_basescore AS DECIMAL)) as avg_cvss FROM interfaces i LEFT JOIN vulnerability_instances vi ON i.nuid = vi.nuid AND i.dev_id = vi.dev_id WHERE (vi.cve_id LIKE 'CVE-2024%' OR vi.cve_id LIKE 'CVE-2025%') OR vi.cve_id IS NULL GROUP BY i.subnet, i.site ORDER BY critical_vulns DESC, vulnerability_count DESC",
            "context": "Direct Visualization - Network Security Map. Shows subnet-level security posture and vulnerability distribution.",
            "document": "mdl_interfaces.json - network_security_analysis",
            "samples": [],
            "instructions": "Analyze network security by subnet to identify vulnerable network segments and prioritize security controls."
        },
        {
            "categories": ["comprehensive_security", "composite_key_analysis"],
            "question": "Create a comprehensive security dashboard showing key metrics for each NUID using composite keys.",
            "sql": "SELECT a.nuid, COUNT(DISTINCT a.dev_id) as total_devices, COUNT(DISTINCT ag.agent) as active_agents, COUNT(DISTINCT si.key) as software_installations, COUNT(vi.instance_id) as total_vulnerabilities, COUNT(DISTINCT vi.cve_id) as unique_cves, COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns, COUNT(CASE WHEN vi.severity = 'HIGH' THEN 1 END) as high_vulns, COUNT(CASE WHEN si.product_state = 'VULNERABLE' THEN 1 END) as vulnerable_software, ROUND(COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) * 100.0 / COUNT(vi.instance_id), 2) as critical_percentage FROM assets a LEFT JOIN agents ag ON a.nuid = ag.nuid AND a.dev_id = ag.dev_id LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id GROUP BY a.nuid ORDER BY critical_vulns DESC, total_vulnerabilities DESC",
            "context": "Dashboard Widget - Executive Security Dashboard. Comprehensive security metrics by organizational unit.",
            "document": "Multiple models - Executive Security Dashboard",
            "samples": [],
            "instructions": "Create executive-level security dashboard using composite keys for organizational risk assessment and reporting."
        }
    ]
    
    # Combine existing and new examples
    all_examples = existing_pairs + new_examples
    
    # Write updated sql_pairs.json
    with open('data/sql_meta/cve_data/sql_pairs.json', 'w') as f:
        json.dump(all_examples, f, indent=2)
    
    print(f"Added {len(new_examples)} new SQL examples to sql_pairs.json")
    print("New examples include:")
    print("- 2024-2025 CVE analysis queries")
    print("- Composite key system demonstrations")
    print("- NUID-based organizational analysis")
    print("- Software vulnerability mapping")
    print("- Network security analysis")
    print("- Comprehensive security dashboards")

def main():
    """Main function to add new SQL examples"""
    print("Adding comprehensive SQL examples to sql_pairs.json...")
    add_new_sql_examples()
    print("✅ SQL examples update completed!")

if __name__ == "__main__":
    main()
