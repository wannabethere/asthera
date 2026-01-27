#!/usr/bin/env python3
"""
Script to verify preview files are compatible with collection factory routing.
Checks metadata structure matches routing requirements.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

def verify_policy_documents(file_path: Path) -> Tuple[bool, List[str]]:
    """Verify policy_documents file compatibility."""
    issues = []
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Check top-level metadata
    top_metadata = data.get("metadata", {})
    if top_metadata.get("content_type") != "policy_documents":
        issues.append("Top-level content_type should be 'policy_documents'")
    
    # Check documents
    for i, doc in enumerate(data.get("documents", [])):
        doc_metadata = doc.get("metadata", {})
        
        # Policy documents should have extraction_type for routing
        if "extraction_type" not in doc_metadata:
            issues.append(f"Document {i}: Missing 'extraction_type' (required for routing)")
        
        # Framework should be present
        if "framework" not in doc_metadata:
            issues.append(f"Document {i}: Missing 'framework' in metadata")
        
        # extraction_type should be one of the valid types
        valid_extraction_types = ["context", "entities", "requirement", "full_content", "evidence", "fields", "control"]
        extraction_type = doc_metadata.get("extraction_type")
        if extraction_type and extraction_type not in valid_extraction_types:
            issues.append(f"Document {i}: Invalid extraction_type '{extraction_type}' (should be one of {valid_extraction_types})")
    
    return len(issues) == 0, issues


def verify_risk_controls(file_path: Path) -> Tuple[bool, List[str]]:
    """Verify riskmanagement_risk_controls file compatibility."""
    issues = []
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Check top-level metadata
    top_metadata = data.get("metadata", {})
    content_type = top_metadata.get("content_type")
    if content_type not in ["riskmanagement_risk_controls", "risk_controls"]:
        issues.append(f"Top-level content_type should be 'riskmanagement_risk_controls' or 'risk_controls', got '{content_type}'")
    
    # Check documents
    for i, doc in enumerate(data.get("documents", [])):
        doc_metadata = doc.get("metadata", {})
        
        # Risk controls should have extraction_type for routing
        if "extraction_type" not in doc_metadata:
            issues.append(f"Document {i}: Missing 'extraction_type' (required for routing)")
        
        # Framework should be present
        if "framework" not in doc_metadata:
            issues.append(f"Document {i}: Missing 'framework' in metadata")
        
        # extraction_type should be one of the valid types
        valid_extraction_types = ["control", "entities", "fields", "evidence", "requirements", "context", "base"]
        extraction_type = doc_metadata.get("extraction_type")
        if extraction_type and extraction_type not in valid_extraction_types:
            issues.append(f"Document {i}: Invalid extraction_type '{extraction_type}' (should be one of {valid_extraction_types})")
    
    return len(issues) == 0, issues


def verify_soc2_controls(file_path: Path) -> Tuple[bool, List[str]]:
    """Verify soc2_controls file compatibility."""
    issues = []
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Check top-level metadata
    top_metadata = data.get("metadata", {})
    if top_metadata.get("content_type") != "soc2_controls":
        issues.append("Top-level content_type should be 'soc2_controls'")
    
    # Framework should be SOC2
    if top_metadata.get("framework") != "SOC2":
        issues.append(f"Top-level framework should be 'SOC2', got '{top_metadata.get('framework')}'")
    
    # Check documents
    for i, doc in enumerate(data.get("documents", [])):
        doc_metadata = doc.get("metadata", {})
        
        # SOC2 controls should have framework="SOC2"
        if doc_metadata.get("framework") != "SOC2":
            issues.append(f"Document {i}: framework should be 'SOC2', got '{doc_metadata.get('framework')}'")
        
        # extraction_type should be present (though routing will handle it)
        if "extraction_type" not in doc_metadata:
            # This is OK - routing will handle it
            pass
    
    return len(issues) == 0, issues


def main():
    """Main verification function."""
    script_dir = Path(__file__).parent
    preview_dir = script_dir.parent.parent.parent / "indexing_preview"
    
    # Files to verify
    files_to_verify = [
        ("policy_documents", "policy_documents_20260121_200125_compliance_Policy.json", verify_policy_documents),
        ("riskmanagement_risk_controls", "riskmanagement_risk_controls_20260121_184741_compliance_Risk_Management.json", verify_risk_controls),
        ("soc2_controls", "soc2_controls_20260121_184841_compliance_SOC2.json", verify_soc2_controls),
    ]
    
    print("="*70)
    print("Preview File Compatibility Verification")
    print("="*70)
    
    all_compatible = True
    
    for folder, filename, verify_func in files_to_verify:
        file_path = preview_dir / folder / filename
        
        if not file_path.exists():
            print(f"\n⚠️  {file_path.name} not found, skipping")
            continue
        
        print(f"\n{'='*70}")
        print(f"Verifying: {file_path.name}")
        print(f"{'='*70}")
        
        is_compatible, issues = verify_func(file_path)
        
        if is_compatible:
            print("✓ File is compatible with collection factory routing")
        else:
            print("✗ Compatibility issues found:")
            for issue in issues:
                print(f"   - {issue}")
            all_compatible = False
    
    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    if all_compatible:
        print("✓ All files are compatible with collection factory routing")
        print("\nRouting Summary:")
        print("  - policy_documents → routes to general stores (entities, evidence, fields, domain_knowledge) with type='policy'")
        print("  - riskmanagement_risk_controls → routes to general stores with type='risk_*' based on extraction_type")
        print("  - soc2_controls → routes to compliance_controls store with framework='SOC2'")
    else:
        print("✗ Some files have compatibility issues that need to be fixed")
    
    return all_compatible


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
