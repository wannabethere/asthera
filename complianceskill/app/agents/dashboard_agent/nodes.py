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
from .tools import fetch_data_tables
from .templates import (
    TEMPLATES, CATEGORIES, DECISION_TREE,
    AUTO_RESOLVE_HINTS, get_template_embedding_text,
)
from app.services.dashboard_template_vector_store import (
    score_templates_hybrid,
    ALL_TEMPLATES,
)
from .taxonomy_matcher import (
    map_metric_widget_to_chart,
    match_metric_to_gold_table,
    get_taxonomy_slice_for_prompt,
    match_domain_from_metrics,
    expand_use_case_group,
    join_control_anchors,
    match_use_case_group,
)
from .retrieval import (
    retrieve_similar_templates,
    retrieve_metric_catalog_context,
    retrieve_past_layout_specs,
)

logger = logging.getLogger(__name__)


# ── Dashboard Decision Tree integration (dashboard_decision_tree.md) ───────

def _build_state_for_resolve_decisions(state: LayoutAdvisorState) -> dict:
    """Build state dict for resolve_decisions from LayoutAdvisorState."""
    upstream = state.get("upstream_context", {})
    decisions = state.get("decisions", {})
    agent_config = state.get("agent_config", {})

    # Metrics: prefer metric_recommendations, else metrics
    metric_recs = upstream.get("metric_recommendations", [])
    metrics_raw = upstream.get("metrics", [])
    metrics = metric_recs or [
        {"name": m.get("name", ""), "type": m.get("widget_type", m.get("type", "")), "metric_type": m.get("metric_type", "")}
        for m in metrics_raw[:30]
    ]

    output_format = (
        state.get("output_format")
        or upstream.get("output_format")
        or agent_config.get("default_output_format", "echarts")
    )
    # Map echarts -> embedded, powerbi -> powerbi, etc.
    dest_map = {"echarts": "embedded", "powerbi": "powerbi", "html": "simple", "slack": "slack_digest", "api": "api_json"}
    output_lower = (output_format or "").lower()
    for k, v in dest_map.items():
        if k in output_lower:
            output_format = v
            break
    if output_format not in ("embedded", "powerbi", "simple", "slack_digest", "api_json"):
        output_format = "embedded"

    framework = upstream.get("framework", "")
    if isinstance(framework, list):
        framework = framework[0] if framework else ""
    framework_id = (framework or "").lower().replace(" ", "_") if framework else ""

    data_sources = upstream.get("data_sources", []) or []
    if isinstance(data_sources, str):
        data_sources = [data_sources]

    return {
        "user_query": upstream.get("goal_statement", "") or upstream.get("use_case", ""),
        "intent": upstream.get("goal_statement", "") or upstream.get("use_case", ""),
        "output_format": output_format,
        "persona": upstream.get("persona", "") or decisions.get("audience", ""),
        "framework_id": framework_id,
        "timeframe": upstream.get("timeframe", "monthly"),
        "selected_data_sources": data_sources,
        "data_enrichment": upstream.get("data_enrichment", {}),
        "resolved_metrics": metrics,
        "metrics": metrics,
        "agent_config": agent_config,
    }


def _run_dashboard_decision_tree(state: LayoutAdvisorState) -> dict | None:
    """
    Run the 7-question dashboard decision tree flow (resolve → gate → score).
    Returns state updates for LayoutAdvisorState, or None if flow fails.
    """
    try:
        from app.agents.decision_trees.dashboard.dashboard_decision_tree_service import (
            DashboardDecisionTreeService,
        )
        from app.agents.decision_trees.dashboard.dt_dashboard_decision_nodes import (
            enrich_dashboard_with_decision_tree,
        )
    except ImportError as e:
        logger.debug("Dashboard decision tree not available: %s", e)
        return None

    dt_state = _build_state_for_resolve_decisions(state)
    query = dt_state.get("user_query", "") or "dashboard"
    if not query.strip():
        query = "compliance security operations dashboard"

    try:
        service = DashboardDecisionTreeService()
        ctx = service.search_all(
            query=query,
            templates_limit=15,
            metrics_limit=20,
            destination_filter=dt_state.get("output_format", "embedded"),
        )
        dt_state.update(ctx.to_state_payload())
    except Exception as e:
        logger.warning("DashboardDecisionTreeService.search_all failed: %s", e)
        return None

    if not dt_state.get("dt_enriched_templates"):
        logger.info("No enriched templates from vector store, falling back to legacy scoring")
        return None

    enrich_dashboard_with_decision_tree(dt_state)

    decisions = dt_state.get("dt_dashboard_decisions", {})
    candidates = dt_state.get("dt_template_candidates", [])
    winning = dt_state.get("dt_winning_template")
    resolution = state.get("resolution_payload", {}) or {}

    # Map dt_* to LayoutAdvisorState format
    candidate_templates = []
    for c in candidates:
        candidate_templates.append({
            "template_id": c.get("template_id", ""),
            "name": c.get("name", ""),
            "icon": c.get("theme_hint", ""),
            "score": int((c.get("composite_score", 0) or 0) * 100),
            "reasons": ["decision_tree_match"],
            "description": c.get("description", ""),
            "category": c.get("category", ""),
            "complexity": c.get("complexity", "medium"),
            "has_chat": c.get("has_chat", False),
            "strip_cells": c.get("strip_cells", 0),
            "best_for": c.get("best_for", []),
            "coverage_gaps": dt_state.get("dt_coverage_gaps", []),
            "coverage_pct": 1.0,
        })

    resolution_update = {
        **resolution,
        "destination_type": decisions.get("destination_type", "embedded"),
        "interaction_mode": decisions.get("interaction_mode", "drill_down"),
        "metric_profile": decisions.get("metric_profile", "mixed"),
        "registry_target": decisions.get("registry_target", "dashboard_registry"),
        "focus_areas": resolution.get("focus_areas", []) or [decisions.get("focus_area", "")],
        "audience": decisions.get("audience", resolution.get("audience", "security_ops")),
        "complexity": decisions.get("complexity", resolution.get("complexity", "medium")),
    }

    decisions_update = {
        **state.get("decisions", {}),
        "destination_type": decisions.get("destination_type"),
        "interaction_mode": decisions.get("interaction_mode"),
        "metric_profile": decisions.get("metric_profile"),
        "focus_area": decisions.get("focus_area"),
        "audience": decisions.get("audience"),
        "category": decisions.get("category"),
        "complexity": decisions.get("complexity"),
        "domain": decisions.get("category", "").replace("_", " "),
    }

    return {
        "candidate_templates": candidate_templates,
        "recommended_top3": candidate_templates[:3],
        "resolution_payload": resolution_update,
        "decisions": decisions_update,
        "retrieved_metric_context": dt_state.get("retrieved_metric_context", state.get("retrieved_metric_context", [])),
    }


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
    Goal-driven path: when metric_recommendations + gold_model_sql are provided,
    routes directly to BIND (skip decision loop).
    """
    upstream = state.get("upstream_context", {})
    auto_resolved = {}
    decisions = {}

    # Goal-driven path: metrics + gold models from upstream → skip to BIND
    metric_recs = upstream.get("metric_recommendations", [])
    gold_sql = upstream.get("gold_model_sql", [])
    has_goal_driven_input = bool(metric_recs and gold_sql)

    if has_goal_driven_input:
        # Build resolution_payload for BIND stage
        resolution_payload = {
            "metric_recommendations": metric_recs,
            "gold_model_sql": gold_sql,
            "timeframe": "monthly",
            "audience": upstream.get("persona", "security_ops"),
            "complexity": "medium",
        }
        # Derive metrics/kpis for domain matching
        metrics_for_domain = [
            {"name": m.get("name", ""), "type": m.get("widget_type", ""), "source_table": ""}
            for m in metric_recs[:20]
        ]
        kpis_for_domain = [{"label": m.get("name", "")} for m in metric_recs[:10] if not m.get("parent_metric_id")]
        domain_matches = match_domain_from_metrics(
            metrics_for_domain,
            kpis_for_domain,
            use_case=upstream.get("goal_statement", ""),
            data_sources=list({m.get("data_source_required") for m in metric_recs if m.get("data_source_required")}),
        )
        if domain_matches:
            top_domain = domain_matches[0][2]
            resolution_payload["focus_areas"] = top_domain.get("focus_areas", [])
            resolution_payload["domain"] = top_domain.get("domain", "security_operations")

        agent_config = state.get("agent_config", {})
        goals = agent_config.get("dashboard_goals", [])
        persona = agent_config.get("summary_writer_persona", "auditor")
        greeting_parts = [
            "I'm the **Layout Advisor**. I see you have **metric recommendations** and **gold model SQL** "
            "from the upstream pipeline.",
            f"\n• **{len(metric_recs)}** metrics recommended",
            f"• **{len(gold_sql)}** gold tables available",
            f"\nI'll recommend a layout and bind metrics to gold tables for human approval. "
            "Target output: **" + (upstream.get("output_format") or agent_config.get("default_output_format", "echarts")) + "**.",
        ]
        if goals:
            greeting_parts.append(f"\n**Dashboard goals:** {', '.join(goals[:3])}")
        if persona:
            greeting_parts.append(f"**Summary persona:** {persona}")
        return {
            "messages": [{"role": "agent", "content": "\n".join(greeting_parts), "metadata": {"phase": "intake", "goal_driven": True}}],
            "phase": Phase.BIND,
            "resolution_payload": resolution_payload,
            "decisions": {},
            "auto_resolved": {"goal_driven": True},
            "needs_user_input": False,
            "output_format": upstream.get("output_format", "echarts"),
        }

    # Standard path: try auto-resolving each decision from upstream
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
            "\nAll decisions resolved from context! Binding to registries and scoring templates..."
        )

    # Determine next phase
    if auto_count == total_count:
        next_phase = Phase.BIND  # Resolve → Bind → Score
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
    Phase.DECISION_KPIS: Phase.BIND,  # Resolve → Bind → Score (goal-driven design)
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
            next_phase = NEXT_PHASE.get(next_phase, Phase.BIND)
        else:
            break

    # Build agent response
    if next_phase in (Phase.BIND, Phase.SCORING):
        agent_msg = (
            f"Got it — **{matched_option['label']}**.\n\n"
            "All decisions collected! Binding to registries and scoring templates..."
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
# NODE: Bind — Join metrics to gold tables (goal-driven path) or registry (standard)
# ═══════════════════════════════════════════════════════════════════════

def bind_node(state: LayoutAdvisorState) -> dict:
    """
    BIND stage: when metric_recommendations + gold_model_sql are in resolution_payload,
    map metrics to gold tables and chart types. Otherwise expand use_case_group from
    decisions and join control anchors (standard path).
    """
    resolution = state.get("resolution_payload", {})
    metric_recs = resolution.get("metric_recommendations", [])
    gold_sql = resolution.get("gold_model_sql", [])
    decisions = state.get("decisions", {})
    goal_statement = state.get("upstream_context", {}).get("goal_statement", "")

    if not metric_recs or not gold_sql:
        # Standard path: expand use case group from decisions
        use_case_group = state.get("use_case_group") or match_use_case_group(goal_statement)[0]
        complexity = decisions.get("complexity", "medium")
        fw = decisions.get("framework") or "soc2"
        framework = fw.lower() if isinstance(fw, str) else (fw[0].lower() if fw else "soc2")
        expanded = expand_use_case_group(use_case_group, complexity)
        # Map metric groups to focus areas (control taxonomy uses these)
        metric_group_to_focus = {
            "compliance_posture": ["training_compliance", "access_control"],
            "control_effectiveness": ["change_management", "access_control"],
            "risk_exposure": ["vulnerability_management", "data_protection"],
            "operational_security": ["vulnerability_management", "access_control"],
            "remediation_velocity": ["vulnerability_management", "change_management"],
            "training_completion": ["training_compliance"],
        }
        all_groups = expanded.get("required_groups", []) + expanded.get("optional_included", [])
        focus_areas = []
        for g in all_groups:
            focus_areas.extend(metric_group_to_focus.get(g, [g]))
        focus_areas = list(dict.fromkeys(focus_areas)) or ["vulnerability_management", "access_control"]
        anchors = join_control_anchors(focus_areas, framework)
        resolution = {
            "resolved_metric_groups": expanded,
            "control_anchors": anchors,
            "focus_areas": focus_areas,
            "timeframe": expanded.get("default_timeframe", "monthly"),
            "audience": expanded.get("default_audience", "security_ops"),
            "complexity": complexity,
        }
        return {"resolution_payload": resolution, "phase": Phase.SCORING}

    bindings = []
    for m in metric_recs:
        gold_table = match_metric_to_gold_table(m, gold_sql)
        chart_type = map_metric_widget_to_chart(
            m.get("widget_type", "trend_line"),
            m.get("kpi_value_type"),
            m.get("metrics_intent"),
        )
        is_strip = m.get("kpi_value_type") in ("count", "percentage") and not m.get("parent_metric_id")
        bindings.append({
            "metric_id": m.get("id", ""),
            "metric_name": m.get("name", ""),
            "gold_table_name": gold_table or "",
            "chart_type": chart_type,
            "strip_cell": is_strip,
            "panel_slot": "center",
        })

    # Parent metrics for strip; limit to 8
    strip_cells = [b["metric_id"] for b in bindings if b.get("strip_cell")][:8]
    if len(strip_cells) < 4:
        strip_cells = [b["metric_id"] for b in bindings[:6] if not b.get("metric_id", "").endswith("_")]

    resolution["metric_to_gold_map"] = {b["metric_id"]: b["gold_table_name"] for b in bindings if b["gold_table_name"]}
    resolution["metric_gold_model_bindings"] = bindings

    return {
        "resolution_payload": resolution,
        "metric_gold_model_bindings": bindings,
        "phase": Phase.SCORING,
    }


# ═══════════════════════════════════════════════════════════════════════
# NODE: Scoring — Score all templates against decisions
# ═══════════════════════════════════════════════════════════════════════

def scoring_node(state: LayoutAdvisorState) -> dict:
    """
    Score templates against decisions. Prefers the 7-question dashboard decision
    tree flow (resolve_decisions + destination gate + vector-store templates).
    Falls back to legacy score_templates_hybrid when decision tree unavailable.
    """
    # Try dashboard decision tree flow first (dashboard_decision_tree.md)
    dt_result = _run_dashboard_decision_tree(state)
    if dt_result:
        return {
            **dt_result,
            "phase": Phase.RECOMMENDATION,
        }

    # Legacy flow: score_templates_hybrid + vector boost
    decisions = state.get("decisions", {})
    bindings = state.get("metric_gold_model_bindings", [])
    resolution = state.get("resolution_payload", {})
    is_goal_driven = bool(bindings)

    # RETRIEVAL POINT 1 — template similarity boost
    upstream = state.get("upstream_context", {})
    goal_statement = upstream.get("goal_statement", "")
    domain = decisions.get("domain", resolution.get("domain", ""))
    query_text = " ".join(filter(None, [
        goal_statement,
        domain,
        decisions.get("complexity", ""),
        upstream.get("use_case", ""),
        " ".join(upstream.get("data_sources", []) or []),
    ]))
    vector_boosts: dict[str, int] = {}
    if query_text.strip():
        boost_list = retrieve_similar_templates(query_text, k=5)
        vector_boosts = {b["template_id"]: b["boost"] for b in boost_list}

    ranked = score_templates_hybrid(decisions)
    if vector_boosts:
        ranked = [
            (tid, score + vector_boosts.get(tid, 0), reasons)
            for tid, score, reasons in ranked
        ]
        ranked.sort(key=lambda x: x[1], reverse=True)

    if is_goal_driven:
        strip_count = min(8, max(4, len([b for b in bindings if b.get("strip_cell")])))
        boosted = []
        for tid, score, reasons in ranked:
            tpl = ALL_TEMPLATES.get(tid) or TEMPLATES.get(tid, {})
            if tpl.get("strip_cells", 0) >= strip_count - 2:
                score += 15
                reasons = list(reasons) + ["strip_cell_count_match"]
            if domain in (tpl.get("domains") or []):
                score += 20
                reasons = list(reasons) + ["domain_match"]
            boosted.append((tid, score, reasons))
        ranked = sorted(boosted, key=lambda x: x[1], reverse=True)

    # Build candidate list with coverage_gaps (goal-driven design)
    control_anchors = resolution.get("control_anchors", [])
    anchor_ids = [a.get("id") for a in control_anchors if isinstance(a, dict) and a.get("id")]

    candidates = []
    for tid, score, reasons in ranked:
        tpl = ALL_TEMPLATES.get(tid) or TEMPLATES.get(tid, {})
        strip_count = tpl.get("strip_cells", 0)
        coverage_gaps = [aid for aid in anchor_ids[strip_count:]] if anchor_ids and strip_count < len(anchor_ids) else []
        coverage_pct = 1.0 - (len(coverage_gaps) / len(anchor_ids)) if anchor_ids else 1.0

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
            "coverage_gaps": coverage_gaps,
            "coverage_pct": round(coverage_pct, 2),
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
        options_text = "\n".join(
            f"  {i+1}. {t.get('icon','')} {t['name']}"
            for i, t in enumerate(top3)
        )
        return {
            "messages": [
                {"role": "user", "content": user_response, "metadata": {}},
                {
                    "role": "agent",
                    "content": (
                        f"I couldn't match '{user_response}' to a template. "
                        f"Please pick by number or name:\n\n{options_text}"
                    ),
                    "metadata": {"phase": "selection", "selection_failed": True},
                },
            ],
            "phase": Phase.SELECTION,
            "needs_user_input": True,
            "recommended_top3": top3,
        }

    tpl = ALL_TEMPLATES.get(selected_id) or TEMPLATES.get(selected_id, {})
    # Fallback: use selected candidate from top3/all_candidates when template not in registry
    # (e.g. decision tree returns templates not in legacy registry)
    if not tpl or not tpl.get("primitives"):
        selected_candidate = next(
            (c for c in top3 + all_candidates if c.get("template_id") == selected_id),
            None,
        )
        if selected_candidate:
            tpl = {
                "name": selected_candidate.get("name", selected_id),
                "primitives": selected_candidate.get("primitives", ["list", "detail"]),
                "panels": selected_candidate.get("panels", {"left": "list", "center": "detail"}),
                "strip_cells": selected_candidate.get("strip_cells", 6),
                "strip_example": selected_candidate.get("strip_example", []),
                "has_chat": selected_candidate.get("has_chat", False),
                "has_graph": selected_candidate.get("has_graph", False),
            }

    agent_config = state.get("agent_config", {})
    enable_data_tables = agent_config.get("enable_data_tables_hitl", True)

    primitives = tpl.get("primitives", [])
    panels = tpl.get("panels", {})
    strip_cells = tpl.get("strip_cells", 6)
    strip_example = tpl.get("strip_example", [])

    if enable_data_tables:
        agent_msg = (
            f"Excellent choice — **{tpl.get('name', selected_id)}**.\n\n"
            f"**Structure:** {' → '.join(primitives) if primitives else 'list → detail'}\n"
            f"**Panels:** {' | '.join(f'{k}: {v}' for k, v in panels.items()) if panels else 'left: list | center: detail'}\n"
            f"**KPI Strip:** {strip_cells} cells"
            + (f" — {', '.join(strip_example[:3])}…" if strip_example else "") + "\n\n"
            "**Add data tables to charts?** Ask in natural language, e.g.:\n"
            "• \"Add vulnerability data\"\n"
            "• \"Include agent coverage metrics\"\n"
            "• \"Show backlog trend\"\n\n"
            "Or say **\"skip\"** or **\"done\"** to go to customization."
        )
        next_phase = Phase.DATA_TABLES
    else:
        agent_msg = (
            f"Excellent choice — **{tpl.get('name', selected_id)}**.\n\n"
            f"**Structure:** {' → '.join(primitives) if primitives else 'list → detail'}\n"
            f"**Panels:** {' | '.join(f'{k}: {v}' for k, v in panels.items()) if panels else 'left: list | center: detail'}\n"
            f"**KPI Strip:** {strip_cells} cells"
            + (f" — {', '.join(strip_example[:3])}…" if strip_example else "") + "\n"
            f"**AI Chat:** {'Yes' if tpl.get('has_chat') else 'No'}\n"
            f"**Causal Graph:** {'Yes' if tpl.get('has_graph') else 'No'}\n\n"
            "Would you like to **customize** anything (KPI labels, filters, theme, panel contents), "
            "or say **\"looks good\"** to generate the final spec?"
        )
        next_phase = Phase.CUSTOMIZATION

    return {
        "messages": [
            {"role": "user", "content": user_response, "metadata": {}},
            {"role": "agent", "content": agent_msg, "metadata": {"phase": "selection", "selected": selected_id}},
        ],
        "phase": next_phase,
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

    # Check full registry (ALL_TEMPLATES includes L&D)
    for tid, tpl in ALL_TEMPLATES.items():
        if tpl.get("name", "").lower() in response_lower or tid in response_lower:
            return tid

    return None


# ═══════════════════════════════════════════════════════════════════════
# NODE: Data Tables — Human-in-the-loop: user asks to add data tables
# ═══════════════════════════════════════════════════════════════════════

def data_tables_node(state: LayoutAdvisorState) -> dict:
    """
    Process user questions to add data tables to charts.
    Uses fetch_data_tables tool (dummy for now) to resolve natural language
    and add table bindings. User says "skip" or "done" to proceed to customization.
    """
    user_response = (state.get("user_response") or "").strip()
    user_added = list(state.get("user_added_tables", []))
    agent_config = state.get("agent_config", {})
    max_len = agent_config.get("max_summary_length", 500)

    # Skip/done → go to customization
    skip_keywords = ["skip", "done", "no", "none", "looks good", "next", "continue"]
    if any(kw in user_response.lower() for kw in skip_keywords):
        agent_msg = (
            "Skipping data tables. Moving to customization — you can adjust "
            "KPI labels, filters, theme, or say **\"looks good\"** to finalize."
        )
        return {
            "messages": [
                {"role": "user", "content": user_response, "metadata": {}},
                {"role": "agent", "content": agent_msg, "metadata": {"phase": "data_tables", "skipped": True}},
            ],
            "phase": Phase.CUSTOMIZATION,
            "needs_user_input": True,
        }

    # Call fetch_data_tables tool (dummy)
    try:
        result = fetch_data_tables.invoke({"user_question": user_response})
        tables = json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.warning(f"fetch_data_tables failed: {e}")
        tables = []

    if not tables:
        agent_msg = (
            "I couldn't find matching data tables for that. Try: "
            "\"add vulnerability data\", \"include agent coverage\", or \"show backlog trend\". "
            "Or say **\"skip\"** to continue."
        )
        return {
            "messages": [
                {"role": "user", "content": user_response, "metadata": {}},
                {"role": "agent", "content": agent_msg, "metadata": {"phase": "data_tables"}},
            ],
            "needs_user_input": True,
        }

    # Add new tables (dedupe by table_id)
    seen_ids = {t.get("table_id") for t in user_added}
    for t in tables:
        tid = t.get("table_id", "")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            user_added.append({
                "table_id": tid,
                "name": t.get("name", tid),
                "description": (t.get("description", ""))[:max_len],
                "columns": t.get("columns", []),
                "suggested_chart_type": t.get("suggested_chart_type", "line_basic"),
                "source": t.get("source", ""),
            })

    summary = ", ".join(t.get("name", t.get("table_id", "?")) for t in user_added[-len(tables):])
    agent_msg = (
        f"Added **{len(tables)}** table(s): {summary}\n\n"
        f"**Total user-added tables:** {len(user_added)}\n\n"
        "Ask to add more (e.g. \"include Snyk issues\") or say **\"done\"** to continue to customization."
    )

    return {
        "messages": [
            {"role": "user", "content": user_response, "metadata": {}},
            {"role": "agent", "content": agent_msg, "metadata": {"phase": "data_tables", "added": len(tables)}},
        ],
        "user_added_tables": user_added,
        "phase": Phase.DATA_TABLES,
        "needs_user_input": True,
    }


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

    user_added = state.get("user_added_tables", [])
    if user_added:
        customizations.append(f"User added {len(user_added)} data table(s) via questions")

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
# NODE: Retrieve Context — fetch metric catalog + past specs before spec gen
# ═══════════════════════════════════════════════════════════════════════

def retrieve_context_node(state: LayoutAdvisorState) -> dict:
    """
    RETRIEVAL POINTS 2 + 3 — runs before spec_generation.
    Fetches metric catalog (DecisionTreeRetrievalService) and past_layout_specs.
    """
    bindings = state.get("metric_gold_model_bindings", [])
    resolution = state.get("resolution_payload", {})
    decisions = state.get("decisions", {})
    agent_config = state.get("agent_config", {})

    domain = decisions.get("domain") or resolution.get("domain", "")
    group_id = agent_config.get("group_id", "unknown")
    framework = decisions.get("framework") or (resolution.get("framework") or [""])[0] if isinstance(resolution.get("framework"), list) else resolution.get("framework", "")

    metric_ids = [b["metric_id"] for b in bindings if b.get("metric_id")]
    metric_context = retrieve_metric_catalog_context(
        metric_ids, k_per_metric=1,
        framework_filter=str(framework) if framework else None,
    )
    past_specs = retrieve_past_layout_specs(group_id, domain, k=2)

    return {
        "retrieved_metric_context": metric_context,
        "retrieved_past_specs": past_specs,
    }


# ═══════════════════════════════════════════════════════════════════════
# NODE: Spec Generation — LLM call to produce the final layout_spec JSON
# ═══════════════════════════════════════════════════════════════════════

def spec_generation_node(state: LayoutAdvisorState) -> dict:
    """
    Generate layout_spec via LLM. Uses retrieved_metric_context and
    retrieved_past_specs. Adds compliance_context and pipeline_audit.
    """
    import json as _json
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    template_id = state.get("selected_template_id", "")
    decisions = state.get("decisions", {})
    customizations = state.get("customization_requests", [])
    bindings = state.get("metric_gold_model_bindings", [])
    resolution = state.get("resolution_payload", {})
    output_format = state.get("output_format", "echarts")
    metric_context = state.get("retrieved_metric_context", [])
    past_specs = state.get("retrieved_past_specs", [])

    tpl = ALL_TEMPLATES.get(template_id) or TEMPLATES.get(template_id)
    if not tpl:
        return {
            "messages": [{"role": "agent", "content": f"Error: template '{template_id}' not found.", "metadata": {}}],
            "error": f"Template not found: {template_id}",
        }

    # Build metric_recommendations index for display_name join (layoutfixes Gap 2)
    metric_recs = resolution.get("metric_recommendations", []) or state.get("upstream_context", {}).get("metric_recommendations", [])
    metric_rec_index = {m.get("id", ""): m for m in metric_recs if m.get("id")}

    catalog_index = {m["metric_id"]: m for m in metric_context}
    enriched_bindings = []
    for b in bindings:
        mid = b.get("metric_id", "")
        rec = metric_rec_index.get(mid, {})
        cat = catalog_index.get(mid, {})
        # Prefer metric_recommendations.name (layoutfixes: join back to get display_name)
        display_name = rec.get("name") or cat.get("display_name") or b.get("metric_name") or mid
        if display_name is None or str(display_name) == "None":
            display_name = mid
        # Use bindings.chart_type from map_metric_widget_to_chart (layoutfixes Gap 3)
        chart_type = b.get("chart_type") or cat.get("chart_type_recommendation") or "line_basic"
        enriched_bindings.append({
            **b,
            "display_name": display_name,
            "chart_type": chart_type,
            "unit": cat.get("unit", ""),
            "threshold_warning": cat.get("thresholds", {}).get("warning"),
            "threshold_critical": cat.get("thresholds", {}).get("critical"),
            "good_direction": cat.get("good_direction", "neutral"),
            "axis_label": cat.get("axis_label", ""),
            "aggregation": cat.get("aggregation", ""),
            "available_filters": rec.get("available_filters", []),
            "available_groups": rec.get("available_groups", []),
        })

    system_prompt = """You are the CCE Dashboard Spec Generator. Your ONLY output is a single valid JSON object.
Do not include any markdown, explanation, or commentary — raw JSON only.

Output shape (goal-driven dashboard spec):
{
  "template_id": str,
  "template_name": str,
  "category": str,
  "theme": "dark" | "light",
  "output_format": str,
  "primitives": [str],
  "panels": {"left": str, "center": str, "right": str},
  "strip_cells": int,
  "strip_kpis": [{"metric_id": str, "display_name": str, "unit": str, "good_direction": "up"|"down"|"neutral", "threshold_warning": number|null, "threshold_critical": number|null, "control_id": str|null}],
  "charts": [{"metric_id": str, "display_name": str, "chart_type": str, "panel": str, "axis_label": str, "unit": str, "aggregation": str, "good_direction": str, "color_rules": [], "gold_table": str, "semantics": {"control_id": str|null}}],
  "filters": [str],
  "has_chat": bool,
  "has_causal_graph": bool,
  "card_anatomy": {},
  "domain": str,
  "decisions_applied": {},
  "customizations_applied": [str]
}

Panel rules: strip_cell=true → strip_kpis only; line/area/bar → center; gauge/scorecard → left/right; table/list → right.
Use threshold values from enriched_bindings when provided. Output strict JSON — no trailing commas."""

    past_spec_block = ""
    if past_specs:
        examples = "\n\n".join(f"// Example: group={s['group_id']}\n{s['layout_spec_snippet']}" for s in past_specs)
        past_spec_block = f"\n\n## Reference examples\n{examples}"

    user_message = f"""Generate the layout_spec JSON:

## Template
{_json.dumps({k: tpl[k] for k in ("name","category","primitives","panels","strip_cells","has_chat","domains") if k in tpl}, indent=2)}

## Decisions
{_json.dumps(decisions, indent=2)}

## Metric Bindings (enriched)
{_json.dumps(enriched_bindings, indent=2)}

## Control Anchors
{_json.dumps(resolution.get("control_anchors", []), indent=2)}

## Customisations
{_json.dumps(customizations, indent=2)}

## Output Format
{output_format}{past_spec_block}

Respond with only the JSON object."""

    agent_config = state.get("agent_config", {})
    model = agent_config.get("spec_gen_model")
    temperature = agent_config.get("spec_gen_temperature")
    try:
        from app.core.dependencies import get_llm
        from app.core.settings import get_settings
        settings = get_settings()
        model = model or settings.LLM_MODEL
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        llm = get_llm(temperature=float(temperature), model=model, provider=settings.LLM_PROVIDER)
    except ImportError:
        llm = ChatAnthropic(
            model=model or "claude-sonnet-4-5-20250514",
            temperature=float(temperature) if temperature is not None else 0.1,
            max_tokens=4096,
        )
    use_fallback = agent_config.get("spec_gen_use_fallback_on_error", True)
    try:
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        spec = _json.loads(raw)
    except (_json.JSONDecodeError, Exception) as e:
        logger.error(f"spec_generation_node LLM/parse error: {e}")
        if not use_fallback:
            raise RuntimeError(
                f"Spec generation LLM call failed (spec_gen_use_fallback_on_error=False): {e}"
            ) from e
        spec = _build_fallback_spec(tpl, decisions, enriched_bindings, customizations, output_format)

    spec["template_id"] = template_id
    spec["output_format"] = output_format
    spec["user_added_tables"] = state.get("user_added_tables", [])

    # Layoutfixes: enrich display_name, chart_type from metric_recommendations + bindings
    spec = _enrich_spec_from_metric_sources(spec, resolution, bindings, metric_rec_index)
    # Layoutfixes Gap 4: add grid.cells with row/col positions for ECharts
    spec = _add_grid_cells_to_spec(spec, enriched_bindings)
    # Layoutfixes Gap 1: when _fallback and qualys data, override template to command-center
    spec = _apply_fallback_template_override(spec, resolution, state)

    # Apply destination-specific overrides (dashboard_decision_tree.md)
    dest_type = resolution.get("destination_type") or (
        "powerbi" if output_format and "powerbi" in str(output_format).lower() else
        "simple" if output_format and "simple" in str(output_format).lower() else
        "embedded"
    )
    try:
        from app.agents.decision_trees.dashboard.dashboard_decision_tree import DESTINATION_GATES
        from app.agents.decision_trees.dashboard.dt_dashboard_decision_nodes import _apply_destination_overrides
        gate = DESTINATION_GATES.get(dest_type, {})
        spec = _apply_destination_overrides(spec, dest_type, gate)
    except ImportError:
        pass

    from datetime import datetime
    spec["compliance_context"] = {
        "control_anchors": [a.get("id") for a in resolution.get("control_anchors", []) if isinstance(a, dict) and a.get("id")],
        "focus_areas": resolution.get("focus_areas", []),
        "risk_categories": resolution.get("risk_categories", []),
    }
    spec["pipeline_audit"] = {
        "resolve_path": state.get("resolve_path", state.get("resolution_path", "decision_tree")),
        "bind_control_count": len(resolution.get("control_anchors", [])),
        "score_candidates_evaluated": len(state.get("candidate_templates", [])),
        "recommend_options_presented": len(state.get("recommended_top3", [])),
        "verify_adjustments_applied": len(state.get("adjustments_applied", [])),
        "verify_options_switched": state.get("selected_option_idx", 0),
        "approved_by": state.get("upstream_context", {}).get("persona", "user"),
        "approved_at": datetime.utcnow().isoformat(),
    }
    spec["status"] = "approved"

    agent_msg = (
        f"Layout spec **finalized** ✓\n\n"
        f"→ Template: **{tpl['name']}** ({tpl.get('icon', '')})\n"
        f"→ Theme: {spec.get('theme', 'light')}\n"
        f"→ {len(spec.get('strip_kpis', []))} KPI strip cells | {len(spec.get('charts', []))} charts\n"
        f"→ Metric catalog enrichment: {len(metric_context)}/{len(bindings)} metrics\n\n"
        "The spec is ready for the downstream renderer."
    )

    return {
        "messages": [{"role": "agent", "content": agent_msg, "metadata": {"phase": "spec_generation"}}],
        "phase": Phase.COMPLETE,
        "layout_spec": spec,
        "needs_user_input": False,
    }


def _enrich_spec_from_metric_sources(
    spec: dict, resolution: dict, bindings: list, metric_rec_index: dict
) -> dict:
    """
    Layoutfixes Gap 2 & 3: Join strip_kpis and charts back to metric_recommendations
    and metric_gold_model_bindings to fix display_name and chart_type.
    """
    bind_by_id = {b["metric_id"]: b for b in bindings if b.get("metric_id")}
    # Fix strip_kpis display_name
    for kpi in spec.get("strip_kpis", []):
        mid = kpi.get("metric_id", "")
        rec = metric_rec_index.get(mid, {})
        b = bind_by_id.get(mid, {})
        name = rec.get("name") or b.get("metric_name") or b.get("display_name")
        if name and str(name) != "None":
            kpi["display_name"] = name
        elif kpi.get("display_name") in (None, "None", ""):
            kpi["display_name"] = mid or "Unknown"
    # Fix charts display_name and chart_type
    for ch in spec.get("charts", []):
        mid = ch.get("metric_id", "")
        rec = metric_rec_index.get(mid, {})
        b = bind_by_id.get(mid, {})
        name = rec.get("name") or b.get("metric_name") or b.get("display_name")
        if name and str(name) != "None":
            ch["display_name"] = name
        elif ch.get("display_name") in (None, "None", ""):
            ch["display_name"] = mid or "Unknown"
        # Use chart_type from bindings (map_metric_widget_to_chart)
        if b.get("chart_type"):
            ch["chart_type"] = b["chart_type"]
        # Promote available_filters, available_groups for axis config
        if rec.get("available_filters"):
            ch["filter_fields"] = rec["available_filters"]
        if rec.get("available_groups"):
            ch["group_by"] = rec["available_groups"][:2]
    return spec


def _add_grid_cells_to_spec(spec: dict, enriched_bindings: list) -> dict:
    """
    Layoutfixes Gap 4: Build grid.cells with row, col, row_span, col_span
    from primitives + strip_kpis + charts for ECharts renderer.
    """
    strip_kpis = spec.get("strip_kpis", [])
    charts = spec.get("charts", [])
    cols = 3

    cells = []
    row = 0

    # Row 0: KPI strip (full width)
    if strip_kpis:
        cells.append({
            "cell_id": "kpi_strip",
            "row": 0, "col": 0, "row_span": 1, "col_span": cols,
            "component_type": "stat_grid",
            "metric_ids": [k.get("metric_id") for k in strip_kpis[:8] if k.get("metric_id")],
        })
        row = 1

    # Place charts in grid (row-major)
    for i, ch in enumerate(charts):
        c = i % cols
        r = row + (i // cols)
        cells.append({
            "cell_id": (ch.get("metric_id") or f"chart_{i}").replace(":", "_").replace(".", "_"),
            "row": r, "col": c, "row_span": 1, "col_span": 1,
            "component_type": "chart",
            "chart_type": ch.get("chart_type", "line_basic"),
            "metric_ids": [ch.get("metric_id")] if ch.get("metric_id") else [],
        })

    if cells:
        spec["grid"] = {
            "rows": max((c["row"] + c.get("row_span", 1) for c in cells), default=2),
            "cols": cols,
            "cells": cells,
        }
    return spec


def _apply_fallback_template_override(spec: dict, resolution: dict, state: dict) -> dict:
    """
    Layoutfixes Gap 1: When _fallback=True and metrics are qualys/vuln,
    override template to command-center instead of wrong risk-register.
    """
    if not spec.get("_fallback"):
        return spec
    metric_recs = resolution.get("metric_recommendations", []) or state.get("upstream_context", {}).get("metric_recommendations", [])
    data_sources = {m.get("data_source_required") for m in metric_recs if m.get("data_source_required")}
    if "qualys" in data_sources and spec.get("template_id") == "risk-register":
        # Qualys vuln metrics → command-center or vuln-management template
        cmd = ALL_TEMPLATES.get("command-center") or TEMPLATES.get("command-center")
        if cmd:
            spec["template_id"] = "command-center"
            spec["template_name"] = cmd.get("name", "Command Center")
            spec["category"] = cmd.get("category", "operations")
            spec["primitives"] = cmd.get("primitives", spec.get("primitives", []))
            spec["panels"] = cmd.get("panels", spec.get("panels", {}))
            spec["card_anatomy"] = cmd.get("card_anatomy", spec.get("card_anatomy", {}))
    return spec


def _build_fallback_spec(tpl: dict, decisions: dict, enriched_bindings: list, customizations: list, output_format: str) -> dict:
    """Deterministic fallback when LLM call or JSON parse fails."""
    strip_b = [b for b in enriched_bindings if b.get("strip_cell")]
    chart_b = [b for b in enriched_bindings if not b.get("strip_cell")]
    return {
        "template_name": tpl["name"],
        "category": tpl["category"],
        "theme": decisions.get("theme", "light"),
        "output_format": output_format,
        "primitives": tpl["primitives"],
        "panels": tpl["panels"],
        "strip_cells": len(strip_b) or tpl["strip_cells"],
        "strip_kpis": [
            {"metric_id": b["metric_id"], "display_name": b.get("display_name", b["metric_id"]),
             "unit": b.get("unit", ""), "good_direction": b.get("good_direction", "neutral"),
             "threshold_warning": b.get("threshold_warning"), "threshold_critical": b.get("threshold_critical")}
            for b in strip_b[:tpl["strip_cells"]]
        ],
        "charts": [
            {"metric_id": b["metric_id"], "display_name": b.get("display_name", b["metric_id"]),
             "chart_type": b.get("chart_type", "line_basic"), "panel": "center",
             "axis_label": b.get("axis_label", ""), "unit": b.get("unit", ""),
             "aggregation": b.get("aggregation", ""), "good_direction": b.get("good_direction", "neutral"),
             "color_rules": [], "gold_table": b.get("gold_table_name", "")}
            for b in chart_b
        ],
        "filters": _get_default_filters(decisions.get("domain", "security")),
        "has_chat": tpl["has_chat"],
        "has_causal_graph": tpl.get("has_graph", False),
        "card_anatomy": tpl.get("card_anatomy", {}),
        "domain": decisions.get("domain", tpl["domains"][0] if tpl.get("domains") else ""),
        "decisions_applied": decisions,
        "customizations_applied": customizations,
        "_fallback": True,
    }


def _get_default_filters(domain: str) -> list[str]:
    filters = {
        "security": ["All", "Critical", "High", "Medium", "Low"],
        "cornerstone": ["All", "Overdue", "In Progress", "Completed", "Not Started"],
        "workday": ["All", "Open", "In Review", "Approved", "Closed"],
        "hybrid": ["All", "Failing", "Degraded", "Passing", "Not Evaluated"],
        "data_ops": ["All", "Failed", "Running", "Succeeded", "Scheduled"],
    }
    return filters.get(domain, filters["security"])
