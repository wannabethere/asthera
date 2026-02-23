"""
Detection & Triage Engineering Workflow

Standalone LangGraph workflow for the Detection & Triage (DT) pipeline.
Mirrors the structure of build_compliance_workflow() in workflow.py but
is scoped to the 11 DT-specific nodes.

Graph topology:
  dt_intent_classifier
    → dt_planner
      → dt_framework_retrieval
        → dt_metrics_retrieval   (conditional: needs_metrics)
          → dt_mdl_schema_retrieval  (conditional: needs_mdl)
            → calculation_needs_assessment
              → calculation_planner  (conditional: needs_calculation)
                → dt_scoring_validator
                  ┌── dt_detection_engineer ──┐
                  │     → dt_siem_rule_validator          │
                  │       → dt_metric_calculation_validator │
                  │         → dt_triage_engineer (if template C) │
                  │         → dt_playbook_assembler │
                  └── dt_triage_engineer ──┘
                        → dt_metric_calculation_validator
                          → dt_playbook_assembler
                            → END

Can also be wired into the existing compliance workflow via
add_dt_workflow_to_existing() helper at the bottom of this file.
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState

# DT-specific nodes — import from the combined dt_nodes.py
from app.agents.dt_nodes import (
    dt_intent_classifier_node,
    dt_planner_node,
    dt_framework_retrieval_node,
    dt_metrics_retrieval_node,
    dt_mdl_schema_retrieval_node,
    dt_scoring_validator_node,
    dt_detection_engineer_node,
    dt_triage_engineer_node,
    dt_siem_rule_validator_node,
    dt_metric_calculation_validator_node,
    dt_playbook_assembler_node,
    calculation_needs_assessment_node,
    calculation_planner_node,
)
from app.core.telemetry import instrument_langgraph_node

logger = logging.getLogger(__name__)

# Max refinement iterations before forcing assembly
MAX_REFINEMENT_ITERATIONS = 3


# ============================================================================
# Conditional routing functions
# ============================================================================

def _route_after_planner(state: EnhancedCompliancePipelineState) -> str:
    """
    After planning, determine whether metrics retrieval is needed.
    Always run framework retrieval first; metrics only if needs_metrics.
    """
    return "dt_framework_retrieval"


def _route_after_framework_retrieval(state: EnhancedCompliancePipelineState) -> str:
    """
    After framework retrieval, go to metrics if needed; else skip to MDL or scoring.
    """
    data_enrichment = state.get("data_enrichment", {})
    if data_enrichment.get("needs_metrics", False):
        return "dt_metrics_retrieval"
    elif data_enrichment.get("needs_mdl", False):
        return "dt_mdl_schema_retrieval"
    else:
        return "dt_scoring_validator"


def _route_after_metrics_retrieval(state: EnhancedCompliancePipelineState) -> str:
    """
    After metrics retrieval, go to MDL schema lookup if needs_mdl; else scoring.
    """
    data_enrichment = state.get("data_enrichment", {})
    if data_enrichment.get("needs_mdl", False):
        return "dt_mdl_schema_retrieval"
    return "dt_scoring_validator"


def _route_after_mdl_schema_retrieval(state: EnhancedCompliancePipelineState) -> str:
    """
    After MDL schema retrieval, route to calculation needs assessment.
    Calculation planning is MDL-specific, so it runs after schema retrieval.
    """
    return "calculation_needs_assessment"


def _route_after_calculation_assessment(state: EnhancedCompliancePipelineState) -> str:
    """
    After calculation needs assessment, route conditionally to calculation_planner or skip.
    """
    needs_calculation = state.get("needs_calculation", True)  # Default to True for backward compatibility
    if needs_calculation:
        return "calculation_planner"
    else:
        return "dt_scoring_validator"  # Skip calculation planning


def _route_after_calculation_planner(state: EnhancedCompliancePipelineState) -> str:
    """
    After calculation planner, always proceed to scoring validator.
    """
    return "dt_scoring_validator"


def _route_after_scoring(state: EnhancedCompliancePipelineState) -> str:
    """
    After scoring, route to the correct execution branch(es) based on template.

    Template A (detection_focused) → detection_engineer only
    Template B (triage_focused)    → triage_engineer only
    Template C (full_chain)        → detection_engineer first, then triage

    For simplicity in LangGraph (single edge per node), we use a sequencing
    pattern: detection_engineer always runs before triage_engineer when both
    are needed; the triage_engineer node checks expected_outputs and skips
    gracefully if not needed.
    """
    expected = state.get("dt_expected_outputs", {})
    template = state.get("dt_playbook_template", "A")

    if template == "B" or (not expected.get("siem_rules", True) and expected.get("metric_recommendations", False)):
        return "dt_triage_engineer"
    else:
        # Templates A and C both start with detection engineer
        return "dt_detection_engineer"


def _route_after_detection_engineer(state: EnhancedCompliancePipelineState) -> str:
    """
    After detection_engineer, go to SIEM validator.
    """
    return "dt_siem_rule_validator"


def _route_after_siem_validator(state: EnhancedCompliancePipelineState) -> str:
    """
    After SIEM validation:
    - Always proceed to metric calculation validator for detection engineer
    - The metric validator will handle both detection and triage engineer outputs
    """
    template = state.get("dt_playbook_template", "A")
    passed = state.get("dt_siem_validation_passed", True)
    iteration = state.get("dt_validation_iteration", 0)

    # If SIEM validation failed and under max iterations, re-run detection_engineer
    if not passed and iteration < MAX_REFINEMENT_ITERATIONS:
        state["dt_validation_iteration"] = iteration + 1
        return "dt_detection_engineer"

    # After SIEM validation passes, validate metrics from detection engineer
    # Mark that we're validating detection engineer metrics
    state["dt_validating_detection_metrics"] = True
    return "dt_metric_calculation_validator"


def _route_after_triage_engineer(state: EnhancedCompliancePipelineState) -> str:
    """After triage engineer, always validate metrics."""
    return "dt_metric_calculation_validator"


def _route_after_metric_validator(state: EnhancedCompliancePipelineState) -> str:
    """
    After metric validation:
    - If validating detection engineer metrics:
      - Passed → check if triage needed (template C) or go to assembler
      - Failed + under max iterations → re-run detection_engineer
      - Failed + at max iterations → assembler with warnings
    - If validating triage engineer metrics:
      - Passed → assembler
      - Failed + under max iterations → re-run triage_engineer
      - Failed + at max iterations → assembler with warnings
    """
    passed = state.get("dt_metric_validation_passed", True)
    iteration = state.get("dt_validation_iteration", 0)
    template = state.get("dt_playbook_template", "A")
    validating_detection = state.get("dt_validating_detection_metrics", False)

    # If validation failed and under max iterations, re-run the appropriate engineer
    if not passed and iteration < MAX_REFINEMENT_ITERATIONS:
        state["dt_validation_iteration"] = iteration + 1
        if validating_detection:
            return "dt_detection_engineer"
        else:
            return "dt_triage_engineer"

    # If validating detection engineer metrics and passed
    if validating_detection:
        # Clear the flag
        state["dt_validating_detection_metrics"] = False
        # If template C (full_chain), proceed to triage_engineer
        if template == "C":
            return "dt_triage_engineer"
        # Otherwise go to assembler
        return "dt_playbook_assembler"

    # If validating triage engineer metrics and passed, go to assembler
    return "dt_playbook_assembler"


# ============================================================================
# Graph builder
# ============================================================================

def build_detection_triage_workflow() -> StateGraph:
    """
    Build the Detection & Triage LangGraph workflow.

    Returns:
        Un-compiled StateGraph (call .compile() to get the runnable app).
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)

    # ── Register nodes (with telemetry instrumentation) ─────────────────────
    workflow.add_node("dt_intent_classifier",          instrument_langgraph_node(dt_intent_classifier_node, "dt_intent_classifier", "detection_triage"))
    workflow.add_node("dt_planner",                    instrument_langgraph_node(dt_planner_node, "dt_planner", "detection_triage"))
    workflow.add_node("dt_framework_retrieval",        instrument_langgraph_node(dt_framework_retrieval_node, "dt_framework_retrieval", "detection_triage"))
    workflow.add_node("dt_metrics_retrieval",          instrument_langgraph_node(dt_metrics_retrieval_node, "dt_metrics_retrieval", "detection_triage"))
    workflow.add_node("dt_mdl_schema_retrieval",       instrument_langgraph_node(dt_mdl_schema_retrieval_node, "dt_mdl_schema_retrieval", "detection_triage"))
    workflow.add_node("calculation_needs_assessment", instrument_langgraph_node(calculation_needs_assessment_node, "calculation_needs_assessment", "detection_triage"))
    workflow.add_node("calculation_planner",          instrument_langgraph_node(calculation_planner_node, "calculation_planner", "detection_triage"))
    workflow.add_node("dt_scoring_validator",          instrument_langgraph_node(dt_scoring_validator_node, "dt_scoring_validator", "detection_triage"))
    workflow.add_node("dt_detection_engineer",         instrument_langgraph_node(dt_detection_engineer_node, "dt_detection_engineer", "detection_triage"))
    workflow.add_node("dt_siem_rule_validator",        instrument_langgraph_node(dt_siem_rule_validator_node, "dt_siem_rule_validator", "detection_triage"))
    workflow.add_node("dt_triage_engineer",            instrument_langgraph_node(dt_triage_engineer_node, "dt_triage_engineer", "detection_triage"))
    workflow.add_node("dt_metric_calculation_validator", instrument_langgraph_node(dt_metric_calculation_validator_node, "dt_metric_calculation_validator", "detection_triage"))
    workflow.add_node("dt_playbook_assembler",         instrument_langgraph_node(dt_playbook_assembler_node, "dt_playbook_assembler", "detection_triage"))

    # ── Entry point ──────────────────────────────────────────────────────────
    workflow.set_entry_point("dt_intent_classifier")

    # ── Fixed edges ──────────────────────────────────────────────────────────
    workflow.add_edge("dt_intent_classifier", "dt_planner")

    # ── Conditional edges ────────────────────────────────────────────────────
    workflow.add_conditional_edges(
        "dt_planner",
        _route_after_planner,
        {"dt_framework_retrieval": "dt_framework_retrieval"},
    )

    workflow.add_conditional_edges(
        "dt_framework_retrieval",
        _route_after_framework_retrieval,
        {
            "dt_metrics_retrieval":    "dt_metrics_retrieval",
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_scoring_validator":    "dt_scoring_validator",
        },
    )

    workflow.add_conditional_edges(
        "dt_metrics_retrieval",
        _route_after_metrics_retrieval,
        {
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_scoring_validator":    "dt_scoring_validator",
        },
    )

    # After MDL schema retrieval, route to calculation needs assessment
    workflow.add_conditional_edges(
        "dt_mdl_schema_retrieval",
        _route_after_mdl_schema_retrieval,
        {"calculation_needs_assessment": "calculation_needs_assessment"},
    )
    
    # After calculation needs assessment, route conditionally
    workflow.add_conditional_edges(
        "calculation_needs_assessment",
        _route_after_calculation_assessment,
        {
            "calculation_planner": "calculation_planner",
            "dt_scoring_validator": "dt_scoring_validator",
        },
    )
    
    # After calculation planner, proceed to scoring validator
    workflow.add_conditional_edges(
        "calculation_planner",
        _route_after_calculation_planner,
        {"dt_scoring_validator": "dt_scoring_validator"},
    )

    workflow.add_conditional_edges(
        "dt_scoring_validator",
        _route_after_scoring,
        {
            "dt_detection_engineer": "dt_detection_engineer",
            "dt_triage_engineer":    "dt_triage_engineer",
        },
    )

    workflow.add_conditional_edges(
        "dt_detection_engineer",
        _route_after_detection_engineer,
        {"dt_siem_rule_validator": "dt_siem_rule_validator"},
    )

    workflow.add_conditional_edges(
        "dt_siem_rule_validator",
        _route_after_siem_validator,
        {
            "dt_metric_calculation_validator": "dt_metric_calculation_validator",
            "dt_detection_engineer": "dt_detection_engineer",  # refinement loop
        },
    )

    workflow.add_conditional_edges(
        "dt_triage_engineer",
        _route_after_triage_engineer,
        {"dt_metric_calculation_validator": "dt_metric_calculation_validator"},
    )

    workflow.add_conditional_edges(
        "dt_metric_calculation_validator",
        _route_after_metric_validator,
        {
            "dt_detection_engineer": "dt_detection_engineer",  # refinement loop (detection)
            "dt_triage_engineer":    "dt_triage_engineer",     # refinement loop (triage)
            "dt_playbook_assembler": "dt_playbook_assembler",
        },
    )

    workflow.add_edge("dt_playbook_assembler", END)

    return workflow


# ============================================================================
# App factory functions — mirror workflow.py pattern exactly
# ============================================================================

def create_detection_triage_app(checkpointer=None):
    """
    Create and compile the Detection & Triage application.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.
                      Defaults to MemorySaver (in-memory, suitable for dev).

    Returns:
        Compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    workflow = build_detection_triage_workflow()
    return workflow.compile(checkpointer=checkpointer)


def get_detection_triage_app():
    """Convenience: return a default DT app with in-memory checkpointer."""
    return create_detection_triage_app()


# ============================================================================
# Integration helper — wire DT into the existing compliance workflow
# ============================================================================

def add_dt_workflow_to_existing(existing_workflow: StateGraph) -> StateGraph:
    """
    Attach the DT nodes to an existing compliance workflow StateGraph.

    After calling this function, add routing from your existing
    'profile_resolver' or 'intent_classifier' to 'dt_intent_classifier'
    when intent is 'detection_engineering', 'triage_engineering', or
    'full_pipeline' with the DT flag set.

    Example — modify route_from_profile_resolver in workflow.py:

        def route_from_profile_resolver(state) -> str:
            intent = state.get("intent", "")
            if intent in ("detection_engineering", "triage_engineering", "full_pipeline"):
                return "dt_intent_classifier"
            ...

        workflow.add_conditional_edges(
            "profile_resolver",
            route_from_profile_resolver,
            {
                ...
                "dt_intent_classifier": "dt_intent_classifier",
            }
        )

    Args:
        existing_workflow: The StateGraph from build_compliance_workflow()

    Returns:
        The same StateGraph with DT nodes added (mutated in place).
    """
    existing_workflow.add_node("dt_intent_classifier",          instrument_langgraph_node(dt_intent_classifier_node, "dt_intent_classifier", "detection_triage"))
    existing_workflow.add_node("dt_planner",                    instrument_langgraph_node(dt_planner_node, "dt_planner", "detection_triage"))
    existing_workflow.add_node("dt_framework_retrieval",        instrument_langgraph_node(dt_framework_retrieval_node, "dt_framework_retrieval", "detection_triage"))
    existing_workflow.add_node("dt_metrics_retrieval",          instrument_langgraph_node(dt_metrics_retrieval_node, "dt_metrics_retrieval", "detection_triage"))
    existing_workflow.add_node("dt_mdl_schema_retrieval",       instrument_langgraph_node(dt_mdl_schema_retrieval_node, "dt_mdl_schema_retrieval", "detection_triage"))
    existing_workflow.add_node("calculation_needs_assessment", instrument_langgraph_node(calculation_needs_assessment_node, "calculation_needs_assessment", "detection_triage"))
    existing_workflow.add_node("calculation_planner",          instrument_langgraph_node(calculation_planner_node, "calculation_planner", "detection_triage"))
    existing_workflow.add_node("dt_scoring_validator",          instrument_langgraph_node(dt_scoring_validator_node, "dt_scoring_validator", "detection_triage"))
    existing_workflow.add_node("dt_detection_engineer",         instrument_langgraph_node(dt_detection_engineer_node, "dt_detection_engineer", "detection_triage"))
    existing_workflow.add_node("dt_siem_rule_validator",        instrument_langgraph_node(dt_siem_rule_validator_node, "dt_siem_rule_validator", "detection_triage"))
    existing_workflow.add_node("dt_triage_engineer",            instrument_langgraph_node(dt_triage_engineer_node, "dt_triage_engineer", "detection_triage"))
    existing_workflow.add_node("dt_metric_calculation_validator", instrument_langgraph_node(dt_metric_calculation_validator_node, "dt_metric_calculation_validator", "detection_triage"))
    existing_workflow.add_node("dt_playbook_assembler",         instrument_langgraph_node(dt_playbook_assembler_node, "dt_playbook_assembler", "detection_triage"))

    # Wire internal DT edges (same as build_detection_triage_workflow)
    existing_workflow.add_edge("dt_intent_classifier", "dt_planner")

    existing_workflow.add_conditional_edges(
        "dt_planner",
        _route_after_planner,
        {"dt_framework_retrieval": "dt_framework_retrieval"},
    )
    existing_workflow.add_conditional_edges(
        "dt_framework_retrieval",
        _route_after_framework_retrieval,
        {
            "dt_metrics_retrieval":    "dt_metrics_retrieval",
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_scoring_validator":    "dt_scoring_validator",
        },
    )
    existing_workflow.add_conditional_edges(
        "dt_metrics_retrieval",
        _route_after_metrics_retrieval,
        {
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_scoring_validator":    "dt_scoring_validator",
        },
    )
    # After MDL schema retrieval, route to calculation needs assessment
    existing_workflow.add_conditional_edges(
        "dt_mdl_schema_retrieval",
        _route_after_mdl_schema_retrieval,
        {"calculation_needs_assessment": "calculation_needs_assessment"},
    )
    
    # After calculation needs assessment, route conditionally
    existing_workflow.add_conditional_edges(
        "calculation_needs_assessment",
        _route_after_calculation_assessment,
        {
            "calculation_planner": "calculation_planner",
            "dt_scoring_validator": "dt_scoring_validator",
        },
    )
    
    # After calculation planner, proceed to scoring validator
    existing_workflow.add_conditional_edges(
        "calculation_planner",
        _route_after_calculation_planner,
        {"dt_scoring_validator": "dt_scoring_validator"},
    )
    
    existing_workflow.add_conditional_edges(
        "dt_scoring_validator",
        _route_after_scoring,
        {
            "dt_detection_engineer": "dt_detection_engineer",
            "dt_triage_engineer":    "dt_triage_engineer",
        },
    )
    existing_workflow.add_conditional_edges(
        "dt_detection_engineer",
        _route_after_detection_engineer,
        {"dt_siem_rule_validator": "dt_siem_rule_validator"},
    )
    existing_workflow.add_conditional_edges(
        "dt_siem_rule_validator",
        _route_after_siem_validator,
        {
            "dt_metric_calculation_validator": "dt_metric_calculation_validator",
            "dt_detection_engineer": "dt_detection_engineer",  # refinement loop
        },
    )
    existing_workflow.add_conditional_edges(
        "dt_triage_engineer",
        _route_after_triage_engineer,
        {"dt_metric_calculation_validator": "dt_metric_calculation_validator"},
    )
    existing_workflow.add_conditional_edges(
        "dt_metric_calculation_validator",
        _route_after_metric_validator,
        {
            "dt_detection_engineer": "dt_detection_engineer",  # refinement loop (detection)
            "dt_triage_engineer":    "dt_triage_engineer",     # refinement loop (triage)
            "dt_playbook_assembler": "dt_playbook_assembler",
        },
    )
    # DT assembler routes back to the existing artifact_assembler for unified output
    existing_workflow.add_edge("dt_playbook_assembler", "artifact_assembler")

    logger.info("DT workflow nodes wired into existing compliance workflow")
    return existing_workflow


# ============================================================================
# Initial state factory
# ============================================================================

def create_dt_initial_state(
    user_query: str,
    session_id: str,
    framework_id: str = None,
    selected_data_sources: list = None,
    active_project_id: str = None,
    compliance_profile: dict = None,
) -> dict:
    """
    Build an initial state dict for the DT workflow.

    Args:
        user_query:             The user's natural language query.
        session_id:             Unique session identifier.
        framework_id:           Optional framework override (e.g., "hipaa", "soc2").
                                If None, the classifier will extract it from the query.
        selected_data_sources:  List of confirmed data source IDs (e.g., ["qualys", "okta"]).
                                ── MANUAL STEP: populate from your tenant profile API. ──
        active_project_id:      ProjectId for GoldStandardTable lookup.
                                ── MANUAL STEP: populate from your tenant config. ──
        compliance_profile:     Full compliance profile dict (optional).

    Returns:
        Initial state dict ready to pass to app.invoke() or app.stream().
    """
    import uuid
    from datetime import datetime

    return {
        # Core
        "user_query": user_query,
        "session_id": session_id or str(uuid.uuid4()),
        "messages": [],
        "created_at": datetime.utcnow(),

        # Pre-populated if known
        "framework_id": framework_id,
        "selected_data_sources": selected_data_sources or [],
        "compliance_profile": compliance_profile or {},
        "active_project_id": active_project_id or "",

        # Base state list fields — must be initialised empty
        "controls": [],
        "risks": [],
        "scenarios": [],
        "test_cases": [],
        "siem_rules": [],
        "playbooks": [],
        "test_scripts": [],
        "data_pipelines": [],
        "dashboards": [],
        "vulnerability_mappings": [],
        "gap_analysis_results": [],
        "cross_framework_mappings": [],
        "metrics_context": [],
        "xsoar_indicators": [],
        "resolved_metrics": [],
        "resolved_focus_areas": [],
        "focus_area_categories": [],
        "execution_steps": [],

        # DT-specific fields
        "dt_retrieved_controls": [],
        "dt_retrieved_risks": [],
        "dt_retrieved_scenarios": [],
        "dt_resolved_schemas": [],
        "dt_gold_standard_tables": [],
        "dt_dropped_items": [],
        "dt_schema_gaps": [],
        "dt_gap_notes": [],
        "dt_rule_gaps": [],
        "dt_metric_recommendations": [],
        "dt_unmeasured_controls": [],
        "dt_siem_validation_failures": [],
        "dt_metric_validation_failures": [],
        "dt_metric_validation_warnings": [],
        "dt_playbook_template_sections": [],
        "dt_validation_iteration": 0,
        "dt_siem_validation_passed": False,
        "dt_metric_validation_passed": False,
        
        # Detection engineer metrics/KPIs (Phase 2 output)
        "kpis": [],
        "control_to_metrics_mappings": [],
        "risk_to_metrics_mappings": [],
        "dt_medallion_plan": {},

        # Planning
        "current_step_index": 0,
        "plan_completion_status": {},
        "context_cache": {},
        "iteration_count": 0,
        "max_iterations": MAX_REFINEMENT_ITERATIONS,
        "validation_results": [],
        "refinement_history": [],
    }


if __name__ == "__main__":
    app = get_detection_triage_app()
    print("Detection & Triage workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")
