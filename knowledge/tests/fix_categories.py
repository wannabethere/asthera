"""
Fix categories in MDL JSON files

This script:
1. Maps current low-level tags to proper semantic categories
2. Adds categories to table_descriptions and column_definitions
3. Updates categories in table_definitions based on table names and descriptions
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Set

# Semantic category mapping based on table name patterns
CATEGORY_MAPPING = {
    # Access requests
    "access requests": [
        r"AccessRequest.*",
        r".*Access.*Request.*",
    ],
    
    # Assets
    "assets": [
        r"Asset.*",
        r".*Asset.*",
    ],
    
    # Projects
    "projects": [
        r"Project.*",
        r".*Project.*",
    ],
    
    # Vulnerabilities
    "vulnerabilities": [
        r"Vulnerability.*",
        r".*Vulnerabilit.*",
        r"Finding.*",
        r".*Issue.*",
        r".*Vuln.*",
    ],
    
    # Integrations
    "integrations": [
        r"Integration.*",
        r".*Integration.*",
        r"Broker.*",
        r".*Connector.*",
    ],
    
    # Configuration
    "configuration": [
        r"Config.*",
        r".*Configuration.*",
        r"Setting.*",
        r".*Settings.*",
    ],
    
    # Audit logs
    "audit logs": [
        r"Audit.*",
        r".*Audit.*",
        r".*Log.*",
        r"CatalogProgress.*",
    ],
    
    # Risk management
    "risk management": [
        r"Risk.*",
        r".*Risk.*",
    ],
    
    # Deployment
    "deployment": [
        r"Deploy.*",
        r".*Deployment.*",
        r".*Pipeline.*",
    ],
    
    # Groups
    "groups": [
        r"Group.*",
        r".*Group.*",
        r"Policy.*",
        r".*Policies.*",
    ],
    
    # Organizations
    "organizations": [
        r"Org.*",
        r".*Organization.*",
    ],
    
    # Memberships and roles
    "memberships and roles": [
        r"Membership.*",
        r".*Member.*",
        r"Role.*",
        r".*Permission.*",
    ],
    
    # Issues
    "issues": [
        r"Issue.*",
        r".*Issue.*",
    ],
    
    # Artifacts
    "artifacts": [
        r"Artifact.*",
        r".*Artifact.*",
    ],
    
    # Application data
    "application data": [
        r"App.*",
        r".*Application.*",
        r"Resource.*",
    ],
    
    # User management
    "user management": [
        r"User.*",
        r".*User.*",
    ],
    
    # Security
    "security": [
        r"Security.*",
        r".*Security.*",
        r"Auth.*",
        r".*Authentication.*",
    ],
}


def determine_categories(table_name: str, description: str = "") -> List[str]:
    """Determine semantic categories for a table based on name and description"""
    categories = set()
    
    # Check table name against patterns
    for category, patterns in CATEGORY_MAPPING.items():
        for pattern in patterns:
            if re.match(pattern, table_name, re.IGNORECASE):
                categories.add(category)
                break
    
    # Check description for additional hints if no categories found
    if not categories and description:
        description_lower = description.lower()
        for category in CATEGORY_MAPPING.keys():
            # Simple keyword matching in description
            category_keywords = category.replace(" and ", " ").split()
            if any(keyword in description_lower for keyword in category_keywords):
                categories.add(category)
    
    # If still no categories, assign "application data" as default
    if not categories:
        categories.add("application data")
    
    return sorted(list(categories))


def fix_table_definitions(input_file: Path, output_file: Path):
    """Fix categories in table_definitions JSON"""
    print(f"\n{'='*80}")
    print(f"Processing: {input_file.name}")
    print(f"{'='*80}")
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    fixed_count = 0
    total_count = len(data.get('documents', []))
    
    for doc in data.get('documents', []):
        metadata = doc.get('metadata', {})
        table_name = metadata.get('table_name', '')
        description = metadata.get('description', '')
        
        # Determine new categories
        new_categories = determine_categories(table_name, description)
        
        # Update categories
        old_categories = metadata.get('categories', [])
        metadata['categories'] = new_categories
        
        if old_categories != new_categories:
            fixed_count += 1
            print(f"  {table_name}: {old_categories} -> {new_categories}")
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nFixed {fixed_count}/{total_count} tables")
    print(f"Output: {output_file}")


def add_categories_to_table_descriptions(input_file: Path, output_file: Path):
    """Add categories to table_descriptions JSON"""
    print(f"\n{'='*80}")
    print(f"Processing: {input_file.name}")
    print(f"{'='*80}")
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    added_count = 0
    total_count = len(data.get('documents', []))
    
    for doc in data.get('documents', []):
        metadata = doc.get('metadata', {})
        table_name = metadata.get('name', '')
        description = metadata.get('description', '')
        
        # Determine categories
        categories = determine_categories(table_name, description)
        
        # Add categories to metadata
        metadata['categories'] = categories
        added_count += 1
        
        print(f"  {table_name}: {categories}")
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nAdded categories to {added_count}/{total_count} tables")
    print(f"Output: {output_file}")


def add_categories_to_column_definitions(input_file: Path, output_file: Path, table_categories_map: Dict[str, List[str]]):
    """Add categories to column_definitions JSON using table categories map"""
    print(f"\n{'='*80}")
    print(f"Processing: {input_file.name}")
    print(f"{'='*80}")
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    added_count = 0
    total_count = len(data.get('documents', []))
    
    for doc in data.get('documents', []):
        metadata = doc.get('metadata', {})
        table_name = metadata.get('table_name', '')
        
        # Get categories from table map (or determine from table name)
        categories = table_categories_map.get(table_name, determine_categories(table_name, ""))
        
        # Add categories to metadata
        metadata['categories'] = categories
        added_count += 1
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nAdded categories to {added_count}/{total_count} columns")
    print(f"Output: {output_file}")


def build_table_categories_map(table_definitions_file: Path) -> Dict[str, List[str]]:
    """Build a map of table_name -> categories from table_definitions"""
    with open(table_definitions_file, 'r') as f:
        data = json.load(f)
    
    table_map = {}
    for doc in data.get('documents', []):
        metadata = doc.get('metadata', {})
        table_name = metadata.get('table_name', '')
        categories = metadata.get('categories', [])
        if table_name:
            table_map[table_name] = categories
    
    return table_map


def main():
    """Main function to fix all JSON files"""
    base_dir = Path("/Users/sameermangalampalli/flowharmonicai/knowledge/indexing_preview")
    
    # Files to process
    files = {
        "table_definitions": base_dir / "table_definitions" / "table_definitions_20260123_180157_Snyk.json",
        "table_descriptions": base_dir / "table_descriptions" / "table_descriptions_20260123_180157_Snyk.json",
        "column_definitions": base_dir / "column_definitions" / "column_definitions_20260123_180157_Snyk.json",
    }
    
    # Output files (with _fixed suffix)
    output_files = {
        "table_definitions": base_dir / "table_definitions" / "table_definitions_20260123_180157_Snyk_fixed.json",
        "table_descriptions": base_dir / "table_descriptions" / "table_descriptions_20260123_180157_Snyk_fixed.json",
        "column_definitions": base_dir / "column_definitions" / "column_definitions_20260123_180157_Snyk_fixed.json",
    }
    
    print("="*80)
    print("MDL Categories Fix Script")
    print("="*80)
    print("\nThis script will:")
    print("1. Fix categories in table_definitions (map low-level tags to semantic categories)")
    print("2. Add categories to table_descriptions")
    print("3. Add categories to column_definitions")
    print("\nSemantic categories being used:")
    for category in sorted(CATEGORY_MAPPING.keys()):
        print(f"  - {category}")
    
    # Step 1: Fix table_definitions
    fix_table_definitions(files['table_definitions'], output_files['table_definitions'])
    
    # Step 2: Build table categories map from fixed table_definitions
    table_categories_map = build_table_categories_map(output_files['table_definitions'])
    
    # Step 3: Add categories to table_descriptions
    add_categories_to_table_descriptions(files['table_descriptions'], output_files['table_descriptions'])
    
    # Step 4: Add categories to column_definitions (using table map)
    add_categories_to_column_definitions(files['column_definitions'], output_files['column_definitions'], table_categories_map)
    
    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print("\nFixed files created:")
    for name, path in output_files.items():
        print(f"  - {path}")
    print("\nNext steps:")
    print("1. Review the fixed files to ensure categories are correct")
    print("2. Replace original files with fixed versions (or rename)")
    print("3. Reindex the data using the fixed JSON files")
    print("4. Update agents to use category filters in retrieval queries")


if __name__ == "__main__":
    main()
