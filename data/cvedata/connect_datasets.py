#!/usr/bin/env python3
"""
Script to connect all datasets by creating fake relationships between:
- Asset IDs (dev_id, nuid)
- CVE IDs
- Vulnerability Instance IDs
- Software Instance IDs

This will allow querying all vulnerabilities, instances, and software for any given asset.
"""

import json
import csv
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Set

# Configuration
NUM_DEVICES = 1000  # Number of unique devices
NUM_NUIDS = 50      # Number of network units
NUM_CVES = 500      # Number of unique CVEs
NUM_SOFTWARE_INSTANCES = 2000  # Number of software instances

def generate_fake_data():
    """Generate fake data to connect all datasets"""
    
    # Generate device IDs and NUIDs
    devices = []
    for i in range(NUM_DEVICES):
        dev_id = 2000000 + i  # Start from a high number to avoid conflicts
        nuid = random.randint(1, NUM_NUIDS)
        devices.append({
            'dev_id': dev_id,
            'nuid': nuid,
            'ip': f"192.168.{random.randint(1, 255)}.{random.randint(1, 254)}",
            'mac': ':'.join([f"{random.randint(0, 255):02x}" for _ in range(6)]),
            'host_name': f"device-{i:04d}.company.com"
        })
    
    # Generate CVE IDs
    cves = []
    for i in range(NUM_CVES):
        year = random.choice([2024, 2025])  # Only 2024 and 2025
        cve_id = f"CVE-{year}-{random.randint(1000, 9999)}"
        cves.append({
            'cve_id': cve_id,
            'nuid': random.randint(1, NUM_NUIDS),
            'balbix_score': round(random.uniform(0, 100), 2),
            'cvss_score': round(random.uniform(0, 10), 1),
            'severity': random.choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
        })
    
    # Generate software instances
    software_instances = []
    vendors_products = [
        ('microsoft', 'windows_10'),
        ('microsoft', 'office_365'),
        ('adobe', 'acrobat_reader'),
        ('mozilla', 'firefox'),
        ('google', 'chrome'),
        ('oracle', 'java_runtime'),
        ('apache', 'http_server'),
        ('nginx', 'nginx'),
        ('mysql', 'mysql_server'),
        ('postgresql', 'postgresql'),
        ('redis', 'redis'),
        ('docker', 'docker_engine'),
        ('kubernetes', 'kubectl'),
        ('git', 'git'),
        ('nodejs', 'node'),
        ('python', 'python'),
        ('java', 'openjdk'),
        ('php', 'php'),
        ('ruby', 'ruby'),
        ('golang', 'go')
    ]
    
    for i in range(NUM_SOFTWARE_INSTANCES):
        dev = random.choice(devices)
        vendor, product = random.choice(vendors_products)
        version = f"{random.randint(1, 20)}.{random.randint(0, 99)}.{random.randint(0, 99)}"
        
        software_instances.append({
            'sw_instance_id': str(uuid.uuid4()),
            'dev_id': dev['dev_id'],
            'nuid': dev['nuid'],
            'vendor': vendor,
            'product': product,
            'version': version,
            'key': f"{vendor}_{product}_{version}_{dev['dev_id']}"
        })
    
    # Generate vulnerability instances
    vulnerability_instances = []
    for i in range(len(devices) * 3):  # 3 vulnerabilities per device on average
        dev = random.choice(devices)
        cve = random.choice(cves)
        
        # Find software instances for this device, or create a default one
        device_software = [s for s in software_instances if s['dev_id'] == dev['dev_id']]
        if device_software:
            sw_instance = random.choice(device_software)
        else:
            # Create a default software instance for this device
            vendor, product = random.choice(vendors_products)
            version = f"{random.randint(1, 20)}.{random.randint(0, 99)}.{random.randint(0, 99)}"
            sw_instance = {
                'sw_instance_id': str(uuid.uuid4()),
                'dev_id': dev['dev_id'],
                'nuid': dev['nuid'],
                'vendor': vendor,
                'product': product,
                'version': version,
                'key': f"{vendor}_{product}_{version}_{dev['dev_id']}"
            }
            software_instances.append(sw_instance)
        
        # Generate dates for 2024-2025
        base_date_2024 = datetime(2024, 1, 1)
        base_date_2025 = datetime(2025, 1, 1)
        current_year = datetime.now().year
        
        if current_year == 2024:
            # If we're in 2024, use dates from 2024 and some from 2025
            if random.choice([True, False]):
                detected_date = base_date_2024 + timedelta(days=random.randint(1, 365))
            else:
                detected_date = base_date_2025 + timedelta(days=random.randint(1, 365))
        else:
            # If we're in 2025 or later, use dates from 2024-2025
            detected_date = random.choice([
                base_date_2024 + timedelta(days=random.randint(1, 365)),
                base_date_2025 + timedelta(days=random.randint(1, 365))
            ])
        
        vulnerability_instances.append({
            'instance_id': str(uuid.uuid4()),
            'dev_id': dev['dev_id'],
            'nuid': dev['nuid'],
            'cve_id': cve['cve_id'],
            'sw_instance_id': sw_instance['sw_instance_id'],
            'status': random.choice(['ACTIVE', 'PATCHED', 'MITIGATED', 'FALSE_POSITIVE']),
            'detected_date': detected_date.isoformat()
        })
    
    return devices, cves, software_instances, vulnerability_instances

def update_agents_csv(devices):
    """Update the agents CSV with connected device data"""
    print("Updating agents CSV...")
    
    # Read existing agents data
    agents_data = []
    with open('data/cvedata/data/agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        agents_data = list(reader)
    
    # Create a mapping of existing dev_ids to new ones and update dates
    dev_id_mapping = {}
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for i, agent in enumerate(agents_data[:len(devices)]):
        old_dev_id = agent['dev_id']
        new_dev_id = devices[i]['dev_id']
        dev_id_mapping[old_dev_id] = new_dev_id
        agent['dev_id'] = str(new_dev_id)
        agent['nuid'] = str(devices[i]['nuid'])
        
        # Update dates to 2024-2025
        first_seen_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        last_seen_date = first_seen_date + timedelta(days=random.randint(1, 30))
        
        agent['first_seen'] = first_seen_date.isoformat()
        agent['last_seen'] = last_seen_date.strftime('%Y-%m-%d')
        agent['raw_created_at'] = first_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        agent['store_created_at'] = first_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        agent['store_updated_at'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Update remaining agents with random assignments and 2024-2025 dates
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for agent in agents_data[len(devices):]:
        dev = random.choice(devices)
        old_dev_id = agent['dev_id']
        new_dev_id = dev['dev_id']
        dev_id_mapping[old_dev_id] = new_dev_id
        agent['dev_id'] = str(new_dev_id)
        agent['nuid'] = str(dev['nuid'])
        
        # Update dates to 2024-2025
        first_seen_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        last_seen_date = first_seen_date + timedelta(days=random.randint(1, 30))
        
        agent['first_seen'] = first_seen_date.isoformat()
        agent['last_seen'] = last_seen_date.strftime('%Y-%m-%d')
        agent['raw_created_at'] = first_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        agent['store_created_at'] = first_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        agent['store_updated_at'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Write updated agents data
    with open('data/cvedata/data/agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv', 'w', newline='') as f:
        fieldnames = agents_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(agents_data)
    
    return dev_id_mapping

def update_assets_json(devices):
    """Update the assets JSON with connected device data"""
    print("Updating assets JSON...")
    
    # Read existing assets metadata
    with open('data/sql_meta/cve_data/mdl_assets.json', 'r') as f:
        assets_meta = json.load(f)
    
    # Create sample asset data based on the schema
    sample_assets = []
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for dev in devices:
        # Generate dates for 2024-2025
        last_seen_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        asset = {
            "nuid": dev['nuid'],
            "dev_id": dev['dev_id'],
            "ip": dev['ip'],
            "mac": dev['mac'],
            "host_name": dev['host_name'],
            "os_name": random.choice(['Windows 10', 'Windows 11', 'Ubuntu 20.04', 'Ubuntu 22.04', 'CentOS 7', 'CentOS 8']),
            "os_version": f"{random.randint(10, 11)}.{random.randint(0, 9)}.{random.randint(0, 9999)}",
            "manufacturer": random.choice(['Dell', 'HP', 'Lenovo', 'Apple', 'VMware']),
            "model": f"Model-{random.randint(1000, 9999)}",
            "location": random.choice(['Data Center A', 'Data Center B', 'Office Building 1', 'Office Building 2', 'Remote']),
            "criticality": random.choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
            "last_seen": last_seen_date.isoformat()
        }
        sample_assets.append(asset)
    
    # Update the metadata with sample data
    assets_meta['sampleData'] = sample_assets[:10]  # Include first 10 as sample
    
    # Write updated assets metadata
    with open('data/sql_meta/cve_data/mdl_assets.json', 'w') as f:
        json.dump(assets_meta, f, indent=2)
    
    return sample_assets

def update_cve_json(cves):
    """Update the CVE JSON with connected CVE data"""
    print("Updating CVE JSON...")
    
    # Read existing CVE metadata
    with open('data/sql_meta/cve_data/mdl_cve.json', 'r') as f:
        cve_meta = json.load(f)
    
    # Create sample CVE data
    sample_cves = []
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for cve in cves[:20]:  # First 20 as sample
        # Generate dates for 2024-2025
        published_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        last_modified_date = published_date + timedelta(days=random.randint(1, 30))
        
        # Ensure last_modified doesn't go beyond 2025
        if last_modified_date.year > 2025:
            last_modified_date = datetime(2025, 12, 31)
        
        cve_data = {
            "nuid": cve['nuid'],
            "cve_id": cve['cve_id'],
            "cve_partition_id": f"CVE-{cve['cve_id'].split('-')[1]}",
            "balbix_score": cve['balbix_score'],
            "cvss_score": cve['cvss_score'],
            "severity": cve['severity'],
            "description": f"Security vulnerability in {random.choice(['web application', 'operating system', 'database', 'network service'])}",
            "published_date": published_date.isoformat(),
            "last_modified": last_modified_date.isoformat()
        }
        sample_cves.append(cve_data)
    
    # Update the metadata with sample data
    cve_meta['sampleData'] = sample_cves
    
    # Write updated CVE metadata
    with open('data/sql_meta/cve_data/mdl_cve.json', 'w') as f:
        json.dump(cve_meta, f, indent=2)
    
    return sample_cves

def update_software_instances_json(software_instances):
    """Update the software instances JSON with connected data"""
    print("Updating software instances JSON...")
    
    # Read existing software instances metadata
    with open('data/sql_meta/cve_data/mdl_software_instances.json', 'r') as f:
        sw_meta = json.load(f)
    
    # Create sample software instances data
    sample_sw = []
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for sw in software_instances[:20]:  # First 20 as sample
        # Generate dates for 2024-2025
        install_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        last_seen_date = install_date + timedelta(days=random.randint(1, 30))
        
        sw_data = {
            "swkey_partition_id": "APPLICATION",
            "nuid": sw['nuid'],
            "dev_id": sw['dev_id'],
            "key": sw['key'],
            "cpe": f"cpe:2.3:a:{sw['vendor']}:{sw['product']}:{sw['version']}:*:*:*:*:*:*:*",
            "vendor": sw['vendor'],
            "product": sw['product'],
            "version": sw['version'],
            "install_date": install_date.isoformat(),
            "last_seen": last_seen_date.isoformat()
        }
        sample_sw.append(sw_data)
    
    # Update the metadata with sample data
    sw_meta['sampleData'] = sample_sw
    
    # Write updated software instances metadata
    with open('data/sql_meta/cve_data/mdl_software_instances.json', 'w') as f:
        json.dump(sw_meta, f, indent=2)
    
    return sample_sw

def update_vulnerability_instances_json(vulnerability_instances):
    """Update the vulnerability instances JSON with connected data"""
    print("Updating vulnerability instances JSON...")
    
    # Read existing vulnerability instances metadata
    with open('data/sql_meta/cve_data/mdl_vuln_instance.json', 'r') as f:
        vuln_meta = json.load(f)
    
    # Create sample vulnerability instances data
    sample_vulns = []
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for vuln in vulnerability_instances[:20]:  # First 20 as sample
        # Generate last_updated date for 2024-2025
        detected_date = datetime.fromisoformat(vuln['detected_date'].replace('Z', '+00:00'))
        last_updated_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        # Ensure last_updated is after detected_date
        if last_updated_date < detected_date:
            last_updated_date = detected_date + timedelta(days=random.randint(1, 30))
        
        # Ensure last_updated doesn't go beyond 2025
        if last_updated_date.year > 2025:
            last_updated_date = datetime(2025, 12, 31)
        
        vuln_data = {
            "cve_partition_id": f"CVE-{vuln['cve_id'].split('-')[1]}",
            "nuid": vuln['nuid'],
            "dev_id": vuln['dev_id'],
            "instance_id": vuln['instance_id'],
            "sw_instance_id": vuln['sw_instance_id'],
            "cve_id": vuln['cve_id'],
            "status": vuln['status'],
            "detected_date": vuln['detected_date'],
            "last_updated": last_updated_date.isoformat()
        }
        sample_vulns.append(vuln_data)
    
    # Update the metadata with sample data
    vuln_meta['sampleData'] = sample_vulns
    
    # Write updated vulnerability instances metadata
    with open('data/sql_meta/cve_data/mdl_vuln_instance.json', 'w') as f:
        json.dump(vuln_meta, f, indent=2)
    
    return sample_vulns

def create_connection_summary(devices, cves, software_instances, vulnerability_instances):
    """Create a summary of all connections for verification"""
    print("Creating connection summary...")
    
    summary = {
        "total_devices": len(devices),
        "total_cves": len(cves),
        "total_software_instances": len(software_instances),
        "total_vulnerability_instances": len(vulnerability_instances),
        "connections": {
            "devices_to_cves": {},
            "devices_to_software": {},
            "devices_to_vulnerabilities": {},
            "cves_to_vulnerabilities": {},
            "software_to_vulnerabilities": {}
        }
    }
    
    # Map devices to their related data
    for dev in devices:
        dev_id = dev['dev_id']
        nuid = dev['nuid']
        
        # Find CVEs for this device's NUID
        device_cves = [cve for cve in cves if cve['nuid'] == nuid]
        summary["connections"]["devices_to_cves"][dev_id] = [cve['cve_id'] for cve in device_cves]
        
        # Find software instances for this device
        device_software = [sw for sw in software_instances if sw['dev_id'] == dev_id]
        summary["connections"]["devices_to_software"][dev_id] = [sw['sw_instance_id'] for sw in device_software]
        
        # Find vulnerability instances for this device
        device_vulns = [vuln for vuln in vulnerability_instances if vuln['dev_id'] == dev_id]
        summary["connections"]["devices_to_vulnerabilities"][dev_id] = [vuln['instance_id'] for vuln in device_vulns]
    
    # Map CVEs to vulnerability instances
    for cve in cves:
        cve_id = cve['cve_id']
        cve_vulns = [vuln for vuln in vulnerability_instances if vuln['cve_id'] == cve_id]
        summary["connections"]["cves_to_vulnerabilities"][cve_id] = [vuln['instance_id'] for vuln in cve_vulns]
    
    # Map software instances to vulnerability instances
    for sw in software_instances:
        sw_id = sw['sw_instance_id']
        sw_vulns = [vuln for vuln in vulnerability_instances if vuln['sw_instance_id'] == sw_id]
        summary["connections"]["software_to_vulnerabilities"][sw_id] = [vuln['instance_id'] for vuln in sw_vulns]
    
    # Write summary to file
    with open('data/connection_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary

def main():
    """Main function to connect all datasets"""
    print("Starting dataset connection process...")
    
    # Generate fake data
    devices, cves, software_instances, vulnerability_instances = generate_fake_data()
    
    print(f"Generated {len(devices)} devices, {len(cves)} CVEs, {len(software_instances)} software instances, {len(vulnerability_instances)} vulnerability instances")
    
    # Update all datasets
    dev_id_mapping = update_agents_csv(devices)
    assets = update_assets_json(devices)
    cve_data = update_cve_json(cves)
    sw_data = update_software_instances_json(software_instances)
    vuln_data = update_vulnerability_instances_json(vulnerability_instances)
    
    # Create connection summary
    summary = create_connection_summary(devices, cves, software_instances, vulnerability_instances)
    
    print("\nDataset connection completed!")
    print(f"Summary saved to: data/connection_summary.json")
    print(f"Total devices: {summary['total_devices']}")
    print(f"Total CVEs: {summary['total_cves']}")
    print(f"Total software instances: {summary['total_software_instances']}")
    print(f"Total vulnerability instances: {summary['total_vulnerability_instances']}")
    
    # Show example connections
    print("\nExample connections for device 2000000:")
    if 2000000 in summary["connections"]["devices_to_cves"]:
        print(f"  CVEs: {len(summary['connections']['devices_to_cves'][2000000])} CVEs")
        print(f"  Software: {len(summary['connections']['devices_to_software'][2000000])} software instances")
        print(f"  Vulnerabilities: {len(summary['connections']['devices_to_vulnerabilities'][2000000])} vulnerability instances")

if __name__ == "__main__":
    main()
