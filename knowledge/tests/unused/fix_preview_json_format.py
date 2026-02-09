#!/usr/bin/env python3
"""
Fix indexing preview JSON files to match project_reader.py format.

This script converts:
1. table_definitions: From JSON with full column objects to stringified dict with comma-separated columns
2. table_descriptions: Already correct, but ensures consistency
3. column_definitions: Convert from JSON to stringified dict format for consistency
"""

import json
import ast
from pathlib import Path
from typing import Dict, Any, List

def fix_table_definitions(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Fix table_definition document to match project_reader.py format."""
    try:
        # Parse the current JSON page_content
        current_content = json.loads(doc["page_content"])
        
        # Extract column names as comma-separated string
        columns = current_content.get("columns", [])
        if isinstance(columns, list):
            column_names = [col.get("name", "") if isinstance(col, dict) else str(col) for col in columns]
            columns_str = ', '.join([name for name in column_names if name])
        else:
            columns_str = str(columns)
        
        # Create new content_dict in project_reader.py format
        content_dict = {
            "name": current_content.get("table_name", ""),
            "mdl_type": "TABLE_SCHEMA",
            "type": "TABLE_DESCRIPTION",
            "description": current_content.get("description", ""),
            "columns": columns_str
        }
        
        # Convert to stringified dict (not JSON)
        doc["page_content"] = str(content_dict)
        
        # Update metadata to match format
        metadata = doc.get("metadata", {})
        metadata["type"] = "TABLE_DESCRIPTION"
        metadata["mdl_type"] = "TABLE_SCHEMA"
        metadata["name"] = current_content.get("table_name", "")
        if "description" not in metadata:
            metadata["description"] = current_content.get("description", "")
        
        # Keep existing metadata fields for backward compatibility
        if "table_name" not in metadata:
            metadata["table_name"] = current_content.get("table_name", "")
        
        return doc
    except Exception as e:
        print(f"Error fixing table_definition document: {e}")
        return doc

def fix_table_descriptions(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure table_description document matches project_reader.py format."""
    try:
        # Parse the current stringified dict
        # Try to evaluate it as a Python dict
        page_content = doc["page_content"]
        
        # If it's already a stringified dict, try to parse it
        if isinstance(page_content, str):
            # Try to parse as Python dict literal
            try:
                content_dict = ast.literal_eval(page_content)
            except:
                # If that fails, try JSON
                try:
                    content_dict = json.loads(page_content)
                except:
                    print(f"Warning: Could not parse page_content: {page_content[:100]}...")
                    return doc
            
            # Ensure columns is a comma-separated string
            columns = content_dict.get("columns", "")
            if isinstance(columns, list):
                columns_str = ', '.join([str(col) for col in columns])
                content_dict["columns"] = columns_str
            
            # Ensure required fields exist
            if "name" not in content_dict:
                content_dict["name"] = content_dict.get("table_name", "")
            if "mdl_type" not in content_dict:
                content_dict["mdl_type"] = "TABLE_SCHEMA"
            if "type" not in content_dict:
                content_dict["type"] = "TABLE_DESCRIPTION"
            
            # Convert back to stringified dict
            doc["page_content"] = str(content_dict)
            
            # Update metadata
            metadata = doc.get("metadata", {})
            metadata["type"] = "TABLE_DESCRIPTION"
            metadata["mdl_type"] = content_dict.get("mdl_type", "TABLE_SCHEMA")
            metadata["name"] = content_dict.get("name", "")
            if "description" not in metadata:
                metadata["description"] = content_dict.get("description", "")
        
        return doc
    except Exception as e:
        print(f"Error fixing table_description document: {e}")
        return doc

def fix_column_definitions(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Fix column_definition document to use stringified dict format."""
    try:
        # Parse the current JSON page_content
        current_content = json.loads(doc["page_content"])
        
        # Create simplified content_dict (keep essential info)
        content_dict = {
            "column_name": current_content.get("column_name", ""),
            "table_name": current_content.get("table_name", ""),
            "type": current_content.get("type", ""),
            "description": current_content.get("description", "")
        }
        
        # Add properties if they exist (simplified)
        if "properties" in current_content and current_content["properties"]:
            # Keep only essential properties
            props = current_content["properties"]
            if isinstance(props, dict):
                simplified_props = {}
                for key in ["description", "displayName", "business_significance"]:
                    if key in props:
                        simplified_props[key] = props[key]
                if simplified_props:
                    content_dict["properties"] = simplified_props
        
        # Convert to stringified dict
        doc["page_content"] = str(content_dict)
        
        # Update metadata if needed
        metadata = doc.get("metadata", {})
        if "type" not in metadata:
            metadata["type"] = "COLUMN_DEFINITION"
        
        return doc
    except Exception as e:
        print(f"Error fixing column_definition document: {e}")
        return doc

def fix_json_file(file_path: Path) -> bool:
    """Fix a single JSON file."""
    print(f"\nProcessing: {file_path}")
    
    try:
        # Read the JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Determine content type
        content_type = data.get("metadata", {}).get("content_type", "")
        
        # Fix documents based on content type
        documents = data.get("documents", [])
        fixed_count = 0
        
        for doc in documents:
            original_content = doc.get("page_content", "")
            
            if content_type == "table_definitions":
                doc = fix_table_definitions(doc)
            elif content_type == "table_descriptions":
                doc = fix_table_descriptions(doc)
            elif content_type == "column_definitions":
                doc = fix_column_definitions(doc)
            else:
                print(f"  Skipping unknown content_type: {content_type}")
                continue
            
            # Check if content changed
            if doc.get("page_content", "") != original_content:
                fixed_count += 1
        
        if fixed_count > 0:
            # Write back the fixed JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  ✅ Fixed {fixed_count} documents")
            return True
        else:
            print(f"  ℹ️  No changes needed ({len(documents)} documents)")
            return False
            
    except Exception as e:
        print(f"  ❌ Error processing file: {e}")
        return False

def main():
    """Main function to fix all preview JSON files."""
    base_path = Path("/Users/sameermangalampalli/flowharmonicai/knowledge/indexing_preview")
    
    # Files to fix
    files_to_fix = [
        base_path / "table_definitions" / "table_definitions_20260123_180157_Snyk.json",
        base_path / "table_descriptions" / "table_descriptions_20260123_180157_Snyk.json",
        base_path / "column_definitions" / "column_definitions_20260123_180157_Snyk.json",
    ]
    
    print("=" * 80)
    print("Fixing indexing preview JSON files to match project_reader.py format")
    print("=" * 80)
    
    fixed_files = 0
    for file_path in files_to_fix:
        if file_path.exists():
            if fix_json_file(file_path):
                fixed_files += 1
        else:
            print(f"\n⚠️  File not found: {file_path}")
    
    print("\n" + "=" * 80)
    print(f"✅ Fixed {fixed_files} out of {len(files_to_fix)} files")
    print("=" * 80)

if __name__ == "__main__":
    main()
