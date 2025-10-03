#!/usr/bin/env python3
"""
Script to update MDL schema with missing columns from CSV data.
This will add comprehensive descriptions and definitions for all missing columns.
"""

import json
import csv
from pathlib import Path

def get_csv_columns(csv_path):
    """Get column names from CSV file."""
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        return next(reader)

def get_mdl_columns(mdl_path):
    """Get existing column names from MDL schema."""
    with open(mdl_path, 'r') as f:
        data = json.load(f)
        if 'models' in data and len(data['models']) > 0:
            return [col['name'] for col in data['models'][0].get('columns', [])]
    return []

def infer_column_type_and_description(column_name):
    """Infer column type and create description based on column name patterns."""
    
    # Type inference based on column name patterns
    if any(keyword in column_name.lower() for keyword in ['id', 'nuid', 'dev_id']):
        col_type = 'INTEGER'
    elif any(keyword in column_name.lower() for keyword in ['ip', 'mac', 'host_name', 'serial_number', 'version', 'vendor', 'manufacturer', 'model', 'name', 'site', 'location', 'zone', 'platform', 'arch', 'policy', 'status']):
        col_type = 'VARCHAR'
    elif any(keyword in column_name.lower() for keyword in ['date', 'time', 'timestamp', 'created', 'updated', 'processed', 'release', 'install']):
        col_type = 'TIMESTAMP'
    elif any(keyword in column_name.lower() for keyword in ['count', 'cores', 'memory', 'mb', 'gb', 'days', 'mins', 'uptime']):
        col_type = 'FLOAT'
    elif any(keyword in column_name.lower() for keyword in ['is_', 'has_', 'can_', 'should_', 'enable', 'disable', 'active', 'inactive', 'pending', 'retired', 'stale', 'cloud', 'bastion', 'manual', 'domain']):
        col_type = 'BOOLEAN'
    elif any(keyword in column_name.lower() for keyword in ['impact', 'likelihood', 'risk', 'score', 'rating', 'probability', 'chance']):
        col_type = 'FLOAT'
    elif any(keyword in column_name.lower() for keyword in ['tags', 'roles', 'search']):
        col_type = 'TEXT'
    else:
        col_type = 'VARCHAR'
    
    # Create description based on column name
    description = create_column_description(column_name)
    
    return col_type, description

def create_column_description(column_name):
    """Create a human-readable description for a column based on its name."""
    
    # Common patterns and their descriptions
    descriptions = {
        # Security and Risk
        'raw_risk': 'Raw risk score calculated for the asset based on various security factors',
        'effective_risk': 'Effective risk score after applying business context and mitigations',
        'raw_impact': 'Raw impact score if the asset were compromised',
        'effective_impact': 'Effective impact score considering business criticality',
        'raw_likelihood': 'Raw likelihood score of the asset being compromised',
        'effective_likelihood': 'Effective likelihood score after applying security controls',
        'unpatched_vulnerability_likelihood': 'Likelihood score based on unpatched vulnerabilities',
        'weak_credentials_likelihood': 'Likelihood score based on weak or compromised credentials',
        'zero_day_likelihood': 'Likelihood score based on zero-day vulnerabilities',
        'weak_encryption_likelihood': 'Likelihood score based on weak encryption implementations',
        'trust_relationship_likelihood': 'Likelihood score based on trust relationship vulnerabilities',
        'misconfiguration_likelihood': 'Likelihood score based on security misconfigurations',
        'compromised_credentials_likelihood': 'Likelihood score based on compromised credentials',
        'phishing_likelihood': 'Likelihood score based on phishing attack vectors',
        'malicious_insider_likelihood': 'Likelihood score based on malicious insider threats',
        'credential_vulnerability_likelihood': 'Likelihood score based on credential vulnerabilities',
        'bastion_impact': 'Impact score specific to bastion host configurations',
        'propagation_impact': 'Impact score based on lateral movement potential',
        'category_impact': 'Impact score based on asset category classification',
        
        # Active/Inherent likelihood variants
        'likelihood_active': 'Current active likelihood score considering all factors',
        'likelihood_inherent': 'Inherent likelihood score without security controls',
        
        # System Information
        'secure_boot_status': 'Status of secure boot configuration on the system',
        'power_shell_exec_policy': 'PowerShell execution policy setting',
        'smb1': 'SMB version 1 protocol status',
        'smb2': 'SMB version 2 protocol status', 
        'smb3': 'SMB version 3 protocol status',
        'smbios_version': 'SMBIOS version information',
        'bios_version': 'BIOS version installed on the system',
        'bios_vendor': 'BIOS vendor information',
        'bios_release_date': 'Date when the BIOS was released',
        'board_manufacturer': 'Motherboard manufacturer information',
        'is_reboot_pending': 'Indicates if a system reboot is pending',
        'is_cloud_asset': 'Indicates if this is a cloud-based asset',
        'is_bastion_device': 'Indicates if this is a bastion host device',
        'is_manual_canonical_label': 'Indicates if the canonical label was manually assigned',
        'is_retired': 'Indicates if the asset has been retired',
        'is_stale': 'Indicates if the asset data is stale or outdated',
        
        # Location and Organization
        'location_id': 'Unique identifier for the physical location',
        'final_name': 'Final canonical name assigned to the asset',
        'device_zone': 'Network zone or segment where the device is located',
        'asset_tags': 'Comma-separated list of asset tags for categorization',
        'discoverable_tags': 'Tags that can be discovered automatically',
        'roles': 'Comma-separated list of roles assigned to the asset',
        'search_tags': 'Tags used for searching and filtering assets',
        
        # Timestamps
        'os_release_install_date': 'Date when the operating system was installed',
        'events_timestamp': 'Timestamp of the last security event',
        'raw_created_at': 'Timestamp when the raw data was first created',
        'store_created_at': 'Timestamp when the record was created in the store',
        'store_updated_at': 'Timestamp when the record was last updated in the store',
        'last_processed': 'Timestamp when the asset was last processed',
        'inserted_at': 'Timestamp when the record was inserted into the database',
        'process_id': 'Unique identifier for the data processing job',
    }
    
    # Return specific description if available, otherwise generate one
    if column_name in descriptions:
        return descriptions[column_name]
    
    # Generate description based on patterns
    if 'likelihood' in column_name.lower():
        return f'Likelihood score for {column_name.replace("_likelihood", "").replace("_", " ")}'
    elif 'impact' in column_name.lower():
        return f'Impact score for {column_name.replace("_impact", "").replace("_", " ")}'
    elif 'active' in column_name.lower():
        return f'Active status for {column_name.replace("_active", "").replace("_", " ")}'
    elif 'inherent' in column_name.lower():
        return f'Inherent value for {column_name.replace("_inherent", "").replace("_", " ")}'
    elif column_name.startswith('is_'):
        return f'Boolean flag indicating {column_name.replace("is_", "").replace("_", " ")}'
    elif column_name.endswith('_id'):
        return f'Unique identifier for {column_name.replace("_id", "").replace("_", " ")}'
    elif column_name.endswith('_date') or column_name.endswith('_time'):
        return f'Timestamp for {column_name.replace("_date", "").replace("_time", "").replace("_", " ")}'
    else:
        return f'Information about {column_name.replace("_", " ")}'

def update_mdl_schema(mdl_path, csv_path, output_path):
    """Update MDL schema with missing columns."""
    
    # Load existing MDL schema
    with open(mdl_path, 'r') as f:
        mdl_data = json.load(f)
    
    # Get column lists
    csv_columns = get_csv_columns(csv_path)
    existing_columns = get_mdl_columns(mdl_path)
    
    # Find missing columns
    missing_columns = [col for col in csv_columns if col not in existing_columns]
    
    print(f"Found {len(missing_columns)} missing columns:")
    for col in missing_columns:
        print(f"  - {col}")
    
    # Get the model
    model = mdl_data['models'][0]
    existing_columns_set = set(existing_columns)
    
    # Add missing columns
    for col_name in missing_columns:
        if col_name not in existing_columns_set:
            col_type, description = infer_column_type_and_description(col_name)
            
            new_column = {
                "name": col_name,
                "type": col_type,
                "properties": {
                    "displayName": col_name.replace('_', ' ').title(),
                    "description": description
                }
            }
            
            # Add notNull property for certain column types
            if col_name in ['nuid', 'dev_id'] or col_name.endswith('_id'):
                new_column["notNull"] = True
            
            model['columns'].append(new_column)
            print(f"Added column: {col_name} ({col_type})")
    
    # Save updated schema
    with open(output_path, 'w') as f:
        json.dump(mdl_data, f, indent=2)
    
    print(f"\nUpdated MDL schema saved to: {output_path}")
    print(f"Total columns: {len(model['columns'])}")

def main():
    """Main function."""
    mdl_path = "data/sql_meta/cve_data/mdl_assets.json"
    csv_path = "data/cvedata/data/assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv"
    output_path = "data/sql_meta/cve_data/mdl_assets_updated.json"
    
    print("Updating MDL Assets Schema...")
    print("=" * 50)
    
    update_mdl_schema(mdl_path, csv_path, output_path)
    
    print("\nSchema update complete!")
    print(f"Original schema: {mdl_path}")
    print(f"Updated schema: {output_path}")

if __name__ == "__main__":
    main()
