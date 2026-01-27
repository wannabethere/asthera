#!/usr/bin/env python3
"""
Script to validate and fix preview files to ensure compatibility with collection factory.
Ensures metadata structure matches routing requirements.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

def fix_policy_documents(file_path: Path) -> bool:
    """Fix policy_documents preview file to ensure compatibility."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    modified = False
    for doc in data.get("documents", []):
        metadata = doc.get("metadata", {})
        
        # Policy documents should have type="policy" (will be added during ingestion, but ensure framework is present)
        if "framework" not in metadata:
            if "framework" in data.get("metadata", {}):
                metadata["framework"] = data["metadata"]["framework"]
                modified = True
        
        # Ensure extraction_type is present (required for routing)
        if "extraction_type" not in metadata:
            # Try to infer from content_type or other fields
            if metadata.get("content_type") == "policy":
                # Default to context if not specified
                metadata["extraction_type"] = "context"
                modified = True
    
    if modified:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False


def fix_risk_controls(file_path: Path) -> bool:
    """Fix riskmanagement_risk_controls preview file to ensure compatibility."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    modified = False
    for doc in data.get("documents", []):
        metadata = doc.get("metadata", {})
        
        # Risk controls should have framework
        if "framework" not in metadata:
            if "framework" in data.get("metadata", {}):
                metadata["framework"] = data["metadata"]["framework"]
                modified = True
        
        # Ensure extraction_type is present (required for routing)
        if "extraction_type" not in metadata:
            # Try to infer from entity_type or other fields
            entity_type = metadata.get("entity_type")
            if entity_type == "control":
                metadata["extraction_type"] = "control"
            elif entity_type == "fields":
                metadata["extraction_type"] = "fields"
            elif entity_type == "row":
                metadata["extraction_type"] = "base"
            else:
                metadata["extraction_type"] = "control"  # Default for risk controls
            modified = True
    
    if modified:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False


def fix_soc2_controls(file_path: Path) -> bool:
    """Fix soc2_controls preview file to ensure compatibility."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    modified = False
    
    # SOC2 controls should route to compliance_controls store
    # Ensure framework="SOC2" is in metadata
    for doc in data.get("documents", []):
        metadata = doc.get("metadata", {})
        
        # Ensure framework is set to SOC2
        if "framework" not in metadata or metadata.get("framework") != "SOC2":
            metadata["framework"] = "SOC2"
            modified = True
        
        # SOC2 controls should have type="compliance" or similar
        # But according to routing, they go to compliance_controls which uses framework in metadata
        # So we don't need to set type here - framework is sufficient
        
        # Ensure extraction_type is present
        if "extraction_type" not in metadata:
            entity_type = metadata.get("entity_type")
            if entity_type == "fields":
                metadata["extraction_type"] = "fields"
            elif entity_type == "row":
                metadata["extraction_type"] = "base"
            else:
                metadata["extraction_type"] = "control"  # Default for controls
            modified = True
    
    # Update top-level metadata if needed
    if "framework" not in data.get("metadata", {}):
        data["metadata"]["framework"] = "SOC2"
        modified = True
    
    if modified:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False


def validate_file_structure(file_path: Path) -> tuple[bool, List[str]]:
    """Validate that a preview file has the correct structure."""
    errors = []
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    
    # Check required top-level keys
    if "metadata" not in data:
        errors.append("Missing 'metadata' key")
    if "documents" not in data:
        errors.append("Missing 'documents' key")
    
    if errors:
        return False, errors
    
    # Check metadata structure
    metadata = data["metadata"]
    if "content_type" not in metadata:
        errors.append("Missing 'content_type' in metadata")
    
    # Check documents structure
    documents = data.get("documents", [])
    if not documents:
        errors.append("No documents in file")
    
    for i, doc in enumerate(documents):
        if "page_content" not in doc:
            errors.append(f"Document {i}: Missing 'page_content'")
        if "metadata" not in doc:
            errors.append(f"Document {i}: Missing 'metadata'")
    
    return len(errors) == 0, errors


def main():
    """Main function to validate and fix preview files."""
    script_dir = Path(__file__).parent
    preview_dir = script_dir.parent.parent.parent / "indexing_preview"
    
    # Files to check
    files_to_check = [
        ("policy_documents", "policy_documents_20260121_200125_compliance_Policy.json", fix_policy_documents),
        ("riskmanagement_risk_controls", "riskmanagement_risk_controls_20260121_184741_compliance_Risk_Management.json", fix_risk_controls),
        ("soc2_controls", "soc2_controls_20260121_184841_compliance_SOC2.json", fix_soc2_controls),
    ]
    
    results = []
    
    for folder, filename, fix_func in files_to_check:
        file_path = preview_dir / folder / filename
        
        if not file_path.exists():
            print(f"⚠️  {file_path} not found, skipping")
            continue
        
        print(f"\n{'='*60}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*60}")
        
        # Validate structure
        is_valid, errors = validate_file_structure(file_path)
        if not is_valid:
            print(f"❌ Validation errors:")
            for error in errors:
                print(f"   - {error}")
            continue
        
        print("✓ File structure is valid")
        
        # Fix compatibility issues
        was_modified = fix_func(file_path)
        if was_modified:
            print("✓ Fixed compatibility issues")
            results.append((file_path, True, "Fixed"))
        else:
            print("✓ No fixes needed - file is compatible")
            results.append((file_path, True, "Already compatible"))
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    for file_path, is_valid, status in results:
        print(f"{'✓' if is_valid else '✗'} {file_path.name}: {status}")
    
    return results


if __name__ == "__main__":
    main()
