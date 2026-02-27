"""
CCE Layout Advisor — LangGraph Nodes
=====================================
Each node handles one phase of the conversational layout advisor.
Nodes read/write the LayoutAdvisorState and return state updates.

Flow:
  intake → [decision_intent → decision_systems → decision_audience 
           → decision_chat → decision_kpis] → scoring → recommendation
           → selection → customization → spec_generation → complete
           
Human-in-the-loop: The graph pauses at each decision node
waiting for user_response before proceeding.
"""

from __future__ import annotations
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from .state import (
    LayoutAdvisorState, Phase, Message,
    UpstreamContext, Decisions,
)
from .templates import (
    TEMPLATES, CATEGORIES, DECISION_TREE,
    AUTO_RESOLVE_HINTS, get_template_embedding_text,
)
from .vector_store import score_templates_hybrid

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# HELPER: Auto-resolve a decision from upstream context
# ═══════════════════════════════════════════════════════════════════════

def _try_auto_resolve(
    decision_node: dict,
    upstream: UpstreamContext,
) -> dict | None:
    """
    Check if upstream context can automatically answer this decision.
    Returns the maps_to dict if resolved, else None.
    """
    field = decision_node.get("auto_resolve_from")
    if not field:
        return None

    value = upstream.get(field)
    if value is None:
        return None

    decision_id = decision_node["id"]
    hints = AUTO_RESOLVE_HINTS.get(decision_id, {})

    # For boolean fields
    if isinstance(value, bool):
        for opt in decision_node["options"]:
            if opt["maps_to"].get("has_chat") == value:
                return opt["maps_to"]
        return None

    # For integer fields (kpi_count)
    if isinstance(value, int):
        if value == 0:
            return {"strip_cells": 0}
        elif value <= 4:
            return {"strip_cells": 4}
        elif value <= 6:
            return {"strip_cells": 6}
        else:
            return {"strip_cells": 8}

    # For string/list fields — keyword matching
    search_text = " ".join(value) if isinstance(value, list) else str(value)
    search_lower = search_text.lower()

    for keyword, option_idx in hints.items():
        if keyword in search_lower:
            if option_idx < len(decision_node["options"]):
                return decision_node["options"][option_idx]["maps_to"]

    return None


# ═══════════════════════════════════════════════════════════════════════
# NODE: Intake — Process upstream context, auto-resolve what we can
# ═══════════════════════════════════════════════════════════════════════

def intake_node(state: LayoutAdvisorState) -> dict:
    """
    Receives upstream context from prior agents.
    Attempts to auto-resolve decisions where possible.
    Outputs greeting + summary of what was auto-resolved.
    """
    upstream = state.get("upstream_context", {})
    auto_resolved = {}
    decisions = {}

    # Try auto-resolving each decision from upstream
    for decision in DECISION_TREE:
        resolved = _try_auto_resolve(decision, upstream)
        if resolved:
            auto_resolved[decision["id"]] = resolved
            decisions.update(resolved)
            logger.info(f"Auto-resolved '{decision['id']}': {resolved}")

    # Build greeting message
    auto_count = len(auto_resolved)
    total_count = len(DECISION_TREE)
    remaining = total_count - auto_count

    greeting_parts = [
        "I'm the **Layout Advisor**. I'll help you define a dashboard layout "
        "based on your use case.",
    ]

    if upstream.get("metrics") or upstream.get("kpis"):
        greeting_parts.append(
            f"\nI can see the upstream agents have prepared "
            f"{len(upstream.get('metrics', []))} metrics and "
            f"{len(upstream.get('kpis', []))} KPIs."
        )

    if auto_count > 0:
        greeting_parts.append(
            f"\nFrom your pipeline context, I was able to auto-resolve "
            f"**{auto_count}/{total_count}** decisions:"
        )
        for did, resolved in auto_resolved.items():
            key = list(resolved.keys())[0]
            val = resolved[key]
            greeting_parts.append(f"  • {did}: {key} = {val}")

    if remaining > 0:
        # Find the first unresolved decision
        first_unresolved = None
        for d in DECISION_TREE:
            if d["id"] not in auto_resolved:
                first_unresolved = d
                break
        if first_unresolved:
            greeting_parts.append(
                f"\nI still need {remaining} answer{'s' if remaining > 1 else ''}. "
                f"Let's start:\n\n**{first_unresolved['question']}**"
            )
    else:
        greeting_parts.append(
            "\nAll decisions resolved from context! Moving to template scoring..."
        )

    # Determine next phase
    if auto_count == total_count:
        next_phase = Phase.SCORING
    else:
        # Find first unresolved decision's phase
        phase_map = {
            "intent": Phase.DECISION_INTENT,
            "systems": Phase.DECISION_SYSTEMS,
            "audience": Phase.DECISION_AUDIENCE,
            "ai_chat": Phase.DECISION_CHAT,
            "kpi_bar": Phase.DECISION_KPIS,
        }
        for d in DECISION_TREE:
            if d["id"] not in auto_resolved:
                next_phase = phase_map[d["id"]]
                break

    return {
        "messages": [{"role": "agent", "content": "\n".join(greeting_parts), "metadata": {"phase": "intake", "auto_resolved": auto_resolved}}],
        "phase": next_phase,
        "decisions": decisions,
        "auto_resolved": auto_resolved,
        "needs_user_input": auto_count < total_count,
    }


# ═══════════════════════════════════════════════════════════════════════
# NODE: Decision — Generic handler for all 5 decision steps
# ═══════════════════════════════════════════════════════════════════════

DECISION_PHASE_MAP = {
    Phase.DECISION_INTENT: 0,
    Phase.DECISION_SYSTEMS: 1,
    Phase.DECISION_AUDIENCE: 2,
    Phase.DECISION_CHAT: 3,
    Phase.DECISION_KPIS: 4,
}

NEXT_PHASE = {
    Phase.DECISION_INTENT: Phase.DECISION_SYSTEMS,
    Phase.DECISION_SYSTEMS: Phase.DECISION_AUDIENCE,
    Phase.DECISION_AUDIENCE: Phase.DECISION_CHAT,
    Phase.DECISION_CHAT: Phase.DECISION_KPIS,
    Phase.DECISION_KPIS: Phase.SCORING,
}


def decision_node(state: LayoutAdvisorState) -> dict:
    """
    Processes the user's answer to the current decision question.
    Applies the decision mapping, advances to next phase.
    If the next decision was auto-resolved, skip it.
    """
    phase = state["phase"]
    user_response = state.get("user_response", "")
    auto_resolved = state.get("auto_resolved", {})

    decision_idx = DECISION_PHASE_MAP.get(phase)
    if decision_idx is None:
        return {"error": f"Invalid phase for decision node: {phase}"}

    decision = DECISION_TREE[decision_idx]

    # Match user response to an option
    matched_option = _match_user_response(user_response, decision["options"])
    if not matched_option:
        # Couldn't match — ask again
        options_text = "\n".join(
            f"  {i+1}. {opt['label']}" for i, opt in enumerate(decision["options"])
        )
        return {
            "messages": [
                {"role": "user", "content": user_response, "metadata": {}},
                {"role": "agent", "content": f"I didn't quite catch that. Could you pick one of these?\n\n{options_text}", "metadata": {"phase": phase.value}},
            ],
            "needs_user_input": True,
        }

    # Apply the decision
    new_decisions = matched_option["maps_to"]

    # Find next phase, skipping auto-resolved ones
    next_phase = NEXT_PHASE[phase]
    while next_phase in DECISION_PHASE_MAP:
        next_decision_idx = DECISION_PHASE_MAP[next_phase]
        next_decision_id = DECISION_TREE[next_decision_idx]["id"]
        if next_decision_id in auto_resolved:
            next_phase = NEXT_PHASE.get(next_phase, Phase.SCORING)
        else:
            break

    # Build agent response
    if next_phase == Phase.SCORING:
        agent_msg = (
            f"Got it — **{matched_option['label']}**.\n\n"
            "All decisions collected! Let me score the templates against your requirements..."
        )
        needs_input = False
    else:
        next_decision_idx = DECISION_PHASE_MAP[next_phase]
        next_question = DECISION_TREE[next_decision_idx]["question"]
        agent_msg = (
            f"Got it — **{matched_option['label']}**.\n\n"
            f"**{next_question}**"
        )
        needs_input = True

    return {
        "messages": [
            {"role": "user", "content": user_response, "metadata": {"decision": decision["id"]}},
            {"role": "agent", "content": agent_msg, "metadata": {"phase": phase.value, "decision_applied": new_decisions}},
        ],
        "phase": next_phase,
        "decisions": {**state.get("decisions", {}), **new_decisions},
        "needs_user_input": needs_input,
    }


def _match_user_response(response: str, options: list[dict]) -> dict | None:
    """Fuzzy-match user text to a decision option."""
    response_lower = response.lower().strip()

    # Try exact number match (1, 2, 3...)
    if response_lower.isdigit():
        idx = int(response_lower) - 1
        if 0 <= idx < len(options):
            return options[idx]

    # Try keyword overlap
    best_match = None
    best_score = 0
    for opt in options:
        label_words = set(opt["label"].lower().split())
        response_words = set(response_lower.split())
        overlap = len(label_words & response_words)
        if overlap > best_score:
            best_score = overlap
            best_match = opt

    # Require at least 1 word overlap
    if best_score >= 1:
        return best_match

    # Try substring match
    for opt in options:
        if opt["label"].lower() in response_lower or response_lower in opt["label"].lower():
            return opt

    return None


# ═══════════════════════════════════════════════════════════════════════
# NODE: Scoring — Score all templates against decisions
# ═══════════════════════════════════════════════════════════════════════

def scoring_node(state: LayoutAdvisorState) -> dict:
    """
    Score all 17 templates against the accumulated decisions.
    Uses hybrid scoring (rule-based + optional vector similarity).
    """
    decisions = state.get("decisions", {})

    # Run hybrid scoring
    ranked = score_templates_hybrid(decisions)

    # Build candidate list
    candidates = []
    for tid, score, reasons in ranked:
        tpl = TEMPLATES[tid]
        candidates.append({
            "template_id": tid,
            "name": tpl["name"],
            "icon": tpl.get("icon", ""),
            "score": score,
            "reasons": reasons,
            "description": tpl["description"],
            "category": tpl["category"],
            "complexity": tpl["complexity"],
            "has_chat": tpl["has_chat"],
            "strip_cells": tpl["strip_cells"],
            "best_for": tpl["best_for"],
        })

    top3 = candidates[:3]

    return {
        "candidate_templates": candidates,
        "recommended_top3": top3,
        "phase": Phase.RECOMMENDATION,
    }


# ═══════════════════════════════════════════════════════════════════════
# NODE: Recommendation — Present top 3 to user
# ═══════════════════════════════════════════════════════════════════════

def recommendation_node(state: LayoutAdvisorState) -> dict:
    """
    Present the top 3 recommended templates to the user.
    """
    top3 = state.get("recommended_top3", [])

    lines = ["Based on your answers, here are my **top 3 template recommendations**:\n"]
    for i, t in enumerate(top3):
        lines.append(
            f"**{i+1}. {t.get('icon','')} {t['name']}** (score: {t['score']})\n"
            f"{t['description']}\n"
            f"Match reasons: {', '.join(t['reasons'])}"
        )

    lines.append(
        "\n**Select a template** by name or number, "
        "or tell me if you want something different."
    )

    return {
        "messages": [{"role": "agent", "content": "\n\n".join(lines), "metadata": {"phase": "recommendation", "top3": [t["template_id"] for t in top3]}}],
        "phase": Phase.SELECTION,
        "needs_user_input": True,
    }


# ═══════════════════════════════════════════════════════════════════════
# NODE: Selection — User picks a template
# ═══════════════════════════════════════════════════════════════════════

def selection_node(state: LayoutAdvisorState) -> dict:
    """
    Process the user's template selection.
    """
    user_response = state.get("user_response", "")
    top3 = state.get("recommended_top3", [])
    all_candidates = state.get("candidate_templates", [])

    # Try to match
    selected_id = _match_template_selection(user_response, top3, all_candidates)

    if not selected_id:
        names = ", ".join(t["name"] for t in top3)
        return {
            "messages": [
                {"role": "user", "content": user_response, "metadata": {}},
                {"role": "agent", "content": f"I couldn't match that to a template. The top 3 are: {names}. Pick one by name or number (1-3).", "metadata": {}},
            ],
            "needs_user_input": True,
        }

    tpl = TEMPLATES[selected_id]

    agent_msg = (
        f"Excellent choice — **{tpl['name']}**.\n\n"
        f"**Structure:** {' → '.join(tpl['primitives'])}\n"
        f"**Panels:** {' | '.join(f'{k}: {v}' for k, v in tpl['panels'].items())}\n"
        f"**KPI Strip:** {tpl['strip_cells']} cells"
        + (f" — {', '.join(tpl.get('strip_example', [])[:3])}…" if tpl.get("strip_example") else "") + "\n"
        f"**AI Chat:** {'Yes' if tpl['has_chat'] else 'No'}\n"
        f"**Causal Graph:** {'Yes' if tpl.get('has_graph') else 'No'}\n\n"
        "Would you like to **customize** anything (KPI labels, filters, theme, panel contents), "
        "or say **\"looks good\"** to generate the final spec?"
    )

    return {
        "messages": [
            {"role": "user", "content": user_response, "metadata": {}},
            {"role": "agent", "content": agent_msg, "metadata": {"phase": "selection", "selected": selected_id}},
        ],
        "phase": Phase.CUSTOMIZATION,
        "selected_template_id": selected_id,
        "needs_user_input": True,
    }


def _match_template_selection(
    response: str, top3: list[dict], all_candidates: list[dict]
) -> str | None:
    """Match user response to a template ID."""
    response_lower = response.lower().strip()

    # Number match (1, 2, 3)
    if response_lower.isdigit():
        idx = int(response_lower) - 1
        if 0 <= idx < len(top3):
            return top3[idx]["template_id"]

    # Name match against top 3
    for t in top3:
        if t["name"].lower() in response_lower or t["template_id"] in response_lower:
            return t["template_id"]

    # Name match against all templates
    for t in all_candidates:
        if t["name"].lower() in response_lower or t["template_id"] in response_lower:
            return t["template_id"]

    # Check full registry
    for tid, tpl in TEMPLATES.items():
        if tpl["name"].lower() in response_lower or tid in response_lower:
            return tid

    return None


# ═══════════════════════════════════════════════════════════════════════
# NODE: Customization — Handle user tweaks
# ═══════════════════════════════════════════════════════════════════════

def customization_node(state: LayoutAdvisorState) -> dict:
    """
    Handle customization requests or finalization.
    If user says 'looks good' / 'finalize' → move to spec generation.
    Otherwise parse the customization and offer more changes.
    """
    user_response = state.get("user_response", "").lower().strip()
    customizations = list(state.get("customization_requests", []))

    # Check for finalization
    finalize_keywords = ["looks good", "finalize", "done", "generate", "go ahead", "perfect", "ship it", "lgtm"]
    if any(kw in user_response for kw in finalize_keywords):
        return {
            "messages": [
                {"role": "user", "content": state.get("user_response", ""), "metadata": {}},
            ],
            "phase": Phase.SPEC_GENERATION,
            "needs_user_input": False,
        }

    # Record the customization request
    customizations.append(state.get("user_response", ""))

    agent_msg = (
        f"Noted — I'll apply that customization. Anything else?\n\n"
        "You can adjust:\n"
        "• **Strip KPIs** — rename or reorder the headline metrics\n"
        "• **Filters** — change the filter chip options\n"
        "• **Theme** — switch between light and dark\n"
        "• **Panels** — swap panel contents or remove the chat panel\n"
        "• **Card anatomy** — change what fields appear on list cards\n\n"
        "Or say **\"looks good\"** to finalize the spec."
    )

    return {
        "messages": [
            {"role": "user", "content": state.get("user_response", ""), "metadata": {}},
            {"role": "agent", "content": agent_msg, "metadata": {"phase": "customization"}},
        ],
        "customization_requests": customizations,
        "needs_user_input": True,
    }


# ═══════════════════════════════════════════════════════════════════════
# NODE: Spec Generation — Build the final layout_spec JSON
# ═══════════════════════════════════════════════════════════════════════

def spec_generation_node(state: LayoutAdvisorState) -> dict:
    """
    Generate the final layout_spec JSON from selected template + decisions.
    This is the output that feeds into the downstream renderer.
    """
    template_id = state.get("selected_template_id", "")
    decisions = state.get("decisions", {})
    customizations_raw = state.get("customization_requests", [])

    tpl = TEMPLATES.get(template_id)
    if not tpl:
        return {
            "messages": [{"role": "agent", "content": f"Error: template '{template_id}' not found.", "metadata": {}}],
            "error": f"Template not found: {template_id}",
        }

    # Build base spec
    spec = {
        "template_id": template_id,
        "template_name": tpl["name"],
        "template_icon": tpl.get("icon", ""),
        "category": tpl["category"],
        "category_label": CATEGORIES.get(tpl["category"], {}).get("label", ""),
        "primitives": tpl["primitives"],
        "panels": tpl["panels"],
        "theme": decisions.get("theme", "dark" if "dark" in tpl.get("theme_hint", "") else "light"),
        "strip_cells": tpl["strip_cells"],
        "strip_kpis": tpl.get("strip_example", []),
        "has_chat": tpl["has_chat"],
        "has_causal_graph": tpl.get("has_graph", False),
        "has_filters": tpl.get("has_filters", False),
        "card_anatomy": tpl.get("card_anatomy", {}),
        "filters": _get_default_filters(decisions.get("domain", "security")),
        "detail_sections": tpl["panels"].get("center", "").split(" + "),
        "domain": decisions.get("domain", tpl["domains"][0] if tpl["domains"] else "security"),
        "complexity": tpl["complexity"],
        "decisions_applied": decisions,
        "best_for": tpl["best_for"],
        "domains": tpl["domains"],
        "customizations_applied": customizations_raw,
    }

    agent_msg = (
        f"Layout spec **finalized** ✓\n\n"
        f"→ Template: **{tpl['name']}** ({tpl.get('icon', '')})\n"
        f"→ {len(tpl['primitives'])} primitives: {' → '.join(tpl['primitives'])}\n"
        f"→ Theme: {spec['theme']}\n"
        f"→ {spec['strip_cells']} KPI cells\n"
        f"→ Chat: {'Yes' if spec['has_chat'] else 'No'}\n\n"
        "The spec is ready for the downstream renderer. "
        "No actual data is bound — this is purely the structural blueprint.\n\n"
        "Say **\"start over\"** for another dashboard, or ask me to explain any part of the spec."
    )

    return {
        "messages": [{"role": "agent", "content": agent_msg, "metadata": {"phase": "spec_generation", "spec_preview": True}}],
        "phase": Phase.COMPLETE,
        "layout_spec": spec,
        "needs_user_input": False,
    }


def _get_default_filters(domain: str) -> list[str]:
    filters = {
        "security":    ["All", "Critical", "High", "Medium", "Low"],
        "cornerstone": ["All", "Overdue", "In Progress", "Completed", "Not Started"],
        "workday":     ["All", "Open", "In Review", "Approved", "Closed"],
        "hybrid":      ["All", "Failing", "Degraded", "Passing", "Not Evaluated"],
        "data_ops":    ["All", "Failed", "Running", "Succeeded", "Scheduled"],
    }
    return filters.get(domain, filters["security"])
