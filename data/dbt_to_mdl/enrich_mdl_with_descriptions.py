#!/usr/bin/env python3
"""
Enrich MDL files with column descriptions and properties from dbt YAML files.
Extracts column descriptions from model descriptions and adds displayName and description properties.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install it with: pip install pyyaml")
    sys.exit(1)


def to_display_name(name: str) -> str:
    """Convert snake_case to Display Name."""
    return ' '.join(word.capitalize() for word in name.split('_'))


def extract_column_descriptions_from_model_description(description: str) -> Dict[str, str]:
    """
    Extract column descriptions from model description text.
    Looks for patterns like:
    - **column_name**: description
    - **column_name** — description
    - **column_name** - description
    - **column_name** (type): description
    """
    descriptions = {}
    
    if not description:
        return descriptions
    
    # Pattern 1: **field_name**: description (with colon)
    pattern1 = r'\*\*(\w+)\*\*:\s*([^\n]+?)(?=\n|$)'
    matches = re.finditer(pattern1, description, re.MULTILINE)
    for match in matches:
        field_name = match.group(1).lower()
        field_desc = match.group(2).strip()
        # Remove trailing period if it's just punctuation
        field_desc = re.sub(r'\.$', '', field_desc)
        if field_desc and field_name not in descriptions:
            descriptions[field_name] = field_desc
    
    # Pattern 2: **field_name** — description (with em dash)
    pattern2 = r'\*\*(\w+)\*\*\s*[—–-]\s*([^\n]+?)(?=\n|$)'
    matches = re.finditer(pattern2, description, re.MULTILINE)
    for match in matches:
        field_name = match.group(1).lower()
        field_desc = match.group(2).strip()
        field_desc = re.sub(r'\.$', '', field_desc)
        if field_desc and field_name not in descriptions:
            descriptions[field_name] = field_desc
    
    # Pattern 3: **field_name** (type): description
    pattern3 = r'\*\*(\w+)\*\*\s*\([^)]+\):\s*([^\n]+?)(?=\n|$)'
    matches = re.finditer(pattern3, description, re.MULTILINE)
    for match in matches:
        field_name = match.group(1).lower()
        field_desc = match.group(2).strip()
        field_desc = re.sub(r'\.$', '', field_desc)
        if field_desc and field_name not in descriptions:
            descriptions[field_name] = field_desc
    
    # Pattern 4: Handle nested fields like service.Archived, service.Count
    # Extract base field name (e.g., "service" from "service.Archived")
    nested_pattern = r'\*\*(\w+)\.(\w+)\*\*[:\s]+([^\n]+?)(?=\n|$)'
    matches = re.finditer(nested_pattern, description, re.MULTILINE)
    for match in matches:
        base_field = match.group(1).lower()
        nested_field = match.group(2).lower()
        field_desc = match.group(3).strip()
        field_desc = re.sub(r'\.$', '', field_desc)
        # Store both the nested field and the base field if it makes sense
        full_field = f"{base_field}.{nested_field}"
        if field_desc:
            descriptions[full_field] = field_desc
    
    return descriptions


def find_dbt_yaml_for_model(model_name: str, models_dir: Path) -> Optional[Path]:
    """Find the dbt YAML file for a given model."""
    # Look for YAML files that contain this model
    for yaml_file in models_dir.rglob("*.yaml"):
        try:
            with open(yaml_file, 'r') as f:
                content = yaml.safe_load(f)
            
            if content and 'models' in content:
                for model in content.get('models', []):
                    if model.get('name') == model_name:
                        return yaml_file
        except:
            continue
    
    return None


def enrich_mdl_file(mdl_path: Path, models_dir: Path):
    """Enrich a single MDL file with column descriptions from dbt YAML."""
    print(f"Processing: {mdl_path.name}")
    
    # Read MDL file
    with open(mdl_path, 'r') as f:
        mdl_data = json.load(f)
    
    if 'models' not in mdl_data:
        print(f"  No models found in {mdl_path.name}")
        return
    
    updated = False
    
    for model in mdl_data['models']:
        model_name = model.get('name')
        if not model_name:
            continue
        
        # Find corresponding dbt YAML file
        yaml_file = find_dbt_yaml_for_model(model_name, models_dir)
        
        if not yaml_file:
            print(f"  No YAML file found for model: {model_name}")
            continue
        
        # Read YAML file
        try:
            with open(yaml_file, 'r') as f:
                yaml_content = yaml.safe_load(f)
        except Exception as e:
            print(f"  Error reading YAML file {yaml_file}: {e}")
            continue
        
        # Find model in YAML
        model_def = None
        if yaml_content and 'models' in yaml_content:
            for m in yaml_content.get('models', []):
                if m.get('name') == model_name:
                    model_def = m
                    break
        
        if not model_def:
            print(f"  Model {model_name} not found in YAML file")
            continue
        
        # Extract model description
        model_description = model_def.get('description', '')
        
        # Extract column descriptions from model description
        column_descriptions = extract_column_descriptions_from_model_description(model_description)
        
        # Also check if there are explicit column definitions in YAML
        if 'columns' in model_def:
            for col_def in model_def.get('columns', []):
                col_name = col_def.get('name', '').lower()
                col_desc = col_def.get('description', '').strip()
                if col_desc:
                    column_descriptions[col_name] = col_desc
        
        # Enrich columns in MDL
        if 'columns' in model:
            for col in model['columns']:
                col_name = col.get('name', '').lower()
                
                # Ensure properties object exists
                if 'properties' not in col:
                    col['properties'] = {}
                
                # Add displayName if not present
                if 'displayName' not in col['properties']:
                    col['properties']['displayName'] = to_display_name(col.get('name', ''))
                
                # Add description if we found one
                if col_name in column_descriptions:
                    col['properties']['description'] = column_descriptions[col_name]
                    updated = True
                elif not col['properties'].get('description'):
                    # If no description found, use a generic one based on the field name
                    # Try to infer from common patterns
                    if col_name.endswith('_id'):
                        col['properties']['description'] = f"Unique identifier for {col_name.replace('_id', '')}"
                    elif col_name.endswith('_at') or col_name.endswith('_timestamp'):
                        col['properties']['description'] = f"Timestamp when {col_name.replace('_at', '').replace('_timestamp', '')} occurred"
                    elif col_name.startswith('is_') or col_name.startswith('has_'):
                        col['properties']['description'] = f"Boolean flag indicating {col_name.replace('is_', '').replace('has_', '')}"
    
    # Write updated MDL file
    if updated:
        with open(mdl_path, 'w') as f:
            json.dump(mdl_data, f, indent=2)
        print(f"  ✓ Updated {mdl_path.name}")
    else:
        print(f"  - No updates needed for {mdl_path.name}")


def main():
    """Enrich all MDL files in the leen-mdls directory."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich MDL files with column descriptions from dbt YAML')
    parser.add_argument('--mdl-dir', type=str, required=True,
                       help='Directory containing MDL files (e.g., /path/to/leen-mdls/models)')
    parser.add_argument('--models-dir', type=str, required=True,
                       help='Directory containing dbt models (e.g., /path/to/leen_dbt/models)')
    
    args = parser.parse_args()
    
    mdl_dir = Path(args.mdl_dir)
    models_dir = Path(args.models_dir)
    
    if not mdl_dir.exists():
        print(f"Error: MDL directory not found: {mdl_dir}")
        sys.exit(1)
    
    if not models_dir.exists():
        print(f"Error: Models directory not found: {models_dir}")
        sys.exit(1)
    
    # Find all MDL files
    mdl_files = list(mdl_dir.glob("*.mdl.json"))
    
    if not mdl_files:
        print(f"No MDL files found in {mdl_dir}")
        return
    
    print(f"Found {len(mdl_files)} MDL files to process")
    print(f"MDL directory: {mdl_dir}")
    print(f"Models directory: {models_dir}\n")
    
    for mdl_file in sorted(mdl_files):
        enrich_mdl_file(mdl_file, models_dir)
    
    print(f"\n✓ Completed processing {len(mdl_files)} MDL files")


if __name__ == '__main__':
    main()
