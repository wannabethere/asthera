"""
Goal Intent Node — asks the user how they want to view their results.

Placed AFTER metrics recommendation (Stage 4), BEFORE output format selection.
The user sees their recommended metrics first, then decides: Dashboard, Report,
Ad hoc analysis, Alerts, etc.

If the goal_intent was already set earlier (e.g., from the orchestrator or
conversation planner), this node passes through.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger


# Same options as conversation/nodes/goal_intent.py — kept in sync
GOAL_INTENT_OPTIONS: List[Tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "Charts, KPIs, and an analytics experience"),
    ("adhoc_analysis", "Ad hoc analysis", "Explore, slice, and answer one-off questions"),
    ("metrics_recommendations", "Metrics recommendations", "Which metrics and KPIs to track"),
    ("report", "Report", "Structured narrative or export for stakeholders"),
    ("alert_generation", "Alerts", "Thresholds, detections, or monitoring rules"),
    ("workflow_automation", "Workflow automation", "Schedules, pipelines, or recurring jobs"),
    ("alert_rca", "RCA for Alerts", "Analysis of the anomaly"),
]

def _auto_infer_goal(state: CSOD_State) -> str:
    """Infer goal_intent from query and csod_intent without user interaction."""
    # Try csod_intent mapping first
    intent = state.get("csod_intent", "")
    intent_to_goal = {
        "dashboard_generation_for_persona": "dashboard",
        "metrics_dashboard_plan": "dashboard",
        "compliance_test_generator": "alert_generation",
        "anomaly_detection": "alert_rca",
        "data_planner": "workflow_automation",
        "data_lineage": "adhoc_analysis",
        "data_discovery": "adhoc_analysis",
        "data_quality_analysis": "adhoc_analysis",
    }
    if intent in intent_to_goal:
        return intent_to_goal[intent]

    # Try keyword matching on query
    user_query = (state.get("user_query") or "").lower()
    for gid, kw in _KEYWORD_HINTS:
        if kw in user_query:
            return gid

    # Default based on what was produced
    if state.get("csod_metric_recommendations"):
        return "metrics_recommendations"
    return "dashboard"


_KEYWORD_HINTS: List[Tuple[str, str]] = [
    ("dashboard", "dashboard"),
    ("adhoc_analysis", "analysis"),
    ("metrics_recommendations", "metric"),
    ("report", "report"),
    ("alert_generation", "alert"),
    ("workflow_automation", "automation"),
    ("alert_rca", "analysis_rca"),
]


def csod_goal_intent_node(state: CSOD_State) -> CSOD_State:
    """
    Present the goal intent selection to the user — AFTER metrics are recommended.

    If ``goal_intent`` is already set (pre-resolved by orchestrator, conversation
    planner, or followup), passes through without prompting.

    Otherwise, tries to infer from the user query or intent. If no inference
    is possible, emits a checkpoint that pauses the workflow for user input.
    """
    logger.info(
        "[csod_goal_intent] Entry — interactive=%s, existing_goal=%r, "
        "followup_sc=%s, checkpoint_resolved=%s",
        state.get("csod_interactive_checkpoints"),
        state.get("goal_intent"),
        state.get("csod_followup_short_circuit"),
        state.get("csod_checkpoint_resolved"),
    )

    # Already resolved — pass through
    existing = state.get("goal_intent")
    if existing and isinstance(existing, str) and existing.strip():
        logger.info("goal_intent already set: %s — pass-through", existing)
        return state

    # Non-interactive mode — auto-infer without checkpoint
    # When called from direct workflow invocation (not conversation planner),
    # infer the goal and continue without pausing for user input.
    if not state.get("csod_interactive_checkpoints", False):
        inferred = _auto_infer_goal(state)
        state["goal_intent"] = inferred
        logger.info("goal_intent auto-inferred (non-interactive): %s", inferred)
        return state

    # Interactive mode: skip keyword / intent inference — always present options to the user.
    # (Keyword inference is too broad; "metric" matches any metrics query and would bypass
    #  the checkpoint even though the user should choose Dashboard vs Report vs Ad-hoc etc.)
    logger.info("goal_intent: interactive mode — emitting checkpoint for user selection")

    # Build context summary for the checkpoint message
    metrics = state.get("csod_metric_recommendations", [])
    kpis = state.get("csod_kpi_recommendations", [])

    message = "How would you like to see your results?"
    if metrics or kpis:
        count = len(metrics) + len(kpis)
        message = f"I've identified {count} metrics and KPIs for your analysis. How would you like to view them?"

    # Emit checkpoint — pauses workflow for user selection
    from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

    checkpoint = ConversationCheckpoint(
        phase="goal_intent",
        turn=ConversationTurn(
            phase="goal_intent",
            turn_type=TurnOutputType.DECISION,
            message=message,
            options=[
                {"id": gid, "label": label, "description": desc}
                for gid, label, desc in GOAL_INTENT_OPTIONS
            ],
            metadata={
                "kind": "goal_intent",
                "metrics_count": len(metrics),
                "kpis_count": len(kpis),
                "placed_after_metrics": True,
            },
        ),
        resume_with_field="goal_intent",
    )
    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    _csod_log_step(
        state, "csod_goal_intent", "csod_goal_intent",
        inputs={"metrics_count": len(metrics)},
        outputs={"checkpoint_emitted": True},
    )

    return state
