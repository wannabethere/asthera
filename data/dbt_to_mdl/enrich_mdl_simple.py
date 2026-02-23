#!/usr/bin/env python3
"""
Enrich MDL files with column descriptions - simple version without PyYAML dependency.
Uses basic string parsing to extract descriptions from YAML files.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional


def to_display_name(name: str) -> str:
    """Convert snake_case to Display Name."""
    return ' '.join(word.capitalize() for word in name.split('_'))


def extract_descriptions_from_yaml_text(yaml_text: str, model_name: str) -> Dict[str, str]:
    """Extract column descriptions from YAML text using regex."""
    descriptions = {}
    
    # Find the model section
    model_pattern = rf'- name:\s+{re.escape(model_name)}\s*\n(.*?)(?=\n- name:|\n\s*config:|\Z)'
    model_match = re.search(model_pattern, yaml_text, re.DOTALL | re.MULTILINE)
    
    if not model_match:
        return descriptions
    
    model_section = model_match.group(1)
    
    # Extract description field
    desc_pattern = r'description:\s*\|\-\s*\n(.*?)(?=\n\s+\w+:|$)'
    desc_match = re.search(desc_pattern, model_section, re.DOTALL | re.MULTILINE)
    
    if desc_match:
        description = desc_match.group(1)
        
        # Pattern 1: **field_name**: description
        pattern1 = r'\*\*(\w+)\*\*:\s*([^\n]+?)(?=\n|$)'
        for match in re.finditer(pattern1, description, re.MULTILINE):
            field_name = match.group(1).lower()
            field_desc = match.group(2).strip()
            field_desc = re.sub(r'\.$', '', field_desc)
            if field_desc:
                descriptions[field_name] = field_desc
        
        # Pattern 2: **field_name** — description
        pattern2 = r'\*\*(\w+)\*\*\s*[—–-]\s*([^\n]+?)(?=\n|$)'
        for match in re.finditer(pattern2, description, re.MULTILINE):
            field_name = match.group(1).lower()
            field_desc = match.group(2).strip()
            field_desc = re.sub(r'\.$', '', field_desc)
            if field_desc and field_name not in descriptions:
                descriptions[field_name] = field_desc
        
        # Pattern 2b: **field1** / **field2** / **field3** — description (multiple fields sharing description)
        # This handles patterns like "- **connection_ip** / **external_ip** / **local_ip** — IP addresses"
        pattern2b = r'[-*]\s+(\*\*[^\*]+\*\*(?:\s*/\s*\*\*[^\*]+\*\*)*)\s*[—–-]\s*([^\n]+?)(?=\n|$)'
        for match in re.finditer(pattern2b, description, re.MULTILINE):
            fields_part = match.group(1)
            field_desc = match.group(2).strip()
            field_desc = re.sub(r'\.$', '', field_desc)
            # Extract all field names from the pattern (handles "**field1** / **field2** / **field3**")
            field_names = re.findall(r'\*\*(\w+)\*\*', fields_part)
            for field_name in field_names:
                field_name_lower = field_name.lower()
                if field_desc and field_name_lower not in descriptions:
                    descriptions[field_name_lower] = field_desc
        
        # Pattern 3: **field_name** (type): description
        pattern3 = r'\*\*(\w+)\*\*\s*\([^)]+\):\s*([^\n]+?)(?=\n|$)'
        for match in re.finditer(pattern3, description, re.MULTILINE):
            field_name = match.group(1).lower()
            field_desc = match.group(2).strip()
            field_desc = re.sub(r'\.$', '', field_desc)
            if field_desc and field_name not in descriptions:
                descriptions[field_name] = field_desc
    
    # Also check explicit column definitions
    cols_pattern = r'columns:\s*\n(.*?)(?=\n\s+\w+:|$)'
    cols_match = re.search(cols_pattern, model_section, re.DOTALL | re.MULTILINE)
    
    if cols_match:
        cols_section = cols_match.group(1)
        col_pattern = r'- name:\s+(\w+)\s*\n.*?description:\s*"([^"]+)"'
        for match in re.finditer(col_pattern, cols_section, re.DOTALL | re.MULTILINE):
            col_name = match.group(1).lower()
            col_desc = match.group(2).strip()
            if col_desc:
                descriptions[col_name] = col_desc
    
    return descriptions


def find_yaml_file(model_name: str, models_dir: Path) -> Optional[Path]:
    """Find YAML file containing the model."""
    for yaml_file in models_dir.rglob("*.yaml"):
        try:
            with open(yaml_file, 'r') as f:
                content = f.read()
            # Check if model name is in the file
            if f'- name: {model_name}' in content or f'name: {model_name}' in content:
                return yaml_file
        except:
            continue
    return None


def enrich_mdl_file(mdl_path: Path, models_dir: Path):
    """Enrich a single MDL file."""
    print(f"Processing: {mdl_path.name}")
    
    with open(mdl_path, 'r') as f:
        mdl_data = json.load(f)
    
    if 'models' not in mdl_data:
        print(f"  No models found")
        return
    
    updated = False
    
    for model in mdl_data['models']:
        model_name = model.get('name')
        if not model_name:
            continue
        
        # Find YAML file
        yaml_file = find_yaml_file(model_name, models_dir)
        if not yaml_file:
            print(f"  No YAML found for {model_name}")
            continue
        
        # Read YAML as text
        try:
            with open(yaml_file, 'r') as f:
                yaml_text = f.read()
        except Exception as e:
            print(f"  Error reading YAML: {e}")
            continue
        
        # Extract descriptions
        column_descriptions = extract_descriptions_from_yaml_text(yaml_text, model_name)
        
        # Enrich columns
        if 'columns' in model:
            for col in model['columns']:
                col_name = col.get('name', '')
                col_name_lower = col_name.lower()
                
                # Ensure properties exist
                if 'properties' not in col:
                    col['properties'] = {}
                
                # Add displayName
                if 'displayName' not in col['properties']:
                    col['properties']['displayName'] = to_display_name(col_name)
                
                # Add description if found
                if col_name_lower in column_descriptions:
                    col['properties']['description'] = column_descriptions[col_name_lower]
                    updated = True
                elif not col['properties'].get('description'):
                    # Generic descriptions
                    if col_name_lower.endswith('_id') and not col_name_lower.startswith('_'):
                        base = col_name_lower.replace('_id', '').replace('_', ' ')
                        col['properties']['description'] = f"Unique identifier for {base}"
                        updated = True
                    elif col_name_lower.endswith('_at') or col_name_lower.endswith('_timestamp'):
                        base = col_name_lower.replace('_at', '').replace('_timestamp', '').replace('_', ' ')
                        col['properties']['description'] = f"Timestamp when {base} occurred"
                        updated = True
                    elif col_name_lower.startswith('is_') or col_name_lower.startswith('has_'):
                        base = col_name_lower.replace('is_', '').replace('has_', '').replace('_', ' ')
                        col['properties']['description'] = f"Boolean flag indicating {base}"
                        updated = True
                    elif col_name_lower == 'connection_id':
                        col['properties']['description'] = "Unique identifier for the integration connection"
                        updated = True
                    elif col_name_lower == 'organization_id':
                        col['properties']['description'] = "Unique identifier for the organization"
                        updated = True
                    elif col_name_lower == '_surrogate_key':
                        col['properties']['description'] = "Composite primary key for deduplication"
                        updated = True
                    elif col_name_lower == '_dlt_id':
                        col['properties']['description'] = "Internal data load tracking identifier"
                        updated = True
                    elif col_name_lower == '_dlt_load_id':
                        col['properties']['description'] = "Data load batch identifier"
                        updated = True
                    elif col_name_lower == 'load_timestamp':
                        col['properties']['description'] = "Timestamp when the data was loaded"
                        updated = True
                    elif col_name_lower == 'is_deleted':
                        col['properties']['description'] = "Flag indicating if the record has been deleted"
                        updated = True
    
    # Write updated file
    if updated:
        with open(mdl_path, 'w') as f:
            json.dump(mdl_data, f, indent=2)
        print(f"  ✓ Updated")
    else:
        print(f"  - No updates needed")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich MDL files with column descriptions')
    parser.add_argument('--mdl-dir', type=str, required=True,
                       help='Directory containing MDL files')
    parser.add_argument('--models-dir', type=str, required=True,
                       help='Directory containing dbt models')
    
    args = parser.parse_args()
    
    mdl_dir = Path(args.mdl_dir)
    models_dir = Path(args.models_dir)
    
    if not mdl_dir.exists():
        print(f"Error: MDL directory not found: {mdl_dir}")
        sys.exit(1)
    
    if not models_dir.exists():
        print(f"Error: Models directory not found: {models_dir}")
        sys.exit(1)
    
    mdl_files = list(mdl_dir.glob("*.mdl.json"))
    
    if not mdl_files:
        print(f"No MDL files found in {mdl_dir}")
        return
    
    print(f"Found {len(mdl_files)} MDL files\n")
    
    for mdl_file in sorted(mdl_files):
        enrich_mdl_file(mdl_file, models_dir)
    
    print(f"\n✓ Completed processing {len(mdl_files)} files")


if __name__ == '__main__':
    main()
