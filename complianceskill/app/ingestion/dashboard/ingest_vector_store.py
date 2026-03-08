"""
Dashboard Decision Tree — Vector Store Ingestion via Dependencies

Uses get_doc_store_provider() from app.core.dependencies to pick the correct
vector store (Chroma or Qdrant) based on VECTOR_STORE_TYPE settings.

Indexes into:
  layout_templates       — EnrichedTemplate docs  (RETRIEVAL POINT 1)
  metric_catalog         — EnrichedMetric docs    (RETRIEVAL POINT 2)
  decision_tree_options  — DecisionOption docs    (prompt injection)

Replaces the standalone VectorStoreWriter so ingestion and retrieval use the
same store, enabling DashboardDecisionTreeService to find the data.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document as LangchainDocument

logger = logging.getLogger(__name__)

BATCH_SIZE = 32


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute from object or dict."""
    if hasattr(obj, key):
        return getattr(obj, key, default)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _to_doc(
    content: str,
    doc_id: str,
    metadata: Dict[str, Any],
) -> LangchainDocument:
    """Build LangchainDocument for add_documents. ChromaDB needs simple metadata values."""
    # Flatten lists to pipe-separated strings for ChromaDB metadata
    flat = {}
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, list):
            flat[k] = "|".join(str(x) for x in v) if v else ""
        elif hasattr(v, "value"):  # Enum
            flat[k] = str(v.value)
        else:
            flat[k] = str(v)
    flat["id"] = doc_id
    return LangchainDocument(page_content=content, metadata=flat)


def index_templates(
    templates: List[Any],
    doc_store_provider: Any,
) -> Tuple[int, int]:
    """
    Index EnrichedTemplate objects into layout_templates store.
    Returns (indexed, skipped).
    """
    store = doc_store_provider.stores.get("layout_templates") if hasattr(doc_store_provider, "stores") else {}
    if not store:
        logger.warning("layout_templates store not available")
        return 0, len(templates)

    docs = []
    for t in templates:
        content = _get_attr(t, "embedding_text") or ""
        tid = _get_attr(t, "template_id") or ""
        cat = _get_attr(t, "category")
        compl = _get_attr(t, "complexity")
        meta = {
            "template_id": tid,
            "registry_source": _get_attr(t, "registry_source") or "",
            "name": _get_attr(t, "name") or "",
            "category": cat.value if hasattr(cat, "value") else (cat or ""),
            "complexity": compl.value if hasattr(compl, "value") else (compl or ""),
            "focus_areas": _get_attr(t, "focus_areas") or [],
            "destinations": _get_attr(t, "supported_destinations") or [],
            "audience": _get_attr(t, "audience_levels") or [],
            "has_chat": str(_get_attr(t, "has_chat", False)),
            "has_graph": str(_get_attr(t, "has_graph", False)),
            "content_hash": _get_attr(t, "content_hash") or "",
        }
        docs.append(_to_doc(content, tid, meta))

    if not docs:
        return 0, 0

    try:
        for i in range(0, len(docs), BATCH_SIZE):
            batch = docs[i : i + BATCH_SIZE]
            store.add_documents(batch)
        logger.info(f"layout_templates: indexed {len(docs)} templates")
        return len(docs), 0
    except Exception as e:
        logger.error(f"Error indexing templates: {e}", exc_info=True)
        return 0, len(templates)


def index_metrics(
    metrics: List[Any],
    doc_store_provider: Any,
) -> Tuple[int, int]:
    """
    Index EnrichedMetric objects into metric_catalog store.
    Returns (indexed, skipped).
    """
    store = doc_store_provider.stores.get("metric_catalog") if hasattr(doc_store_provider, "stores") else {}
    if not store:
        logger.warning("metric_catalog store not available")
        return 0, len(metrics)

    docs = []
    for m in metrics:
        content = _get_attr(m, "embedding_text") or ""
        mid = _get_attr(m, "metric_id") or ""
        cat = _get_attr(m, "category")
        prof = _get_attr(m, "metric_profile")
        meta = {
            "metric_id": mid,
            "dashboard_id": _get_attr(m, "dashboard_id") or "",
            "name": _get_attr(m, "name") or "",
            "display_name": _get_attr(m, "display_name") or "",
            "metric_type": _get_attr(m, "metric_type") or "",
            "unit": _get_attr(m, "unit") or "",
            "chart_type": _get_attr(m, "chart_type") or "",
            "category": cat.value if hasattr(cat, "value") else (cat or ""),
            "metric_profile": prof.value if hasattr(prof, "value") else (prof or ""),
            "focus_areas": _get_attr(m, "focus_areas") or [],
            "source_capabilities": _get_attr(m, "source_capabilities") or [],
            "good_direction": _get_attr(m, "good_direction") or "",
            "axis_label": _get_attr(m, "axis_label") or "",
            "aggregation": _get_attr(m, "aggregation") or "",
            "threshold_warning": str(_get_attr(m, "threshold_warning") or ""),
            "threshold_critical": str(_get_attr(m, "threshold_critical") or ""),
            "content_hash": _get_attr(m, "content_hash") or "",
        }
        docs.append(_to_doc(content, mid, meta))

    if not docs:
        return 0, 0

    try:
        for i in range(0, len(docs), BATCH_SIZE):
            batch = docs[i : i + BATCH_SIZE]
            store.add_documents(batch)
        logger.info(f"metric_catalog: indexed {len(docs)} metrics")
        return len(docs), 0
    except Exception as e:
        logger.error(f"Error indexing metrics: {e}", exc_info=True)
        return 0, len(metrics)


def index_decision_tree(
    tree: Any,
    doc_store_provider: Any,
) -> int:
    """
    Index DecisionTree options into decision_tree_options store.
    Returns number of options indexed.
    """
    store = doc_store_provider.stores.get("decision_tree_options") if hasattr(doc_store_provider, "stores") else {}
    if not store:
        logger.warning("decision_tree_options store not available")
        return 0

    docs = []
    questions = _get_attr(tree, "questions") or []
    for q in questions:
        qid = _get_attr(q, "question_id") or ""
        field = _get_attr(q, "field") or ""
        question = _get_attr(q, "question") or ""
        for opt in _get_attr(q, "options") or []:
            oid = _get_attr(opt, "option_id") or ""
            label = _get_attr(opt, "label") or ""
            keywords = _get_attr(opt, "keywords") or []
            maps_to = _get_attr(opt, "maps_to") or {}
            doc_id = f"{qid}::{oid}"
            content = (
                f"Question: {question}\n"
                f"Option: {label}\n"
                f"Keywords: {', '.join(keywords)}\n"
                f"Maps to: {json.dumps(maps_to)}"
            )
            meta = {
                "question_id": qid,
                "option_id": oid,
                "label": label,
                "keywords": "|".join(keywords),
                "maps_to": json.dumps(maps_to),
                "confidence": str(_get_attr(opt, "confidence", 0.8)),
                "field": field,
            }
            docs.append(_to_doc(content, doc_id, meta))

    if not docs:
        return 0

    try:
        for i in range(0, len(docs), BATCH_SIZE):
            batch = docs[i : i + BATCH_SIZE]
            store.add_documents(batch)
        logger.info(f"decision_tree_options: indexed {len(docs)} options")
        return len(docs)
    except Exception as e:
        logger.error(f"Error indexing decision tree: {e}", exc_info=True)
        return 0


def ingest_dashboard_to_vector_store(
    templates: List[Any],
    metrics: List[Any],
    tree: Any,
    doc_store_provider: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Ingest enriched dashboard data into the vector store via dependencies.

    Args:
        templates: List of EnrichedTemplate (or dicts with same fields)
        metrics: List of EnrichedMetric (or dicts with same fields)
        tree: DecisionTree (or dict with questions)
        doc_store_provider: Optional. If None, uses get_doc_store_provider()

    Returns:
        Dict with indexed, skipped counts per collection.
    """
    if doc_store_provider is None:
        try:
            from app.core.dependencies import get_doc_store_provider
            doc_store_provider = get_doc_store_provider()
        except ImportError as e:
            logger.error(f"Cannot get doc store provider: {e}")
            return {"layout_templates": 0, "metric_catalog": 0, "decision_tree_options": 0}

    t_idx, t_skip = index_templates(templates, doc_store_provider)
    m_idx, m_skip = index_metrics(metrics, doc_store_provider)
    dt_idx = index_decision_tree(tree, doc_store_provider)

    return {
        "layout_templates": t_idx,
        "layout_templates_skipped": t_skip,
        "metric_catalog": m_idx,
        "metric_catalog_skipped": m_skip,
        "decision_tree_options": dt_idx,
    }
