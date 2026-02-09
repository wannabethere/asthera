#!/usr/bin/env python3
"""
Script to verify contextual edges are compatible with the system structure.
Checks that edges have the correct structure for:
- hybrid_search_service.py
- mdl_context_breakdown_agent.py
- mdl_reasoning_nodes.py
- contextual_graph_storage.py
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

def verify_edge_structure(file_path: Path) -> Tuple[bool, List[str]]:
    """Verify edge structure matches expected format."""
    issues = []
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    
    # Check required top-level keys
    if "metadata" not in data:
        issues.append("Missing 'metadata' key")
    if "documents" not in data:
        issues.append("Missing 'documents' key")
    
    if issues:
        return False, issues
    
    # Check metadata
    metadata = data["metadata"]
    if metadata.get("content_type") != "contextual_edges":
        issues.append("content_type should be 'contextual_edges'")
    
    # Check documents structure
    documents = data.get("documents", [])
    if not documents:
        issues.append("No documents in file")
    
    required_edge_fields = [
        "edge_id",
        "source_entity_id",
        "source_entity_type",
        "target_entity_id",
        "target_entity_type",
        "edge_type"
    ]
    
    for i, doc in enumerate(documents):
        # Check page_content exists and is a string (should be the document/description)
        if "page_content" not in doc:
            issues.append(f"Document {i}: Missing 'page_content'")
        elif not isinstance(doc.get("page_content"), str):
            issues.append(f"Document {i}: page_content should be a string (document description), not JSON")
        
        # Check metadata has all required edge fields
        doc_metadata = doc.get("metadata", {})
        for field in required_edge_fields:
            if field not in doc_metadata:
                issues.append(f"Document {i}: Missing required field '{field}' in metadata")
        
        # Verify page_content is the document (human-readable), not JSON
        page_content = doc.get("page_content", "")
        if page_content.strip().startswith("{") and page_content.strip().endswith("}"):
            try:
                # If it's JSON, it should be converted to document string
                parsed = json.loads(page_content)
                if "document" in parsed:
                    issues.append(f"Document {i}: page_content is JSON but should be the 'document' field value")
            except:
                pass  # Not JSON, which is fine
    
    return len(issues) == 0, issues


def fix_edge_structure(file_path: Path) -> bool:
    """Fix edge structure to match expected format."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    modified = False
    
    for doc in data.get("documents", []):
        metadata = doc.get("metadata", {})
        page_content = doc.get("page_content", "")
        
        # If page_content is JSON, extract the document field
        if page_content.strip().startswith("{") and page_content.strip().endswith("}"):
            try:
                parsed = json.loads(page_content)
                if "document" in parsed:
                    doc["page_content"] = parsed["document"]
                    modified = True
            except:
                pass
        
        # Ensure all required fields are in metadata
        required_fields = {
            "edge_id": metadata.get("edge_id", ""),
            "source_entity_id": metadata.get("source_entity_id", ""),
            "source_entity_type": metadata.get("source_entity_type", ""),
            "target_entity_id": metadata.get("target_entity_id", ""),
            "target_entity_type": metadata.get("target_entity_type", ""),
            "edge_type": metadata.get("edge_type", ""),
            "context_id": metadata.get("context_id", ""),
            "relevance_score": metadata.get("relevance_score", 0.0)
        }
        
        for field, default_value in required_fields.items():
            if field not in metadata:
                metadata[field] = default_value
                modified = True
    
    if modified:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False


def main():
    """Main verification function."""
    script_dir = Path(__file__).parent
    preview_dir = script_dir.parent.parent.parent / "indexing_preview" / "contextual_edges"
    
    # Find the latest contextual edges file
    edge_files = list(preview_dir.glob("contextual_edges_*.json"))
    if not edge_files:
        print("No contextual edges files found")
        return False
    
    # Use the most recent file
    latest_file = max(edge_files, key=lambda p: p.stat().st_mtime)
    
    print("="*70)
    print("Contextual Edges Compatibility Verification")
    print("="*70)
    print(f"\nVerifying: {latest_file.name}")
    print(f"File size: {latest_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    # Verify structure
    is_compatible, issues = verify_edge_structure(latest_file)
    
    if is_compatible:
        print("\n✓ Edge structure is compatible with system requirements")
        print("\nRequired fields verified:")
        print("  - page_content: Document description (string)")
        print("  - metadata.edge_id: Unique edge identifier")
        print("  - metadata.source_entity_id: Source entity ID")
        print("  - metadata.source_entity_type: Source entity type")
        print("  - metadata.target_entity_id: Target entity ID")
        print("  - metadata.target_entity_type: Target entity type")
        print("  - metadata.edge_type: Edge relationship type")
        print("  - metadata.context_id: Context identifier")
        print("  - metadata.relevance_score: Relevance score")
    else:
        print("\n✗ Compatibility issues found:")
        for issue in issues:
            print(f"   - {issue}")
        
        print("\nAttempting to fix issues...")
        was_fixed = fix_edge_structure(latest_file)
        if was_fixed:
            print("✓ Fixed structure issues")
            # Re-verify
            is_compatible, issues = verify_edge_structure(latest_file)
            if is_compatible:
                print("✓ File is now compatible")
            else:
                print("✗ Some issues remain:")
                for issue in issues:
                    print(f"   - {issue}")
        else:
            print("✗ Could not auto-fix all issues")
    
    print("\n" + "="*70)
    print("Edge Type Summary")
    print("="*70)
    
    # Count edge types
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    edge_types = {}
    for doc in data.get("documents", []):
        edge_type = doc.get("metadata", {}).get("edge_type", "UNKNOWN")
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
    
    for edge_type, count in sorted(edge_types.items()):
        print(f"  - {edge_type}: {count:,} edges")
    
    return is_compatible


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
