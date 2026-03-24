"""
Stage 2: Capability Router — determines what capabilities are available and needed.

Checks data source availability, framework context, and sets the DT mode
(with_mdl vs no_mdl) based on whether schemas are accessible.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.orchestrator.orchestrator_state import OrchestratorState

logger = logging.getLogger(__name__)


def capability_router_node(state: OrchestratorState) -> OrchestratorState:
    """
    Determine available capabilities based on classification and connected sources.

    Reads: request_classification, selected_data_sources, compliance_profile
    Writes: capabilities_needed
    """
    classification = state.get("request_classification", {})
    request_type = classification.get("request_type", "analysis_only")
    data_sources = state.get("selected_data_sources", [])
    profile = state.get("compliance_profile", {})

    has_data_sources = bool(data_sources)
    has_framework_context = bool(
        classification.get("framework_signals")
        or profile.get("framework_id")
        or state.get("framework_id")
    )

    # Determine what's needed based on request type
    needs_detection = request_type in ("detection_only", "hybrid")
    needs_analysis = request_type in ("analysis_only", "hybrid")
    needs_dashboard = request_type == "dashboard"

    # If analysis is needed but no data sources → still allow with default categories
    # If detection is needed but no MDL → DT runs in no_mdl mode (LLM-direct generation)
    dt_mode = "with_mdl" if (needs_detection and has_data_sources) else "no_mdl"

    capabilities = {
        "needs_data_analysis": needs_analysis or needs_dashboard,
        "needs_detection_engineering": needs_detection,
        "needs_dashboard": needs_dashboard or (needs_analysis and "dashboard" in (classification.get("analysis_signals") or [])),
        "has_data_sources": has_data_sources,
        "has_framework_context": has_framework_context,
        "dt_mode": dt_mode,
        "request_type": request_type,
    }

    state["capabilities_needed"] = capabilities

    logger.info(
        "Capability router: type=%s, detection=%s (mode=%s), analysis=%s, dashboard=%s, data_sources=%s",
        request_type, needs_detection, dt_mode, needs_analysis, needs_dashboard, has_data_sources,
    )

    _log_step(state, "capability_router", capabilities)
    return state


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "outputs": outputs,
    })
