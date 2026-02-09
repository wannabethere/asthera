#!/usr/bin/env python3
"""
Script to create preview files for product documentation.
Converts product markdown documentation into preview format for ingestion into multiple stores:
- entities: Key concepts and product entities
- evidence: Documentation and API links
- fields: Metadata and attributes
- controls: Access controls and security controls
- domain_knowledge: Product documentation content
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def extract_sections_from_markdown(md_path: Path) -> Dict[str, Any]:
    """Extract sections from markdown file."""
    with open(md_path, 'r') as f:
        content = f.read()
    
    sections = {}
    current_section = None
    current_content = []
    current_links = {"docs": [], "apis": []}
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        # Check for main section headers (##)
        if line.startswith('## ') and not line.startswith('### '):
            if current_section:
                sections[current_section] = {
                    "content": "\n".join(current_content),
                    "docs_links": current_links["docs"],
                    "api_links": current_links["apis"]
                }
            current_section = line.replace('## ', '').strip()
            current_content = []
            current_links = {"docs": [], "apis": []}
        # Check for documentation/API link sections
        elif line.startswith('### Related Documentation Links'):
            # Collect doc links
            j = i + 1
            while j < len(lines) and not lines[j].startswith('###') and not lines[j].startswith('##'):
                if lines[j].startswith('- ['):
                    match = re.search(r'\[([^\]]+)\]\(([^\)]+)\)', lines[j])
                    if match:
                        current_links["docs"].append({
                            "title": match.group(1),
                            "url": match.group(2)
                        })
                j += 1
        elif line.startswith('### Related API Links'):
            # Collect API links
            j = i + 1
            while j < len(lines) and not lines[j].startswith('###') and not lines[j].startswith('##'):
                if lines[j].startswith('- ['):
                    match = re.search(r'\[([^\]]+)\]\(([^\)]+)\)', lines[j])
                    if match:
                        current_links["apis"].append({
                            "title": match.group(1),
                            "url": match.group(2)
                        })
                j += 1
        elif current_section and not line.startswith('###'):
            current_content.append(line)
    
    # Add last section
    if current_section:
        sections[current_section] = {
            "content": "\n".join(current_content),
            "docs_links": current_links["docs"],
            "api_links": current_links["apis"]
        }
    
    return sections


def create_product_docs_preview(md_path: Path, output_dir: Path, product_name: str = "Snyk") -> List[Path]:
    """
    Convert product documentation markdown into preview files for different stores.
    
    Args:
        md_path: Path to product documentation markdown file
        output_dir: Directory to write preview files
        product_name: Name of the product
    """
    sections = extract_sections_from_markdown(md_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    created_files = []
    
    # Extract entities (key concepts, product features)
    entities_docs = []
    entity_index = 0
    
    # Extract controls (access controls, security controls)
    controls_docs = []
    control_index = 0
    
    # Extract domain knowledge (all content sections)
    domain_knowledge_docs = []
    dk_index = 0
    
    # Extract evidence (documentation and API links)
    evidence_docs = []
    evidence_index = 0
    
    # Extract fields (metadata, attributes)
    fields_docs = []
    field_index = 0
    
    # Process each section
    for section_name, section_data in sections.items():
        content = section_data["content"].strip()
        docs_links = section_data.get("docs_links", [])
        api_links = section_data.get("api_links", [])
        
        # Domain Knowledge: Full section content
        domain_knowledge_docs.append({
            "index": dk_index,
            "page_content": content,
            "metadata": {
                "content_type": "product_docs",
                "type": "product",
                "product_name": product_name,
                "section": section_name.lower().replace(' ', '_'),
                "section_title": section_name,
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "content_length": len(content),
            "metadata_keys": ["content_type", "type", "product_name", "section", "section_title", "extraction_type", "indexed_at", "source", "source_file"]
        })
        dk_index += 1
        
        # Entities: Extract key concepts from section
        # Look for capitalized terms, product features, etc.
        key_concepts = []
        if section_name == "Overview":
            key_concepts = ["AI-driven platform", "Developer security", "SDLC integration", "Context-aware recommendations", "Security intelligence"]
        elif section_name == "Assets":
            key_concepts = ["Asset management", "Open source dependencies", "Container images", "Infrastructure as code", "Asset lifecycle"]
        elif section_name == "Vulnerabilities":
            key_concepts = ["Vulnerability database", "Contextual risk assessment", "Vulnerability prioritization", "Remediation guidance", "Exploit intelligence"]
        elif section_name == "Access Controls":
            key_concepts = ["Role-based access control", "RBAC", "SSO integration", "Audit logging", "API tokens", "Service accounts"]
        elif section_name == "Reporting":
            key_concepts = ["Executive reporting", "Compliance reporting", "Technical reporting", "Custom reports", "Trend analysis"]
        
        for concept in key_concepts:
            entities_docs.append({
                "index": entity_index,
                "page_content": json.dumps({
                    "entity_id": f"{product_name.lower()}_{section_name.lower().replace(' ', '_')}_{concept.lower().replace(' ', '_')}",
                    "entity_type": "product_concept",
                    "entity_name": concept,
                    "properties": {
                        "product": product_name,
                        "section": section_name,
                        "description": f"{concept} in {product_name} {section_name}",
                        "source": "product_documentation"
                    }
                }, indent=2),
                "metadata": {
                    "content_type": "product_key_concepts",
                    "type": "product",
                    "product_name": product_name,
                    "section": section_name.lower().replace(' ', '_'),
                    "entity_type": "product_concept",
                    "entity_name": concept,
                    "extraction_type": "entities",
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source": "product_documentation",
                    "source_file": str(md_path)
                },
                "content_length": len(concept),
                "metadata_keys": ["content_type", "type", "product_name", "section", "entity_type", "entity_name", "extraction_type", "indexed_at", "source", "source_file"]
            })
            entity_index += 1
        
        # Controls: Extract from Access Controls section
        if section_name == "Access Controls":
            controls = [
                "Role-Based Access Control (RBAC)",
                "Single Sign-On (SSO)",
                "Multi-Factor Authentication (MFA)",
                "API Token Management",
                "Service Account Management",
                "Audit Logging",
                "Permission Delegation"
            ]
            
            for control in controls:
                controls_docs.append({
                    "index": control_index,
                    "page_content": f"Control: {control}\n\nDescription: {control} is implemented in {product_name} to manage access to platform resources and security information.",
                    "metadata": {
                        "content_type": "controls",
                        "type": "product",
                        "product_name": product_name,
                        "section": "access_controls",
                        "control_name": control,
                        "control_type": "access_control",
                        "extraction_type": "control",
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source": "product_documentation",
                        "source_file": str(md_path)
                    },
                    "content_length": len(control),
                    "metadata_keys": ["content_type", "type", "product_name", "section", "control_name", "control_type", "extraction_type", "indexed_at", "source", "source_file"]
                })
                control_index += 1
        
        # Evidence: Documentation and API links
        for doc_link in docs_links:
            evidence_docs.append({
                "index": evidence_index,
                "page_content": json.dumps({
                    "evidence_type": "documentation_link",
                    "title": doc_link["title"],
                    "url": doc_link["url"],
                    "product": product_name,
                    "section": section_name,
                    "description": f"Documentation link for {doc_link['title']} in {product_name} {section_name}"
                }, indent=2),
                "metadata": {
                    "content_type": "product_docs_link",
                    "type": "product",
                    "product_name": product_name,
                    "section": section_name.lower().replace(' ', '_'),
                    "evidence_type": "documentation_link",
                    "title": doc_link["title"],
                    "url": doc_link["url"],
                    "extraction_type": "evidence",
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source": "product_documentation",
                    "source_file": str(md_path)
                },
                "content_length": len(doc_link["title"]),
                "metadata_keys": ["content_type", "type", "product_name", "section", "evidence_type", "title", "url", "extraction_type", "indexed_at", "source", "source_file"]
            })
            evidence_index += 1
        
        for api_link in api_links:
            evidence_docs.append({
                "index": evidence_index,
                "page_content": json.dumps({
                    "evidence_type": "api_link",
                    "title": api_link["title"],
                    "url": api_link["url"],
                    "product": product_name,
                    "section": section_name,
                    "description": f"API link for {api_link['title']} in {product_name} {section_name}"
                }, indent=2),
                "metadata": {
                    "content_type": "product_docs_link",
                    "type": "product",
                    "product_name": product_name,
                    "section": section_name.lower().replace(' ', '_'),
                    "evidence_type": "api_link",
                    "title": api_link["title"],
                    "url": api_link["url"],
                    "extraction_type": "evidence",
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source": "product_documentation",
                    "source_file": str(md_path)
                },
                "content_length": len(api_link["title"]),
                "metadata_keys": ["content_type", "type", "product_name", "section", "evidence_type", "title", "url", "extraction_type", "indexed_at", "source", "source_file"]
            })
            evidence_index += 1
        
        # Fields: Extract metadata and attributes from sections
        fields_docs.append({
            "index": field_index,
            "page_content": json.dumps({
                "extracted_fields": [
                    {
                        "field_name": "Product",
                        "field_value": product_name,
                        "source_section": section_name
                    },
                    {
                        "field_name": "Section",
                        "field_value": section_name,
                        "source_section": section_name
                    },
                    {
                        "field_name": "Content Length",
                        "field_value": str(len(content)),
                        "source_section": section_name
                    },
                    {
                        "field_name": "Documentation Links Count",
                        "field_value": str(len(docs_links)),
                        "source_section": section_name
                    },
                    {
                        "field_name": "API Links Count",
                        "field_value": str(len(api_links)),
                        "source_section": section_name
                    }
                ]
            }, indent=2),
            "metadata": {
                "content_type": "fields",
                "type": "product",
                "product_name": product_name,
                "section": section_name.lower().replace(' ', '_'),
                "extraction_type": "fields",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "content_length": len(content),
            "metadata_keys": ["content_type", "type", "product_name", "section", "extraction_type", "indexed_at", "source", "source_file"]
        })
        field_index += 1
    
    # Create preview files for each store
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Entities preview file
    if entities_docs:
        entities_file = output_dir / f"product_key_concepts_{timestamp}_{product_name}.json"
        entities_preview = {
            "metadata": {
                "content_type": "product_key_concepts",
                "product_name": product_name,
                "document_count": len(entities_docs),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "documents": entities_docs
        }
        with open(entities_file, 'w') as f:
            json.dump(entities_preview, f, indent=2)
        created_files.append(entities_file)
        print(f"Created entities preview: {entities_file} ({len(entities_docs)} documents)")
    
    # 2. Evidence preview file
    if evidence_docs:
        evidence_file = output_dir / f"product_docs_link_{timestamp}_{product_name}.json"
        evidence_preview = {
            "metadata": {
                "content_type": "product_docs_link",
                "product_name": product_name,
                "document_count": len(evidence_docs),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "documents": evidence_docs
        }
        with open(evidence_file, 'w') as f:
            json.dump(evidence_preview, f, indent=2)
        created_files.append(evidence_file)
        print(f"Created evidence preview: {evidence_file} ({len(evidence_docs)} documents)")
    
    # 3. Fields preview file
    if fields_docs:
        fields_file = output_dir / f"fields_{timestamp}_{product_name}.json"
        fields_preview = {
            "metadata": {
                "content_type": "fields",
                "product_name": product_name,
                "document_count": len(fields_docs),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "documents": fields_docs
        }
        with open(fields_file, 'w') as f:
            json.dump(fields_preview, f, indent=2)
        created_files.append(fields_file)
        print(f"Created fields preview: {fields_file} ({len(fields_docs)} documents)")
    
    # 4. Controls preview file
    if controls_docs:
        controls_file = output_dir / f"controls_{timestamp}_{product_name}.json"
        controls_preview = {
            "metadata": {
                "content_type": "controls",
                "product_name": product_name,
                "document_count": len(controls_docs),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "documents": controls_docs
        }
        with open(controls_file, 'w') as f:
            json.dump(controls_preview, f, indent=2)
        created_files.append(controls_file)
        print(f"Created controls preview: {controls_file} ({len(controls_docs)} documents)")
    
    # 5. Domain Knowledge preview file
    if domain_knowledge_docs:
        dk_file = output_dir / f"extendable_doc_{timestamp}_{product_name}.json"
        dk_preview = {
            "metadata": {
                "content_type": "extendable_doc",
                "product_name": product_name,
                "document_count": len(domain_knowledge_docs),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "product_documentation",
                "source_file": str(md_path)
            },
            "documents": domain_knowledge_docs
        }
        with open(dk_file, 'w') as f:
            json.dump(dk_preview, f, indent=2)
        created_files.append(dk_file)
        print(f"Created domain knowledge preview: {dk_file} ({len(domain_knowledge_docs)} documents)")
    
    return created_files


def main():
    """Main function to process product documentation."""
    script_dir = Path(__file__).parent
    examples_dir = script_dir
    preview_dir = script_dir.parent.parent.parent / "indexing_preview" / "product_docs"
    
    # Product documentation file
    product_doc_file = examples_dir / "snyk_product_doc.md"
    
    if not product_doc_file.exists():
        print(f"Error: {product_doc_file} not found", file=sys.stderr)
        return []
    
    try:
        created_files = create_product_docs_preview(
            product_doc_file,
            preview_dir,
            product_name="Snyk"
        )
        print(f"\nCreated {len(created_files)} preview files in {preview_dir}")
        return created_files
    except Exception as e:
        print(f"Error processing product documentation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    main()
