"""
CCE Template Scoring Utilities
===============================
Scoring functions for matching dashboard templates against user decisions.

Note: For vector store operations, use DashboardTemplateRetrievalService
from app.dashboard_agent.dashboard_template_service.

This module provides the score_templates_hybrid function which is used
by the LangGraph workflow (nodes.py, tools.py, server.py).
"""

from __future__ import annotations
import logging
from typing import Optional

# Try to import unified registry, fallback to base templates
try:
    from app.dashboard_agent.registry_config.registry_unified import (
        ALL_TEMPLATES as TEMPLATES,
        ALL_CATEGORIES as CATEGORIES,
        score_all_templates,
    )
except ImportError:
    # Fallback to base templates
    from .templates import TEMPLATES, CATEGORIES
    score_all_templates = None  # Set later to avoid circular dependency

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# HYBRID SCORER — Combines vector similarity + rule-based scoring
# ═══════════════════════════════════════════════════════════════════════

def score_templates_hybrid(
    decisions: dict,
    vector_results: Optional[list[dict]] = None,
) -> list[tuple[str, int, list[str]]]:
    """
    Score all templates against decisions using rule-based weights,
    optionally boosted by vector similarity scores.
    
    Uses unified registry scoring if available, otherwise falls back to local implementation.
    
    Returns: [(template_id, total_score, [reasons]), ...] sorted desc.
    """
    # Use unified registry scoring if available
    if score_all_templates is not None:
        try:
            base_scores = score_all_templates(decisions)
            
            # Add vector boost if provided
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
            pass  # Fall through to local implementation
    
    # Fallback to local implementation
    scores: dict[str, dict] = {}

    for tid, tpl in TEMPLATES.items():
        score = 0
        reasons = []

        # Category match (30 pts)
        if decisions.get("category") and tpl.get("category"):
            cats = decisions["category"]
            if isinstance(cats, list):
                if tpl["category"] in cats:
                    score += 30
                    reasons.append(f"category match: {tpl['category']}")
            elif tpl["category"] == cats:
                score += 30
                reasons.append(f"category match: {tpl['category']}")

        # Domain match (25 pts)
        if decisions.get("domain") and tpl.get("domains"):
            if decisions["domain"] in tpl["domains"]:
                score += 25
                reasons.append(f"domain match: {decisions['domain']}")

        # Theme match (10 pts)
        if decisions.get("theme") and tpl.get("theme_hint"):
            if decisions["theme"] in tpl["theme_hint"]:
                score += 10
                reasons.append(f"theme: {decisions['theme']}")

        # Complexity match (10 pts)
        if decisions.get("complexity") and tpl.get("complexity"):
            if tpl["complexity"] == decisions["complexity"]:
                score += 10
                reasons.append(f"complexity: {decisions['complexity']}")

        # Chat match (15 pts)
        if decisions.get("has_chat") is not None:
            if tpl.get("has_chat") == decisions["has_chat"]:
                score += 15
                reasons.append(f"chat: {'yes' if decisions['has_chat'] else 'no'}")

        # Strip cells match (10 pts)
        if decisions.get("strip_cells") is not None:
            if decisions["strip_cells"] == 0 and tpl.get("strip_cells", 0) == 0:
                score += 10
                reasons.append("no KPI strip")
            elif decisions["strip_cells"] > 0 and tpl.get("strip_cells", 0) > 0:
                score += 5
                if abs(decisions["strip_cells"] - tpl["strip_cells"]) <= 2:
                    score += 5
                    reasons.append(f"strip cells ~{tpl['strip_cells']}")

        # Vector similarity boost (up to 15 pts)
        if vector_results:
            for vr in vector_results:
                if vr["template_id"] == tid:
                    boost = int(vr.get("similarity_score", 0.0) * 15)
                    score += boost
                    reasons.append(f"semantic similarity +{boost}")
                    break

        scores[tid] = {"score": score, "reasons": reasons}

    # Sort descending
    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    return [(tid, data["score"], data["reasons"]) for tid, data in ranked]
