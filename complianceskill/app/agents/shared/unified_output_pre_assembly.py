"""
Shared pre-assembly hook for CSOD output assembler and DT playbook assembler.

Runs goal-driven generators (calculation, gold SQL, Cube), per-metric demo/stub
artifacts, and dashboard + metrics layout when deliverables ask for it.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal

from app.agents.shared.goal_output_routing import DELIVERABLE_DASHBOARD, DELIVERABLE_REPORT
from app.agents.shared.goal_shared_output_tools import (
    _has_goal_routing,
    apply_goal_shared_pipeline,
)
from app.agents.shared.demo_sql_insight_agent import (
    apply_per_metric_demo_sql_insights,
    apply_per_metric_stub_artifacts,
)

logger = logging.getLogger(__name__)

WorkflowId = Literal["csod", "dt"]


def _has_metric_recommendations(state: Dict[str, Any], workflow: WorkflowId) -> bool:
    if workflow == "dt":
        return bool(state.get("dt_metric_recommendations"))
    return bool(
        state.get("csod_metric_recommendations") or state.get("resolved_metrics")
    )


def _wants_dashboard_or_report(state: Dict[str, Any]) -> bool:
    cp = state.get("compliance_profile")
    d: List[Any] = []
    if isinstance(cp, dict):
        raw = cp.get("goal_deliverables")
        if isinstance(raw, list):
            d = raw
    if DELIVERABLE_DASHBOARD in d or DELIVERABLE_REPORT in d:
        return True
    for key in ("csod_intent", "intent"):
        intent = (state.get(key) or "").lower()
        if "dashboard" in intent or "report" in intent:
            return True
    return False


def apply_shared_dashboard_and_metrics_layout(state: Dict[str, Any]) -> List[str]:
    """Run CSOD layout prompts when goal deliverables include dashboard or report."""
    if not _wants_dashboard_or_report(state):
        return []
    try:
        from app.agents.csod.csod_nodes.node_layout import (
            _run_dashboard_layout,
            _run_metrics_layout,
        )

        _run_dashboard_layout(state)
        _run_metrics_layout(state)
        return ["dashboard_layout", "metrics_layout"]
    except Exception as e:
        logger.warning("shared dashboard/metrics layout failed: %s", e, exc_info=True)
        return []


def apply_unified_output_pre_assembly(
    state: Dict[str, Any],
    workflow: WorkflowId,
) -> List[str]:
    """
    Single entry for CSOD ``csod_output_assembler_node`` and DT ``dt_playbook_assembler_node``.
    """
    actions: List[str] = []

    if _has_goal_routing(state):
        actions.extend(apply_goal_shared_pipeline(state, workflow))

    if _has_metric_recommendations(state, workflow):
        actions.extend(apply_per_metric_demo_sql_insights(state, workflow))
        actions.extend(apply_per_metric_stub_artifacts(state, workflow))

    actions.extend(apply_shared_dashboard_and_metrics_layout(state))

    state["unified_pre_assembly_actions"] = actions
    if workflow == "csod":
        state["csod_assembler_goal_actions"] = actions
    else:
        state["dt_assembler_goal_actions"] = actions

    if actions:
        logger.info("unified_pre_assembly (%s): %s", workflow, actions)
    return actions
