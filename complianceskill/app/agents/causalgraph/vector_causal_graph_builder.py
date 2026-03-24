"""
Vector-Store-Backed Causal Graph Builder

Implements the vector-store approach for causal graph construction:
- Uses unified VectorStoreClient (ChromaDB/Qdrant) for semantic search
- Postgres for structural adjacency lookups
- Single LLM call for graph assembly (replaces N1-N5 pipeline)

Based on vector_causal_graph_builder.py but adapted for:
- Unified storage architecture (app.storage.vector_store)
- CSOD workflow integration
- LMS/HR vertical support
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import networkx as nx
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
from app.storage.vector_store import get_vector_store_client, VectorStoreClient
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def lms_causal_node_collection() -> str:
    return get_settings().LMS_CAUSAL_NODES_COLLECTION


def lms_causal_edge_collection() -> str:
    return get_settings().LMS_CAUSAL_EDGES_COLLECTION


def lms_focus_area_collection() -> str:
    return get_settings().LMS_FOCUS_AREA_TAXONOMY_COLLECTION


def lms_use_case_groups_collection() -> str:
    return get_settings().LMS_USE_CASE_GROUPS_COLLECTION


def causal_collection_for_domain(domain_id: str, collection_key: str) -> str:
    """
    Generic collection name accessor — reads from DomainConfig.

    Args:
        domain_id: Domain identifier (e.g., "lms", "security")
        collection_key: Logical collection key (e.g., "causal_nodes", "causal_edges",
                        "focus_area_taxonomy", "use_case_groups")

    Returns:
        Collection name string. Falls back to lms_* functions for "lms" domain
        or constructs ``{domain_id}_{collection_key}`` as default.
    """
    try:
        from app.agents.domain_config import DomainRegistry
        cfg = DomainRegistry.instance().get(domain_id)
        if cfg:
            return cfg.collection(collection_key)
    except Exception:
        pass
    # Fallback for lms domain — use settings-based functions
    if domain_id == "lms":
        _fallback = {
            "causal_nodes": lms_causal_node_collection,
            "causal_edges": lms_causal_edge_collection,
            "focus_area_taxonomy": lms_focus_area_collection,
            "use_case_groups": lms_use_case_groups_collection,
        }
        fn = _fallback.get(collection_key)
        if fn:
            return fn()
    return f"{domain_id}_{collection_key}"


# Module-level singleton
_vector_store_client: Optional[VectorStoreClient] = None
_embeddings_model = None


def _get_vector_store_client() -> Optional[VectorStoreClient]:
    """Get or create the vector store client singleton."""
    global _vector_store_client
    if _vector_store_client is None:
        try:
            settings = get_settings()
            config = settings.get_vector_store_config()
            _vector_store_client = get_vector_store_client(config=config)
        except Exception as e:
            logger.warning(f"Failed to initialize vector store client: {e}")
            return None
    return _vector_store_client


async def _get_embeddings_model():
    """Get or create the embeddings model from vector store client."""
    global _embeddings_model
    if _embeddings_model is None:
        client = _get_vector_store_client()
        if client:
            try:
                await client.initialize()
                _embeddings_model = await client.get_embeddings_model()
            except Exception as e:
                logger.warning(f"Failed to get embeddings model: {e}")
                return None
    return _embeddings_model


# ============================================================================
# SECTION 1 — Document Conversion Helpers
# ============================================================================

def _domains_list(node_or_edge: Dict[str, Any]) -> List[str]:
    d = node_or_edge.get("domains")
    if isinstance(d, list) and d:
        return [str(x) for x in d]
    v = node_or_edge.get("vertical")
    return [str(v)] if v else ["lms"]


def _node_to_document(node: Dict[str, Any]) -> Tuple[str, str, Dict]:
    """
    Convert a node dict → (doc_id, doc_text, metadata).

    Embedding text (Qdrant): display_name + description + domain_context.lms
    (falls back to full domain_context sentences if lms key missing).
    """
    node_id = node.get("node_id", node.get("metric_ref", str(uuid.uuid4())))
    domains = _domains_list(node)
    display = node.get("display_name") or node.get("name") or node_id
    vertical = domains[0] if domains else "lms"

    ctx = node.get("domain_context") or {}
    lms_ctx = ""
    if isinstance(ctx, dict):
        raw_lms = ctx.get("lms")
        if raw_lms:
            lms_ctx = str(raw_lms).strip()
        elif ctx:
            lms_ctx = " ".join(f"{k}: {v}" for k, v in ctx.items() if v)

    caps_req = node.get("required_capabilities") or []
    caps_opt = node.get("optional_capabilities") or []
    if not isinstance(caps_req, list):
        caps_req = []
    if not isinstance(caps_opt, list):
        caps_opt = []
    focus_areas = node.get("focus_areas") or []
    if not isinstance(focus_areas, list):
        focus_areas = []
    all_caps = list(dict.fromkeys([str(c) for c in caps_req] + [str(c) for c in caps_opt]))

    desc = (node.get("description") or "").strip()
    doc_text = f"{display}. {desc}".strip()
    if lms_ctx:
        doc_text = f"{doc_text} {lms_ctx}".strip()

    category = node.get("category") or (focus_areas[0] if focus_areas else "")

    metadata: Dict[str, Any] = {
        "node_id": node_id,
        "metric_ref": node.get("metric_ref", node_id),
        "display_name": display,
        "category": category,
        "node_type": node.get("node_type", "mediator"),
        "temporal_grain": node.get("temporal_grain", "monthly"),
        "observable": str(node.get("observable", True)),
        "latent_proxy": node.get("latent_proxy", "") or "",
        "is_outcome": str(node.get("node_type") == "terminal" or node.get("is_outcome")),
        "collider_warning": str(
            node.get("node_type") == "collider" or node.get("collider_warning", False)
        ),
        "vertical": vertical,
        "domains_json": json.dumps(domains),
        "focus_areas_json": json.dumps(focus_areas),
        "required_capabilities_json": json.dumps(caps_req),
        "optional_capabilities_json": json.dumps(caps_opt),
        "framework_codes_json": json.dumps(node.get("framework_codes") or []),
        "capabilities_json": json.dumps(all_caps),
        "source": node.get("source", "seed"),
        "version": str(node.get("version", "1.0")),
    }
    return node_id, doc_text, metadata


def _edge_to_document(edge: Dict[str, Any]) -> Tuple[str, str, Dict]:
    """
    Convert a corpus entry / edge dict → (doc_id, doc_text, metadata).

    Embedding text: source → mechanism → target (narrative chain).
    """
    edge_id = edge.get(
        "edge_id",
        edge.get("entry_id", f"E_{edge.get('source_node_id','')}_{edge.get('target_node_id','')}"),
    )

    src_name = edge.get("source_name", edge.get("source_node_id", ""))
    tgt_name = edge.get("target_name", edge.get("target_node_id", ""))
    mechanism = (edge.get("mechanism") or "").strip()

    doc_text = f"{src_name} → {mechanism} → {tgt_name}".strip()

    ed_domains = _domains_list(edge)
    ev_vertical = ed_domains[0] if ed_domains else str(edge.get("vertical", "lms"))

    metadata = {
        "edge_id":           edge_id,
        "source_node_id":    edge.get("source_node_id", edge.get("source_node", "")),
        "target_node_id":    edge.get("target_node_id", edge.get("target_node", "")),
        "source_category":   edge.get("source_node_category", edge.get("source_category", "")),
        "target_category":   edge.get("target_node_category", edge.get("target_category", "")),
        "direction":         edge.get("direction", "positive"),
        "lag_window_days":   str(edge.get("lag_window_days", 14)),
        "confidence":        str(edge.get("confidence", edge.get("confidence_score", 0.5))),
        "corpus_match_type": edge.get("corpus_match_type", "confirmed"),
        "evidence_type":     edge.get("evidence_type", "operational_study"),
        "vertical":          ev_vertical,
        "domains_json":      json.dumps(ed_domains),
        "source_capability": edge.get("source_capability", "") or "",
        "target_capability": edge.get("target_capability", "") or "",
        "domain":            edge.get("domain", ""),
        "provenance":        edge.get("provenance", ""),
        "source":            edge.get("source", "seed"),
        "version":           str(edge.get("version", "2.0")),
    }
    return edge_id, doc_text, metadata


def _focus_area_framework_codes(fa: Dict[str, Any]) -> List[str]:
    codes: List[str] = []
    for key in (
        "soc2_controls",
        "hipaa_controls",
        "nist_ai_rmf_controls",
        "iso27001_controls",
    ):
        raw = fa.get(key) or []
        if isinstance(raw, list):
            codes.extend(str(x) for x in raw)
    return list(dict.fromkeys(codes))


def _focus_area_to_document(
    focus_key: str,
    fa: Dict[str, Any],
    root_domain: str,
) -> Tuple[str, str, Dict[str, Any]]:
    """focus area key + description + intent_tags + framework codes → embed text; payload for CCE seeding."""
    desc = (fa.get("description") or "").strip()
    intent_tags = fa.get("intent_tags") or []
    if not isinstance(intent_tags, list):
        intent_tags = []
    fw = _focus_area_framework_codes(fa)
    doc_text = (
        f"{focus_key}. {desc} "
        f"Intent tags: {', '.join(str(t) for t in intent_tags)}. "
        f"Framework codes: {', '.join(fw)}."
    ).strip()

    causal_terminals = fa.get("causal_terminals") or []
    if not isinstance(causal_terminals, list):
        causal_terminals = []
    csod_schemas = fa.get("csod_schemas") or []
    if not isinstance(csod_schemas, list):
        csod_schemas = []
    dt_use_cases = fa.get("dt_use_cases") or []
    if not isinstance(dt_use_cases, list):
        dt_use_cases = []
    cap_req = fa.get("capabilities_required") or []
    cap_opt = fa.get("capabilities_optional") or []
    if not isinstance(cap_req, list):
        cap_req = []
    if not isinstance(cap_opt, list):
        cap_opt = []

    metadata: Dict[str, Any] = {
        "focus_area_key": focus_key,
        "domain": root_domain or "lms",
        "causal_terminals_json": json.dumps(causal_terminals),
        "csod_schemas_json": json.dumps(csod_schemas),
        "intent_tags_json": json.dumps(intent_tags),
        "framework_codes_json": json.dumps(fw),
        "dt_use_cases_json": json.dumps(dt_use_cases),
        "capabilities_required_json": json.dumps([str(c) for c in cap_req]),
        "capabilities_optional_json": json.dumps([str(c) for c in cap_opt]),
        "metric_categories_json": json.dumps(fa.get("metric_categories") or []),
    }
    return focus_key, doc_text, metadata


def _flags_from_use_case_notes(notes: str) -> Tuple[bool, bool]:
    low = (notes or "").lower()
    collider_guard = "collider guard" in low
    requires_shapley = "shapley" in low
    return collider_guard, requires_shapley


def _use_case_group_to_document(uc_key: str, uc: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """key + notes + required_groups + audience → embed text."""
    req_g = uc.get("required_groups") or []
    opt_g = uc.get("optional_groups") or []
    if not isinstance(req_g, list):
        req_g = []
    if not isinstance(opt_g, list):
        opt_g = []
    audience = str(uc.get("default_audience") or "")
    timeframe = str(uc.get("default_timeframe") or "")
    notes = (uc.get("notes") or "").strip()
    primary_fa = uc.get("primary_focus_areas") or []
    if not isinstance(primary_fa, list):
        primary_fa = []
    caps = uc.get("required_capabilities") or []
    if not isinstance(caps, list):
        caps = []
    terminals = uc.get("causal_terminals") or []
    if not isinstance(terminals, list):
        terminals = []

    doc_text = (
        f"{uc_key}. {notes} "
        f"Required metric groups: {', '.join(str(x) for x in req_g)}. "
        f"Audience: {audience}. Timeframe: {timeframe}."
    ).strip()

    scorer = uc.get("scorer_weights_override")
    scorer_json = json.dumps(scorer) if scorer is not None else ""
    lms_specific = uc.get("lms_specific")
    lms_json = json.dumps(lms_specific) if lms_specific is not None else ""

    collider_guard, requires_shapley = _flags_from_use_case_notes(notes)

    metadata: Dict[str, Any] = {
        "use_case_key": uc_key,
        "required_groups_json": json.dumps([str(x) for x in req_g]),
        "optional_groups_json": json.dumps([str(x) for x in opt_g]),
        "default_audience": audience,
        "default_timeframe": timeframe,
        "causal_terminals_json": json.dumps([str(x) for x in terminals]),
        "primary_focus_areas_json": json.dumps([str(x) for x in primary_fa]),
        "required_capabilities_json": json.dumps([str(c) for c in caps]),
        "scorer_weights_override_json": scorer_json or "null",
        "lms_specific_json": lms_json or "",
        "collider_guard": str(collider_guard).lower(),
        "requires_shapley": str(requires_shapley).lower(),
    }
    return uc_key, doc_text, metadata


def _hydrate_causal_node_metadata(meta: Dict[str, Any]) -> None:
    """Expand JSON-serialized list fields from vector store payloads."""
    dj = meta.get("domains_json")
    if isinstance(dj, str) and dj and "domains" not in meta:
        try:
            parsed = json.loads(dj)
            if isinstance(parsed, list):
                meta["domains"] = [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
    for key_json, key_out in (
        ("focus_areas_json", "focus_areas"),
        ("required_capabilities_json", "required_capabilities"),
        ("optional_capabilities_json", "optional_capabilities"),
        ("framework_codes_json", "framework_codes"),
        ("capabilities_json", "capabilities"),
    ):
        raw = meta.get(key_json)
        if isinstance(raw, str) and raw and key_out not in meta:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    meta[key_out] = parsed
            except json.JSONDecodeError:
                pass


def _prompt_category_line(meta: Dict[str, Any]) -> str:
    c = meta.get("category")
    if c:
        return str(c)
    fa = meta.get("focus_areas")
    if isinstance(fa, list) and fa:
        return str(fa[0])
    return str(meta.get("metric_ref", meta.get("node_id", "")))


def build_causal_vector_where_filter(
    vector_store_client: Optional[VectorStoreClient],
    domains: Optional[List[str]] = None,
    legacy_vertical: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Metadata filter for causal collections. Uses `vertical` on each point for
    Chroma compatibility (seed ingest sets vertical = domains[0]).
    """
    ids = [str(d) for d in (domains or []) if d]
    if legacy_vertical and legacy_vertical not in ids:
        ids.append(str(legacy_vertical))
    if not ids:
        ids = ["lms"]
    uniq = list(dict.fromkeys(ids))
    if len(uniq) == 1:
        raw: Dict[str, Any] = {"vertical": uniq[0]}
    else:
        raw = {"$or": [{"vertical": u} for u in uniq]}
    if vector_store_client is None:
        return raw
    return vector_store_client.normalize_filter(raw)


# ============================================================================
# SECTION 2 — Ingestion Helpers
# ============================================================================

async def ingest_nodes(
    nodes: List[Dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """
    Upsert a list of node dicts into the node collection using VectorStoreClient.
    
    Returns the number of nodes ingested.
    """
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.error("Vector store client not available for node ingestion")
        return 0
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass  # Already initialized
    
    ids, docs, metas = [], [], []
    for node in nodes:
        doc_id, doc_text, metadata = _node_to_document(node)
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append(metadata)

    # Process in batches
    ingested = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_docs = docs[i:i + batch_size]
        batch_metas = metas[i:i + batch_size]
        
        await vector_store_client.add_documents(
            collection_name=lms_causal_node_collection(),
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids,
        )
        ingested += len(batch_ids)

    logger.info(
        "ingest_nodes: upserted %s nodes into %s",
        ingested,
        lms_causal_node_collection(),
    )
    return ingested


async def ingest_edges(
    edges: List[Dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """
    Upsert a list of edge / corpus entry dicts into the edge collection.
    
    Returns the number of edges ingested.
    """
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.error("Vector store client not available for edge ingestion")
        return 0
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass  # Already initialized
    
    ids, docs, metas = [], [], []
    for edge in edges:
        doc_id, doc_text, metadata = _edge_to_document(edge)
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append(metadata)

    ingested = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_docs = docs[i:i + batch_size]
        batch_metas = metas[i:i + batch_size]
        
        await vector_store_client.add_documents(
            collection_name=lms_causal_edge_collection(),
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids,
        )
        ingested += len(batch_ids)

    logger.info(
        "ingest_edges: upserted %s edges into %s",
        ingested,
        lms_causal_edge_collection(),
    )
    return ingested


async def ingest_focus_areas(
    focus_areas: Dict[str, Dict[str, Any]],
    root_domain: str = "lms",
    batch_size: int = 50,
) -> int:
    """Upsert LMS focus_area_taxonomy entries into Qdrant (one point per focus area key)."""
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.error("Vector store client not available for focus area ingestion")
        return 0
    try:
        await vector_store_client.initialize()
    except Exception:
        pass

    ids, docs, metas = [], [], []
    for key, fa in focus_areas.items():
        if not isinstance(fa, dict):
            continue
        doc_id, doc_text, metadata = _focus_area_to_document(str(key), fa, root_domain)
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append(metadata)

    ingested = 0
    for i in range(0, len(ids), batch_size):
        await vector_store_client.add_documents(
            collection_name=lms_focus_area_collection(),
            documents=docs[i : i + batch_size],
            metadatas=metas[i : i + batch_size],
            ids=ids[i : i + batch_size],
        )
        ingested += len(ids[i : i + batch_size])

    logger.info(
        "ingest_focus_areas: upserted %s rows into %s",
        ingested,
        lms_focus_area_collection(),
    )
    return ingested


async def ingest_use_case_groups(
    use_case_groups: Dict[str, Dict[str, Any]],
    batch_size: int = 50,
) -> int:
    """Upsert LMS metric use case groups (intent routing / scorer weights) into Qdrant."""
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.error("Vector store client not available for use case group ingestion")
        return 0
    try:
        await vector_store_client.initialize()
    except Exception:
        pass

    ids, docs, metas = [], [], []
    for key, uc in use_case_groups.items():
        if not isinstance(uc, dict):
            continue
        doc_id, doc_text, metadata = _use_case_group_to_document(str(key), uc)
        ids.append(doc_id)
        docs.append(doc_text)
        metas.append(metadata)

    ingested = 0
    for i in range(0, len(ids), batch_size):
        await vector_store_client.add_documents(
            collection_name=lms_use_case_groups_collection(),
            documents=docs[i : i + batch_size],
            metadatas=metas[i : i + batch_size],
            ids=ids[i : i + batch_size],
        )
        ingested += len(ids[i : i + batch_size])

    logger.info(
        "ingest_use_case_groups: upserted %s rows into %s",
        ingested,
        lms_use_case_groups_collection(),
    )
    return ingested


def _config_json_path(settings: Any, relative_name: str) -> Path:
    p = Path(relative_name)
    if p.is_absolute():
        return p
    return settings.CONFIG_DIR / relative_name


async def ingest_lms_causal_seed_bundle(
    *,
    nodes_path: Optional[Path] = None,
    edges_path: Optional[Path] = None,
    focus_areas_path: Optional[Path] = None,
    use_case_groups_path: Optional[Path] = None,
    skip_nodes: bool = False,
    skip_edges: bool = False,
    skip_focus_areas: bool = False,
    skip_use_case_groups: bool = False,
) -> Dict[str, int]:
    """
    Load the four LMS JSON configs from disk and upsert into their Qdrant collections.

    Paths default to settings.CONFIG_DIR + LMS_*_PATH filenames.
    """
    settings = get_settings()
    counts: Dict[str, int] = {
        "nodes": 0,
        "edges": 0,
        "focus_areas": 0,
        "use_case_groups": 0,
    }

    np = nodes_path or _config_json_path(settings, settings.LMS_CAUSAL_NODES_SEED_PATH)
    ep = edges_path or _config_json_path(settings, settings.LMS_CAUSAL_EDGES_PATH)
    fp = focus_areas_path or _config_json_path(settings, settings.LMS_FOCUS_AREA_TAXONOMY_PATH)
    up = use_case_groups_path or _config_json_path(settings, settings.LMS_METRIC_USE_CASE_GROUPS_PATH)

    if not skip_nodes:
        if not np.exists():
            logger.warning("LMS nodes seed file missing: %s", np)
        else:
            data = json.loads(np.read_text(encoding="utf-8"))
            nodes = data.get("nodes") if isinstance(data, dict) else None
            if not isinstance(nodes, list):
                raise ValueError(f"Expected 'nodes' list in {np}")
            counts["nodes"] = await ingest_nodes(nodes)

    if not skip_edges:
        if not ep.exists():
            logger.warning("LMS edges file missing: %s", ep)
        else:
            data = json.loads(ep.read_text(encoding="utf-8"))
            edges = data.get("edges") if isinstance(data, dict) else data
            if not isinstance(edges, list):
                raise ValueError(f"Expected 'edges' list in {ep}")
            counts["edges"] = await ingest_edges(edges)

    if not skip_focus_areas:
        if not fp.exists():
            logger.warning("LMS focus area taxonomy missing: %s", fp)
        else:
            data = json.loads(fp.read_text(encoding="utf-8"))
            fa_map = data.get("focus_areas") if isinstance(data, dict) else None
            if not isinstance(fa_map, dict):
                raise ValueError(f"Expected 'focus_areas' object in {fp}")
            root_domain = str(data.get("domain") or "lms")
            counts["focus_areas"] = await ingest_focus_areas(fa_map, root_domain=root_domain)

    if not skip_use_case_groups:
        if not up.exists():
            logger.warning("LMS use case groups file missing: %s", up)
        else:
            data = json.loads(up.read_text(encoding="utf-8"))
            uc_map = data.get("use_case_groups") if isinstance(data, dict) else None
            if not isinstance(uc_map, dict):
                raise ValueError(f"Expected 'use_case_groups' object in {up}")
            counts["use_case_groups"] = await ingest_use_case_groups(uc_map)

    logger.info("ingest_lms_causal_seed_bundle complete: %s", counts)
    return counts


# ============================================================================
# SECTION 3 — Retrieval Helpers
# ============================================================================

async def retrieve_causal_nodes(
    query: str,
    vertical: str = "lms",
    domains: Optional[List[str]] = None,
    n_results: int = 20,
    confidence_floor: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most semantically relevant causal nodes for a query.

    ``domains`` (preferred): active domain partition ids + _shared — see
    lexy_causal_concept_mapping_design §5.5. ``vertical`` is a legacy single-domain alias.
    """
    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.warning("Vector store client not available")
        return []
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass
    
    where_filter = build_causal_vector_where_filter(
        vector_store_client,
        domains=domains,
        legacy_vertical=vertical if vertical else None,
    )
    
    try:
        results = await vector_store_client.query(
            collection_name=lms_causal_node_collection(),
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
        )
        
        nodes = []
        if results and results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                
                # Convert distance to similarity score
                similarity = 1.0 - (dist / 2.0) if dist <= 2.0 else 0.0
                if similarity < confidence_floor:
                    continue
                
                node = dict(meta)
                _hydrate_causal_node_metadata(node)
                node["_doc_text"] = doc
                node["_retrieval_score"] = round(similarity, 4)
                # Re-cast booleans (vector stores may store as strings)
                node["observable"] = str(node.get("observable", "True")).lower() == "true"
                node["is_outcome"] = str(node.get("is_outcome", "False")).lower() == "true"
                node["collider_warning"] = str(node.get("collider_warning", "False")).lower() == "true"
                nodes.append(node)
        
        logger.debug(f"retrieve_causal_nodes: '{query[:60]}' → {len(nodes)} nodes")
        return nodes
    except Exception as e:
        logger.error(f"Failed to retrieve causal nodes: {e}", exc_info=True)
        return []


async def retrieve_causal_edges(
    query: str,
    node_ids: List[str],
    vertical: str = "lms",
    domains: Optional[List[str]] = None,
    n_results: int = 30,
    min_confidence: Optional[float] = None,
    conn_string: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve causal edges relevant to the query AND anchored to the retrieved nodes.
    
    Two-phase retrieval:
        Phase 1 — semantic: query the edge collection with the user question
        Phase 2 — structural: filter to edges where source OR target is in node_ids
                    OR use Postgres adjacency lookup if available
    """
    if not node_ids:
        return []

    if min_confidence is None:
        min_confidence = float(get_settings().LMS_CAUSAL_EDGE_MIN_CONFIDENCE_DEFAULT)

    vector_store_client = _get_vector_store_client()
    if vector_store_client is None:
        logger.warning("Vector store client not available")
        return []
    
    try:
        await vector_store_client.initialize()
    except Exception:
        pass
    
    # Phase 1: semantic retrieval
    where_filter = build_causal_vector_where_filter(
        vector_store_client,
        domains=domains,
        legacy_vertical=vertical if vertical else None,
    )
    semantic_n = min(n_results * 2, 100)  # Cast wider net
    
    try:
        results = await vector_store_client.query(
            collection_name=lms_causal_edge_collection(),
            query_texts=[query],
            n_results=semantic_n,
            where=where_filter,
        )
        
        node_id_set = set(node_ids)
        edges = []
        
        if results and results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                
                similarity = 1.0 - (dist / 2.0) if dist <= 2.0 else 0.0
                conf = float(meta.get("confidence", 0.5))
                
                # Phase 2: connectivity filter
                src = meta.get("source_node_id", "")
                tgt = meta.get("target_node_id", "")
                is_connected = (src in node_id_set) or (tgt in node_id_set)
                
                if not is_connected or conf < min_confidence:
                    continue
                
                edge = dict(meta)
                dj = edge.get("domains_json")
                if isinstance(dj, str) and dj:
                    try:
                        parsed = json.loads(dj)
                        if isinstance(parsed, list):
                            edge["domains"] = [str(x) for x in parsed]
                    except json.JSONDecodeError:
                        pass
                edge["_doc_text"] = doc
                edge["_retrieval_score"] = round(similarity, 4)
                edge["lag_window_days"] = int(meta.get("lag_window_days", 14))
                edge["confidence"] = conf
                edges.append(edge)
    except Exception as e:
        logger.error(f"Failed to retrieve causal edges semantically: {e}", exc_info=True)
        edges = []
    
    # Phase 3: Postgres structural lookup (if available)
    structural_edges = []
    if conn_string:
        try:
            from app.agents.csod.csod_causal_graph import fetch_adjacent_edges_pg
            structural_edges = await asyncio.to_thread(
                fetch_adjacent_edges_pg,
                conn_string,
                node_ids,
                vertical,
                min_confidence,
                domains,
            )
            # Add structural edges that weren't already found
            existing_edge_ids = {e.get("edge_id", "") for e in edges}
            for se in structural_edges:
                if se.get("edge_id", "") not in existing_edge_ids:
                    se["_retrieval_score"] = 0.70  # structural match
                    edges.append(se)
        except Exception as e:
            logger.debug(f"Postgres structural lookup failed (non-fatal): {e}")
    
    # Sort by confidence × retrieval_score
    edges.sort(
        key=lambda e: e.get("confidence", 0.5) * e.get("_retrieval_score", 0.5),
        reverse=True,
    )
    
    logger.debug(f"retrieve_causal_edges: '{query[:60]}' → {len(edges)} edges")
    return edges[:n_results]


# ============================================================================
# SECTION 4 — LLM Graph Assembly
# ============================================================================

_ASSEMBLY_SYSTEM_PROMPT = """You are a causal graph assembler for an enterprise analytics platform.

You are given:
1. A user question (may span LMS, HR, security/GRC, or other domains)
2. A set of RETRIEVED NODES — pre-validated, typed causal nodes from a curated knowledge base
3. A set of RETRIEVED EDGES — pre-validated causal relationships from a curated corpus

Your task has THREE parts:

PART A — SELECT the nodes and edges that are relevant to the question.
  - Do NOT invent new nodes or edges. Work only from the retrieved candidates.
  - A node is relevant if it lies on a causal path to or from the outcome the question is about.
  - An edge is relevant if both its source AND target are in your selected node set.
  - Mark the primary outcome node as the terminal. There should be exactly 1–3 terminals.
  - Mark upstream exogenous nodes (no parents in scope) as root.

PART B — IDENTIFY structural properties:
  - Colliders: nodes caused by 2+ INDEPENDENT parents. Mark collider_warning=true.
    CRITICAL: Never use a collider as a filter. Flag this in the output.
  - Confounders: nodes that independently cause 2+ other nodes.
  - Hot paths: the 2–3 chains with highest mean edge confidence × 1/lag_days.

PART C — Synthesise a plain-language DIAGNOSIS relevant to the question.
  - 2–4 sentences. State the most likely causal mechanism for what the question asks about.
  - Name the root cause, the mechanism pathway, and the outcome.
  - If a collider warning applies, state it explicitly.

Return ONLY valid JSON:
{
  "selected_nodes": [
    {
      "node_id":        "string",
      "metric_ref":     "string",
      "category":       "string",
      "node_type":      "root|mediator|confounder|collider|terminal",
      "temporal_grain": "string",
      "observable":     true,
      "description":    "string — causal role in this graph, 1–2 sentences",
      "collider_warning": false,
      "is_outcome":     false
    }
  ],
  "selected_edges": [
    {
      "edge_id":        "string",
      "source_node":    "node_id",
      "target_node":    "node_id",
      "direction":      "positive|negative",
      "mechanism":      "string",
      "lag_window_days": 14,
      "confidence_score": 0.80,
      "corpus_match_type": "confirmed|analogous|novel"
    }
  ],
  "terminal_nodes":  ["node_id"],
  "root_nodes":      ["node_id"],
  "collider_nodes":  ["node_id"],
  "confounder_nodes": ["node_id"],
  "hot_paths": [
    {
      "path":            ["node_id", "node_id", "node_id"],
      "path_confidence": 0.78,
      "lag_total_days":  21
    }
  ],
  "diagnosis": "string — plain-language causal mechanism summary",
  "coverage_note": "string — what the retrieved set covers well / what it misses"
}"""


def assemble_causal_graph_with_llm(
    question: str,
    retrieved_nodes: List[Dict[str, Any]],
    retrieved_edges: List[Dict[str, Any]],
    llm: Any,  # BaseChatModel from langchain (obtained via get_llm())
) -> Dict[str, Any]:
    """
    Single LLM call: select relevant nodes+edges and assemble the causal graph.
    
    This replaces N1 (decomposer) + N2 (node proposer) + N3 (edge proposer)
    + N4 (lag estimator) + N5 (validation) in one shot.
    
    Args:
        question: User's natural language question
        retrieved_nodes: List of retrieved causal nodes
        retrieved_edges: List of retrieved causal edges
        llm: LLM instance (obtained via get_llm() from dependencies)
    
    Returns:
        Dict with selected_nodes, selected_edges, terminal_nodes, etc.
    """
    # Build compact representations for the prompt
    node_lines = []
    for n in retrieved_nodes[:25]:
        dom = n.get("domains")
        dom_s = " ".join(dom) if isinstance(dom, list) else str(n.get("vertical", ""))
        caps = n.get("required_capabilities") or []
        cap_s = ",".join(caps[:4]) if isinstance(caps, list) else ""
        node_lines.append(
            f"- [{n.get('node_id', '')}] type={n.get('node_type', '')}, "
            f"cat={_prompt_category_line(n)}, domains={dom_s}, caps=[{cap_s}], "
            f"grain={n.get('temporal_grain', '')}, observable={n.get('observable', '')}, "
            f"score={float(n.get('_retrieval_score', 0) or 0):.2f} | "
            f"{str(n.get('_doc_text', ''))[:120]}"
        )

    edge_lines = []
    for e in retrieved_edges[:35]:
        sc = e.get("source_capability", "") or ""
        tc = e.get("target_capability", "") or ""
        edge_lines.append(
            f"- [{e.get('edge_id', '')}] {e.get('source_node_id', '')} → {e.get('target_node_id', '')} "
            f"({e.get('direction', '')}, lag={e.get('lag_window_days', '')}d, "
            f"conf={float(e.get('confidence', 0) or 0):.2f}, "
            f"match={e.get('corpus_match_type', '')}, score={float(e.get('_retrieval_score', 0) or 0):.2f}) "
            f"cap={sc}→{tc} | {str(e.get('_doc_text', ''))[:150]}"
        )

    human_message = f"""QUESTION: {question}

RETRIEVED NODES ({len(retrieved_nodes[:25])} candidates):
{chr(10).join(node_lines) or 'None retrieved'}

RETRIEVED EDGES ({len(retrieved_edges[:35])} candidates):
{chr(10).join(edge_lines) or 'None retrieved'}

Select the relevant subset, identify structural properties, and produce the diagnosis.
Return JSON only."""

    from langchain_core.messages import HumanMessage, SystemMessage
    response = llm.invoke([
        SystemMessage(content=_ASSEMBLY_SYSTEM_PROMPT),
        HumanMessage(content=human_message),
    ])
    raw = response.content if hasattr(response, "content") else str(response)

    # Parse JSON with fence fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for pat in (r'```json\s*(\{.*?\})\s*```', r'(\{.*\})'):
            m = re.search(pat, raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
    logger.warning("assemble_causal_graph_with_llm: failed to parse LLM response")
    return {"selected_nodes": [], "selected_edges": [], "diagnosis": "Assembly failed"}


# ============================================================================
# SECTION 5 — LangGraph Node (drop-in for CSOD workflow)
# ============================================================================

def vector_causal_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single LangGraph node that replaces the N1→N5 chain using vector retrieval.
    
    Reads from state:
        user_query              — the original question
        active_domains          — preferred partition list (design §4); falls back to causal_vertical / vertical
        causal_vertical         — legacy single-domain alias (e.g. 'lms')
        causal_metric_registry   — metric registry (used to infer query terms)
        cce_db_url              — optional Postgres connection string
    
    Writes to state:
        causal_proposed_nodes    — selected nodes
        causal_proposed_edges    — selected edges
        causal_graph_metadata    — partial metadata
        causal_assembly_result   — full LLM assembly output
        causal_retrieval_stats   — retrieval statistics
    """
    try:
        question = state.get("user_query", "")
        vertical = state.get("causal_vertical", state.get("vertical", "lms"))
        raw_domains = state.get("active_domains")
        domain_ids: List[str] = (
            [str(x) for x in raw_domains if x]
            if isinstance(raw_domains, list) and raw_domains
            else []
        )
        if not domain_ids:
            domain_ids = [vertical] if vertical else ["lms"]
        if "_shared" not in domain_ids:
            domain_ids = list(domain_ids) + ["_shared"]
        conn_string = state.get("cce_db_url") or os.environ.get("CCE_DB_URL")

        # ── Build an enriched retrieval query ────────────────────────────────
        metric_registry = state.get("causal_metric_registry", state.get("metric_registry", []))
        enriched_query = question
        if metric_registry and len(question.split()) < 8:
            top_categories = list({
                m.get("category", "") for m in metric_registry[:10] if m.get("category")
            })[:5]
            enriched_query = f"{question} {' '.join(top_categories)}"

        # ── Retrieve nodes and edges (async) ──────────────────────────────────
        async def _retrieve():
            nodes = await retrieve_causal_nodes(
                query=enriched_query,
                vertical=vertical,
                domains=domain_ids,
                n_results=20,
            )
            
            if not nodes:
                return [], []
            
            node_ids = [n["node_id"] for n in nodes if n.get("node_id")]
            edges = await retrieve_causal_edges(
                query=enriched_query,
                node_ids=node_ids,
                vertical=vertical,
                domains=domain_ids,
                n_results=30,
                min_confidence=float(
                    get_settings().LMS_CAUSAL_EDGE_MIN_CONFIDENCE_DEFAULT
                ),
                conn_string=conn_string,
            )
            return nodes, edges
        
        from app.agents.csod.csod_tool_integration import run_async

        retrieved_nodes, retrieved_edges = run_async(_retrieve())

        if not retrieved_nodes:
            logger.warning("vector_causal_graph_node: no nodes retrieved — graph will be empty")
            state.setdefault("causal_proposed_nodes", [])
            state.setdefault("causal_proposed_edges", [])
            return state

        # ── LLM assembly ─────────────────────────────────────────────────────
        from app.core.dependencies import get_llm

        llm = get_llm(temperature=0)
        assembly = assemble_causal_graph_with_llm(
            question=question,
            retrieved_nodes=retrieved_nodes,
            retrieved_edges=retrieved_edges,
            llm=llm,
        )

        # ── Map to causal engine state fields ─────────────────────────────────
        retrieved_by_id = {
            n["node_id"]: n for n in retrieved_nodes if n.get("node_id")
        }
        proposed_nodes = []
        for n in assembly.get("selected_nodes", []):
            nid = n.get("node_id", "")
            src = retrieved_by_id.get(nid, {})
            merged = {
                "node_id":          nid,
                "metric_ref":       n.get("metric_ref", nid),
                "category": (n.get("category") or (_prompt_category_line(src) if src else "")),
                "node_type":        n.get("node_type", "mediator"),
                "observable":       n.get("observable", True),
                "latent_proxy":     n.get("latent_proxy"),
                "temporal_grain":   n.get("temporal_grain", "monthly"),
                "description":      n.get("description", ""),
                "parent_count":     0,  # computed later
                "child_count":      0,
                "collider_warning": n.get("collider_warning", False),
                "is_outcome":       n.get("is_outcome", n.get("node_type") == "terminal"),
            }
            if src.get("focus_areas"):
                merged["focus_areas"] = src["focus_areas"]
            if src.get("required_capabilities"):
                merged["required_capabilities"] = src["required_capabilities"]
            if src.get("optional_capabilities"):
                merged["optional_capabilities"] = src["optional_capabilities"]
            if src.get("domains"):
                merged["domains"] = src["domains"]
            if not merged.get("category"):
                merged["category"] = n.get("category", "")
            proposed_nodes.append(merged)

        proposed_edges = []
        for idx, e in enumerate(assembly.get("selected_edges", [])):
            proposed_edges.append({
                "edge_id":          e.get("edge_id", f"VE{idx:03d}"),
                "source_node":      e.get("source_node", e.get("source_node_id", "")),
                "target_node":      e.get("target_node", e.get("target_node_id", "")),
                "lag_window_days":  e.get("lag_window_days", 14),
                "lag_confidence":   0.75,
                "direction":        e.get("direction", "positive"),
                "mechanism":        e.get("mechanism", ""),
                "confounders":      e.get("confounders", []),
                "confidence_score": e.get("confidence_score", e.get("confidence", 0.65)),
                "corpus_validated": True,
                "corpus_match_type": e.get("corpus_match_type", "confirmed"),
                "flags":            [],
            })

        # Partial metadata
        partial_metadata = {
            "node_count":             len(proposed_nodes),
            "edge_count":             len(proposed_edges),
            "terminal_node_ids":      assembly.get("terminal_nodes", []),
            "collider_node_ids":      assembly.get("collider_nodes", []),
            "confounder_node_ids":    assembly.get("confounder_nodes", []),
            "hot_paths":              assembly.get("hot_paths", []),
            "show_causal_graph":      len(proposed_nodes) >= 3,
            "coverage_note":          assembly.get("coverage_note", ""),
        }

        state["causal_proposed_nodes"]  = proposed_nodes
        state["causal_proposed_edges"]  = proposed_edges
        state["causal_graph_metadata"]  = partial_metadata
        state["causal_assembly_result"] = assembly
        state["causal_retrieval_stats"] = {
            "nodes_retrieved":    len(retrieved_nodes),
            "edges_retrieved":    len(retrieved_edges),
            "nodes_selected":     len(proposed_nodes),
            "edges_selected":     len(proposed_edges),
            "enriched_query":     enriched_query,
            "active_domains":     domain_ids,
        }

        # Lexy stage_2_concept_mapping-shaped payload for UI / API (lexy_conversation_flows.json)
        state["lexy_stage_2_concept_mapping"] = {
            "concepts": [
                {
                    "name": (
                        retrieved_by_id.get(n.get("node_id", ""), {}).get("display_name")
                        or n.get("metric_ref")
                        or n.get("node_id", "")
                    ),
                    "description": (n.get("description") or "")[:500],
                    "confidence": round(
                        float(retrieved_by_id.get(n.get("node_id", ""), {}).get("_retrieval_score", 0.85) or 0.85),
                        4,
                    ),
                    "tags": (n.get("focus_areas") or [])[:8],
                    "node_id": n.get("node_id", ""),
                    "node_type": n.get("node_type", ""),
                }
                for n in proposed_nodes[:16]
            ],
            "excluded": [],
        }

        # Populate decomposed groups for downstream compatibility
        state["causal_decomposed_metric_groups"] = [{
            "group_id":          "vector_retrieved",
            "group_name":        "Vector-Retrieved Causal Group",
            "domain_theme":      ",".join(domain_ids[:3]) or vertical,
            "metric_ids":        [n["node_id"] for n in proposed_nodes],
            "terminal_candidates": assembly.get("terminal_nodes", []),
            "bridging_metrics":  [],
            "rationale":         f"Assembled via vector retrieval for: '{question[:80]}'",
        }]

        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"[VectorCausal] Retrieved {len(retrieved_nodes)} nodes, {len(retrieved_edges)} edges → "
                f"selected {len(proposed_nodes)} nodes, {len(proposed_edges)} edges | "
                f"Diagnosis: {assembly.get('diagnosis', '')[:100]}"
            )
        ))

        logger.info(
            f"vector_causal_graph_node: {len(proposed_nodes)} nodes, "
            f"{len(proposed_edges)} edges assembled for '{question[:60]}'"
        )

    except Exception as e:
        logger.error(f"vector_causal_graph_node failed: {e}", exc_info=True)
        state["error"] = f"VectorCausalGraph failed: {str(e)}"
        state.setdefault("causal_proposed_nodes", [])
        state.setdefault("causal_proposed_edges", [])

    return state
