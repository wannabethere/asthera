"""
Dashboard Template Vector Store & Scoring
==========================================
Centralized vector store building and hybrid scoring for dashboard templates.
Used by DashboardTemplateRetrievalService — single source for registry, scoring, and vector ops.

Provides:
- ALL_TEMPLATES, ALL_CATEGORIES, get_unified_embedding_text, score_all_templates (from registry)
- score_templates_hybrid (rule-based + optional vector boost)
- build_dashboard_template_vector_store (FAISS/Chroma from templates)
"""

from __future__ import annotations
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Import unified registry
try:
    from app.utils.registry_config.registry_unified import (
        ALL_TEMPLATES,
        ALL_CATEGORIES,
        get_unified_embedding_text,
        score_all_templates,
    )
except ImportError:
    from app.agents.dashboard_agent.templates import (
        TEMPLATES as ALL_TEMPLATES,
        CATEGORIES as ALL_CATEGORIES,
        get_template_embedding_text as get_unified_embedding_text,
    )
    def score_all_templates(decisions: dict) -> list[tuple[str, int, list[str]]]:
        """Fallback scoring when registry_unified unavailable."""
        scores = []
        for tid, tpl in ALL_TEMPLATES.items():
            score = 0
            reasons = []
            if decisions.get("category") and tpl.get("category"):
                cats = decisions["category"]
                if isinstance(cats, list) and tpl["category"] in cats:
                    score += 30
                elif tpl["category"] == cats:
                    score += 30
                reasons.append(f"category: {tpl['category']}")
            scores.append((tid, score, reasons))
        return sorted(scores, key=lambda x: x[1], reverse=True)


# ═══════════════════════════════════════════════════════════════════════
# HYBRID SCORER
# ═══════════════════════════════════════════════════════════════════════

def score_templates_hybrid(
    decisions: dict,
    vector_results: Optional[list[dict]] = None,
) -> list[tuple[str, int, list[str]]]:
    """
    Score all templates against decisions using rule-based weights,
    optionally boosted by vector similarity scores.
    
    Returns: [(template_id, total_score, [reasons]), ...] sorted desc.
    """
    try:
        base_scores = score_all_templates(decisions)
        
        if vector_results:
            vector_map = {vr["template_id"]: vr.get("similarity_score", 0.0) for vr in vector_results}
            boosted_scores = []
            for tid, score, reasons in base_scores:
                if tid in vector_map:
                    boost = int(vector_map[tid] * 15)
                    score += boost
                    reasons.append(f"semantic similarity +{boost}")
                boosted_scores.append((tid, score, reasons))
            return boosted_scores
        
        return base_scores
    
    except (NameError, AttributeError, TypeError):
        pass

    # Fallback local implementation
    scores: dict[str, dict] = {}
    for tid, tpl in ALL_TEMPLATES.items():
        score = 0
        reasons = []

        if decisions.get("category") and tpl.get("category"):
            cats = decisions["category"]
            if isinstance(cats, list) and tpl["category"] in cats:
                score += 30
                reasons.append(f"category match: {tpl['category']}")
            elif tpl["category"] == cats:
                score += 30
                reasons.append(f"category match: {tpl['category']}")

        if decisions.get("domain") and decisions["domain"] in tpl.get("domains", []):
            score += 25
            reasons.append(f"domain match: {decisions['domain']}")

        if decisions.get("theme") and decisions["theme"] in tpl.get("theme_hint", ""):
            score += 10
            reasons.append(f"theme: {decisions['theme']}")

        if decisions.get("complexity") and tpl.get("complexity") == decisions["complexity"]:
            score += 10
            reasons.append(f"complexity: {decisions['complexity']}")

        if decisions.get("has_chat") is not None and tpl.get("has_chat") == decisions["has_chat"]:
            score += 15
            reasons.append(f"chat: {'yes' if decisions['has_chat'] else 'no'}")

        if decisions.get("strip_cells") is not None:
            if decisions["strip_cells"] == 0 and tpl.get("strip_cells", 0) == 0:
                score += 10
                reasons.append("no KPI strip")
            elif decisions["strip_cells"] > 0 and tpl.get("strip_cells", 0) > 0:
                score += 5
                if abs(decisions["strip_cells"] - tpl["strip_cells"]) <= 2:
                    score += 5
                    reasons.append(f"strip cells ~{tpl['strip_cells']}")

        if vector_results:
            for vr in vector_results:
                if vr["template_id"] == tid:
                    boost = int(vr.get("similarity_score", 0.0) * 15)
                    score += boost
                    reasons.append(f"semantic similarity +{boost}")
                    break

        scores[tid] = {"score": score, "reasons": reasons}

    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    return [(tid, data["score"], data["reasons"]) for tid, data in ranked]


# ═══════════════════════════════════════════════════════════════════════
# VECTOR STORE BUILDER
# ═══════════════════════════════════════════════════════════════════════

def build_dashboard_template_vector_store(
    embedder,
    templates: Optional[Dict[str, Any]] = None,
    categories: Optional[Dict[str, Any]] = None,
    backend: str = "faiss",
    persist_dir: Optional[str] = None,
):
    """
    Build FAISS or Chroma vector store from dashboard templates.
    
    Args:
        embedder: EmbeddingService or compatible (embed_one(text) -> list[float])
        templates: Template dict (default: ALL_TEMPLATES from registry)
        categories: Category dict (default: ALL_CATEGORIES)
        backend: "faiss" or "chroma"
        persist_dir: For Chroma persistence
    
    Returns:
        LangChain vector store (FAISS or Chroma)
    """
    from langchain_core.embeddings import Embeddings
    from langchain_core.documents import Document

    templates = templates or ALL_TEMPLATES
    categories = categories or ALL_CATEGORIES

    class EmbeddingAdapter(Embeddings):
        def __init__(self, embedder):
            self._embedder = embedder

        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return [self._embedder.embed_one(text) for text in texts]

        def embed_query(self, text: str) -> List[float]:
            return self._embedder.embed_one(text)

    embeddings = EmbeddingAdapter(embedder)
    docs = []

    for tid, tpl in templates.items():
        text = get_unified_embedding_text(tpl)
        metadata = {
            "template_id": tid,
            "name": tpl["name"],
            "category": tpl["category"],
            "category_label": categories.get(tpl["category"], {}).get("label", ""),
            "domains": json.dumps(tpl.get("domains", [])),
            "complexity": tpl.get("complexity", "medium"),
            "has_chat": tpl.get("has_chat", False),
            "has_graph": tpl.get("has_graph", False),
            "strip_cells": tpl.get("strip_cells", 0),
            "best_for": json.dumps(tpl.get("best_for", [])),
            "primitives": json.dumps(tpl.get("primitives", [])),
            "theme": tpl.get("theme_hint", "light"),
        }
        if tpl.get("chart_types"):
            metadata["chart_types"] = json.dumps(tpl["chart_types"])
        if tpl.get("activity_types"):
            metadata["activity_types"] = json.dumps(tpl["activity_types"])
        if tpl.get("table_columns"):
            metadata["table_columns"] = json.dumps(tpl["table_columns"]) if isinstance(tpl["table_columns"], (list, dict)) else str(tpl["table_columns"])
        docs.append(Document(page_content=text, metadata=metadata))

    if backend == "chroma":
        from langchain_chroma import Chroma
        store = Chroma.from_documents(
            docs,
            embeddings,
            collection_name="dashboard_templates",
            persist_directory=persist_dir or "./chroma_dashboard_templates",
        )
        logger.info(f"Built Chroma store with {len(docs)} template documents")
    else:
        from langchain_community.vectorstores import FAISS
        store = FAISS.from_documents(docs, embeddings)
        logger.info(f"Built FAISS store with {len(docs)} template documents")

    return store
