#!/usr/bin/env python3
"""
Extract SQL examples from MDL files into a separate file and remove them from MDL files.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def extract_sql_examples_from_mdl(mdl_path: Path) -> List[Dict[str, Any]]:
    """
    Extract SQL examples from an MDL file in sql_pairs format.
    
    Returns:
        List of SQL pairs (each with categories, question, sql, context, document, samples, instructions)
    """
    with open(mdl_path, 'r') as f:
        mdl_data = json.load(f)
    
    schema_name = mdl_data.get('schema', 'unknown')
    # Try to infer layer from filename or model properties
    layer = 'silver'  # default
    if '_silver' in str(mdl_path):
        layer = 'silver'
    elif '_gold' in str(mdl_path):
        layer = 'gold'
    elif '_bronze' in str(mdl_path):
        layer = 'bronze'
    
    # Also check model properties for layer
    for model in mdl_data.get('models', []):
        model_layer = model.get('properties', {}).get('layer')
        if model_layer:
            layer = model_layer
            break
    
    examples = []
    
    if 'models' not in mdl_data:
        return examples
    
    for model in mdl_data['models']:
        model_name = model.get('name', '')
        if not model_name:
            continue
        
        properties = model.get('properties', {})
        # Check both old and new format (prefer _sql_examples which is in sql_pairs format)
        sql_examples = properties.get('_sql_examples', []) or properties.get('sql_examples', [])
        
        if sql_examples:
            # Convert to sql_pairs format if needed
            for example in sql_examples:
                # If already in sql_pairs format, use as-is
                if 'categories' in example and 'question' in example:
                    examples.append(example)
                else:
                    # Convert old format to new format
                    # Infer categories from model name and description
                    categories = ['security_analysis']
                    if 'vulnerability' in model_name.lower() or 'vuln' in model_name.lower():
                        categories = ['vulnerability_management']
                    elif 'asset' in model_name.lower() or 'device' in model_name.lower() or 'host' in model_name.lower():
                        categories = ['asset_management']
                    elif 'alert' in model_name.lower() or 'threat' in model_name.lower():
                        categories = ['security_monitoring']
                    
                    sql_pair = {
                        "categories": example.get('categories', categories),
                        "question": example.get('title', example.get('question', f"What can we learn from {model_name}?")),
                        "sql": example.get('sql', ''),
                        "context": example.get('context', f"Direct Visualization - Table. {example.get('description', '')}"),
                        "document": f"{schema_name}_{layer}.mdl.json - {model_name}",
                        "samples": example.get('samples', []),
                        "instructions": example.get('instructions', example.get('description', f"Query to analyze {model_name}"))
                    }
                    examples.append(sql_pair)
    
    return examples


def remove_sql_examples_from_mdl(mdl_path: Path) -> bool:
    """
    Remove sql_examples and _sql_examples from an MDL file.
    
    Returns:
        True if file was updated, False otherwise
    """
    with open(mdl_path, 'r') as f:
        mdl_data = json.load(f)
    
    updated = False
    
    if 'models' not in mdl_data:
        return False
    
    for model in mdl_data['models']:
        properties = model.get('properties', {})
        if 'sql_examples' in properties:
            del properties['sql_examples']
            updated = True
        if '_sql_examples' in properties:
            del properties['_sql_examples']
            updated = True
    
    if updated:
        with open(mdl_path, 'w') as f:
            json.dump(mdl_data, f, indent=2)
    
    return updated


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract SQL examples from MDL files')
    parser.add_argument('--mdl-dir', type=str, required=True,
                       help='Directory containing MDL files')
    parser.add_argument('--output-file', type=str, 
                       default='sql_pairs.json',
                       help='Output file for SQL pairs (default: sql_pairs.json)')
    parser.add_argument('--remove', action='store_true',
                       help='Remove sql_examples from MDL files after extraction')
    
    args = parser.parse_args()
    
    mdl_dir = Path(args.mdl_dir)
    if not mdl_dir.exists():
        print(f"Error: MDL directory not found: {mdl_dir}")
        sys.exit(1)
    
    # Find all MDL files
    mdl_files = list(mdl_dir.glob("*.mdl.json"))
    if not mdl_files:
        print(f"No MDL files found in {mdl_dir}")
        return
    
    print(f"Found {len(mdl_files)} MDL files")
    print(f"Extracting SQL examples...\n")
    
    # Extract SQL examples from all files (in sql_pairs format)
    all_examples = []
    files_with_examples = 0
    total_examples = 0
    
    for mdl_file in sorted(mdl_files):
        examples = extract_sql_examples_from_mdl(mdl_file)
        if examples:
            all_examples.extend(examples)
            files_with_examples += 1
            total_examples += len(examples)
            print(f"  {mdl_file.name}: {len(examples)} SQL pairs")
    
    if not all_examples:
        print("\nNo SQL examples found in any MDL files")
        return
    
    # Write to output file as array (sql_pairs format)
    output_file = mdl_dir / args.output_file
    with open(output_file, 'w') as f:
        json.dump(all_examples, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Extracted {total_examples} SQL pairs from {files_with_examples} files")
    print(f"Saved to: {output_file}")
    print(f"{'='*60}")
    
    # Remove from MDL files if requested
    if args.remove:
        print(f"\nRemoving SQL examples from MDL files...")
        updated_count = 0
        for mdl_file in sorted(mdl_files):
            if remove_sql_examples_from_mdl(mdl_file):
                updated_count += 1
                print(f"  ✓ Removed from {mdl_file.name}")
        
        print(f"\n{'='*60}")
        print(f"Removed SQL examples from {updated_count} MDL files")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()
