# Dataset Connections Summary

## Overview
All datasets have been successfully connected with fake data to enable comprehensive vulnerability analysis. You can now query all vulnerabilities, vulnerability instances, and software instances for any given asset.

## What Was Connected

### 1. **Assets** ↔ **CVEs**
- Connected via `nuid` (Network Unit ID)
- Each asset can have multiple CVEs based on its organizational unit
- 1,000 devices connected to 500 unique CVEs

### 2. **Assets** ↔ **Software Instances**
- Connected via `dev_id` (Device ID)
- Each device can have multiple software installations
- 1,000 devices connected to 2,142 software instances

### 3. **Assets** ↔ **Vulnerability Instances**
- Connected via `dev_id` (Device ID)
- Each device can have multiple vulnerability instances
- 1,000 devices connected to 3,000 vulnerability instances

### 4. **CVEs** ↔ **Vulnerability Instances**
- Connected via `cve_id`
- Each CVE can have multiple instances across different devices
- 500 CVEs connected to 3,000 vulnerability instances

### 5. **Software Instances** ↔ **Vulnerability Instances**
- Connected via `sw_instance_id`
- Each software instance can have multiple vulnerabilities
- 2,142 software instances connected to 3,000 vulnerability instances

## Key Statistics
- **Total Devices**: 1,000
- **Total CVEs**: 500
- **Total Software Instances**: 2,142
- **Total Vulnerability Instances**: 3,000
- **Devices with Critical Vulnerabilities**: 64
- **Average Vulnerabilities per Device**: 3

## Example Queries

### Find All Vulnerabilities for a Specific Asset
```sql
SELECT 
    a.dev_id,
    a.host_name,
    a.ip,
    a.os_name,
    c.cve_id,
    c.severity,
    c.cvss_score,
    vi.instance_id,
    vi.status,
    si.vendor,
    si.product,
    si.version
FROM dev_assets a
JOIN dev_vulnerability_instances vi ON a.dev_id = vi.dev_id
JOIN dev_cve c ON vi.cve_id = c.cve_id
JOIN dev_software_instances si ON vi.sw_instance_id = si.sw_instance_id
WHERE a.dev_id = 2000000;
```

### Find All Critical Vulnerabilities
```sql
SELECT 
    a.dev_id,
    a.host_name,
    a.ip,
    c.cve_id,
    c.severity,
    c.cvss_score,
    vi.status
FROM dev_assets a
JOIN dev_vulnerability_instances vi ON a.dev_id = vi.dev_id
JOIN dev_cve c ON vi.cve_id = c.cve_id
WHERE c.severity = 'CRITICAL'
ORDER BY c.cvss_score DESC;
```

### Find Most Vulnerable Devices
```sql
SELECT 
    a.dev_id,
    a.host_name,
    COUNT(vi.instance_id) as vulnerability_count,
    COUNT(DISTINCT vi.cve_id) as unique_cves
FROM dev_assets a
JOIN dev_vulnerability_instances vi ON a.dev_id = vi.dev_id
GROUP BY a.dev_id, a.host_name
ORDER BY vulnerability_count DESC
LIMIT 10;
```

## Files Created/Modified

### New Files
- `connect_datasets.py` - Script to generate and connect all datasets
- `verify_connections.py` - Script to verify and demonstrate connections
- `data/connection_summary.json` - Complete mapping of all connections
- `DATASET_CONNECTIONS_SUMMARY.md` - This summary document

### Modified Files
- `data/cvedata/data/agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv` - Updated with connected dev_ids and nuids
- `data/sql_meta/cve_data/mdl_assets.json` - Added sample asset data
- `data/sql_meta/cve_data/mdl_cve.json` - Added sample CVE data
- `data/sql_meta/cve_data/mdl_software_instances.json` - Added sample software instance data
- `data/sql_meta/cve_data/mdl_vuln_instance.json` - Added sample vulnerability instance data

## Usage Examples

### Python Scripts
```bash
# Run the connection script
python connect_datasets.py

# Verify connections and see examples
python verify_connections.py
```

### Sample Asset Analysis
For device 2000000:
- **Host Name**: device-0000.company.com
- **IP Address**: 192.168.87.149
- **OS**: CentOS 7
- **Criticality**: MEDIUM
- **CVEs**: 6 CVEs
- **Software Instances**: 1 instance
- **Vulnerability Instances**: 2 instances

## Benefits
1. **Complete Asset Visibility**: For any asset, you can now see all related vulnerabilities, software, and instances
2. **Cross-Dataset Analysis**: Query across all datasets using common identifiers
3. **Risk Assessment**: Identify the most vulnerable devices and critical vulnerabilities
4. **Compliance Reporting**: Generate comprehensive reports across organizational units
5. **Remediation Planning**: Track vulnerability status and prioritize based on asset criticality

## Next Steps
1. Use the provided SQL queries to analyze your data
2. Customize the connection script if you need different data patterns
3. Integrate with your existing vulnerability management tools
4. Set up automated reporting based on the connected data structure
