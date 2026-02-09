#!/usr/bin/env python3
"""
Script to create hierarchical contextual edges for compliance knowledge graph.
Creates edges representing relationships:
- Framework -> Controls
- Framework -> Policies
- Policies -> Controls
- Policies -> Actors
- Controls -> Actors
- Controls -> Risks
- Policies -> Risks
- Actors -> Domain Knowledge
- Product -> Domain Knowledge
"""
import json
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set
from collections import defaultdict

def generate_edge_id(source_id: str, target_id: str, edge_type: str) -> str:
    """Generate a unique edge ID."""
    combined = f"{source_id}_{target_id}_{edge_type}"
    hash_val = hashlib.md5(combined.encode()).hexdigest()[:12]
    return f"edge_{hash_val}"


def extract_frameworks_from_domain_knowledge(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract framework information from domain knowledge files."""
    frameworks = {}
    domain_knowledge_dir = preview_dir / "domain_knowledge"
    
    if not domain_knowledge_dir.exists():
        return frameworks
    
    for json_file in domain_knowledge_dir.glob("*.json"):
        if "summary" in json_file.name:
            continue
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            top_metadata = data.get("metadata", {})
            framework = top_metadata.get("framework")
            
            if framework and framework not in frameworks:
                frameworks[framework] = {
                    "entity_id": f"framework_{framework.lower()}",
                    "entity_name": framework,
                    "entity_type": "framework",
                    "framework": framework,
                    "source_file": str(json_file)
                }
        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return frameworks


def extract_actors_from_domain_knowledge(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract actor information from domain knowledge files."""
    actors = {}
    domain_knowledge_dir = preview_dir / "domain_knowledge"
    
    if not domain_knowledge_dir.exists():
        return actors
    
    for json_file in domain_knowledge_dir.glob("*actors*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            for doc in data.get("documents", []):
                metadata = doc.get("metadata", {})
                actor_name = metadata.get("actor_name")
                
                if actor_name and actor_name not in actors:
                    actors[actor_name] = {
                        "entity_id": f"actor_{actor_name.lower().replace(' ', '_')}",
                        "entity_name": actor_name,
                        "entity_type": "actor",
                        "type": "compliance_actor",
                        "source_file": str(json_file)
                    }
        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return actors


def extract_controls_from_preview_files(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract control information from preview files."""
    controls = {}
    
    # From soc2_controls
    soc2_dir = preview_dir / "soc2_controls"
    if soc2_dir.exists():
        for json_file in soc2_dir.glob("*.json"):
            if "summary" in json_file.name:
                continue
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                for doc in data.get("documents", []):
                    metadata = doc.get("metadata", {})
                    control_id = metadata.get("control_id")
                    control_name = metadata.get("control_name")
                    framework = metadata.get("framework", "SOC2")
                    
                    if control_id:
                        control_key = f"{framework}_{control_id}"
                        if control_key not in controls:
                            controls[control_key] = {
                                "entity_id": f"control_{framework.lower()}_{control_id.lower().replace('.', '_')}",
                                "entity_name": control_name or control_id,
                                "entity_type": "control",
                                "control_id": control_id,
                                "framework": framework,
                                "source_file": str(json_file)
                            }
            except Exception as e:
                print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    # From riskmanagement_risk_controls
    risk_dir = preview_dir / "riskmanagement_risk_controls"
    if risk_dir.exists():
        for json_file in risk_dir.glob("*.json"):
            if "summary" in json_file.name:
                continue
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                for doc in data.get("documents", []):
                    metadata = doc.get("metadata", {})
                    if metadata.get("extraction_type") == "control":
                        control_id = metadata.get("control_id")
                        control_name = metadata.get("control_name")
                        framework = metadata.get("framework", "Risk Management")
                        
                        if control_id:
                            control_key = f"{framework}_{control_id}"
                            if control_key not in controls:
                                controls[control_key] = {
                                    "entity_id": f"control_{framework.lower().replace(' ', '_')}_{control_id.lower().replace('.', '_')}",
                                    "entity_name": control_name or control_id,
                                    "entity_type": "control",
                                    "control_id": control_id,
                                    "framework": framework,
                                    "source_file": str(json_file)
                                }
            except Exception as e:
                print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return controls


def extract_policies_from_preview_files(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract policy information from preview files."""
    policies = {}
    policy_dir = preview_dir / "policy_documents"
    
    if not policy_dir.exists():
        return policies
    
    for json_file in policy_dir.glob("*.json"):
        if "summary" in json_file.name:
            continue
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            for doc in data.get("documents", []):
                metadata = doc.get("metadata", {})
                if metadata.get("extraction_type") == "entities":
                    # Try to parse entities from page_content
                    try:
                        content = doc.get("page_content", "{}")
                        if isinstance(content, str):
                            entities_data = json.loads(content)
                            entities = entities_data.get("entities", [])
                            
                            for entity in entities:
                                if entity.get("entity_type") == "policy":
                                    policy_name = entity.get("entity_name")
                                    if policy_name and policy_name not in policies:
                                        policies[policy_name] = {
                                            "entity_id": f"policy_{policy_name.lower().replace(' ', '_')}",
                                            "entity_name": policy_name,
                                            "entity_type": "policy",
                                            "framework": metadata.get("framework", "policy"),
                                            "source_file": str(json_file)
                                        }
                    except:
                        pass
                
                # Also check metadata for policy_name
                policy_name = metadata.get("policy_name")
                if policy_name and policy_name not in policies:
                    policies[policy_name] = {
                        "entity_id": f"policy_{policy_name.lower().replace(' ', '_')}",
                        "entity_name": policy_name,
                        "entity_type": "policy",
                        "framework": metadata.get("framework", "policy"),
                        "source_file": str(json_file)
                    }
        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return policies


def extract_risks_from_preview_files(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract risk information from preview files."""
    risks = {}
    risk_dir = preview_dir / "riskmanagement_risk_controls"
    
    if not risk_dir.exists():
        return risks
    
    for json_file in risk_dir.glob("*.json"):
        if "summary" in json_file.name:
            continue
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            for doc in data.get("documents", []):
                metadata = doc.get("metadata", {})
                # Extract risk scenario from content
                content = doc.get("page_content", "")
                
                # Try multiple extraction methods
                risk_name = None
                
                # Method 1: Look for "## Risk Scenario" followed by value
                if "## Risk Scenario" in content or "Risk Scenario" in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if "## Risk Scenario" in line or ("Risk Scenario" in line and "**Value**" in lines[i+1] if i+1 < len(lines) else False):
                            # Look for the value line
                            for j in range(i, min(i+5, len(lines))):
                                if "**Value**" in lines[j] and j+1 < len(lines):
                                    risk_name = lines[j+1].strip()
                                    break
                            if risk_name:
                                break
                
                # Method 2: Look in fields extraction_type documents
                if not risk_name and metadata.get("extraction_type") == "fields":
                    try:
                        # Try to parse JSON from page_content
                        if "Risk Scenario" in content:
                            # Look for pattern: **Value**: <risk scenario>
                            import re
                            match = re.search(r'\*\*Value\*\*:\s*(.+?)(?:\n|$)', content)
                            if match:
                                risk_name = match.group(1).strip()
                    except:
                        pass
                
                # Method 3: Extract from control description if it mentions risk
                if not risk_name and "risk" in content.lower():
                    # Use control name as risk identifier if it's risk-related
                    control_name = metadata.get("control_name", "")
                    if control_name and "risk" in control_name.lower():
                        risk_name = f"Risk related to {control_name}"
                
                if risk_name and risk_name not in risks and len(risk_name) > 10:  # Filter out very short names
                    risk_key = risk_name[:100]  # Limit key length
                    if risk_key not in risks:
                        risks[risk_key] = {
                            "entity_id": f"risk_{hashlib.md5(risk_name.encode()).hexdigest()[:12]}",
                            "entity_name": risk_name,
                            "entity_type": "risk",
                            "framework": metadata.get("framework", "Risk Management"),
                            "control_id": metadata.get("control_id"),
                            "source_file": str(json_file)
                        }
        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return risks


def extract_products_from_preview_files(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract product information from preview files."""
    products = {}
    product_dir = preview_dir / "product_docs"
    
    if not product_dir.exists():
        return products
    
    for json_file in product_dir.glob("*.json"):
        if "summary" in json_file.name:
            continue
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            top_metadata = data.get("metadata", {})
            product_name = top_metadata.get("product_name")
            
            if product_name and product_name not in products:
                products[product_name] = {
                    "entity_id": f"product_{product_name.lower().replace(' ', '_')}",
                    "entity_name": product_name,
                    "entity_type": "product",
                    "product_name": product_name,
                    "source_file": str(json_file)
                }
        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return products


def extract_domain_knowledge_sections(preview_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract domain knowledge sections as entities."""
    domain_knowledge_entities = {}
    domain_knowledge_dir = preview_dir / "domain_knowledge"
    
    if not domain_knowledge_dir.exists():
        return domain_knowledge_entities
    
    for json_file in domain_knowledge_dir.glob("*.json"):
        if "summary" in json_file.name:
            continue
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            top_metadata = data.get("metadata", {})
            framework = top_metadata.get("framework", "compliance")
            domain_name = top_metadata.get("domain_name") or top_metadata.get("product_name", "Unknown")
            
            for doc in data.get("documents", []):
                metadata = doc.get("metadata", {})
                section = metadata.get("section")
                section_title = metadata.get("section_title")
                
                if section:
                    dk_key = f"{framework}_{section}"
                    if dk_key not in domain_knowledge_entities:
                        domain_knowledge_entities[dk_key] = {
                            "entity_id": f"domain_knowledge_{framework.lower()}_{section}",
                            "entity_name": section_title or section,
                            "entity_type": "domain_knowledge",
                            "section": section,
                            "framework": framework,
                            "domain_name": domain_name,
                            "source_file": str(json_file)
                        }
        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)
    
    return domain_knowledge_entities


def create_hierarchical_edges(
    frameworks: Dict[str, Dict],
    controls: Dict[str, Dict],
    policies: Dict[str, Dict],
    actors: Dict[str, Dict],
    risks: Dict[str, Dict],
    products: Dict[str, Dict],
    domain_knowledge: Dict[str, Dict]
) -> List[Dict[str, Any]]:
    """Create hierarchical edges based on relationships."""
    edges = []
    
    # Framework -> Controls
    for framework_key, framework in frameworks.items():
        framework_id = framework["entity_id"]
        framework_name = framework["entity_name"]
        
        for control_key, control in controls.items():
            if control.get("framework") == framework_name:
                edge_id = generate_edge_id(framework_id, control["entity_id"], "HAS_CONTROL")
                edges.append({
                    "edge_id": edge_id,
                    "source_entity_id": framework_id,
                    "source_entity_type": "framework",
                    "target_entity_id": control["entity_id"],
                    "target_entity_type": "control",
                    "edge_type": "HAS_CONTROL",
                    "document": f"{framework_name} framework has control {control['entity_name']}",
                    "context_id": f"framework_{framework_name.lower()}",
                    "relevance_score": 1.0,
                    "framework": framework_name
                })
    
    # Framework -> Policies
    for framework_key, framework in frameworks.items():
        framework_id = framework["entity_id"]
        framework_name = framework["entity_name"]
        
        for policy_key, policy in policies.items():
            policy_framework = policy.get("framework", "policy")
            # Link policies to frameworks (SOC2, HIPAA, etc. or generic "policy")
            if framework_name == "SOC2" or framework_name == policy_framework or policy_framework == "policy":
                edge_id = generate_edge_id(framework_id, policy["entity_id"], "HAS_POLICY")
                edges.append({
                    "edge_id": edge_id,
                    "source_entity_id": framework_id,
                    "source_entity_type": "framework",
                    "target_entity_id": policy["entity_id"],
                    "target_entity_type": "policy",
                    "edge_type": "HAS_POLICY",
                    "document": f"{framework_name} framework has policy {policy['entity_name']}",
                    "context_id": f"framework_{framework_name.lower()}",
                    "relevance_score": 1.0,
                    "framework": framework_name
                })
    
    # Policies -> Controls
    for policy_key, policy in policies.items():
        policy_id = policy["entity_id"]
        policy_framework = policy.get("framework", "policy")
        
        for control_key, control in controls.items():
            control_framework = control.get("framework", "")
            # Link controls to policies if they're in the same framework context
            if policy_framework == "policy" or control_framework == policy_framework:
                edge_id = generate_edge_id(policy_id, control["entity_id"], "DEFINES_CONTROL")
                edges.append({
                    "edge_id": edge_id,
                    "source_entity_id": policy_id,
                    "source_entity_type": "policy",
                    "target_entity_id": control["entity_id"],
                    "target_entity_type": "control",
                    "edge_type": "DEFINES_CONTROL",
                    "document": f"Policy {policy['entity_name']} defines control {control['entity_name']}",
                    "context_id": f"policy_{policy_key.lower().replace(' ', '_')}",
                    "relevance_score": 0.9,
                    "framework": control_framework or policy_framework
                })
    
    # Policies -> Actors
    for policy_key, policy in policies.items():
        policy_id = policy["entity_id"]
        policy_framework = policy.get("framework", "policy")
        
        for actor_key, actor in actors.items():
            edge_id = generate_edge_id(policy_id, actor["entity_id"], "REQUIRES_ACTOR")
            edges.append({
                "edge_id": edge_id,
                "source_entity_id": policy_id,
                "source_entity_type": "policy",
                "target_entity_id": actor["entity_id"],
                "target_entity_type": "actor",
                "edge_type": "REQUIRES_ACTOR",
                "document": f"Policy {policy['entity_name']} requires actor {actor['entity_name']}",
                "context_id": f"policy_{policy_key.lower().replace(' ', '_')}",
                "relevance_score": 0.8,
                "framework": policy_framework if policy_framework != "policy" else "compliance"
            })
    
    # Controls -> Actors
    for control_key, control in controls.items():
        control_id = control["entity_id"]
        control_framework = control.get("framework", "")
        
        for actor_key, actor in actors.items():
            edge_id = generate_edge_id(control_id, actor["entity_id"], "MANAGED_BY_ACTOR")
            edges.append({
                "edge_id": edge_id,
                "source_entity_id": control_id,
                "source_entity_type": "control",
                "target_entity_id": actor["entity_id"],
                "target_entity_type": "actor",
                "edge_type": "MANAGED_BY_ACTOR",
                "document": f"Control {control['entity_name']} is managed by actor {actor['entity_name']}",
                "context_id": f"control_{control_key.lower().replace('.', '_')}",
                "relevance_score": 0.9,
                "framework": control_framework or "compliance"
            })
    
    # Controls -> Risks
    for control_key, control in controls.items():
        control_id = control["entity_id"]
        control_framework = control.get("framework", "")
        
        for risk_key, risk in risks.items():
            risk_framework = risk.get("framework", "")
            # Link controls to risks in the same framework
            if control_framework == risk_framework or control_framework == "Risk Management":
                edge_id = generate_edge_id(control_id, risk["entity_id"], "MITIGATES_RISK")
                edges.append({
                    "edge_id": edge_id,
                    "source_entity_id": control_id,
                    "source_entity_type": "control",
                    "target_entity_id": risk["entity_id"],
                    "target_entity_type": "risk",
                    "edge_type": "MITIGATES_RISK",
                    "document": f"Control {control['entity_name']} mitigates risk {risk['entity_name']}",
                    "context_id": f"control_{control_key.lower().replace('.', '_')}",
                    "relevance_score": 0.9,
                    "framework": control_framework or risk_framework or "compliance"
                })
    
    # Policies -> Risks
    for policy_key, policy in policies.items():
        policy_id = policy["entity_id"]
        policy_framework = policy.get("framework", "policy")
        
        for risk_key, risk in risks.items():
            risk_framework = risk.get("framework", "")
            edge_id = generate_edge_id(policy_id, risk["entity_id"], "ADDRESSES_RISK")
            edges.append({
                "edge_id": edge_id,
                "source_entity_id": policy_id,
                "source_entity_type": "policy",
                "target_entity_id": risk["entity_id"],
                "target_entity_type": "risk",
                "edge_type": "ADDRESSES_RISK",
                "document": f"Policy {policy['entity_name']} addresses risk {risk['entity_name']}",
                "context_id": f"policy_{policy_key.lower().replace(' ', '_')}",
                "relevance_score": 0.8,
                "framework": policy_framework if policy_framework != "policy" else (risk_framework or "compliance")
            })
    
    # Actors -> Domain Knowledge
    for actor_key, actor in actors.items():
        actor_id = actor["entity_id"]
        
        for dk_key, dk in domain_knowledge.items():
            dk_framework = dk.get("framework", "compliance")
            edge_id = generate_edge_id(actor_id, dk["entity_id"], "USES_DOMAIN_KNOWLEDGE")
            edges.append({
                "edge_id": edge_id,
                "source_entity_id": actor_id,
                "source_entity_type": "actor",
                "target_entity_id": dk["entity_id"],
                "target_entity_type": "domain_knowledge",
                "edge_type": "USES_DOMAIN_KNOWLEDGE",
                "document": f"Actor {actor['entity_name']} uses domain knowledge {dk['entity_name']}",
                "context_id": f"actor_{actor_key.lower().replace(' ', '_')}",
                "relevance_score": 0.8,
                "framework": dk_framework
            })
    
    # Product -> Domain Knowledge
    for product_key, product in products.items():
        product_id = product["entity_id"]
        
        for dk_key, dk in domain_knowledge.items():
            dk_framework = dk.get("framework", "compliance")
            # Link products to relevant domain knowledge
            edge_id = generate_edge_id(product_id, dk["entity_id"], "RELATED_TO_DOMAIN_KNOWLEDGE")
            edges.append({
                "edge_id": edge_id,
                "source_entity_id": product_id,
                "source_entity_type": "product",
                "target_entity_id": dk["entity_id"],
                "target_entity_type": "domain_knowledge",
                "edge_type": "RELATED_TO_DOMAIN_KNOWLEDGE",
                "document": f"Product {product['entity_name']} is related to domain knowledge {dk['entity_name']}",
                "context_id": f"product_{product_key.lower().replace(' ', '_')}",
                "relevance_score": 0.7,
                "framework": dk_framework,
                "product_name": product_key
            })
    
    return edges


def create_contextual_edges_preview(edges: List[Dict[str, Any]], output_dir: Path) -> Path:
    """Create preview file for contextual edges."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"contextual_edges_{timestamp}_compliance.json"
    
    # Convert edges to document format
    # page_content should be the document (human-readable description)
    # All edge fields should be in metadata
    documents = []
    for i, edge in enumerate(edges):
        # page_content is the document field (human-readable description)
        page_content = edge.get("document", f"{edge['source_entity_id']} {edge['edge_type']} {edge['target_entity_id']}")
        
        documents.append({
            "index": i,
            "page_content": page_content,
            "metadata": {
                "content_type": "contextual_edges",
                "edge_id": edge["edge_id"],
                "source_entity_id": edge["source_entity_id"],
                "source_entity_type": edge["source_entity_type"],
                "target_entity_id": edge["target_entity_id"],
                "target_entity_type": edge["target_entity_type"],
                "edge_type": edge["edge_type"],
                "context_id": edge.get("context_id", ""),
                "relevance_score": edge.get("relevance_score", 0.0),
                "domain": "compliance",
                "framework": edge.get("framework", "compliance"),
                "indexed_at": datetime.utcnow().isoformat(),
                "source": "hierarchical_edge_generation",
                # Add optional fields if present
                **({k: v for k, v in edge.items() if k in [
                    "priority_in_context", "risk_score_in_context", "likelihood_in_context",
                    "impact_in_context", "implementation_complexity", "estimated_effort_hours",
                    "estimated_cost", "automation_possible", "evidence_available", "data_quality",
                    "created_at", "valid_until"
                ] and v is not None})
            },
            "content_length": len(page_content),
            "metadata_keys": list(documents[-1]["metadata"].keys()) if documents else []
        })
    
    preview_data = {
        "metadata": {
            "content_type": "contextual_edges",
            "domain": "compliance",
            "product_name": "Compliance Hierarchical Edges",
            "document_count": len(documents),
            "timestamp": timestamp,
            "indexed_at": datetime.utcnow().isoformat(),
            "source": "hierarchical_edge_generation",
            "comprehensive": False,
            "framework": "compliance"
        },
        "documents": documents
    }
    
    with open(output_file, 'w') as f:
        json.dump(preview_data, f, indent=2)
    
    print(f"Created contextual edges preview: {output_file}")
    print(f"  Total edges: {len(edges)}")
    
    # Print edge type summary
    edge_type_counts = defaultdict(int)
    for edge in edges:
        edge_type_counts[edge["edge_type"]] += 1
    
    print(f"\nEdge type breakdown:")
    for edge_type, count in sorted(edge_type_counts.items()):
        print(f"  - {edge_type}: {count} edges")
    
    return output_file


def main():
    """Main function to create hierarchical edges."""
    script_dir = Path(__file__).parent
    preview_dir = script_dir.parent.parent.parent / "indexing_preview"
    output_dir = preview_dir / "contextual_edges"
    
    print("="*70)
    print("Creating Hierarchical Contextual Edges")
    print("="*70)
    
    # Extract entities
    print("\nExtracting entities...")
    frameworks = extract_frameworks_from_domain_knowledge(preview_dir)
    print(f"  Found {len(frameworks)} frameworks: {list(frameworks.keys())}")
    
    controls = extract_controls_from_preview_files(preview_dir)
    print(f"  Found {len(controls)} controls")
    
    policies = extract_policies_from_preview_files(preview_dir)
    print(f"  Found {len(policies)} policies: {list(policies.keys())[:5]}...")
    
    actors = extract_actors_from_domain_knowledge(preview_dir)
    print(f"  Found {len(actors)} actors: {list(actors.keys())}")
    
    risks = extract_risks_from_preview_files(preview_dir)
    print(f"  Found {len(risks)} risks")
    
    products = extract_products_from_preview_files(preview_dir)
    print(f"  Found {len(products)} products: {list(products.keys())}")
    
    domain_knowledge = extract_domain_knowledge_sections(preview_dir)
    print(f"  Found {len(domain_knowledge)} domain knowledge sections")
    
    # Create edges
    print("\nCreating hierarchical edges...")
    edges = create_hierarchical_edges(
        frameworks, controls, policies, actors, risks, products, domain_knowledge
    )
    
    print(f"  Created {len(edges)} edges")
    
    # Create preview file
    print("\nGenerating preview file...")
    output_file = create_contextual_edges_preview(edges, output_dir)
    
    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"✓ Created {len(edges)} hierarchical edges")
    print(f"✓ Preview file: {output_file}")
    print(f"\nEdge relationships created:")
    print(f"  - Framework -> Controls: {sum(1 for e in edges if e['edge_type'] == 'HAS_CONTROL')}")
    print(f"  - Framework -> Policies: {sum(1 for e in edges if e['edge_type'] == 'HAS_POLICY')}")
    print(f"  - Policies -> Controls: {sum(1 for e in edges if e['edge_type'] == 'DEFINES_CONTROL')}")
    print(f"  - Policies -> Actors: {sum(1 for e in edges if e['edge_type'] == 'REQUIRES_ACTOR')}")
    print(f"  - Controls -> Actors: {sum(1 for e in edges if e['edge_type'] == 'MANAGED_BY_ACTOR')}")
    print(f"  - Controls -> Risks: {sum(1 for e in edges if e['edge_type'] == 'MITIGATES_RISK')}")
    print(f"  - Policies -> Risks: {sum(1 for e in edges if e['edge_type'] == 'ADDRESSES_RISK')}")
    print(f"  - Actors -> Domain Knowledge: {sum(1 for e in edges if e['edge_type'] == 'USES_DOMAIN_KNOWLEDGE')}")
    print(f"  - Product -> Domain Knowledge: {sum(1 for e in edges if e['edge_type'] == 'RELATED_TO_DOMAIN_KNOWLEDGE')}")
    
    return output_file


if __name__ == "__main__":
    main()
