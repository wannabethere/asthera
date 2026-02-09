"""
Product Knowledge Base Extraction

Builds product KB hierarchy and contextual edges using the same store names
as CollectionFactory (entities, domain_knowledge, controls, contextual_edges).

Hierarchy (per Untitled-1 / product KB spec):
1. Product information -> domain_knowledge (type=product)
2. Key concepts and features -> entities (type=product)
3. Usage patterns per concept -> embedded in key concept docs or domain_knowledge
4. Best practices and constraints -> embedded or domain_knowledge
5. Key concept -> Controls, risks, policies, procedures, playbooks, tables (contextual edges)

Output: in-memory structures that can be written as preview JSON for ingest_preview_files.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default: one vendor (Snyk) with two products. Override via config file.
DEFAULT_VENDORS: Dict[str, Dict[str, Any]] = {
    "vendor-snyk": {
        "name": "Snyk",
        "products": {
            "Snyk Documentation": {"key_concepts": [
                "Vulnerabilities", "Assets", "Projects", "Integrations", "Configuration",
                "Audit Logs", "Risk Management", "Deployment", "Groups", "Organizations",
                "Memberships and Roles", "Issues", "Artifacts",
            ]},
            "Snyk CLI Reference": {"key_concepts": [
                "Vulnerabilities", "Assets", "Projects", "Integrations", "Configuration",
                "Audit Logs", "Risk Management", "Deployment", "Groups", "Organizations",
                "Memberships and Roles", "Issues", "Artifacts",
            ]},
        },
    },
}

# Edge types for key concept -> X (aligned with contextual graph)
EDGE_TYPES = {
    "control": "KEY_CONCEPT_RELATES_TO_CONTROL",
    "risk": "KEY_CONCEPT_RELATES_TO_RISK",
    "policy": "KEY_CONCEPT_RELATES_TO_POLICY",
    "procedure": "KEY_CONCEPT_RELATES_TO_PROCEDURE",
    "playbook": "KEY_CONCEPT_RELATES_TO_PLAYBOOK",
    "table": "KEY_CONCEPT_RELATES_TO_TABLE",
    "requirement": "KEY_CONCEPT_RELATES_TO_REQUIREMENT",
}


def _concept_search_keywords(concept: str) -> List[str]:
    """Build minimal search keywords from a concept (words >= 2 chars, lower)."""
    words = (concept or "").replace("-", " ").replace("_", " ").split()
    return [w.lower() for w in words if len(w) >= 2]


def _concept_matches_section(concept: str, section: Dict[str, Any]) -> bool:
    """True if section content/heading/title contains the concept or its words (minimal, useful match)."""
    keywords = _concept_search_keywords(concept)
    if not keywords:
        return False
    text_parts = [
        section.get("content") or "",
        section.get("excerpt") or "",
        section.get("heading") or "",
        section.get("heading_path") or "",
        section.get("title") or "",
    ]
    text = " ".join(str(p) for p in text_parts).lower()
    return any(kw in text for kw in keywords)


def _section_searchable_snippet(section: Dict[str, Any], max_len: int = 120) -> str:
    """Heading or title snippet for edge text (searchable)."""
    h = (section.get("heading") or section.get("heading_path") or section.get("title") or "").strip()
    if h:
        return h[:max_len] if len(h) > max_len else h
    title = (section.get("title") or "").strip()
    if title:
        return title[:max_len] if len(title) > max_len else title
    content = (section.get("content") or section.get("excerpt") or "").strip()
    if content:
        return content[:max_len].replace("\n", " ") + ("..." if len(content) > max_len else "")
    return ""


def _section_framework(section: Dict[str, Any]) -> str:
    """Framework/domain from section (e.g. SOC2, vulnerability_management) for searchable edge."""
    domains = section.get("domains") or []
    if domains:
        d = domains[0] if isinstance(domains[0], str) else str(domains[0])
        return d.upper() if d.upper() in ("SOC2", "HIPAA", "ISO27001", "NIST") else d
    for t in (section.get("supports_traversals") or []):
        if isinstance(t, str) and "category:" in t.lower():
            return t.split(":", 1)[-1].strip()
    return ""


def load_product_key_concepts_config(path: Optional[Path]) -> Dict[str, List[str]]:
    """Load flat product -> key_concepts (legacy). Prefer load_vendors_config for vendor/product structure."""
    if path and path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "vendors" in data:
                # Build flat map from vendors.products for backward compat
                flat = {}
                for v_id, v_data in (data.get("vendors") or {}).items():
                    for p_name, p_data in (v_data.get("products") or {}).items():
                        flat[p_name] = (p_data.get("key_concepts") or [])
                if flat:
                    return flat
            if isinstance(data, dict):
                if "product_key_concepts" in data and data["product_key_concepts"]:
                    return data["product_key_concepts"]
                # Direct flat map
                if not any(k in data for k in ("vendors", "product_key_concepts", "version", "description")):
                    return {k: v for k, v in data.items() if isinstance(v, list)}
            if isinstance(data, list):
                return {item.get("product", ""): item.get("key_concepts", []) for item in data if item.get("product")}
        except Exception as e:
            logger.warning(f"Could not load product key concepts from {path}: {e}")
    return _vendors_to_flat(DEFAULT_VENDORS)


def _vendors_to_flat(vendors: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Build flat product_name -> key_concepts from vendors.products."""
    flat: Dict[str, List[str]] = {}
    for v_data in (vendors or {}).values():
        for p_name, p_data in (v_data.get("products") or {}).items():
            flat[p_name] = p_data.get("key_concepts") or []
    return flat


def load_vendors_config(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """
    Load vendors and products from JSON. Returns product_name -> { vendor_id, vendor_name, product_name, key_concepts }.
    A vendor can have multiple products; same hierarchy applies to all.
    Accepts: { "vendors": { "vendor-id": { "name": "...", "products": { "Product Name": { "key_concepts": [...] } } } } }
    or legacy { "product_key_concepts": { "Product Name": [...] } } (vendor_id/vendor_name then "").
    """
    if path and path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _vendors_to_product_map(DEFAULT_VENDORS)
            if "vendors" in data and data["vendors"]:
                return _vendors_to_product_map(data["vendors"])
            if "product_key_concepts" in data and data["product_key_concepts"]:
                # Legacy flat: product_name -> key_concepts; no vendor
                return {
                    p_name: {"vendor_id": "", "vendor_name": "", "product_name": p_name, "key_concepts": concepts}
                    for p_name, concepts in data["product_key_concepts"].items()
                }
        except Exception as e:
            logger.warning(f"Could not load vendors config from {path}: {e}")
    return _vendors_to_product_map(DEFAULT_VENDORS)


def _vendors_to_product_map(vendors: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build product_name -> { vendor_id, vendor_name, product_name, key_concepts } from vendors."""
    out: Dict[str, Dict[str, Any]] = {}
    for v_id, v_data in (vendors or {}).items():
        v_name = v_data.get("name") or v_id
        for p_name, p_data in (v_data.get("products") or {}).items():
            out[p_name] = {
                "vendor_id": v_id,
                "vendor_name": v_name,
                "product_name": p_name,
                "key_concepts": p_data.get("key_concepts") or [],
            }
    return out


def _find_product_for_source(source_id: str, product_map: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Return product name from product_map that matches source_id (exact or substring)."""
    if not source_id or not product_map:
        return None
    s = (source_id or "").strip()
    if s in product_map:
        return s
    for product in product_map:
        if product in s or s in product:
            return product
    return None


def load_enriched_sections(
    preview_dir: Path,
    enriched_subdirs: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Load all sections from enriched/*.json under preview_dir. Returns flat list of sections with doc_type."""
    subdirs = enriched_subdirs or ["enriched", "enriched_vendor"]
    sections: List[Dict[str, Any]] = []
    for sub in subdirs:
        base = preview_dir / sub
        if not base.exists() or not base.is_dir():
            continue
        for json_path in base.glob("*.json"):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                doc_type = data.get("doc_type", json_path.stem.lower())
                for sec in data.get("sections") or []:
                    sec = dict(sec)
                    sec["_doc_type"] = doc_type
                    sec["_source_file"] = str(json_path)
                    sections.append(sec)
            except Exception as e:
                logger.warning(f"Skip {json_path}: {e}")
    return sections


def build_product_entities_and_edges(
    sections: List[Dict[str, Any]],
    product_map: Dict[str, Dict[str, Any]],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """
    Build product info docs, key concept entity docs, and contextual edge docs.
    product_map: product_name -> { vendor_id, vendor_name, product_name, key_concepts }.
    Same hierarchy applies to all vendors and products.
    """
    product_info_docs: List[Dict[str, Any]] = []
    key_concept_docs: List[Dict[str, Any]] = []
    edge_docs: List[Dict[str, Any]] = []

    # Unique product names we've seen (from source_id)
    products_seen: Dict[str, str] = {}  # product_name -> source_id
    for sec in sections:
        source_id = sec.get("source_id") or ""
        product = _find_product_for_source(source_id, product_map)
        if product and product not in products_seen:
            products_seen[product] = source_id

    # 1. Product information (one doc per product) -> domain_knowledge, type=product
    for product, source_id in products_seen.items():
        entry = product_map.get(product, {})
        concepts = entry.get("key_concepts") or []
        vendor_id = entry.get("vendor_id") or ""
        vendor_name = entry.get("vendor_name") or ""
        page_content = f"Vendor: {vendor_name}. Product: {product}. Source: {source_id}. Key concepts: {', '.join(concepts)}."
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"product_info_{vendor_id}_{product}"))
        meta = {
            "id": doc_id,
            "type": "product",
            "store_name": "domain_knowledge",
            "source_content_type": "product_purpose",
            "product_name": product,
            "source_id": source_id,
            "key_concepts": concepts,
        }
        if vendor_id:
            meta["vendor_id"] = vendor_id
        if vendor_name:
            meta["vendor_name"] = vendor_name
        product_info_docs.append({"page_content": page_content, "metadata": meta})

    # 2. Key concept entities (one doc per product+concept) -> entities, type=product
    key_concept_ids: Dict[Tuple[str, str], str] = {}  # (product, concept) -> entity id
    for product, source_id in products_seen.items():
        entry = product_map.get(product, {})
        concepts = entry.get("key_concepts") or []
        vendor_id = entry.get("vendor_id") or ""
        vendor_name = entry.get("vendor_name") or ""
        for concept in concepts:
            cid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"key_concept_{vendor_id}_{product}_{concept}"))
            key_concept_ids[(product, concept)] = cid
            page_content = f"Key concept: {concept}. Vendor: {vendor_name}. Product: {product}. Relates to controls, risks, policies, procedures, playbooks, and tables."
            meta = {
                "id": cid,
                "type": "product",
                "store_name": "entities",
                "source_content_type": "product_key_concepts",
                "product_name": product,
                "key_concept": concept,
                "source_id": source_id,
            }
            if vendor_id:
                meta["vendor_id"] = vendor_id
            if vendor_name:
                meta["vendor_name"] = vendor_name
            key_concept_docs.append({
                "page_content": page_content,
                "metadata": meta,
            })

    # 3. Contextual edges: key_concept -> section (playbook, procedure, policy, control, etc.) or -> control/requirement
    context_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "product_kb_context"))
    edge_id_counter = [0]

    def make_edge(
        source_entity_id: str,
        source_entity_type: str,
        target_entity_id: str,
        target_entity_type: str,
        edge_type: str,
        document: str = "",
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        edge_id_counter[0] += 1
        eid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"product_kb_edge_{source_entity_id}_{target_entity_id}_{edge_id_counter[0]}"))
        meta: Dict[str, Any] = {
            "edge_id": eid,
            "source_entity_id": source_entity_id,
            "source_entity_type": source_entity_type,
            "target_entity_id": target_entity_id,
            "target_entity_type": target_entity_type,
            "edge_type": edge_type,
            "context_id": context_id,
            "relevance_score": 0.8,
        }
        if keywords:
            meta["keywords"] = keywords
        return {
            "page_content": document or f"{source_entity_type} {source_entity_id} relates to {target_entity_type} {target_entity_id}",
            "metadata": meta,
        }

    keyword_match_only = True  # Only create section edges when concept appears in section (minimal, useful)

    for sec in sections:
        source_id = sec.get("source_id") or ""
        product = _find_product_for_source(source_id, product_map)
        if not product:
            continue
        concepts = (product_map.get(product) or {}).get("key_concepts") or []
        doc_type = (sec.get("_doc_type") or "domain_knowledge").lower()
        section_id = sec.get("section_id") or sec.get("doc_id") or ""
        if not section_id:
            continue
        framework = _section_framework(sec)
        snippet = _section_searchable_snippet(sec)
        edge_type = EDGE_TYPES.get(doc_type) or "KEY_CONCEPT_RELATES_TO_PLAYBOOK"
        if doc_type == "control":
            edge_type = EDGE_TYPES["control"]
        elif doc_type in ("policy", "standard", "framework", "requirement"):
            edge_type = EDGE_TYPES.get("policy") or EDGE_TYPES.get("requirement") or "KEY_CONCEPT_RELATES_TO_POLICY"
        elif doc_type == "procedure":
            edge_type = EDGE_TYPES["procedure"]
        elif doc_type == "playbook":
            edge_type = EDGE_TYPES["playbook"]

        for concept in concepts:
            if keyword_match_only and not _concept_matches_section(concept, sec):
                continue
            cid = key_concept_ids.get((product, concept))
            if not cid:
                continue
            doc_parts = [f"Key concept {concept}", f"Product {product}", doc_type]
            if snippet:
                doc_parts.append(f"Section: {snippet}")
            if source_id:
                doc_parts.append(source_id)
            if framework:
                doc_parts.append(framework)
            doc_text = " | ".join(doc_parts)
            kw = [concept, product, doc_type]
            if snippet:
                kw.append(snippet[:60])
            if framework:
                kw.append(framework)
            edge_docs.append(make_edge(
                source_entity_id=cid,
                source_entity_type="key_concept",
                target_entity_id=section_id,
                target_entity_type=doc_type,
                edge_type=edge_type,
                document=doc_text,
                keywords=kw,
            ))

        for control_ref in sec.get("controls") or []:
            control_id = control_ref if isinstance(control_ref, str) else (control_ref.get("id") or control_ref.get("control_id") or str(control_ref))
            for concept in concepts:
                cid = key_concept_ids.get((product, concept))
                if not cid:
                    continue
                doc_text = f"Key concept {concept} | Control {control_id} | Product {product}"
                if framework:
                    doc_text += f" | {framework}"
                kw = [concept, control_id, product]
                if framework:
                    kw.append(framework)
                edge_docs.append(make_edge(
                    source_entity_id=cid,
                    source_entity_type="key_concept",
                    target_entity_id=control_id,
                    target_entity_type="control",
                    edge_type=EDGE_TYPES["control"],
                    document=doc_text,
                    keywords=kw,
                ))
        for req_ref in sec.get("requirements") or []:
            req_id = req_ref if isinstance(req_ref, str) else (req_ref.get("id") or req_ref.get("requirement_id") or str(req_ref))
            for concept in concepts:
                cid = key_concept_ids.get((product, concept))
                if not cid:
                    continue
                doc_text = f"Key concept {concept} | Requirement {req_id} | Product {product}"
                if framework:
                    doc_text += f" | {framework}"
                kw = [concept, req_id, product]
                if framework:
                    kw.append(framework)
                edge_docs.append(make_edge(
                    source_entity_id=cid,
                    source_entity_type="key_concept",
                    target_entity_id=req_id,
                    target_entity_type="requirement",
                    edge_type=EDGE_TYPES["requirement"],
                    document=doc_text,
                    keywords=kw,
                ))

        for clause in (sec.get("entities") or {}).get("framework_clauses") or []:
            for concept in concepts:
                cid = key_concept_ids.get((product, concept))
                if not cid:
                    continue
                doc_text = f"Key concept {concept} | Control {clause} | Product {product}"
                if framework:
                    doc_text += f" | {framework}"
                kw = [concept, clause, product]
                if framework:
                    kw.append(framework)
                edge_docs.append(make_edge(
                    source_entity_id=cid,
                    source_entity_type="key_concept",
                    target_entity_id=clause,
                    target_entity_type="control",
                    edge_type=EDGE_TYPES["control"],
                    document=doc_text,
                    keywords=kw,
                ))

    return product_info_docs, key_concept_docs, edge_docs


def run_extraction(
    preview_dir: Path,
    enriched_subdirs: Optional[List[str]] = None,
    product_key_concepts_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run full product KB extraction from a preview directory.

    Returns dict with keys:
      - product_info_documents
      - product_key_concept_documents
      - contextual_edge_documents
      - stats (counts)
    """
    product_map = load_vendors_config(product_key_concepts_path)
    sections = load_enriched_sections(preview_dir, enriched_subdirs)
    vendor_count = len({v.get("vendor_id") or "" for v in product_map.values() if v.get("vendor_id")})
    logger.info(f"Loaded {len(sections)} enriched sections from {preview_dir}; {len(product_map)} products from {vendor_count} vendors")
    product_info_docs, key_concept_docs, edge_docs = build_product_entities_and_edges(
        sections, product_map
    )
    return {
        "product_info_documents": product_info_docs,
        "product_key_concept_documents": key_concept_docs,
        "contextual_edge_documents": edge_docs,
        "stats": {
            "sections_loaded": len(sections),
            "product_info_documents": len(product_info_docs),
            "product_key_concept_documents": len(key_concept_docs),
            "contextual_edge_documents": len(edge_docs),
        },
    }
