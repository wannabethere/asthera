"""
Standalone product KB extraction (no app.* or langchain deps).
Used by extract_product_kb_preview CLI so it can run without full knowledge app.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

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
    words = (concept or "").replace("-", " ").replace("_", " ").split()
    return [w.lower() for w in words if len(w) >= 2]


def _concept_matches_section(concept: str, section: Dict[str, Any]) -> bool:
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
    domains = section.get("domains") or []
    if domains:
        d = domains[0] if isinstance(domains[0], str) else str(domains[0])
        return d.upper() if d.upper() in ("SOC2", "HIPAA", "ISO27001", "NIST") else d
    for t in (section.get("supports_traversals") or []):
        if isinstance(t, str) and "category:" in t.lower():
            return t.split(":", 1)[-1].strip()
    return ""


def _vendors_to_product_map(vendors: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
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


def load_vendors_config(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """Load vendors and products. Returns product_name -> { vendor_id, vendor_name, product_name, key_concepts }."""
    if path and path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _vendors_to_product_map(DEFAULT_VENDORS)
            if "vendors" in data and data["vendors"]:
                return _vendors_to_product_map(data["vendors"])
            if "product_key_concepts" in data and data["product_key_concepts"]:
                return {
                    p_name: {"vendor_id": "", "vendor_name": "", "product_name": p_name, "key_concepts": concepts}
                    for p_name, concepts in data["product_key_concepts"].items()
                }
        except Exception as e:
            logger.warning("Could not load vendors config from %s: %s", path, e)
    return _vendors_to_product_map(DEFAULT_VENDORS)


def _find_product_for_source(source_id: str, product_map: Dict[str, Dict[str, Any]]) -> Optional[str]:
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
                logger.warning("Skip %s: %s", json_path, e)
    return sections


def build_product_entities_and_edges(
    sections: List[Dict[str, Any]],
    product_map: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    product_info_docs = []
    key_concept_docs = []
    edge_docs = []
    products_seen: Dict[str, str] = {}
    for sec in sections:
        source_id = sec.get("source_id") or ""
        product = _find_product_for_source(source_id, product_map)
        if product and product not in products_seen:
            products_seen[product] = source_id

    for product, source_id in products_seen.items():
        entry = product_map.get(product, {})
        concepts = entry.get("key_concepts") or []
        vendor_id = entry.get("vendor_id") or ""
        vendor_name = entry.get("vendor_name") or ""
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"product_info_{vendor_id}_{product}"))
        meta = {
            "id": doc_id, "type": "product", "store_name": "domain_knowledge",
            "source_content_type": "product_purpose", "product_name": product,
            "source_id": source_id, "key_concepts": concepts,
        }
        if vendor_id:
            meta["vendor_id"] = vendor_id
        if vendor_name:
            meta["vendor_name"] = vendor_name
        product_info_docs.append({
            "page_content": f"Vendor: {vendor_name}. Product: {product}. Source: {source_id}. Key concepts: {', '.join(concepts)}.",
            "metadata": meta,
        })

    key_concept_ids: Dict[Tuple[str, str], str] = {}
    for product, source_id in products_seen.items():
        entry = product_map.get(product, {})
        concepts = entry.get("key_concepts") or []
        vendor_id = entry.get("vendor_id") or ""
        vendor_name = entry.get("vendor_name") or ""
        for concept in concepts:
            cid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"key_concept_{vendor_id}_{product}_{concept}"))
            key_concept_ids[(product, concept)] = cid
            meta = {
                "id": cid, "type": "product", "store_name": "entities",
                "source_content_type": "product_key_concepts", "product_name": product,
                "key_concept": concept, "source_id": source_id,
            }
            if vendor_id:
                meta["vendor_id"] = vendor_id
            if vendor_name:
                meta["vendor_name"] = vendor_name
            key_concept_docs.append({
                "page_content": f"Key concept: {concept}. Vendor: {vendor_name}. Product: {product}. Relates to controls, risks, policies, procedures, playbooks, and tables.",
                "metadata": meta,
            })

    context_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "product_kb_context"))
    edge_id_counter = [0]
    keyword_match_only = True

    def make_edge(sid: str, styp: str, tid: str, ttyp: str, etyp: str, doc: str = "", keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        edge_id_counter[0] += 1
        eid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"product_kb_edge_{sid}_{tid}_{edge_id_counter[0]}"))
        meta = {
            "edge_id": eid, "source_entity_id": sid, "source_entity_type": styp,
            "target_entity_id": tid, "target_entity_type": ttyp, "edge_type": etyp,
            "context_id": context_id, "relevance_score": 0.8,
        }
        if keywords:
            meta["keywords"] = keywords
        return {
            "page_content": doc or f"{styp} {sid} relates to {ttyp} {tid}",
            "metadata": meta,
        }

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
            edge_docs.append(make_edge(cid, "key_concept", section_id, doc_type, edge_type, doc_text, kw))

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
                edge_docs.append(make_edge(cid, "key_concept", control_id, "control", EDGE_TYPES["control"], doc_text, kw))
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
                edge_docs.append(make_edge(cid, "key_concept", req_id, "requirement", EDGE_TYPES["requirement"], doc_text, kw))
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
                edge_docs.append(make_edge(cid, "key_concept", clause, "control", EDGE_TYPES["control"], doc_text, kw))

    return product_info_docs, key_concept_docs, edge_docs


def run_extraction(
    preview_dir: Path,
    enriched_subdirs: Optional[List[str]] = None,
    product_key_concepts_path: Optional[Path] = None,
) -> Dict[str, Any]:
    product_map = load_vendors_config(product_key_concepts_path)
    sections = load_enriched_sections(preview_dir, enriched_subdirs)
    vendor_count = len({v.get("vendor_id") or "" for v in product_map.values() if v.get("vendor_id")})
    logger.info("Loaded %s enriched sections from %s; %s products from %s vendors", len(sections), preview_dir, len(product_map), vendor_count)
    product_info_docs, key_concept_docs, edge_docs = build_product_entities_and_edges(sections, product_map)
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
