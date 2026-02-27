"""
CCE Layout Advisor — LangGraph Tools
=====================================
Tools callable by the LLM agent during the layout conversation.
These are bound to the agent node so the LLM can:
  1. Search templates by semantic similarity
  2. Score templates against accumulated decisions
  3. Get template details
  4. Generate the final layout spec
  5. Apply customizations to an existing spec
"""

from __future__ import annotations
import json
from typing import Optional

from langchain_core.tools import tool

from .templates import TEMPLATES, CATEGORIES, DECISION_TREE
from .vector_store import score_templates_hybrid


# ═══════════════════════════════════════════════════════════════════════
# TOOL 1: Search Templates (semantic — requires vector store in state)
# ═══════════════════════════════════════════════════════════════════════

@tool
def search_templates(query: str, k: int = 5) -> str:
    """
    Semantic search across the 17-template registry.
    Use when the user describes what they need in natural language
    and you want to find the closest matching templates.
    
    Args:
        query: Natural language description of the dashboard need
        k: Number of results to return (default 5)
    
    Returns:
        JSON array of matching templates with scores.
    """
    # NOTE: In production, this accesses the vector store from the graph state.
    # For the tool definition, we provide the signature.
    # The actual vector store call is wired in the agent node.
    return json.dumps({
        "note": "Vector store search — wired at runtime via graph state",
        "query": query,
        "k": k,
    })


# ═══════════════════════════════════════════════════════════════════════
# TOOL 2: Score Templates (rule-based + optional vector boost)
# ═══════════════════════════════════════════════════════════════════════

@tool
def score_templates(decisions: dict) -> str:
    """
    Score all 17 templates against the accumulated user decisions.
    Combines rule-based matching (category, domain, theme, complexity, 
    chat, KPI strip) with optional semantic similarity boost.
    
    Args:
        decisions: Dict with keys like category, domain, theme, 
                   complexity, has_chat, strip_cells
    
    Returns:
        JSON array of top 5 templates with scores and match reasons.
    """
    ranked = score_templates_hybrid(decisions)
    top5 = ranked[:5]
    results = []
    for tid, score, reasons in top5:
        tpl = TEMPLATES[tid]
        results.append({
            "template_id": tid,
            "name": tpl["name"],
            "score": score,
            "reasons": reasons,
            "description": tpl["description"],
            "category": tpl["category"],
            "complexity": tpl["complexity"],
            "has_chat": tpl["has_chat"],
            "strip_cells": tpl["strip_cells"],
        })
    return json.dumps(results, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 3: Get Template Detail
# ═══════════════════════════════════════════════════════════════════════

@tool
def get_template_detail(template_id: str) -> str:
    """
    Get the full specification of a specific template by ID.
    Use after scoring to present detailed information about 
    a recommended template.
    
    Args:
        template_id: The template ID (e.g. "command-center", "risk-register")
    
    Returns:
        Full template JSON or error message.
    """
    tpl = TEMPLATES.get(template_id)
    if not tpl:
        return json.dumps({"error": f"Template '{template_id}' not found. Available: {list(TEMPLATES.keys())}"})
    return json.dumps(tpl, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4: Generate Layout Spec
# ═══════════════════════════════════════════════════════════════════════

@tool
def generate_layout_spec(
    template_id: str,
    decisions: dict,
    customizations: Optional[dict] = None,
) -> str:
    """
    Generate the final layout_spec JSON from a selected template + decisions.
    This is the output that the downstream renderer consumes.
    
    Args:
        template_id: Selected template ID
        decisions: All accumulated decisions from the conversation
        customizations: Optional overrides (strip_kpis, filters, theme, etc.)
    
    Returns:
        Complete layout_spec JSON ready for the renderer.
    """
    tpl = TEMPLATES.get(template_id)
    if not tpl:
        return json.dumps({"error": f"Template '{template_id}' not found"})

    # Build base spec
    spec = {
        "template_id": template_id,
        "template_name": tpl["name"],
        "template_icon": tpl.get("icon", ""),
        "category": tpl["category"],
        "category_label": CATEGORIES.get(tpl["category"], {}).get("label", ""),

        # Structure
        "primitives": tpl["primitives"],
        "panels": tpl["panels"],

        # Theme
        "theme": decisions.get("theme") or (
            "dark" if "dark" in tpl.get("theme_hint", "") else "light"
        ),

        # KPI Strip
        "strip_cells": tpl["strip_cells"],
        "strip_kpis": tpl.get("strip_example", []),

        # Features
        "has_chat": tpl["has_chat"],
        "has_causal_graph": tpl.get("has_graph", False),
        "has_filters": tpl.get("has_filters", False),

        # Card anatomy
        "card_anatomy": tpl.get("card_anatomy", {}),

        # Filters
        "filters": _default_filters(tpl, decisions),

        # Detail sections (parsed from center panel config)
        "detail_sections": tpl["panels"].get("center", "").split(" + "),

        # Domain & complexity
        "domain": decisions.get("domain", tpl["domains"][0] if tpl["domains"] else "security"),
        "complexity": tpl["complexity"],

        # Metadata
        "decisions_applied": decisions,
        "best_for": tpl["best_for"],
        "domains": tpl["domains"],
    }

    # Apply customizations
    if customizations:
        if "strip_kpis" in customizations:
            spec["strip_kpis"] = customizations["strip_kpis"]
            spec["strip_cells"] = len(customizations["strip_kpis"])
        if "filters" in customizations:
            spec["filters"] = customizations["filters"]
        if "theme" in customizations:
            spec["theme"] = customizations["theme"]
        if "panels" in customizations:
            spec["panels"] = {**spec["panels"], **customizations["panels"]}
        if "has_chat" in customizations:
            spec["has_chat"] = customizations["has_chat"]
        if "detail_sections" in customizations:
            spec["detail_sections"] = customizations["detail_sections"]
        if "card_anatomy" in customizations:
            spec["card_anatomy"] = {**spec["card_anatomy"], **customizations["card_anatomy"]}

    return json.dumps(spec, indent=2, default=str)


def _default_filters(tpl: dict, decisions: dict) -> list[str]:
    """Pick default filter chips based on domain."""
    domain = decisions.get("domain", "security")
    domain_filters = {
        "security":     ["All", "Critical", "High", "Medium", "Low"],
        "cornerstone":  ["All", "Overdue", "In Progress", "Completed", "Not Started"],
        "workday":      ["All", "Open", "In Review", "Approved", "Closed"],
        "hybrid":       ["All", "Failing", "Degraded", "Passing", "Not Evaluated"],
        "data_ops":     ["All", "Failed", "Running", "Succeeded", "Scheduled"],
    }
    if tpl.get("has_filters"):
        return domain_filters.get(domain, domain_filters["security"])
    return []


# ═══════════════════════════════════════════════════════════════════════
# TOOL 5: Apply Customization
# ═══════════════════════════════════════════════════════════════════════

@tool
def apply_customization(
    current_spec: dict,
    modification: dict,
) -> str:
    """
    Apply a user's customization request to an existing layout spec.
    
    Args:
        current_spec: The current layout_spec dict
        modification: Dict of fields to update, e.g.:
            {"theme": "dark"}
            {"strip_kpis": ["KPI A", "KPI B", "KPI C"]}
            {"has_chat": False}
            {"panels": {"right": "removed"}}
    
    Returns:
        Updated layout_spec JSON.
    """
    updated = {**current_spec}

    for key, value in modification.items():
        if key == "strip_kpis":
            updated["strip_kpis"] = value
            updated["strip_cells"] = len(value)
        elif key == "panels" and isinstance(value, dict):
            updated["panels"] = {**updated.get("panels", {}), **value}
        elif key == "card_anatomy" and isinstance(value, dict):
            updated["card_anatomy"] = {**updated.get("card_anatomy", {}), **value}
        elif key == "detail_sections" and isinstance(value, list):
            updated["detail_sections"] = value
        else:
            updated[key] = value

    return json.dumps(updated, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 6: List Available Templates
# ═══════════════════════════════════════════════════════════════════════

@tool
def list_templates(category: Optional[str] = None) -> str:
    """
    List all available templates, optionally filtered by category.
    
    Args:
        category: Optional category filter (operations, executive, 
                  hr_learning, cross_domain, data_ops, grc, iam, compliance)
    
    Returns:
        JSON array of template summaries.
    """
    results = []
    for tid, tpl in TEMPLATES.items():
        if category and tpl["category"] != category:
            continue
        results.append({
            "id": tid,
            "name": tpl["name"],
            "icon": tpl.get("icon", ""),
            "category": tpl["category"],
            "description": tpl["description"][:120] + "…",
            "complexity": tpl["complexity"],
            "domains": tpl["domains"],
        })
    return json.dumps(results, indent=2)


# ── Collect all tools for binding to agent ────────────────────────────

LAYOUT_TOOLS = [
    search_templates,
    score_templates,
    get_template_detail,
    generate_layout_spec,
    apply_customization,
    list_templates,
]
