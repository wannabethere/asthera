"""
Goal intent — first human turn: what does the user want to accomplish?

Emits a DECISION checkpoint with stable option ids; resume by setting ``goal_intent``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.config import VerticalConversationConfig
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

logger = logging.getLogger(__name__)

# (id, label, description) — ids must match goal_output_intent classifier prompt
GOAL_INTENT_OPTIONS: List[Tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "Charts, KPIs, and an analytics experience"),
    ("adhoc_analysis", "Ad hoc analysis", "Explore, slice, and answer one-off questions"),
    ("metrics_recommendations", "Metrics recommendations", "Which metrics and KPIs to track"),
    ("report", "Report", "Structured narrative or export for stakeholders"),
    ("alert_generation", "Alerts", "Thresholds, detections, or monitoring rules"),
    ("workflow_automation", "Workflow automation", "Schedules, pipelines, or recurring jobs"),
    ("alert_rca", "Rca for Alerts", "Analysis of the anomaly")
]

_KEYWORD_HINTS: List[Tuple[str, str]] = [
    ("dashboard", "dashboard"),
    ("adhoc_analysis", "analysis"),
    ("metrics_recommendations", "metric"),
    ("report", "report"),
    ("alert_generation", "alert"),
    ("workflow_automation", "automation"),
    ("alert_rca", "analysis_rca")
]


def _canonical_goal_intent(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    s = raw.strip().lower().replace(" ", "_").replace("-", "_")
    ids = {t[0] for t in GOAL_INTENT_OPTIONS}
    if s in ids:
        return s
    for gid, _, _ in GOAL_INTENT_OPTIONS:
        if gid.replace("_", "") == s.replace("_", ""):
            return gid
    return ""


def _infer_goal_from_query(q: str) -> str:
    low = (q or "").lower()
    for gid, kw in _KEYWORD_HINTS:
        if kw in low:
            return gid
    return ""


def goal_intent_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    if not getattr(config, "enable_goal_intent_phases", True):
        return state

    existing = _canonical_goal_intent(state.get("goal_intent"))
    if existing:
        state["goal_intent"] = existing
        state["csod_checkpoint_resolved"] = True
        return state

    inferred = _infer_goal_from_query(state.get("user_query", ""))
    if inferred:
        state["goal_intent"] = inferred
        state["csod_checkpoint_resolved"] = True
        logger.info("goal_intent inferred from query: %s", inferred)
        return state

    checkpoint = ConversationCheckpoint(
        phase="goal_intent",
        turn=ConversationTurn(
            phase="goal_intent",
            turn_type=TurnOutputType.DECISION,
            message="What would you like to do with your data?",
            options=[
                {"id": gid, "label": label, "description": desc}
                for gid, label, desc in GOAL_INTENT_OPTIONS
            ],
            metadata={"kind": "goal_intent"},
        ),
        resume_with_field="goal_intent",
    )
    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False
    return state
