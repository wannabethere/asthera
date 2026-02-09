#!/usr/bin/env python3
"""
Script to create preview files for compliance actors documentation.
Converts actor markdown documentation into preview format for ingestion into domain_knowledge store.
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def extract_actors_from_markdown(md_path: Path) -> Dict[str, Dict[str, Any]]:
    """Extract actor information from markdown file."""
    with open(md_path, 'r') as f:
        content = f.read()
    
    actors = {}
    current_actor = None
    current_section = None
    current_content = []
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        # Check for actor headers (## Actor Name)
        if line.startswith('## ') and not line.startswith('### '):
            if current_actor and current_section:
                if current_section not in actors[current_actor]:
                    actors[current_actor][current_section] = []
                actors[current_actor][current_section].append("\n".join(current_content))
            current_actor = line.replace('## ', '').strip()
            if current_actor not in actors:
                actors[current_actor] = {}
            current_section = None
            current_content = []
        # Check for section headers (### Section Name)
        elif line.startswith('### '):
            if current_actor and current_section:
                if current_section not in actors[current_actor]:
                    actors[current_actor][current_section] = []
                actors[current_actor][current_section].append("\n".join(current_content))
            current_section = line.replace('### ', '').strip()
            current_content = []
        elif current_actor and line.strip():
            current_content.append(line)
    
    # Add last section
    if current_actor and current_section:
        if current_section not in actors[current_actor]:
            actors[current_actor][current_section] = []
        actors[current_actor][current_section].append("\n".join(current_content))
    
    return actors


def create_actors_preview(md_path: Path, output_dir: Path) -> Path:
    """
    Convert actor documentation markdown into preview format.
    
    Args:
        md_path: Path to actor documentation markdown file
        output_dir: Directory to write preview file
    """
    actors = extract_actors_from_markdown(md_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Build documents list
    documents = []
    doc_index = 0
    
    # Process each actor
    for actor_name, actor_data in actors.items():
        # Create a comprehensive document for each actor
        actor_content_parts = [
            f"Actor: {actor_name}",
            "\n" + "="*50,
        ]
        
        # Add role description
        if "Role Description" in actor_data:
            role_desc = "\n".join(actor_data["Role Description"])
            actor_content_parts.append(f"\n## Role Description\n\n{role_desc}")
        
        # Add actions
        if "Actions They Are Supposed to Take" in actor_data:
            actions = "\n".join(actor_data["Actions They Are Supposed to Take"])
            actor_content_parts.append(f"\n## Actions They Are Supposed to Take\n\n{actions}")
        
        # Add what they want
        if "What They Want" in actor_data:
            wants = "\n".join(actor_data["What They Want"])
            actor_content_parts.append(f"\n## What They Want\n\n{wants}")
        
        # Add what they look for
        if "What They Look For When There Is Compliance" in actor_data:
            looks_for = "\n".join(actor_data["What They Look For When There Is Compliance"])
            actor_content_parts.append(f"\n## What They Look For When There Is Compliance\n\n{looks_for}")
        
        actor_content = "\n".join(actor_content_parts)
        
        # Extract keywords and concepts from actor content
        keywords = [
            actor_name.lower(),
            "compliance",
            "actor",
            "role",
            "responsibilities"
        ]
        
        # Add section-specific keywords
        if "Role Description" in actor_data:
            role_text = "\n".join(actor_data["Role Description"]).lower()
            if "manager" in role_text:
                keywords.append("management")
            if "engineer" in role_text:
                keywords.append("engineering")
            if "security" in role_text:
                keywords.append("security")
            if "executive" in role_text:
                keywords.append("executive")
            if "hr" in role_text or "human resources" in role_text:
                keywords.append("human resources")
        
        concepts = [
            "compliance management",
            "role-based compliance",
            "actor responsibilities",
            "compliance actions",
            "compliance expectations"
        ]
        
        # Create main actor document
        documents.append({
            "index": doc_index,
            "page_content": actor_content,
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": "compliance",
                "type": "compliance_actor",
                "actor_name": actor_name,
                "framework": "compliance",
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "actor_documentation",
                "source_file": str(md_path),
                "keywords": keywords,
                "concepts": concepts
            },
            "content_length": len(actor_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
        
        # Create separate documents for each section to enable better retrieval
        section_mapping = {
            "Role Description": "role_description",
            "Actions They Are Supposed to Take": "actions",
            "What They Want": "wants",
            "What They Look For When There Is Compliance": "compliance_criteria"
        }
        
        for section_name, section_key in section_mapping.items():
            if section_name in actor_data:
                section_content = "\n".join(actor_data[section_name])
                
                documents.append({
                    "index": doc_index,
                    "page_content": f"Actor: {actor_name}\n\nSection: {section_name}\n\n{section_content}",
                    "metadata": {
                        "content_type": "domain_knowledge",
                        "domain": "compliance",
                        "type": "compliance_actor",
                        "actor_name": actor_name,
                        "section": section_key,
                        "section_title": section_name,
                        "framework": "compliance",
                        "extraction_type": "context",
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source": "actor_documentation",
                        "source_file": str(md_path),
                        "keywords": keywords,
                        "concepts": concepts
                    },
                    "content_length": len(section_content),
                    "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
                })
                doc_index += 1
    
    # Create preview file structure
    preview_data = {
        "metadata": {
            "content_type": "domain_knowledge",
            "domain": "compliance",
            "product_name": "Compliance Actors",
            "document_count": len(documents),
            "timestamp": timestamp,
            "indexed_at": datetime.utcnow().isoformat(),
            "source": "actor_documentation",
            "comprehensive": False,
            "framework": "compliance",
            "type": "compliance_actor",
            "source_file": str(md_path)
        },
        "documents": documents
    }
    
    # Write preview file
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"compliance_actors_{timestamp}_compliance.json"
    output_path = output_dir / output_filename
    
    with open(output_path, 'w') as f:
        json.dump(preview_data, f, indent=2)
    
    print(f"Created preview file: {output_path}")
    print(f"  Actors: {len(actors)}")
    print(f"  Documents: {len(documents)}")
    return output_path


def main():
    """Main function to process actor documentation."""
    script_dir = Path(__file__).parent
    examples_dir = script_dir
    preview_dir = script_dir.parent.parent.parent / "indexing_preview" / "domain_knowledge"
    
    # Actor documentation file
    actor_doc_file = examples_dir / "compliance_actors_doc.md"
    
    if not actor_doc_file.exists():
        print(f"Error: {actor_doc_file} not found", file=sys.stderr)
        return None
    
    try:
        output_path = create_actors_preview(actor_doc_file, preview_dir)
        print(f"\nCreated actor preview file: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error processing actor documentation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
