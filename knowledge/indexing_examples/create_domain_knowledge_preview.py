#!/usr/bin/env python3
"""
Script to create preview files for domain knowledge JSON files.
Converts domain knowledge JSON files into preview format for ingestion.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def create_domain_knowledge_preview(domain_json_path: Path, output_dir: Path) -> None:
    """
    Convert a domain knowledge JSON file into preview format.
    
    Args:
        domain_json_path: Path to domain knowledge JSON file
        output_dir: Directory to write preview file
    """
    # Read domain knowledge JSON
    with open(domain_json_path, 'r') as f:
        domain_data = json.load(f)
    
    framework = domain_data.get('metadata', {}).get('framework', 'Unknown')
    domain_name = domain_data.get('domain_name', 'Unknown')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output filename
    output_filename = f"domain_knowledge_{timestamp}_compliance_{framework}.json"
    output_path = output_dir / output_filename
    
    # Build documents list
    documents = []
    doc_index = 0
    
    # Document 1: Domain Overview
    if 'detailed_domain_knowledge' in domain_data:
        documents.append({
            "index": doc_index,
            "page_content": domain_data['detailed_domain_knowledge'],
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
                "framework": framework,
                "type": "compliance",
                "domain_name": domain_name,
                "section": "domain_overview",
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "domain_knowledge_json",
                "source_file": str(domain_json_path),
                "keywords": domain_data.get('metadata', {}).get('keywords', []),
                "concepts": domain_data.get('metadata', {}).get('concepts', []),
                "evidence_types": domain_data.get('metadata', {}).get('evidence_types', [])
            },
            "content_length": len(domain_data['detailed_domain_knowledge']),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
    
    # Documents for each role
    for role in domain_data.get('roles', []):
        role_content_parts = [
            f"Role: {role.get('role_name', 'Unknown')}",
            f"\nDescription: {role.get('description', '')}",
        ]
        
        if 'detailed_knowledge' in role:
            role_content_parts.append(f"\n\nDetailed Knowledge:\n{role['detailed_knowledge']}")
        
        if 'responsibilities' in role:
            role_content_parts.append("\n\nResponsibilities:")
            for resp in role['responsibilities']:
                role_content_parts.append(f"- {resp}")
        
        if 'key_questions' in role:
            role_content_parts.append("\n\nKey Questions:")
            for q in role['key_questions']:
                role_content_parts.append(f"- {q}")
        
        role_content = "\n".join(role_content_parts)
        
        documents.append({
            "index": doc_index,
            "page_content": role_content,
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
                "framework": framework,
                "type": "compliance",
                "domain_name": domain_name,
                "section": "role",
                "role_name": role.get('role_name', ''),
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "domain_knowledge_json",
                "source_file": str(domain_json_path),
                "keywords": role.get('keywords', []),
                "concepts": role.get('concepts', []),
                "evidence_requirements": role.get('evidence_requirements', [])
            },
            "content_length": len(role_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
    
    # Documents for each use case
    for use_case in domain_data.get('use_cases', []):
        use_case_content_parts = [
            f"Use Case: {use_case.get('name', 'Unknown')}",
            f"\nDescription: {use_case.get('description', '')}",
        ]
        
        if 'detailed_knowledge' in use_case:
            use_case_content_parts.append(f"\n\nDetailed Knowledge:\n{use_case['detailed_knowledge']}")
        
        if 'business_value' in use_case:
            use_case_content_parts.append(f"\n\nBusiness Value: {use_case['business_value']}")
        
        if 'example_queries' in use_case:
            use_case_content_parts.append("\n\nExample Queries:")
            for q in use_case['example_queries']:
                use_case_content_parts.append(f"- {q}")
        
        if 'capabilities' in use_case:
            use_case_content_parts.append("\n\nCapabilities:")
            for cap in use_case['capabilities']:
                use_case_content_parts.append(f"- {cap}")
        
        use_case_content = "\n".join(use_case_content_parts)
        
        documents.append({
            "index": doc_index,
            "page_content": use_case_content,
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
                "framework": framework,
                "type": "compliance",
                "domain_name": domain_name,
                "section": "use_case",
                "use_case_name": use_case.get('name', ''),
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "domain_knowledge_json",
                "source_file": str(domain_json_path),
                "keywords": use_case.get('keywords', []),
                "concepts": use_case.get('concepts', []),
                "evidence_requirements": use_case.get('evidence_requirements', [])
            },
            "content_length": len(use_case_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
    
    # Documents for trust service criteria / security rule safeguards / annex a domains
    criteria_key = None
    criteria_list = []
    if 'trust_service_criteria' in domain_data:
        criteria_key = 'trust_service_criteria'
        criteria_list = domain_data['trust_service_criteria']
    elif 'security_rule_safeguards' in domain_data:
        criteria_key = 'security_rule_safeguards'
        criteria_list = domain_data['security_rule_safeguards']
    elif 'annex_a_control_domains' in domain_data:
        criteria_key = 'annex_a_control_domains'
        criteria_list = domain_data['annex_a_control_domains']
    
    for criteria in criteria_list:
        criteria_content_parts = [
            f"{criteria_key.replace('_', ' ').title()}: {criteria.get('criteria_name') or criteria.get('safeguard_category') or criteria.get('domain_name', 'Unknown')}",
            f"\nDescription: {criteria.get('description', '')}",
        ]
        
        if 'detailed_knowledge' in criteria:
            criteria_content_parts.append(f"\n\nDetailed Knowledge:\n{criteria['detailed_knowledge']}")
        
        if 'common_controls' in criteria:
            criteria_content_parts.append("\n\nCommon Controls:")
            for ctrl in criteria['common_controls']:
                criteria_content_parts.append(f"- {ctrl}")
        elif 'implementation_specifications' in criteria:
            criteria_content_parts.append("\n\nImplementation Specifications:")
            for spec in criteria['implementation_specifications']:
                criteria_content_parts.append(f"- {spec}")
        elif 'controls' in criteria:
            criteria_content_parts.append("\n\nControls:")
            for ctrl in criteria['controls']:
                criteria_content_parts.append(f"- {ctrl}")
        
        criteria_content = "\n".join(criteria_content_parts)
        
        documents.append({
            "index": doc_index,
            "page_content": criteria_content,
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
                "framework": framework,
                "type": "compliance",
                "domain_name": domain_name,
                "section": criteria_key,
                "criteria_name": criteria.get('criteria_name') or criteria.get('safeguard_category') or criteria.get('domain_name', ''),
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "domain_knowledge_json",
                "source_file": str(domain_json_path),
                "keywords": criteria.get('keywords', []),
                "concepts": criteria.get('concepts', []),
                "evidence_requirements": criteria.get('evidence_requirements', [])
            },
            "content_length": len(criteria_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
    
    # Documents for common control areas
    for area in domain_data.get('common_control_areas', []):
        area_content_parts = [
            f"Control Area: {area.get('area_name', 'Unknown')}",
            f"\nDescription: {area.get('description', '')}",
        ]
        
        if 'detailed_knowledge' in area:
            area_content_parts.append(f"\n\nDetailed Knowledge:\n{area['detailed_knowledge']}")
        
        if 'key_questions' in area:
            area_content_parts.append("\n\nKey Questions:")
            for q in area['key_questions']:
                area_content_parts.append(f"- {q}")
        
        area_content = "\n".join(area_content_parts)
        
        documents.append({
            "index": doc_index,
            "page_content": area_content,
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
                "framework": framework,
                "type": "compliance",
                "domain_name": domain_name,
                "section": "control_area",
                "area_name": area.get('area_name', ''),
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "domain_knowledge_json",
                "source_file": str(domain_json_path),
                "keywords": area.get('keywords', []),
                "concepts": area.get('concepts', []),
                "evidence_requirements": area.get('evidence_requirements', [])
            },
            "content_length": len(area_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
    
    # Documents for domain knowledge documents
    for doc in domain_data.get('domain_knowledge_documents', []):
        doc_content = f"Document Title: {doc.get('document_title', 'Unknown')}\n"
        doc_content += f"Document Type: {doc.get('document_type', '')}\n\n"
        doc_content += doc.get('content', '')
        
        documents.append({
            "index": doc_index,
            "page_content": doc_content,
            "metadata": {
                "content_type": "domain_knowledge",
                "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
                "framework": framework,
                "type": "compliance",
                "domain_name": domain_name,
                "section": "domain_knowledge_document",
                "document_title": doc.get('document_title', ''),
                "document_type": doc.get('document_type', ''),
                "extraction_type": "context",
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "domain_knowledge_json",
                "source_file": str(domain_json_path),
                "keywords": doc.get('keywords', []),
                "concepts": doc.get('concepts', []),
                "evidence_types": doc.get('evidence_types', [])
            },
            "content_length": len(doc_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
        doc_index += 1
    
    # Create preview file structure
    preview_data = {
        "metadata": {
            "content_type": "domain_knowledge",
            "domain": domain_data.get('metadata', {}).get('type', 'compliance'),
            "product_name": framework,
            "document_count": len(documents),
            "timestamp": timestamp,
            "indexed_at": datetime.utcnow().isoformat(),
            "source": "domain_knowledge_json",
            "comprehensive": False,
            "framework": framework,
            "source_file": str(domain_json_path)
        },
        "documents": documents
    }
    
    # Write preview file
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(preview_data, f, indent=2)
    
    print(f"Created preview file: {output_path}")
    print(f"  Framework: {framework}")
    print(f"  Documents: {len(documents)}")
    return output_path


def main():
    """Main function to process all domain knowledge files."""
    script_dir = Path(__file__).parent
    examples_dir = script_dir
    # indexing_preview is at knowledge root level
    preview_dir = script_dir.parent.parent.parent / "indexing_preview" / "domain_knowledge"
    
    # Domain knowledge files to process
    domain_files = [
        "SOC2_Security_Compliance_domain.json",
        "HIPAA_Security_Compliance_domain.json",
        "ISO27001_Security_Compliance_domain.json",
        "FEDRAMP_Security_Compliance_domain.json"
    ]
    
    created_files = []
    for domain_file in domain_files:
        domain_path = examples_dir / domain_file
        if domain_path.exists():
            try:
                output_path = create_domain_knowledge_preview(domain_path, preview_dir)
                created_files.append(output_path)
            except Exception as e:
                print(f"Error processing {domain_file}: {e}", file=sys.stderr)
        else:
            print(f"Warning: {domain_file} not found, skipping", file=sys.stderr)
    
    print(f"\nCreated {len(created_files)} preview files in {preview_dir}")
    return created_files


if __name__ == "__main__":
    main()
