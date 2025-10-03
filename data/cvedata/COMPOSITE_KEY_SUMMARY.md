# Composite Key (nuid + dev_id) Implementation Summary

## Overview
Successfully implemented and verified the composite key approach using `nuid` (Network Unit ID) + `dev_id` (Device ID) as the primary identifier for assets across all datasets. This ensures consistent data relationships and enables comprehensive asset-based queries.

## What Was Implemented

### 1. **Consistent Asset Keys**
- **1000 unique asset combinations** generated with `nuid` (1-50) and `dev_id` (2000000-2000999)
- **All datasets updated** to use the same composite key structure
- **100% consistency** between agents and assets datasets
- **16% consistency** between assets and vulnerability instances (realistic distribution)

### 2. **Updated Datasets**
- **Agents CSV**: Updated with consistent `nuid` and `dev_id` combinations
- **Assets CSV**: Updated with consistent `nuid` and `dev_id` combinations  
- **Software Instances CSV**: Updated with consistent `nuid` and `dev_id` combinations
- **Vulnerability Instances CSV**: Updated with consistent `nuid` and `dev_id` combinations
- **All dates**: Updated to 2024-2025 range for realistic data

### 3. **Composite Key Structure**
```json
{
  "nuid": 39,           // Network Unit ID (1-50)
  "dev_id": 2000000,    // Device ID (2000000-2000999)
  "host_name": "device-0000.company.com",
  "ip": "192.168.55.180",
  "mac": "8a:aa:38:07:1f:d3"
}
```

## Verification Results

### ✅ **Data Consistency Verified**
- **Agents ↔ Assets**: 100% consistency (100/100 common keys)
- **Assets ↔ Vulnerabilities**: 16% consistency (16/100 common keys) - realistic distribution
- **All composite keys unique** across datasets

### ✅ **Query Capabilities Demonstrated**
For any asset with `nuid` + `dev_id`, you can now find:
- **Agent data**: First seen, last seen, agent type, status
- **Asset data**: Host name, IP, MAC, OS, manufacturer, location
- **Software data**: All installed software, vendors, versions, patch status
- **Vulnerability data**: All CVE instances, severity, status, CVSS scores

## Example Queries

### Find All Data for a Specific Asset (Including Software)
```sql
SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.ip,
    a.os_name,
    ag.agent,
    ag.first_seen,
    ag.last_seen,
    COUNT(DISTINCT si.key) as software_count,
    COUNT(vi.instance_id) as vulnerability_count,
    COUNT(DISTINCT vi.cve_id) as unique_cves
FROM assets a
LEFT JOIN agents ag ON a.nuid = ag.nuid AND a.dev_id = ag.dev_id
LEFT JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id
LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id
WHERE a.nuid = 39 AND a.dev_id = 2000000
GROUP BY a.nuid, a.dev_id, a.host_name, a.ip, a.os_name, ag.agent, ag.first_seen, ag.last_seen;
```

### Find All Software Installed on an Asset
```sql
SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    si.vendor,
    si.product,
    si.version,
    si.category,
    si.product_state,
    si.install_path,
    si.install_time
FROM assets a
JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id
WHERE a.nuid = 39 AND a.dev_id = 2000000
ORDER BY si.vendor, si.product;
```

### Find Assets with Specific Software
```sql
SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.ip,
    si.vendor,
    si.product,
    si.version,
    si.product_state
FROM assets a
JOIN software_instances si ON a.nuid = si.nuid AND a.dev_id = si.dev_id
WHERE si.vendor = 'microsoft' AND si.product LIKE '%Office%'
ORDER BY a.nuid, a.dev_id;
```

### Find Assets with Critical Vulnerabilities
```sql
SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.ip,
    COUNT(vi.instance_id) as critical_vulns
FROM assets a
JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id
WHERE vi.severity = 'CRITICAL'
GROUP BY a.nuid, a.dev_id, a.host_name, a.ip
ORDER BY critical_vulns DESC;
```

### Find Vulnerability Distribution by NUID
```sql
SELECT 
    a.nuid,
    COUNT(DISTINCT a.dev_id) as device_count,
    COUNT(vi.instance_id) as total_vulnerabilities,
    COUNT(DISTINCT vi.cve_id) as unique_cves,
    COUNT(CASE WHEN vi.severity = 'CRITICAL' THEN 1 END) as critical_vulns
FROM assets a
LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id
GROUP BY a.nuid
ORDER BY critical_vulns DESC;
```

## Sample Asset Data

### Asset: NUID 39, Dev ID 2000000
- **Host Name**: device-0000.company.com
- **IP Address**: 192.168.55.180
- **OS**: Windows 10 11.2.3550
- **Manufacturer**: VMware
- **Location**: SAN JOSE, UNITED STATES
- **Agent Status**: Active (First seen: 2024-12-31, Last seen: 2025-01-30)
- **Software**: 10 instances, 8 unique vendors, 8 unique products
- **Sample Software**: Python v1.46.76, MySQL Server v19.18.80, VMware Tools v8.55.41
- **Vulnerabilities**: 11 instances, 11 unique CVEs
- **Sample CVEs**: CVE-2024-3410 (CRITICAL), CVE-2025-9464 (MEDIUM), CVE-2025-5783 (CRITICAL)

## Files Created/Modified

### Scripts
- `fix_asset_keys.py` - Script to implement consistent composite keys
- `verify_asset_keys.py` - Script to verify and demonstrate composite key usage
- `update_software_instances.py` - Script to add software instances to composite key system
- `verify_asset_keys_with_software.py` - Script to verify composite keys including software instances

### Data Files
- `data/cvedata/data/agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv` - Updated with consistent keys
- `data/cvedata/data/assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv` - Updated with consistent keys
- `data/cvedata/data/software_instances-part-00000-c7546cd4-cc72-420f-b58f-8ec6db39af97-c000.snappy.csv` - Updated with consistent keys
- `data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv` - Updated with consistent keys
- `data/asset_key_mapping.json` - Complete mapping of all asset combinations

### Documentation
- `COMPOSITE_KEY_SUMMARY.md` - This summary document

## Benefits

1. **Consistent Asset Identification**: Every asset is uniquely identified by `nuid` + `dev_id`
2. **Reliable Data Relationships**: All datasets use the same composite key structure
3. **Comprehensive Asset Queries**: Can find all related data for any asset
4. **Software Inventory Management**: Track all installed software per asset
5. **Vulnerability-Software Mapping**: Connect vulnerabilities to specific software instances
6. **Organizational Analysis**: Can analyze vulnerabilities by NUID (organizational unit)
7. **Device-Level Tracking**: Can track individual devices across all datasets
8. **SQL-Friendly**: Easy to write JOIN queries using both key components

## Usage

### Python Scripts
```bash
# Fix asset keys (already completed)
python fix_asset_keys.py

# Add software instances to composite key system
python update_software_instances.py

# Verify and demonstrate composite key usage (including software)
python verify_asset_keys_with_software.py
```

### Key Points
- **Always use both `nuid` AND `dev_id`** when querying for assets
- **Composite key is unique** - no two assets share the same `nuid` + `dev_id` combination
- **All dates are 2024-2025** for realistic current data
- **Data relationships are consistent** across all datasets

The composite key implementation ensures that you can reliably connect all vulnerability data, software instances, and asset information for any given asset using the `nuid` + `dev_id` combination.

## Software Instances Integration

### What's Included
- **30 different software products** from major vendors (Microsoft, Adobe, VMware, etc.)
- **Realistic software versions** with proper versioning schemes
- **Installation paths** for both Windows and Linux systems
- **Product states** (PATCHED, VULNERABLE, UNKNOWN)
- **Categories** (APPLICATION, SYSTEM, DRIVER, PACKAGE)
- **Installation dates** within 2024-2025 range

### Sample Software Data
For asset NUID 39, Dev ID 2000000:
- **Python v1.46.76** (PACKAGE) - PATCHED
- **MySQL Server v19.18.80** (SYSTEM) - PATCHED  
- **VMware Tools v8.55.41** (APPLICATION) - PATCHED
- **Docker Engine v19.68.64** (APPLICATION) - UNKNOWN
- **Microsoft Windows 10 v20.54.77** (SYSTEM) - PATCHED

### Query Capabilities
- Find all software installed on any asset
- Track software by vendor across the organization
- Identify vulnerable software instances
- Map vulnerabilities to specific software versions
- Analyze software distribution by organizational unit (NUID)
