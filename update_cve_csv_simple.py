#!/usr/bin/env python3
"""
Simple script to update CVE CSV file with all schema columns and dummy values
"""

import csv
import json
import random
from datetime import datetime, timedelta

def load_schema_columns():
    """Load column definitions from the schema file"""
    with open('/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta/cve_data/mdl_cve.json', 'r') as f:
        schema = json.load(f)
    
    columns = []
    for model in schema['models']:
        if model['name'] == 'dev_cve':
            for column in model['columns']:
                columns.append({
                    'name': column['name'],
                    'type': column['type'],
                    'notNull': column.get('notNull', False),
                    'isCalculated': column.get('isCalculated', False)
                })
    return columns

def generate_dummy_value(column_info, row_index):
    """Generate appropriate dummy values based on column type and constraints"""
    col_name = column_info['name']
    col_type = column_info['type']
    is_not_null = column_info['notNull']
    is_calculated = column_info['isCalculated']
    
    # Skip calculated columns as they are computed
    if is_calculated:
        return None
    
    # Handle specific columns with meaningful dummy data
    if col_name == 'nuid':
        return random.randint(1, 100)
    elif col_name == 'cve_partition_id':
        years = ['CVE-2017', 'CVE-2018', 'CVE-2019', 'CVE-2020', 'CVE-2021', 'CVE-2022', 'CVE-2023', 'CVE-2024', 'CVE-2025']
        return random.choice(years)
    elif col_name == 'cve_id':
        # This will be replaced with actual CVE ID from original data
        return f"CVE-{random.randint(2017, 2025)}-{random.randint(1000, 9999)}"
    elif col_name in ['mod_date', 'pub_date', 'published_date', 'last_modified_date', 'computed_at', 'processed_date']:
        # Generate random dates within reasonable range
        start_date = datetime(2017, 1, 1)
        end_date = datetime.now()
        random_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
        return random_date.strftime('%Y-%m-%d %H:%M:%S')
    elif col_name in ['cvss', 'cvssv2_base_score', 'cvssv3_base_score', 'balbix_score', 'balbix_mitigated_score']:
        return round(random.uniform(0.0, 10.0), 2)
    elif col_name in ['cwe_code']:
        return random.randint(1, 1000)
    elif col_name in ['asset_count', 'rank']:
        return random.randint(0, 1000)
    elif col_name in ['published_year']:
        return random.randint(2017, 2025)
    elif col_name in ['cwe_name']:
        cwe_names = [
            "Cross-Site Request Forgery (CSRF)",
            "Incorrect Permission Assignment for Critical Resource",
            "Authorization Bypass Through User-Controlled Key",
            "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')",
            "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
            "Information Exposure",
            "Improper Input Validation",
            "Cleartext Transmission of Sensitive Information"
        ]
        return random.choice(cwe_names)
    elif col_name in ['access_authentication']:
        return random.choice(['NONE', 'SINGLE', 'MULTIPLE'])
    elif col_name in ['access_complexity']:
        return random.choice(['LOW', 'MEDIUM', 'HIGH'])
    elif col_name in ['access_vector']:
        return random.choice(['LOCAL', 'ADJACENT', 'NETWORK'])
    elif col_name in ['impact_availability', 'impact_confidentiality', 'impact_integrity']:
        return random.choice(['NONE', 'PARTIAL', 'COMPLETE'])
    elif col_name in ['cvssv2_base_severity', 'cvssv3_base_severity', 'severity_level', 'threat_level']:
        return random.choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
    elif col_name in ['remediation_urgency']:
        return random.choice(['Low', 'Medium', 'High', 'Urgent'])
    elif col_name in ['vulnerability_age_category']:
        return random.choice(['New (30 days)', 'Recent (90 days)', 'Mature (1 year)', 'Old (>1 year)'])
    elif col_name in ['assigner']:
        return random.choice(['MITRE', 'Cisco', 'Microsoft', 'Oracle', 'Red Hat', ''])
    elif col_name in ['summary', 'description']:
        return f"Security vulnerability in {random.choice(['web application', 'database', 'operating system', 'network service'])}"
    elif col_name in ['references']:
        return '[]'  # Empty JSON array
    elif col_name in ['cvssv2_vector_string', 'cvssv3_vector_string']:
        return f"AV:{random.choice(['L', 'A', 'N'])}/AC:{random.choice(['L', 'M', 'H'])}/Au:{random.choice(['N', 'S', 'M'])}/C:{random.choice(['N', 'P', 'C'])}/I:{random.choice(['N', 'P', 'C'])}/A:{random.choice(['N', 'P', 'C'])}"
    elif col_name in ['doc_id']:
        return f"doc_{random.randint(100000, 999999)}"
    elif col_name in ['is_critical_severity', 'is_high_risk', 'has_exploit_available']:
        return random.choice([True, False])
    elif col_type == 'DECIMAL':
        return round(random.uniform(0.0, 100.0), 2)
    elif col_type == 'INTEGER':
        return random.randint(0, 1000)
    elif col_type == 'BOOLEAN':
        return random.choice([True, False])
    elif col_type == 'VARCHAR':
        return f"dummy_{col_name}_{row_index}"
    elif col_type == 'TEXT':
        return f"Dummy text for {col_name}"
    elif col_type == 'TIMESTAMP':
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elif col_type == 'DATE':
        return datetime.now().strftime('%Y-%m-%d')
    else:
        return f"dummy_{col_name}"

def update_cve_csv():
    """Update the CVE CSV file with all schema columns and dummy values"""
    
    # Load the original CSV
    print("Loading original CSV...")
    with open('/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/cvedata/data/cve.csv', 'r') as f:
        reader = csv.reader(f)
        original_rows = list(reader)
    
    # Load schema columns
    print("Loading schema columns...")
    schema_columns = load_schema_columns()
    
    # Create column mapping from original CSV to schema
    original_headers = original_rows[0]
    column_mapping = {
        0: 'cve_id',  # First unnamed column is CVE ID
        1: 'mod_date',
        2: 'pub_date', 
        3: 'cvss',
        4: 'cwe_code',
        5: 'cwe_name',
        6: 'summary',
        7: 'access_authentication',
        8: 'access_complexity',
        9: 'access_vector',
        10: 'impact_availability',
        11: 'impact_confidentiality',
        12: 'impact_integrity'
    }
    
    # Create new headers with all schema columns
    print("Creating new headers...")
    new_headers = []
    for column_info in schema_columns:
        if not column_info['isCalculated']:
            new_headers.append(column_info['name'])
    
    # Create new rows
    print("Creating new rows with dummy data...")
    new_rows = [new_headers]
    
    # Process each original row
    for row_idx, original_row in enumerate(original_rows[1:], 1):  # Skip header
        if row_idx % 1000 == 0:
            print(f"Processing row {row_idx}...")
        
        new_row = []
        
        # Create a mapping of column names to values for this row
        row_data = {}
        
        # Map original data
        for col_idx, value in enumerate(original_row):
            if col_idx in column_mapping:
                schema_col = column_mapping[col_idx]
                row_data[schema_col] = value
        
        # Generate dummy values for all schema columns
        for column_info in schema_columns:
            if not column_info['isCalculated']:
                col_name = column_info['name']
                if col_name in row_data:
                    new_row.append(row_data[col_name])
                else:
                    dummy_value = generate_dummy_value(column_info, row_idx)
                    new_row.append(dummy_value)
        
        new_rows.append(new_row)
    
    # Save the updated CSV
    output_file = '/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/cvedata/data/cve_updated.csv'
    print(f"Saving updated CSV to {output_file}...")
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)
    
    print(f"Updated CSV saved with {len(new_headers)} columns and {len(new_rows)-1} rows")
    print("Column names:", new_headers)
    
    return new_rows

if __name__ == "__main__":
    updated_rows = update_cve_csv()
    print("CSV update completed successfully!")
