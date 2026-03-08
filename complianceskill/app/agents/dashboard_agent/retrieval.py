"""
CCE Layout Advisor — Retrieval Layer (Goal-Driven Dashboard Design)
====================================================================
Uses DashboardTemplateRetrievalService and DecisionTreeRetrievalService
for goal-driven dashboard spec generation. All retrieval logic is centralized here.

Three retrieval points in the pipeline:

  RETRIEVAL POINT 1 — scoring_node
    retrieve_similar_templates(query) / retrieve_templates_by_decisions(decisions)
    → DashboardTemplateRetrievalService (uses doc store from dependencies)

  RETRIEVAL POINT 2 — retrieve_context_node
    retrieve_metric_catalog_context(metric_ids)
    → DecisionTreeRetrievalService.search_metrics (metric definitions, thresholds)

  RETRIEVAL POINT 3 — retrieve_context_node
    retrieve_past_layout_specs(group_id, domain)
    → past_layout_specs collection via get_doc_store_provider (ChromaDB or Qdrant per settings)
"""

from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy-initialized services
_template_service: Optional[Any] = None
_decision_tree_service: Optional[Any] = None


def _get_template_service():
    """Lazy-init DashboardTemplateRetrievalService (uses doc store from dependencies)."""
    global _template_service
    if _template_service is None:
        try:
            from app.services.dashboard_template_service import DashboardTemplateRetrievalService
            _template_service = DashboardTemplateRetrievalService()
        except Exception as e:
            logger.warning(f"DashboardTemplateRetrievalService unavailable: {e}")
            _template_service = False  # sentinel
    return _template_service if _template_service else None


def _get_decision_tree_service():
    """Lazy-init DecisionTreeRetrievalService."""
    global _decision_tree_service
    if _decision_tree_service is None:
        try:
            from app.retrieval.decision_tree_service import DecisionTreeRetrievalService
            _decision_tree_service = DecisionTreeRetrievalService()
        except Exception as e:
            logger.warning(f"DecisionTreeRetrievalService unavailable: {e}")
            _decision_tree_service = False
    return _decision_tree_service if _decision_tree_service else None


def _get_past_layout_specs_store():
    """Get past_layout_specs doc store from dependencies (ChromaDB or Qdrant per VECTOR_STORE_TYPE)."""
    try:
        from app.core.dependencies import get_doc_store_provider
        provider = get_doc_store_provider()
        return provider.get_store("past_layout_specs")
    except Exception as e:
        logger.debug(f"past_layout_specs store unavailable: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# RETRIEVAL POINT 1 — Template similarity (DashboardTemplateRetrievalService)
# ═══════════════════════════════════════════════════════════════════════

def retrieve_similar_templates(
    query: str,
    k: int = 5,
) -> list[dict]:
    """
    RETRIEVAL POINT 1 — Semantic search via DashboardTemplateRetrievalService.
    Returns [{template_id, boost, similarity}] for scoring_node.
    """
    svc = _get_template_service()
    if not svc:
        return []

    try:
        ctx = svc.search_templates(query, k=k)
        boosts = []
        for t in ctx.templates:
            sim = t.similarity_score or 0.0
            boost = round(sim * 15)
            boosts.append({
                "template_id": t.template_id,
                "boost": boost,
                "similarity": round(sim, 3),
            })
        logger.debug(f"[RETRIEVAL 1] template boosts: {[b['template_id'] for b in boosts]}")
        return boosts
    except Exception as e:
        logger.warning(f"[RETRIEVAL 1] retrieve_similar_templates failed: {e}")
        return []


def retrieve_templates_by_decisions(
    decisions: dict,
    k: int = 5,
    use_hybrid: bool = True,
) -> tuple[list[dict], Optional[float]]:
    """
    RETRIEVAL POINT 1 (decision path) — search_by_decisions via DashboardTemplateRetrievalService.
    Returns (candidates, None) where candidates = [{template_id, name, score, reasons, ...}].
    Used when scoring_node has full decision context.
    """
    svc = _get_template_service()
    if not svc:
        return [], None

    try:
        ctx = svc.search_by_decisions(decisions, k=k, use_hybrid=use_hybrid)
        candidates = []
        for t in ctx.templates:
            candidates.append({
                "template_id": t.template_id,
                "name": t.name,
                "score": int((t.similarity_score or 0) * 100),
                "reasons": [f"score:{t.similarity_score}"],
                "description": t.description,
                "category": t.category,
                "complexity": t.complexity,
                "has_chat": t.has_chat,
                "strip_cells": t.strip_cells,
                "best_for": t.best_for or [],
                "icon": t.icon,
            })
        return candidates, None
    except Exception as e:
        logger.warning(f"[RETRIEVAL 1] retrieve_templates_by_decisions failed: {e}")
        return [], None


# ═══════════════════════════════════════════════════════════════════════
# RETRIEVAL POINT 2 — Metric catalog (DecisionTreeRetrievalService)
# ═══════════════════════════════════════════════════════════════════════

def _metric_result_to_catalog(m: Any, metric_id: str) -> dict:
    """Map MetricResult to spec_generation catalog format."""
    # Extract thresholds from kpis or risk_quantification_hints
    warning, critical = None, None
    if m.kpis:
        for kpi in m.kpis[:3]:
            if isinstance(kpi, dict):
                warning = kpi.get("threshold_warning") or kpi.get("warning") or warning
                critical = kpi.get("threshold_critical") or kpi.get("critical") or critical
    hints = m.risk_quantification_hints or {}
    if warning is None:
        warning = hints.get("warning") or hints.get("threshold_warning")
    if critical is None:
        critical = hints.get("critical") or hints.get("threshold_critical")

    # Chart type from metric_type or metadata
    chart_type = m.metric_type or ""
    if not chart_type and hasattr(m, "metadata"):
        chart_type = (m.metadata or {}).get("chart_type", "")

    # Good direction from hints
    good_dir = "neutral"
    if hints:
        good_dir = hints.get("good_direction", "neutral")
    if good_dir == "neutral" and m.control_evidence_hints:
        good_dir = (m.control_evidence_hints or {}).get("good_direction", "neutral")

    # Aggregation from aggregation_windows
    agg = ""
    if m.aggregation_windows:
        agg = m.aggregation_windows[0] if isinstance(m.aggregation_windows[0], str) else str(m.aggregation_windows[0])

    return {
        "metric_id": metric_id,
        "definition": m.description or "",
        "display_name": m.name or metric_id,
        "unit": (m.metadata or {}).get("unit", ""),
        "chart_type_recommendation": chart_type,
        "thresholds": {"warning": warning, "critical": critical},
        "good_direction": good_dir,
        "axis_label": (m.metadata or {}).get("axis_label", ""),
        "aggregation": agg,
    }


def retrieve_metric_catalog_context(
    metric_ids: list[str],
    k_per_metric: int = 1,
    framework_filter: Optional[str] = None,
) -> list[dict]:
    """
    RETRIEVAL POINT 2 — DecisionTreeRetrievalService.search_metrics.
    Fetches metric definitions, thresholds, chart recs from metrics registry.
    Returns [] if service unavailable — LLM uses metric bindings alone.
    """
    if not metric_ids:
        return []

    svc = _get_decision_tree_service()
    if not svc:
        return []

    results = []
    for metric_id in metric_ids:
        try:
            # Try exact lookup first, then semantic search
            m = svc.get_metric_by_id(metric_id)
            if not m:
                metrics = svc.search_metrics(
                    query=metric_id,
                    limit=k_per_metric,
                    framework_filter=framework_filter,
                )
                m = metrics[0] if metrics else None
                if metrics:
                    for candidate in metrics:
                        if candidate.metric_id == metric_id or getattr(candidate, "id", "") == metric_id:
                            m = candidate
                            break
            if m:
                results.append(_metric_result_to_catalog(m, metric_id))
        except Exception as e:
            logger.warning(f"[RETRIEVAL 2] metric lookup failed for {metric_id}: {e}")

    logger.debug(f"[RETRIEVAL 2] metric catalog hits: {[r['metric_id'] for r in results]}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# RETRIEVAL POINT 3 — Past approved layout specs (called from retrieve_context_node)
# ═══════════════════════════════════════════════════════════════════════

def retrieve_past_layout_specs(
    group_id: str,
    domain: str,
    k: int = 2,
) -> list[dict]:
    """
    RETRIEVAL POINT 3 — past_layout_specs collection via get_doc_store_provider.
    Uses ChromaDB or Qdrant per VECTOR_STORE_TYPE in settings.
    Returns prior approved specs for the same domain as few-shot context.
    Returns [] if unavailable — LLM generates from template alone.
    """
    store = _get_past_layout_specs_store()
    if not store:
        return []

    try:
        query_text = f"{domain} {group_id} dashboard layout"
        where = {"domain": domain}
        results = store.semantic_search(query=query_text, k=max(1, k), where=where)

        specs = []
        for r in results:
            meta = r.get("metadata", {})
            doc = r.get("content", "")
            if meta.get("group_id") == group_id:
                continue  # skip self
            specs.append({
                "group_id":    meta.get("group_id", ""),
                "domain":      meta.get("domain", domain),
                "template_id": meta.get("template_id", ""),
                "version":     meta.get("version", ""),
                "metric_count": meta.get("metric_count", 0),
                "layout_spec_snippet": (doc or "")[:800],
            })

        logger.debug(f"[RETRIEVAL 3] past spec examples: {[s['group_id'] for s in specs]}")
        return specs

    except Exception as e:
        logger.warning(f"[RETRIEVAL 3] retrieve_past_layout_specs failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
# WRITE-BACK — called by storage_node after a spec is approved
# ═══════════════════════════════════════════════════════════════════════

def index_approved_layout_spec(
    group_id: str,
    domain: str,
    template_id: str,
    version: str,
    layout_spec: dict,
    metric_count: int,
) -> bool:
    """
    Write an approved layout spec back to the "past_layout_specs" collection.
    Uses doc store from dependencies (ChromaDB or Qdrant per VECTOR_STORE_TYPE). Called by storage_node.

    Returns True on success, False if the store is unavailable.
    """
    import json
    from langchain_core.documents import Document as LangchainDocument

    store = _get_past_layout_specs_store()
    if not store:
        return False

    try:
        doc_text = json.dumps(layout_spec, separators=(",", ":"))
        doc_id = f"{group_id}::{version}"
        metadata = {
            "id": doc_id,
            "group_id": group_id,
            "domain": domain,
            "template_id": template_id,
            "version": version,
            "metric_count": metric_count,
        }
        doc = LangchainDocument(page_content=doc_text, metadata=metadata)
        store.add_documents([doc])
        logger.info(f"[WRITE-BACK] indexed spec {doc_id} into past_layout_specs")
        return True

    except Exception as e:
        logger.warning(f"[WRITE-BACK] index_approved_layout_spec failed: {e}")
        return False
