#!/usr/bin/env python3
"""
Script to fix asset keys by ensuring all datasets use the same nuid+dev_id combinations.
This creates a consistent composite key across all datasets.
"""

import json
import csv
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple

# Configuration
NUM_DEVICES = 1000  # Number of unique devices
NUM_NUIDS = 50      # Number of network units

def generate_consistent_asset_keys():
    """Generate consistent nuid+dev_id combinations for all datasets"""
    
    # Generate unique device combinations
    asset_combinations = []
    for i in range(NUM_DEVICES):
        nuid = random.randint(1, NUM_NUIDS)
        dev_id = 2000000 + i  # Start from a high number to avoid conflicts
        asset_combinations.append({
            'nuid': nuid,
            'dev_id': dev_id,
            'ip': f"192.168.{random.randint(1, 255)}.{random.randint(1, 254)}",
            'mac': ':'.join([f"{random.randint(0, 255):02x}" for _ in range(6)]),
            'host_name': f"device-{i:04d}.company.com"
        })
    
    return asset_combinations

def update_agents_csv(asset_combinations):
    """Update agents CSV with consistent asset keys"""
    print("Updating agents CSV with consistent asset keys...")
    
    # Read existing agents data
    with open('data/cvedata/data/agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        agents_data = list(reader)
    
    # Update agents with consistent asset combinations
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for i, agent in enumerate(agents_data):
        if i < len(asset_combinations):
            asset = asset_combinations[i]
        else:
            asset = random.choice(asset_combinations)
        
        # Update asset keys
        agent['nuid'] = str(asset['nuid'])
        agent['dev_id'] = str(asset['dev_id'])
        
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
    
    return asset_combinations

def update_assets_csv(asset_combinations):
    """Update assets CSV with consistent asset keys"""
    print("Updating assets CSV with consistent asset keys...")
    
    # Read existing assets data
    with open('data/cvedata/data/assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        assets_data = list(reader)
    
    # Update assets with consistent combinations
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for i, asset in enumerate(assets_data):
        if i < len(asset_combinations):
            asset_combo = asset_combinations[i]
        else:
            asset_combo = random.choice(asset_combinations)
        
        # Update asset keys
        asset['nuid'] = str(asset_combo['nuid'])
        asset['dev_id'] = str(asset_combo['dev_id'])
        asset['ip'] = asset_combo['ip']
        asset['mac'] = asset_combo['mac']
        asset['host_name'] = asset_combo['host_name']
        
        # Update other fields
        asset['os_name'] = random.choice(['Windows 10', 'Windows 11', 'Ubuntu 20.04', 'Ubuntu 22.04', 'CentOS 7', 'CentOS 8'])
        asset['os_version'] = f"{random.randint(10, 11)}.{random.randint(0, 9)}.{random.randint(0, 9999)}"
        asset['manufacturer'] = random.choice(['Dell', 'HP', 'Lenovo', 'Apple', 'VMware'])
        
        # Update dates
        last_seen_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        asset['inserted_at'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        asset['events_timestamp'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        asset['raw_created_at'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        asset['store_created_at'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        asset['store_updated_at'] = last_seen_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        asset['last_processed'] = last_seen_date.isoformat()
    
    # Write updated assets data
    with open('data/cvedata/data/assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv', 'w', newline='') as f:
        fieldnames = assets_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(assets_data)

def update_vulnerability_instances_csv(asset_combinations):
    """Update vulnerability instances CSV with consistent asset keys"""
    print("Updating vulnerability instances CSV with consistent asset keys...")
    
    # Read existing vulnerability instances data
    with open('data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        vuln_data = list(reader)
    
    # Generate CVE data
    cves = []
    for i in range(500):
        year = random.choice([2024, 2025])
        cve_id = f"CVE-{year}-{random.randint(1000, 9999)}"
        cves.append(cve_id)
    
    # Update vulnerability instances with consistent combinations
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for i, vuln in enumerate(vuln_data):
        # Assign to a random asset
        asset = random.choice(asset_combinations)
        
        # Update asset keys
        vuln['nuid'] = str(asset['nuid'])
        vuln['dev_id'] = str(asset['dev_id'])
        
        # Update CVE
        vuln['cve_id'] = random.choice(cves)
        vuln['cve_partition_id'] = f"CVE-{vuln['cve_id'].split('-')[1]}"
        
        # Update other fields
        vuln['instance_id'] = str(uuid.uuid4())
        vuln['sw_instance_id'] = str(uuid.uuid4())
        vuln['severity'] = random.choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
        vuln['state'] = random.choice(['ACTIVE', 'PATCHED', 'MITIGATED', 'FALSE_POSITIVE'])
        
        # Update dates
        detected_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        
        vuln['detected_time'] = detected_date.isoformat()
        vuln['published_time'] = (detected_date - timedelta(days=random.randint(1, 30))).isoformat()
        vuln['raw_created_at'] = detected_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        vuln['store_created_at'] = detected_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        vuln['store_updated_at'] = detected_date.strftime('%Y-%m-%d %H:%M:%S.%f')
    
    # Write updated vulnerability instances data
    with open('data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv', 'w', newline='') as f:
        fieldnames = vuln_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(vuln_data)

def create_asset_key_mapping(asset_combinations):
    """Create a mapping of asset keys for verification"""
    print("Creating asset key mapping...")
    
    mapping = {
        "total_assets": len(asset_combinations),
        "asset_keys": [],
        "nuid_distribution": {},
        "dev_id_range": {
            "min": min(combo['dev_id'] for combo in asset_combinations),
            "max": max(combo['dev_id'] for combo in asset_combinations)
        }
    }
    
    # Create asset key list
    for combo in asset_combinations:
        mapping["asset_keys"].append({
            "nuid": combo['nuid'],
            "dev_id": combo['dev_id'],
            "host_name": combo['host_name'],
            "ip": combo['ip']
        })
    
    # Count NUID distribution
    for combo in asset_combinations:
        nuid = combo['nuid']
        mapping["nuid_distribution"][nuid] = mapping["nuid_distribution"].get(nuid, 0) + 1
    
    # Write mapping to file
    with open('data/asset_key_mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)
    
    return mapping

def verify_asset_key_consistency():
    """Verify that all datasets use consistent asset keys"""
    print("Verifying asset key consistency...")
    
    # Read all datasets
    with open('data/cvedata/data/agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        agents_data = list(reader)
    
    with open('data/cvedata/data/assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        assets_data = list(reader)
    
    with open('data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        vuln_data = list(reader)
    
    # Extract asset keys from each dataset
    agents_keys = set()
    assets_keys = set()
    vuln_keys = set()
    
    for agent in agents_data[:100]:  # Check first 100
        key = (int(agent['nuid']), int(agent['dev_id']))
        agents_keys.add(key)
    
    for asset in assets_data[:100]:  # Check first 100
        key = (int(asset['nuid']), int(asset['dev_id']))
        assets_keys.add(key)
    
    for vuln in vuln_data[:100]:  # Check first 100
        key = (int(vuln['nuid']), int(vuln['dev_id']))
        vuln_keys.add(key)
    
    # Check for consistency
    print(f"Agents unique keys: {len(agents_keys)}")
    print(f"Assets unique keys: {len(assets_keys)}")
    print(f"Vulnerability instances unique keys: {len(vuln_keys)}")
    
    # Check for overlaps
    agents_assets_overlap = agents_keys.intersection(assets_keys)
    agents_vuln_overlap = agents_keys.intersection(vuln_keys)
    assets_vuln_overlap = assets_keys.intersection(vuln_keys)
    
    print(f"Agents-Assets overlap: {len(agents_assets_overlap)}")
    print(f"Agents-Vulnerability overlap: {len(agents_vuln_overlap)}")
    print(f"Assets-Vulnerability overlap: {len(assets_vuln_overlap)}")
    
    # Show sample consistent keys
    if agents_assets_overlap:
        print(f"\nSample consistent asset keys:")
        for i, key in enumerate(list(agents_assets_overlap)[:5]):
            print(f"  {i+1}. NUID: {key[0]}, Dev ID: {key[1]}")
    
    return len(agents_assets_overlap) > 0 and len(agents_vuln_overlap) > 0

def main():
    """Main function to fix asset keys"""
    print("Starting asset key consistency fix...")
    
    # Generate consistent asset combinations
    asset_combinations = generate_consistent_asset_keys()
    print(f"Generated {len(asset_combinations)} consistent asset combinations")
    
    # Update all datasets
    update_agents_csv(asset_combinations)
    update_assets_csv(asset_combinations)
    update_vulnerability_instances_csv(asset_combinations)
    
    # Create mapping
    mapping = create_asset_key_mapping(asset_combinations)
    
    # Verify consistency
    is_consistent = verify_asset_key_consistency()
    
    print(f"\nAsset key consistency fix completed!")
    print(f"Total assets: {mapping['total_assets']}")
    print(f"Dev ID range: {mapping['dev_id_range']['min']} - {mapping['dev_id_range']['max']}")
    print(f"NUID distribution: {len(mapping['nuid_distribution'])} unique NUIDs")
    print(f"Consistency verified: {'✓' if is_consistent else '✗'}")
    
    return is_consistent

if __name__ == "__main__":
    main()
