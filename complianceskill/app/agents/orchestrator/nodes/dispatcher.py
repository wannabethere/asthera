"""
Stage 4: Subtask Dispatcher — invokes CSOD and DT sub-graph workflows.

Dispatches subtasks in execution_order, respecting dependencies.
Each subtask runs the appropriate compiled LangGraph app.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.agents.orchestrator.orchestrator_state import OrchestratorState, Subtask

logger = logging.getLogger(__name__)


def subtask_dispatcher_node(state: OrchestratorState) -> OrchestratorState:
    """
    Dispatch subtasks to CSOD and DT sub-graph workflows.

    Iterates through execution_order, builds initial state for each sub-graph,
    invokes the compiled app, and stores results back in the subtask.

    Reads: subtasks, execution_order, selected_data_sources, compliance_profile
    Writes: subtasks (updated with results), csod_results, dt_results
    """
    subtasks = state.get("subtasks", [])
    execution_order = state.get("execution_order", [])
    capabilities = state.get("capabilities_needed", {})

    csod_results: List[Dict[str, Any]] = []
    dt_results: List[Dict[str, Any]] = []

    # Index subtasks by ID for fast lookup
    subtask_map = {s["subtask_id"]: s for s in subtasks}

    for subtask_id in execution_order:
        st = subtask_map.get(subtask_id)
        if not st:
            continue

        # Check dependencies
        deps_met = all(
            subtask_map.get(dep, {}).get("status") == "completed"
            for dep in st.get("depends_on", [])
        )
        if not deps_met:
            logger.warning("Subtask %s has unmet dependencies, skipping", subtask_id)
            st["status"] = "failed"
            st["error"] = "Unmet dependencies"
            continue

        st["status"] = "dispatched"
        target = st.get("target_workflow", "csod")

        try:
            if target == "dt":
                result = _dispatch_to_dt(st, state, capabilities)
                dt_results.append(result)
            else:
                result = _dispatch_to_csod(st, state)
                csod_results.append(result)

            st["status"] = "completed"
            st["result"] = result

        except Exception as e:
            logger.error("Subtask %s (%s) failed: %s", subtask_id, target, e, exc_info=True)
            st["status"] = "failed"
            st["error"] = str(e)

    state["csod_results"] = _merge_workflow_results(csod_results) if csod_results else None
    state["dt_results"] = _merge_workflow_results(dt_results) if dt_results else None

    _log_step(state, "subtask_dispatcher", {
        "total": len(subtasks),
        "completed": sum(1 for s in subtasks if s["status"] == "completed"),
        "failed": sum(1 for s in subtasks if s["status"] == "failed"),
    })

    return state


def _dispatch_to_csod(subtask: Subtask, parent_state: OrchestratorState) -> Dict[str, Any]:
    """
    Build initial state and invoke the CSOD data analysis sub-graph.
    """
    from app.agents.csod.workflows.csod_main_graph import get_csod_app

    initial_state = _build_csod_initial_state(subtask, parent_state)
    app = get_csod_app()

    logger.info("Dispatching CSOD subtask: %s", subtask["subtask_id"])
    final_state = app.invoke(initial_state)

    return _extract_csod_results(final_state)


def _dispatch_to_dt(
    subtask: Subtask,
    parent_state: OrchestratorState,
    capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build initial state and invoke the DT detection/triage sub-graph.

    When dt_mode is "no_mdl", sets flags to skip retrieval stage entirely.
    """
    from app.agents.mdlworkflows.dt_workflow import create_dt_app

    initial_state = _build_dt_initial_state(subtask, parent_state, capabilities)
    app = create_dt_app()

    logger.info("Dispatching DT subtask: %s (mode=%s)", subtask["subtask_id"], capabilities.get("dt_mode", "no_mdl"))
    final_state = app.invoke(initial_state)

    return _extract_dt_results(final_state)


# ── State builders ────────────────────────────────────────────────────────────

def _build_csod_initial_state(subtask: Subtask, parent: OrchestratorState) -> Dict[str, Any]:
    """Build initial state for CSOD sub-graph from subtask + parent context."""
    state: Dict[str, Any] = {
        "user_query": subtask.get("user_query", parent.get("user_query", "")),
        "messages": [],
        "selected_data_sources": parent.get("selected_data_sources", []),
        "compliance_profile": parent.get("compliance_profile", {}),
        "active_project_id": parent.get("active_project_id"),
        "skill_pipeline_enabled": True,
        "csod_session_turn": 1,
    }
    if subtask.get("intent_hint"):
        state["csod_intent"] = subtask["intent_hint"]
    if subtask.get("focus_areas"):
        state.setdefault("data_enrichment", {})["suggested_focus_areas"] = subtask["focus_areas"]
    return state


def _build_dt_initial_state(
    subtask: Subtask,
    parent: OrchestratorState,
    capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build initial state for DT sub-graph from subtask + parent context.

    The DT workflow always runs the same detection/triage node chain
    (detection_engineer → siem_validator → triage_engineer → playbook_assembler).
    The difference between with-MDL and no-MDL is what context these nodes receive:

    **With MDL:** metrics from registry + schemas + causal graph → richer context
    **No MDL:** framework controls + default categories → LLM generates directly

    The detection/triage LLM nodes always run — MDL just enriches their input.
    """
    dt_mode = capabilities.get("dt_mode", "no_mdl")
    has_data_sources = capabilities.get("has_data_sources", False)

    state: Dict[str, Any] = {
        "user_query": subtask.get("user_query", parent.get("user_query", "")),
        "messages": [],
        "selected_data_sources": parent.get("selected_data_sources", []),
        "compliance_profile": parent.get("compliance_profile", {}),
    }

    if subtask.get("framework_id"):
        state["framework_id"] = subtask["framework_id"]
    if subtask.get("requirement_code"):
        state["requirement_code"] = subtask["requirement_code"]
    if subtask.get("intent_hint"):
        state["intent"] = subtask["intent_hint"]

    # No-MDL mode: skip retrieval, detection/triage nodes use LLM-direct generation
    if dt_mode == "no_mdl":
        state["data_enrichment"] = {
            "needs_mdl": False,
            "needs_metrics": False,
            "suggested_focus_areas": subtask.get("focus_areas", []),
            "dt_skip_retrieval": True,
        }
        state["dt_no_mdl_mode"] = True
        # Provide default focus categories so LLM has generic structure to work with
        try:
            from app.agents.domain_config import DomainRegistry
            domain_cfg = DomainRegistry.instance().get_for_state(state)
            state["focus_area_categories"] = list(domain_cfg.focus_area_category_map.keys())
        except Exception:
            state["focus_area_categories"] = [
                "vulnerability_management", "incident_detection",
                "log_management_siem", "endpoint_detection",
                "audit_logging_compliance",
            ]
    else:
        # With MDL: retrieval runs normally, enriching detection/triage context
        state["data_enrichment"] = {
            "needs_mdl": True,
            "needs_metrics": True,
            "suggested_focus_areas": subtask.get("focus_areas", []),
        }

    # Pass CSOD analysis results as additional context if available
    # (from a prior analysis subtask that completed before this detection subtask)
    csod_prior = parent.get("csod_results")
    if csod_prior and isinstance(csod_prior, dict):
        # Feed CSOD metrics into DT so detection rules can reference real metrics
        csod_metrics = csod_prior.get("metric_recommendations", [])
        if csod_metrics:
            state["dt_csod_metric_context"] = csod_metrics
            logger.info("DT subtask enriched with %d CSOD metrics", len(csod_metrics))

    return state


# ── Result extractors ─────────────────────────────────────────────────────────

def _extract_csod_results(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant outputs from completed CSOD sub-graph state."""
    return {
        "workflow": "csod",
        "intent": final_state.get("csod_intent"),
        "metric_recommendations": final_state.get("csod_metric_recommendations", []),
        "kpi_recommendations": final_state.get("csod_kpi_recommendations", []),
        "table_recommendations": final_state.get("csod_table_recommendations", []),
        "medallion_plan": final_state.get("csod_medallion_plan"),
        "dashboard": final_state.get("csod_dashboard_assembled"),
        "assembled_output": final_state.get("csod_assembled_output"),
        "completion_narration": final_state.get("csod_completion_narration"),
        "data_science_insights": final_state.get("csod_data_science_insights", []),
        "selected_layout": final_state.get("csod_selected_layout"),
    }


def _extract_dt_results(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant outputs from completed DT sub-graph state."""
    return {
        "workflow": "dt",
        "intent": final_state.get("intent"),
        "siem_rules": final_state.get("siem_rules", []),
        "playbook": final_state.get("dt_assembled_playbook"),
        "playbook_template": final_state.get("dt_playbook_template"),
        "metric_recommendations": final_state.get("dt_metric_recommendations", []),
        "resolved_schemas": final_state.get("dt_resolved_schemas", []),
        "controls": final_state.get("controls", []),
        "risks": final_state.get("risks", []),
        "scenarios": final_state.get("scenarios", []),
        # Hand-off context for CSOD if caller wants to run data analysis
        "data_analysis_context": {
            "metric_candidates": final_state.get("dt_metric_recommendations", []),
            "resolved_schemas": final_state.get("dt_resolved_schemas", []),
            "scored_context": final_state.get("dt_scored_context", {}),
            "focus_area_categories": final_state.get("focus_area_categories", []),
        },
    }


def _merge_workflow_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple results from the same workflow type."""
    if len(results) == 1:
        return results[0]
    merged: Dict[str, Any] = {"workflow": results[0].get("workflow", "unknown"), "subtask_results": results}
    # Aggregate lists
    for key in ("metric_recommendations", "kpi_recommendations", "siem_rules", "controls", "risks"):
        all_items = []
        for r in results:
            all_items.extend(r.get(key, []))
        if all_items:
            merged[key] = all_items
    return merged


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name, "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(), "status": "completed",
        "outputs": outputs,
    })
