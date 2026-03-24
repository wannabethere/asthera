"""
Stage 5a: Subtask Result Merger — combines outputs from CSOD and DT sub-graphs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.orchestrator.orchestrator_state import OrchestratorState

logger = logging.getLogger(__name__)


def subtask_result_merger_node(state: OrchestratorState) -> OrchestratorState:
    """
    Merge results from CSOD and DT sub-graphs into a unified result set.

    Reads: csod_results, dt_results, subtasks
    Writes: merged_results
    """
    csod = state.get("csod_results") or {}
    dt = state.get("dt_results") or {}

    merged: Dict[str, Any] = {
        "has_detection": bool(dt),
        "has_analysis": bool(csod),
    }

    # Detection outputs (from DT)
    if dt:
        merged["siem_rules"] = dt.get("siem_rules", [])
        merged["playbook"] = dt.get("playbook")
        merged["playbook_template"] = dt.get("playbook_template")
        merged["dt_controls"] = dt.get("controls", [])
        merged["dt_risks"] = dt.get("risks", [])
        merged["dt_scenarios"] = dt.get("scenarios", [])
        merged["dt_data_analysis_context"] = dt.get("data_analysis_context", {})

    # Analysis outputs (from CSOD)
    if csod:
        merged["metric_recommendations"] = csod.get("metric_recommendations", [])
        merged["kpi_recommendations"] = csod.get("kpi_recommendations", [])
        merged["table_recommendations"] = csod.get("table_recommendations", [])
        merged["medallion_plan"] = csod.get("medallion_plan")
        merged["dashboard"] = csod.get("dashboard")
        merged["data_science_insights"] = csod.get("data_science_insights", [])
        merged["selected_layout"] = csod.get("selected_layout")
        merged["csod_assembled_output"] = csod.get("assembled_output")

    # Summary counts
    merged["summary"] = {
        "siem_rule_count": len(merged.get("siem_rules", [])),
        "metric_count": len(merged.get("metric_recommendations", [])),
        "kpi_count": len(merged.get("kpi_recommendations", [])),
        "has_playbook": merged.get("playbook") is not None,
        "has_dashboard": merged.get("dashboard") is not None,
        "has_medallion_plan": merged.get("medallion_plan") is not None,
        "subtasks_completed": sum(1 for s in state.get("subtasks", []) if s.get("status") == "completed"),
        "subtasks_failed": sum(1 for s in state.get("subtasks", []) if s.get("status") == "failed"),
    }

    state["merged_results"] = merged

    logger.info(
        "Results merged: %d SIEM rules, %d metrics, playbook=%s, dashboard=%s",
        merged["summary"]["siem_rule_count"],
        merged["summary"]["metric_count"],
        merged["summary"]["has_playbook"],
        merged["summary"]["has_dashboard"],
    )

    _log_step(state, "subtask_result_merger", merged["summary"])
    return state


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name, "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(), "status": "completed",
        "outputs": outputs,
    })
