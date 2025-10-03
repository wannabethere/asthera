#!/usr/bin/env python3
"""
Script to add 200 new CVEs from 2024 and 2025 and integrate them into:
- CVE CSV
- Vulnerability instances CSV
- Software instances CSV
- Vendor product CSV
"""

import json
import csv
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple

def generate_new_cves():
    """Generate 200 new CVEs from 2024 and 2025"""
    print("Generating 200 new CVEs from 2024 and 2025...")
    
    # CWE categories for realistic CVE descriptions
    cwe_categories = [
        (352, "Cross-Site Request Forgery (CSRF)"),
        (732, "Incorrect Permission Assignment for Critical Resource"),
        (639, "Authorization Bypass Through User-Controlled Key"),
        (79, "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')"),
        (89, "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')"),
        (200, "Information Exposure"),
        (20, "Improper Input Validation"),
        (319, "Cleartext Transmission of Sensitive Information"),
        (22, "Path Traversal"),
        (78, "OS Command Injection"),
        (94, "Code Injection"),
        (287, "Improper Authentication"),
        (362, "Concurrent Execution using Shared Resource with Improper Synchronization"),
        (416, "Use After Free"),
        (190, "Integer Overflow or Wraparound"),
        (476, "NULL Pointer Dereference"),
        (787, "Out-of-bounds Write"),
        (125, "Out-of-bounds Read"),
        (269, "Improper Privilege Management"),
        (399, "Resource Exhaustion")
    ]
    
    # Software products that can be affected
    affected_products = [
        "Windows 10", "Windows 11", "Office 365", "Visual Studio", "SQL Server",
        "Internet Information Services", "Adobe Acrobat Reader", "Adobe Photoshop",
        "Mozilla Firefox", "Google Chrome", "Java Runtime Environment",
        "Apache HTTP Server", "Nginx", "MySQL Server", "PostgreSQL",
        "Redis", "Docker Engine", "Kubernetes", "Git", "Node.js",
        "Python", "OpenJDK", "PHP", "Ruby", "Go", "VMware Tools",
        "vSphere Client", "VirtualBox", "Apache Tomcat", "IntelliJ IDEA"
    ]
    
    new_cves = []
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for i in range(200):
        # Generate CVE ID
        year = random.choice([2024, 2025])
        cve_id = f"CVE-{year}-{random.randint(1000, 9999)}"
        
        # Generate dates
        pub_date = random.choice([
            base_date_2024 + timedelta(days=random.randint(1, 365)),
            base_date_2025 + timedelta(days=random.randint(1, 365))
        ])
        mod_date = pub_date + timedelta(days=random.randint(1, 30))
        
        # Generate CVSS score
        cvss_score = round(random.uniform(0.1, 10.0), 1)
        
        # Select CWE
        cwe_code, cwe_name = random.choice(cwe_categories)
        
        # Generate summary
        product = random.choice(affected_products)
        summary = f"A {cwe_name.lower()} vulnerability in {product} allows attackers to {random.choice(['execute arbitrary code', 'obtain sensitive information', 'cause denial of service', 'bypass security restrictions', 'escalate privileges'])}."
        
        # Generate access vectors
        access_authentication = random.choice(["None", "Single", "Multiple"])
        access_complexity = random.choice(["Low", "Medium", "High"])
        access_vector = random.choice(["Local", "Adjacent Network", "Network"])
        
        # Generate impact
        impact_availability = random.choice(["None", "Partial", "Complete"])
        impact_confidentiality = random.choice(["None", "Partial", "Complete"])
        impact_integrity = random.choice(["None", "Partial", "Complete"])
        
        cve = {
            '': cve_id,
            'mod_date': mod_date.strftime('%Y-%m-%d %H:%M:%S'),
            'pub_date': pub_date.strftime('%Y-%m-%d %H:%M:%S'),
            'cvss': str(cvss_score),
            'cwe_code': str(cwe_code),
            'cwe_name': cwe_name,
            'summary': summary,
            'access_authentication': access_authentication,
            'access_complexity': access_complexity,
            'access_vector': access_vector,
            'impact_availability': impact_availability,
            'impact_confidentiality': impact_confidentiality,
            'impact_integrity': impact_integrity
        }
        new_cves.append(cve)
    
    return new_cves

def add_cves_to_csv(new_cves):
    """Add new CVEs to the CVE CSV file"""
    print("Adding new CVEs to CVE CSV...")
    
    # Read existing CVE data
    with open('data/cvedata/data/cve.csv', 'r') as f:
        reader = csv.DictReader(f)
        existing_cves = list(reader)
    
    # Add new CVEs
    all_cves = existing_cves + new_cves
    
    # Write updated CVE data
    with open('data/cvedata/data/cve.csv', 'w', newline='') as f:
        fieldnames = all_cves[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_cves)
    
    print(f"Added {len(new_cves)} new CVEs to CVE CSV")

def add_vendor_products(new_cves):
    """Add new vendor-product combinations to vendor_product.csv"""
    print("Adding new vendor-product combinations...")
    
    # Read existing vendor-product data
    with open('data/cvedata/data/vendor_product.csv', 'r') as f:
        reader = csv.DictReader(f)
        existing_products = list(reader)
    
    # Extract unique vendor-product combinations from new CVEs
    new_products = set()
    for cve in new_cves:
        summary = cve['summary']
        # Extract product names from summaries
        if 'Windows 10' in summary:
            new_products.add(('microsoft', 'windows_10'))
        if 'Windows 11' in summary:
            new_products.add(('microsoft', 'windows_11'))
        if 'Office 365' in summary:
            new_products.add(('microsoft', 'office_365'))
        if 'Visual Studio' in summary:
            new_products.add(('microsoft', 'visual_studio'))
        if 'SQL Server' in summary:
            new_products.add(('microsoft', 'sql_server'))
        if 'Internet Information Services' in summary:
            new_products.add(('microsoft', 'iis'))
        if 'Adobe Acrobat Reader' in summary:
            new_products.add(('adobe', 'acrobat_reader'))
        if 'Adobe Photoshop' in summary:
            new_products.add(('adobe', 'photoshop'))
        if 'Mozilla Firefox' in summary:
            new_products.add(('mozilla', 'firefox'))
        if 'Google Chrome' in summary:
            new_products.add(('google', 'chrome'))
        if 'Java Runtime Environment' in summary:
            new_products.add(('oracle', 'java_runtime'))
        if 'Apache HTTP Server' in summary:
            new_products.add(('apache', 'http_server'))
        if 'Nginx' in summary:
            new_products.add(('nginx', 'nginx'))
        if 'MySQL Server' in summary:
            new_products.add(('mysql', 'mysql_server'))
        if 'PostgreSQL' in summary:
            new_products.add(('postgresql', 'postgresql'))
        if 'Redis' in summary:
            new_products.add(('redis', 'redis'))
        if 'Docker Engine' in summary:
            new_products.add(('docker', 'docker_engine'))
        if 'Kubernetes' in summary:
            new_products.add(('kubernetes', 'kubectl'))
        if 'Git' in summary:
            new_products.add(('git', 'git'))
        if 'Node.js' in summary:
            new_products.add(('nodejs', 'node'))
        if 'Python' in summary:
            new_products.add(('python', 'python'))
        if 'OpenJDK' in summary:
            new_products.add(('java', 'openjdk'))
        if 'PHP' in summary:
            new_products.add(('php', 'php'))
        if 'Ruby' in summary:
            new_products.add(('ruby', 'ruby'))
        if 'Go' in summary:
            new_products.add(('golang', 'go'))
        if 'VMware Tools' in summary:
            new_products.add(('vmware', 'vmware_tools'))
        if 'vSphere Client' in summary:
            new_products.add(('vmware', 'vsphere'))
        if 'VirtualBox' in summary:
            new_products.add(('oracle', 'virtualbox'))
        if 'Apache Tomcat' in summary:
            new_products.add(('apache', 'tomcat'))
        if 'IntelliJ IDEA' in summary:
            new_products.add(('jetbrains', 'intellij'))
    
    # Add new products to existing data
    max_index = max(int(row['']) for row in existing_products if row[''].isdigit())
    new_product_rows = []
    
    for i, (vendor, product) in enumerate(new_products):
        new_product_rows.append({
            '': str(max_index + i + 1),
            'vendor': vendor,
            'product': product
        })
    
    all_products = existing_products + new_product_rows
    
    # Write updated vendor-product data
    with open('data/cvedata/data/vendor_product.csv', 'w', newline='') as f:
        fieldnames = all_products[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_products)
    
    print(f"Added {len(new_product_rows)} new vendor-product combinations")

def add_cves_to_vulnerability_instances(new_cves):
    """Add new CVEs to vulnerability instances CSV"""
    print("Adding new CVEs to vulnerability instances...")
    
    # Read existing vulnerability instances data
    with open('data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        vuln_data = list(reader)
    
    # Load asset key mapping to get available devices
    with open('data/asset_key_mapping.json', 'r') as f:
        mapping = json.load(f)
    
    asset_keys = mapping['asset_keys']
    
    # Add new vulnerability instances for new CVEs
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for cve in new_cves:
        # Create 5-15 vulnerability instances per CVE
        num_instances = random.randint(5, 15)
        
        for i in range(num_instances):
            # Select random asset
            asset = random.choice(asset_keys)
            
            # Generate dates
            detected_date = random.choice([
                base_date_2024 + timedelta(days=random.randint(1, 365)),
                base_date_2025 + timedelta(days=random.randint(1, 365))
            ])
            
            # Add random hours to the same day
            detected_time = detected_date + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
            published_time = detected_time - timedelta(hours=random.randint(1, 24))
            
            # Parse CVSS score from CVE
            cvss_score = float(cve['cvss'])
            severity = 'LOW' if cvss_score < 4.0 else 'MEDIUM' if cvss_score < 7.0 else 'HIGH' if cvss_score < 9.0 else 'CRITICAL'
            
            vuln_instance = {
                'cve_partition_id': f"CVE-{cve[''].split('-')[1]}",
                'nuid': str(asset['nuid']),
                'dev_id': str(asset['dev_id']),
                'instance_id': str(uuid.uuid4()),
                'sw_instance_id': str(uuid.uuid4()),
                'cve_id': cve[''],
                'cvssv2_basescore': str(cvss_score) if cvss_score < 10.0 else '',
                'cvssv3_basescore': str(cvss_score),
                'gtm_score': str(random.uniform(0, 100)),
                'fix_versions': '',
                'patches': '',
                'severity': severity,
                'threat_level': str(random.randint(1, 4)),
                'exposure': str(random.randint(0, 4)),
                'priority': str(random.randint(1, 4)),
                'tags': '',
                'state': random.choice(['ACTIVE', 'PATCHED', 'MITIGATED', 'FALSE_POSITIVE']),
                'published_time': published_time.isoformat(),
                'detected_time': detected_time.isoformat(),
                'remediation_time': '',
                'is_stale': 'False',
                'raw_created_at': detected_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'store_created_at': detected_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'store_updated_at': detected_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'process_id': str(uuid.uuid4())
            }
            vuln_data.append(vuln_instance)
    
    # Write updated vulnerability instances data
    with open('data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv', 'w', newline='') as f:
        fieldnames = vuln_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(vuln_data)
    
    print(f"Added vulnerability instances for {len(new_cves)} new CVEs")

def add_cves_to_software_instances(new_cves):
    """Add new CVEs to software instances CSV by creating vulnerable software"""
    print("Adding vulnerable software instances for new CVEs...")
    
    # Read existing software instances data
    with open('data/cvedata/data/software_instances-part-00000-c7546cd4-cc72-420f-b58f-8ec6db39af97-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        sw_data = list(reader)
    
    # Load asset key mapping to get available devices
    with open('data/asset_key_mapping.json', 'r') as f:
        mapping = json.load(f)
    
    asset_keys = mapping['asset_keys']
    
    # Create vulnerable software instances based on new CVEs
    base_date_2024 = datetime(2024, 1, 1)
    base_date_2025 = datetime(2025, 1, 1)
    
    for cve in new_cves:
        # Create 3-8 vulnerable software instances per CVE
        num_instances = random.randint(3, 8)
        
        for i in range(num_instances):
            # Select random asset
            asset = random.choice(asset_keys)
            
            # Extract vendor and product from CVE summary
            summary = cve['summary']
            vendor = 'unknown'
            product = 'unknown'
            product_key = 'unknown'
            
            if 'Windows 10' in summary:
                vendor, product, product_key = 'microsoft', 'Windows 10', 'windows_10'
            elif 'Windows 11' in summary:
                vendor, product, product_key = 'microsoft', 'Windows 11', 'windows_11'
            elif 'Office 365' in summary:
                vendor, product, product_key = 'microsoft', 'Microsoft Office 365', 'office_365'
            elif 'Visual Studio' in summary:
                vendor, product, product_key = 'microsoft', 'Visual Studio', 'visual_studio'
            elif 'SQL Server' in summary:
                vendor, product, product_key = 'microsoft', 'SQL Server', 'sql_server'
            elif 'Internet Information Services' in summary:
                vendor, product, product_key = 'microsoft', 'Internet Information Services', 'iis'
            elif 'Adobe Acrobat Reader' in summary:
                vendor, product, product_key = 'adobe', 'Adobe Acrobat Reader', 'acrobat_reader'
            elif 'Adobe Photoshop' in summary:
                vendor, product, product_key = 'adobe', 'Adobe Photoshop', 'photoshop'
            elif 'Mozilla Firefox' in summary:
                vendor, product, product_key = 'mozilla', 'Mozilla Firefox', 'firefox'
            elif 'Google Chrome' in summary:
                vendor, product, product_key = 'google', 'Google Chrome', 'chrome'
            elif 'Java Runtime Environment' in summary:
                vendor, product, product_key = 'oracle', 'Java Runtime Environment', 'java_runtime'
            elif 'Apache HTTP Server' in summary:
                vendor, product, product_key = 'apache', 'Apache HTTP Server', 'http_server'
            elif 'Nginx' in summary:
                vendor, product, product_key = 'nginx', 'Nginx', 'nginx'
            elif 'MySQL Server' in summary:
                vendor, product, product_key = 'mysql', 'MySQL Server', 'mysql_server'
            elif 'PostgreSQL' in summary:
                vendor, product, product_key = 'postgresql', 'PostgreSQL', 'postgresql'
            elif 'Redis' in summary:
                vendor, product, product_key = 'redis', 'Redis', 'redis'
            elif 'Docker Engine' in summary:
                vendor, product, product_key = 'docker', 'Docker Engine', 'docker_engine'
            elif 'Kubernetes' in summary:
                vendor, product, product_key = 'kubernetes', 'Kubernetes CLI', 'kubectl'
            elif 'Git' in summary:
                vendor, product, product_key = 'git', 'Git', 'git'
            elif 'Node.js' in summary:
                vendor, product, product_key = 'nodejs', 'Node.js', 'node'
            elif 'Python' in summary:
                vendor, product, product_key = 'python', 'Python', 'python'
            elif 'OpenJDK' in summary:
                vendor, product, product_key = 'java', 'OpenJDK', 'openjdk'
            elif 'PHP' in summary:
                vendor, product, product_key = 'php', 'PHP', 'php'
            elif 'Ruby' in summary:
                vendor, product, product_key = 'ruby', 'Ruby', 'ruby'
            elif 'Go' in summary:
                vendor, product, product_key = 'golang', 'Go', 'go'
            elif 'VMware Tools' in summary:
                vendor, product, product_key = 'vmware', 'VMware Tools', 'vmware_tools'
            elif 'vSphere Client' in summary:
                vendor, product, product_key = 'vmware', 'vSphere Client', 'vsphere'
            elif 'VirtualBox' in summary:
                vendor, product, product_key = 'oracle', 'VirtualBox', 'virtualbox'
            elif 'Apache Tomcat' in summary:
                vendor, product, product_key = 'apache', 'Apache Tomcat', 'tomcat'
            elif 'IntelliJ IDEA' in summary:
                vendor, product, product_key = 'jetbrains', 'IntelliJ IDEA', 'intellij'
            
            # Generate version
            version = f"{random.randint(1, 20)}.{random.randint(0, 99)}.{random.randint(0, 99)}"
            
            # Generate dates
            install_date = random.choice([
                base_date_2024 + timedelta(days=random.randint(1, 365)),
                base_date_2025 + timedelta(days=random.randint(1, 365))
            ])
            
            # Add random hours to the same day
            install_time = install_date + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            sw_instance = {
                'swkey_partition_id': random.choice(['APPLICATION', 'SYSTEM', 'DRIVER', 'PACKAGE']),
                'nuid': str(asset['nuid']),
                'dev_id': str(asset['dev_id']),
                'key': f"{vendor}_{product_key}_{version}_{asset['dev_id']}",
                'cpe': f"cpe:2.3:a:{vendor}:{product_key}:{version}:*:*:*:*:*:*:*",
                'source': random.choice(['HA', 'MANUAL', 'AUTO']),
                'category': random.choice(['APPLICATION', 'SYSTEM', 'DRIVER', 'PACKAGE']),
                'product': product,
                'vendor': vendor,
                'version': version,
                'install_path': f"/opt/{vendor}/{product_key}" if random.choice([True, False]) else f"C:\\Program Files\\{vendor}\\{product}",
                'latest_remediation_id': '',
                'latest_available_patch': '',
                'latest_installed_patch': '',
                'patch_class': '',
                'product_state': 'VULNERABLE',  # Mark as vulnerable since it's related to a CVE
                'install_time': install_time.isoformat(),
                'latest_remediation_release_time': '',
                'latest_installed_patch_release_time': '',
                'latest_patch_release_time': '',
                'latest_patch_install_time': '',
                'is_stale': 'False',
                'raw_created_at': install_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'store_created_at': install_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'store_updated_at': install_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'process_id': str(uuid.uuid4())
            }
            sw_data.append(sw_instance)
    
    # Write updated software instances data
    with open('data/cvedata/data/software_instances-part-00000-c7546cd4-cc72-420f-b58f-8ec6db39af97-c000.snappy.csv', 'w', newline='') as f:
        fieldnames = sw_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sw_data)
    
    print(f"Added vulnerable software instances for {len(new_cves)} new CVEs")

def verify_new_cves():
    """Verify that new CVEs were added correctly"""
    print("Verifying new CVEs...")
    
    # Check CVE CSV
    with open('data/cvedata/data/cve.csv', 'r') as f:
        reader = csv.DictReader(f)
        cve_data = list(reader)
    
    cve_2024_2025 = [cve for cve in cve_data if cve[''].startswith('CVE-2024') or cve[''].startswith('CVE-2025')]
    print(f"Total CVEs from 2024-2025: {len(cve_2024_2025)}")
    
    # Check vulnerability instances
    with open('data/cvedata/data/vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        vuln_data = list(reader)
    
    vuln_2024_2025 = [vuln for vuln in vuln_data if vuln['cve_id'].startswith('CVE-2024') or vuln['cve_id'].startswith('CVE-2025')]
    print(f"Vulnerability instances for 2024-2025 CVEs: {len(vuln_2024_2025)}")
    
    # Check software instances
    with open('data/cvedata/data/software_instances-part-00000-c7546cd4-cc72-420f-b58f-8ec6db39af97-c000.snappy.csv', 'r') as f:
        reader = csv.DictReader(f)
        sw_data = list(reader)
    
    vulnerable_sw = [sw for sw in sw_data if sw['product_state'] == 'VULNERABLE']
    print(f"Vulnerable software instances: {len(vulnerable_sw)}")
    
    # Show sample new CVEs
    print("\\nSample new CVEs:")
    for cve in cve_2024_2025[:5]:
        print(f"  {cve['']}: {cve['summary'][:80]}...")

def main():
    """Main function to add new CVEs and integrate them"""
    print("Adding 200 new CVEs from 2024 and 2025...")
    
    # Generate new CVEs
    new_cves = generate_new_cves()
    print(f"Generated {len(new_cves)} new CVEs")
    
    # Add to CVE CSV
    add_cves_to_csv(new_cves)
    
    # Add vendor-product combinations
    add_vendor_products(new_cves)
    
    # Add to vulnerability instances
    add_cves_to_vulnerability_instances(new_cves)
    
    # Add to software instances
    add_cves_to_software_instances(new_cves)
    
    # Verify results
    verify_new_cves()
    
    print("\\nNew CVEs integration completed!")
    print(f"Added {len(new_cves)} new CVEs from 2024 and 2025")
    print("Integrated into all relevant datasets")

if __name__ == "__main__":
    main()
