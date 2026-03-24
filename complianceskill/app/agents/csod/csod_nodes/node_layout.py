"""
Layout resolver: dashboard sections or metrics ordering (after DT qualification).

Merged from separate dashboard_layout + metrics_layout nodes into a single
intent-conditional node.
"""
import json

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)
from app.agents.csod.csod_nodes.narrative import append_csod_narrative


def csod_dashboard_layout_node(state: CSOD_State) -> CSOD_State:
    """Dashboard intent only: DT groups → csod_dt_layout (before CCE)."""
    state.setdefault("csod_dt_layout", {})
    if state.get("csod_intent") == "dashboard_generation_for_persona":
        _run_dashboard_layout(state)
    return state


def csod_metrics_layout_node(state: CSOD_State) -> CSOD_State:
    """After CCE: order metrics for recommender (uses centrality when present)."""
    state.setdefault("csod_metrics_layout", {})
    _run_metrics_layout(state)
    return state


def _run_dashboard_layout(state: CSOD_State) -> None:
    try:
        prompt = load_prompt("26_dashboard_layout", prompts_dir=str(PROMPTS_CSOD))
    except FileNotFoundError:
        logger.warning("26_dashboard_layout prompt missing")
        state["csod_dt_layout"] = _fallback_dashboard_layout(state)
        return

    groups = state.get("dt_metric_groups") or []
    metrics = state.get("dt_scored_metrics") or []
    persona = state.get("csod_persona") or state.get("compliance_profile", {}).get(
        "persona", "learning_admin"
    )
    human = f"""persona: {persona}
dt_metric_groups:
{json.dumps(groups, indent=2)[:10000]}
dt_scored_metrics (ids and composite):
{json.dumps([{"metric_id": m.get("metric_id"), "composite": m.get("composite_score")} for m in metrics[:40]], indent=2)}
"""
    try:
        raw = _llm_invoke(state, "csod_dashboard_layout", prompt, human, [], False)
        layout = _parse_json_response(raw, {})
        if not layout:
            layout = _fallback_dashboard_layout(state)
        state["csod_dt_layout"] = layout
    except Exception as e:
        logger.error("dashboard layout: %s", e)
        state["csod_dt_layout"] = _fallback_dashboard_layout(state)

    append_csod_narrative(
        state,
        "layout",
        "Dashboard Layout Resolver",
        "Mapped metric groups to dashboard sections and widget types.",
    )
    _csod_log_step(
        state,
        "dashboard_layout",
        "csod_layout_resolver",
        {"persona": persona},
        {"sections": len(state["csod_dt_layout"].get("sections") or [])},
    )
    state["messages"].append(AIMessage(content="[Layout] Dashboard sections resolved"))


def _fallback_dashboard_layout(state: CSOD_State) -> dict:
    groups = state.get("dt_metric_groups") or []
    sections = []
    for i, g in enumerate(groups[:6]):
        mids = g.get("metric_ids") or g.get("metrics") or []
        if isinstance(mids, list) and mids and isinstance(mids[0], dict):
            mids = [x.get("metric_id") for x in mids]
        sections.append({
            "section_id": f"section_{i}",
            "title": str(g.get("group_name") or g.get("goal") or f"Group {i}"),
            "widget_type": "kpi_card",
            "metric_ids": [str(x) for x in (mids or [])[:8]],
        })
    return {"sections": sections, "widget_assignments": [], "persona_notes": "fallback"}


def _run_metrics_layout(state: CSOD_State) -> None:
    try:
        prompt = load_prompt("27_metrics_layout", prompts_dir=str(PROMPTS_CSOD))
    except FileNotFoundError:
        logger.warning("27_metrics_layout prompt missing")
        state["csod_metrics_layout"] = _fallback_metrics_layout(state)
        return

    groups = state.get("dt_metric_groups") or []
    decisions = state.get("dt_metric_decisions") or {}
    centrality = state.get("csod_causal_centrality") or {}
    human = f"""dt_metric_decisions: {json.dumps(decisions, indent=2)[:4000]}
dt_metric_groups:
{json.dumps(groups, indent=2)[:10000]}
csod_causal_centrality (may be empty if CCE not run yet):
{json.dumps(dict(list(centrality.items())[:30]), indent=2)}
"""
    try:
        raw = _llm_invoke(state, "csod_metrics_layout", prompt, human, [], False)
        layout = _parse_json_response(raw, {})
        if not layout:
            layout = _fallback_metrics_layout(state)
        state["csod_metrics_layout"] = layout
    except Exception as e:
        logger.error("metrics layout: %s", e)
        state["csod_metrics_layout"] = _fallback_metrics_layout(state)

    append_csod_narrative(
        state,
        "layout",
        "Metrics Layout Resolver",
        state["csod_metrics_layout"].get("summary")
        or "Ordered metric groups with leading/lagging hints where available.",
    )
    _csod_log_step(
        state,
        "metrics_layout",
        "csod_layout_resolver",
        {},
        {"groups": len(state["csod_metrics_layout"].get("ordered_groups") or [])},
    )
    state["messages"].append(AIMessage(content="[Layout] Metrics order resolved"))


def _fallback_metrics_layout(state: CSOD_State) -> dict:
    groups = state.get("dt_metric_groups") or []
    ordered = []
    for g in groups:
        key = g.get("group_key") or g.get("goal") or "default"
        mids = g.get("metric_ids") or []
        if isinstance(mids, list) and mids and isinstance(mids[0], dict):
            mids = [x.get("metric_id") for x in mids]
        ordered.append({"group_key": str(key), "metric_ids": mids or [], "rationale": ""})
    return {
        "ordered_groups": ordered,
        "leading_metric_ids": [],
        "lagging_metric_ids": [],
        "summary": "fallback ordering from DT groups",
    }


# ── Unified layout resolver (replaces two separate nodes) ────────────────────

METRICS_LAYOUT_INTENTS = frozenset({
    "metrics_dashboard_plan",
    "metrics_recommender_with_gold_plan",
    "data_planner",
    "metric_kpi_advisor",
})


def csod_layout_resolver_node(state: CSOD_State) -> CSOD_State:
    """
    Unified layout resolver: runs dashboard layout OR metrics layout
    based on intent. Replaces separate dashboard_layout + metrics_layout nodes.
    """
    intent = state.get("csod_intent", "")
    state.setdefault("csod_dt_layout", {})
    state.setdefault("csod_metrics_layout", {})

    if intent == "dashboard_generation_for_persona":
        _run_dashboard_layout(state)
    elif intent in METRICS_LAYOUT_INTENTS:
        _run_metrics_layout(state)
    # else: no layout needed — pass-through

    return state
