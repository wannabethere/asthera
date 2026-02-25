#!/usr/bin/env python3
"""
Batch convert dbt models to MDL format for all subdirectories.
Automatically discovers all silver layer models and converts them.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def discover_silver_directories(models_dir: Path) -> List[Tuple[str, str]]:
    """
    Discover all silver layer directories and generate schema names.
    
    Returns:
        List of (subdirectory, schema_name) tuples
    """
    conversions = []
    models_path = Path(models_dir)
    
    # Find all directories containing "silver"
    for silver_dir in models_path.rglob("silver"):
        if not silver_dir.is_dir():
            continue
        
        # Get relative path from models directory
        rel_path = silver_dir.relative_to(models_path)
        subdirectory = str(rel_path)
        
        # Generate schema name from path
        # e.g., "aws/guardduty/silver" -> "aws_guardduty"
        # e.g., "crowdstrike/vms/silver" -> "crowdstrike_vms"
        # e.g., "ms_defender/common/silver" -> "ms_defender_common"
        parts = rel_path.parts[:-1]  # Remove "silver"
        schema_name = "_".join(parts)
        
        # Check if there are any SQL or YAML files in this directory
        has_models = any(silver_dir.glob("*.sql")) or any(silver_dir.glob("*.yaml"))
        
        if has_models:
            conversions.append((subdirectory, schema_name))
    
    # Sort for consistent output
    conversions.sort(key=lambda x: x[0])
    
    return conversions


def run_conversion(converter_script: Path, models_dir: Path, output_dir: Path, subdirectory: str, schema: str):
    """Run the conversion script for a specific directory."""
    cmd = [
        sys.executable,
        str(converter_script),
        "--models-dir", str(models_dir),
        "--output-dir", str(output_dir),
        "--subdirectory", subdirectory,
        "--schema", schema,
        "--catalog", "product_knowledge"
    ]
    
    print(f"\n{'='*60}")
    print(f"Converting: {subdirectory} -> {schema}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(result.stdout)
        print(f"✓ Successfully converted {subdirectory}")
        return True
    else:
        print(result.stderr)
        print(f"✗ Failed to convert {subdirectory}")
        return False


def main():
    """Convert all discovered silver layer directories."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch convert dbt models to MDL format')
    parser.add_argument('--models-dir', type=str, required=True,
                       help='Directory containing dbt models (e.g., /path/to/leen_dbt/models)')
    parser.add_argument('--output-dir', type=str, 
                       default='/Users/sameerm/ComplianceSpark/byziplatform/mdl_schemas',
                       help='Output directory for MDL files (default: /Users/sameerm/ComplianceSpark/byziplatform/mdl_schemas)')
    
    args = parser.parse_args()
    
    # Determine base paths
    script_dir = Path(__file__).parent
    converter_script = script_dir / "convert_dbt_to_mdl.py"
    models_dir = Path(args.models_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not models_dir.exists():
        print(f"Error: Models directory not found: {models_dir}")
        sys.exit(1)
    
    if not converter_script.exists():
        print(f"Error: Converter script not found: {converter_script}")
        sys.exit(1)
    
    print("Discovering silver layer models...")
    conversions = discover_silver_directories(models_dir)
    
    if not conversions:
        print("No silver layer directories found!")
        return
    
    print(f"Found {len(conversions)} silver layer directories:")
    for subdirectory, schema in conversions:
        print(f"  - {subdirectory} -> {schema}")
    
    print(f"\nStarting batch conversion of dbt models to MDL format...")
    print(f"Models directory: {models_dir}")
    print(f"Output directory: {output_dir}")
    
    success_count = 0
    failed = []
    
    for subdirectory, schema in conversions:
        if run_conversion(converter_script, models_dir, output_dir, subdirectory, schema):
            success_count += 1
        else:
            failed.append((subdirectory, schema))
    
    print(f"\n{'='*60}")
    print(f"Conversion complete!")
    print(f"  Successfully converted: {success_count}/{len(conversions)}")
    if failed:
        print(f"  Failed conversions ({len(failed)}):")
        for subdirectory, schema in failed:
            print(f"    - {subdirectory} -> {schema}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
