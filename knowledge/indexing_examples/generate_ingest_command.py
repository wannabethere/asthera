#!/usr/bin/env python3
"""
Script to generate the correct ingest command excluding schema-related content types.
"""
from pathlib import Path

def get_content_types_in_preview(preview_dir: Path) -> dict:
    """Get all content types in preview directory."""
    content_types = {}
    
    if not preview_dir.exists():
        return content_types
    
    for content_dir in preview_dir.iterdir():
        if not content_dir.is_dir():
            continue
        
        content_type = content_dir.name
        json_files = list(content_dir.glob("*.json"))
        # Exclude summary files
        json_files = [f for f in json_files if "summary" not in f.name]
        
        if json_files:
            content_types[content_type] = len(json_files)
    
    return content_types

def main():
    """Generate ingest command."""
    script_dir = Path(__file__).parent
    preview_dir = script_dir.parent.parent.parent / "indexing_preview"
    
    content_types = get_content_types_in_preview(preview_dir)
    
    # Schema-related content types to exclude
    schema_content_types = {
        "table_definitions",
        "table_descriptions", 
        "column_definitions",
        "schema_descriptions"
    }
    
    # Content types to include (compliance, product, domain knowledge)
    compliance_content_types = [
        "domain_knowledge",      # SOC2, HIPAA, ISO27001, FEDRAMP domain knowledge + actors
        "product_docs",          # Snyk product documentation
        "policy_documents",      # Policy documents
        "riskmanagement_risk_controls",  # Risk controls
        "soc2_controls"          # SOC2 controls
    ]
    
    # Filter to only include what exists and exclude schema types
    available_types = [ct for ct in content_types.keys() if ct not in schema_content_types]
    
    print("="*70)
    print("Preview Directory Content Types")
    print("="*70)
    print(f"\nAll content types found ({len(content_types)} total):")
    for ct, count in sorted(content_types.items()):
        marker = " (schema - will exclude)" if ct in schema_content_types else ""
        print(f"  - {ct}: {count} file(s){marker}")
    
    print(f"\n\nContent types to ingest ({len(available_types)} total):")
    for ct in sorted(available_types):
        count = content_types.get(ct, 0)
        print(f"  - {ct}: {count} file(s)")
    
    print("\n" + "="*70)
    print("Recommended Ingest Command (Excluding Schema Types)")
    print("="*70)
    print("\npython -m indexing_cli.ingest_preview_files \\")
    print("    --preview-dir indexing_preview \\")
    print("    --collection-prefix comprehensive_index \\")
    print(f"    --content-types {' '.join(sorted(available_types))}")
    
    print("\n" + "="*70)
    print("Alternative: Ingest Only New Content Types")
    print("="*70)
    print("\nTo ingest only the newly created content (actors, products, domain knowledge):")
    print("\npython -m indexing_cli.ingest_preview_files \\")
    print("    --preview-dir indexing_preview \\")
    print("    --collection-prefix comprehensive_index \\")
    print(f"    --content-types {' '.join(sorted(compliance_content_types))}")
    
    print("\n" + "="*70)
    print("Note")
    print("="*70)
    print("\nWithout --content-types, the command will index EVERYTHING including:")
    print("  - table_definitions")
    print("  - table_descriptions")
    print("  - column_definitions")
    print("  - schema_descriptions")
    print("\nTo exclude schema types, you MUST specify --content-types")

if __name__ == "__main__":
    main()
