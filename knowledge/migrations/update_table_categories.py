#!/usr/bin/env python3
"""
Script to update table definitions and descriptions with category group information.
Based on actual categories: access requests, application data, assets, projects, 
vulnerabilities, integrations, configuration, audit logs, risk management, deployment
"""

import json
import ast
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define category mappings based on table name patterns
# IMPORTANT: Only tables matching these 15 categories will be categorized.
# Tables that don't match will remain uncategorized.
# See: @FINAL_CATEGORIES.md (9-23) for the complete list
# Order matters - more specific patterns should come first
CATEGORY_PATTERNS = [
    # Groups - check early to catch all Group* tables
    ("groups", [
        r"^Group",  # Group, GroupAttributes, GroupMembership, GroupPolicy, etc.
    ]),
    # Organizations - check before OrgMembership to catch Org* first
    ("organizations", [
        r"^Org$",  # Org (exact match)
        r"^Org[A-Z]",  # OrgAttributes, OrgInvitation, etc.
        r"^Organization",  # Organization-related tables
    ]),
    # Memberships and roles - check after Org to avoid matching Org* as membership
    ("memberships and roles", [
        r".*Membership",  # OrgMembership, GroupMembership, TenantMembership, etc.
        r".*Role",  # OrgRole, TenantRole, Role-related tables
        r"^Member",  # Member-related tables
    ]),
    # Issues - check before Risk to avoid matching Issues* as risk
    ("issues", [
        r"^Issue",  # Issue, IssueAttributes, Issues, IssuesCount, etc.
    ]),
    # Artifacts
    ("artifacts", [
        r".*Artifact",  # ArtifactoryAttributes, GoogleArtifactCrAttributes, etc.
    ]),
    # Risk management - check before App to catch AppRiskAttributes
    ("risk management", [
        r".*Risk[A-Z]",  # AppRiskAttributes, Risk, RiskFactor, etc.
        r".*RiskFactor",  # DeployedRiskFactor, etc.
    ]),
    # Assets - check before Project to catch AssetProjectAttributes as asset
    ("assets", [
        r"^Asset[A-Z]",  # AssetAttributes, AssetClass, etc.
    ]),
    # Projects
    ("projects", [
        r"^Project[A-Z]",  # ProjectAttributes, ProjectMeta, etc.
        r".*Project[A-Z]",  # AssetProjectAttributes, etc.
    ]),
    # Integrations
    ("integrations", [
        r".*Integration[A-Z]",  # AppliedIntegrationRelationship, IntegrationResource, etc.
        r".*BrokerConnection",  # BrokerConnectionIntegrationWithContextResource, etc.
    ]),
    # Access requests
    ("access requests", [
        r"^AccessRequest",  # AccessRequest, AccessRequestAttributes
    ]),
    # Vulnerabilities
    ("vulnerabilities", [
        r"^Vulnerability",  # Vulnerability-related tables
        r".*Finding",  # Finding-related tables
    ]),
    # Application data - check after Risk to avoid matching AppRiskAttributes
    ("application data", [
        r"^App[A-Z]",  # AppInstallWithClient, etc.
    ]),
    # Configuration
    ("configuration", [
        r"^Config",  # Config-related tables
        r".*Settings",  # ProjectSettings, etc.
    ]),
    # Audit logs
    ("audit logs", [
        r"^Audit",  # Audit-related tables
        r".*Log",  # Log-related tables
    ]),
    # Deployment
    ("deployment", [
        r"^Deploy",  # Deploy-related tables
        r".*Deploy",  # DeployedRiskFactor, etc.
    ]),
]

# Valid categories from FINAL_CATEGORIES.md (9-23)
VALID_CATEGORIES = {
    "access requests",
    "application data",
    "assets",
    "projects",
    "vulnerabilities",
    "integrations",
    "configuration",
    "audit logs",
    "risk management",
    "deployment",
    "groups",
    "organizations",
    "memberships and roles",
    "issues",
    "artifacts",
}

def get_category_group(table_name):
    """
    Determine the category group for a table based on its name.
    
    Only returns categories from the 15 valid categories defined in FINAL_CATEGORIES.md.
    If a table doesn't match any pattern, returns None (uncategorized).
    
    Args:
        table_name: Name of the table
        
    Returns:
        Category name if matched, None if uncategorized
    """
    for category, patterns in CATEGORY_PATTERNS:
        # Validate that category is in the allowed list
        if category not in VALID_CATEGORIES:
            logger.warning(f"Category '{category}' not in VALID_CATEGORIES list, skipping")
            continue
            
        for pattern in patterns:
            if re.match(pattern, table_name, re.IGNORECASE):
                return category
    return None

def update_page_content_description(page_content_str, category_group):
    """Update the description in page_content string with category group info."""
    if not category_group:
        return page_content_str
    
    category_desc = f" This is a {category_group}-related table."
    
    # Check if already added
    if category_desc in page_content_str:
        return page_content_str
    
    try:
        # Parse the string representation of dict
        content_dict = ast.literal_eval(page_content_str)
        
        # Get current description
        current_desc = content_dict.get('description', '')
        
        # Add category group description
        content_dict['description'] = current_desc + category_desc
        
        # Convert back to string representation (matching original format)
        # Use single quotes and proper formatting
        result = str(content_dict)
        # Replace double quotes with single quotes to match original format
        result = result.replace('"', "'")
        return result
    except Exception as e:
        # If parsing fails, try regex replacement
        # Match the description field in the string
        desc_pattern = r"('description':\s*)'([^']*)'"
        match = re.search(desc_pattern, page_content_str)
        if match:
            prefix = match.group(1)
            old_desc = match.group(2)
            new_desc = old_desc + category_desc
            # Replace the description
            page_content_str = re.sub(
                desc_pattern,
                f"{prefix}'{new_desc}'",
                page_content_str,
                count=1
            )
        return page_content_str

def process_file(file_path, output_path, category_tracker=None):
    """Process a JSON file and update descriptions with category groups."""
    print(f"Processing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    updated_count = 0
    
    for doc in data.get('documents', []):
        # Get table name from metadata
        table_name = None
        if 'metadata' in doc:
            table_name = doc['metadata'].get('table_name') or doc['metadata'].get('name')
        
        if not table_name:
            continue
        
        # Determine category group
        category_group = get_category_group(table_name)
        
        # Track categories
        if category_tracker is not None:
            if category_group:
                if category_group not in category_tracker:
                    category_tracker[category_group] = []
                category_tracker[category_group].append(table_name)
            else:
                if 'uncategorized' not in category_tracker:
                    category_tracker['uncategorized'] = []
                category_tracker['uncategorized'].append(table_name)
        
        # Only update tables that match one of the 15 valid categories
        # Tables that don't match remain uncategorized (no description added)
        if category_group:
            # Validate category is in allowed list
            if category_group not in VALID_CATEGORIES:
                logger.warning(f"Skipping {table_name}: category '{category_group}' not in valid categories")
                continue
                
            # Update page_content
            if 'page_content' in doc:
                old_content = doc['page_content']
                new_content = update_page_content_description(old_content, category_group)
                if old_content != new_content:
                    doc['page_content'] = new_content
                    updated_count += 1
                    logger.info(f"Updated page_content for {table_name} with category: {category_group}")
            
            # Update metadata description if it exists
            if 'metadata' in doc and 'description' in doc['metadata']:
                current_desc = doc['metadata']['description']
                category_desc = f" This is a {category_group}-related table."
                if category_desc not in current_desc:
                    doc['metadata']['description'] = current_desc + category_desc
                    updated_count += 1
                    logger.info(f"Updated metadata.description for {table_name} with category: {category_group}")
        # Note: Tables without a category_group remain uncategorized (no updates made)
    
    # Write updated data
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Updated {updated_count} entries in {output_path}")
    return updated_count

def generate_category_report(category_tracker, output_file):
    """Generate a report of categories and their tables."""
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("CATEGORY GROUP SUMMARY REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Sort categories by name, but put uncategorized last
    sorted_categories = sorted([c for c in category_tracker.keys() if c != 'uncategorized'])
    if 'uncategorized' in category_tracker:
        sorted_categories.append('uncategorized')
    
    total_tables = sum(len(tables) for tables in category_tracker.values())
    
    report_lines.append(f"Total Categories: {len(sorted_categories)}")
    report_lines.append(f"Total Tables: {total_tables}")
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    for category in sorted_categories:
        tables = category_tracker[category]
        report_lines.append(f"Category: {category.upper()}")
        report_lines.append(f"  Count: {len(tables)}")
        report_lines.append(f"  Tables:")
        for table in sorted(tables):
            report_lines.append(f"    - {table}")
        report_lines.append("")
    
    report_content = "\n".join(report_lines)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"\nCategory report saved to: {output_file}")
    return report_content

def main():
    base_dir = Path("/Users/sameermangalampalli/flowharmonicai/knowledge/indexing_preview")
    
    # Process table_definitions file
    definitions_file = base_dir / "table_definitions" / "table_definitions_20260123_180157_Snyk.json"
    definitions_output = base_dir / "table_definitions" / "table_definitions_20260123_180157_Snyk.json"
    
    # Process table_descriptions file
    descriptions_file = base_dir / "table_descriptions" / "table_descriptions_20260123_180157_Snyk.json"
    descriptions_output = base_dir / "table_descriptions" / "table_descriptions_20260123_180157_Snyk.json"
    
    # Track categories across both files
    category_tracker = {}
    
    total_updated = 0
    
    if definitions_file.exists():
        total_updated += process_file(definitions_file, definitions_output, category_tracker)
    else:
        print(f"File not found: {definitions_file}")
    
    if descriptions_file.exists():
        total_updated += process_file(descriptions_file, descriptions_output, category_tracker)
    else:
        print(f"File not found: {descriptions_file}")
    
    print(f"\nTotal entries updated: {total_updated}")
    
    # Generate category report
    report_file = base_dir.parent / "category_report.txt"
    generate_category_report(category_tracker, report_file)
    
    # Print summary
    print("\n" + "=" * 80)
    print("CATEGORY SUMMARY")
    print("=" * 80)
    sorted_categories = sorted([c for c in category_tracker.keys() if c != 'uncategorized'])
    if 'uncategorized' in category_tracker:
        sorted_categories.append('uncategorized')
    
    for category in sorted_categories:
        count = len(category_tracker[category])
        print(f"  {category:20s}: {count:3d} tables")

if __name__ == "__main__":
    main()
