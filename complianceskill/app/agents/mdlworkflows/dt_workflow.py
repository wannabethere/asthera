"""
Detection & Triage Engineering Workflow

Standalone LangGraph workflow for the Detection & Triage (DT) pipeline.
Mirrors the structure of build_compliance_workflow() in detectiontriageworkflows/workflow.py but
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
                  ┌── dt_detection_engineer ──→ dt_siem_rule_validator ──→ dt_metric_calculation_validator
                  │       → dt_metric_feasibility_filter (if template C) ──→ dt_triage_engineer
                  │       → dt_playbook_assembler (else)
                  └── dt_metric_feasibility_filter ──→ dt_triage_engineer ──→ dt_metric_calculation_validator
                        ──→ dt_playbook_assembler ──→ END

Can also be wired into the existing compliance workflow via
add_dt_workflow_to_existing() helper at the bottom of this file.
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState

# DT-specific nodes
from .dt_nodes import (
    dt_intent_classifier_node,
    dt_planner_node,
    dt_framework_retrieval_node,
    dt_metrics_retrieval_node,
    dt_metrics_format_converter_node,
    dt_unified_format_converter_node,
    dt_mdl_schema_retrieval_node,
    dt_scoring_validator_node,
    dt_metric_feasibility_filter_node,
    dt_detection_engineer_node,
    dt_triage_engineer_node,
    dt_siem_rule_validator_node,
    dt_metric_calculation_validator_node,
    dt_playbook_assembler_node,
    calculation_needs_assessment_node,
    dt_dashboard_context_discoverer_node,
    dt_dashboard_clarifier_node,
    dt_dashboard_question_generator_node,
    dt_dashboard_question_validator_node,
    dt_dashboard_assembler_node,
)
from .dt_validation_reset_node import dt_validation_reset_node
# Shared workflow-agnostic calculation planner + cubejs generation
from app.agents.shared import calculation_planner_node, cubejs_schema_generation_node
from app.agents.decision_trees.dt_decision_tree_generation_node import dt_decision_tree_generation_node
from app.agents.decision_trees.dt_metric_decision_nodes import (
    dt_metric_decision_node,
    get_metric_decision_state_extensions,
)
from app.core.telemetry import instrument_langgraph_node

logger = logging.getLogger(__name__)

from .constants import MAX_REFINEMENT_ITERATIONS


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
    After metrics retrieval, route based on:
    1. If leen request, convert format first
    2. Then go to MDL schema lookup if needs_mdl
    3. Or go to decision tree generation if metrics are available
    """
    # If this is a leen request, convert metrics format first
    is_leen_request = state.get("is_leen_request", False)
    if is_leen_request:
        return "dt_metrics_format_converter"
    
    data_enrichment = state.get("data_enrichment", {})
    if data_enrichment.get("needs_mdl", False):
        return "dt_mdl_schema_retrieval"
    
    # If we have metrics and decision tree is enabled, generate artifacts
    # Default to False since control taxonomy and metrics enrichment already exist
    resolved_metrics = state.get("resolved_metrics", [])
    if resolved_metrics and state.get("dt_use_llm_generation", False):
        return "dt_decision_tree_generation"
    
    return "dt_scoring_validator"


def _route_after_format_converter(state: EnhancedCompliancePipelineState) -> str:
    """
    After format converter, route to MDL schema lookup if needs_mdl,
    or to decision tree generation if metrics are available.
    """
    data_enrichment = state.get("data_enrichment", {})
    if data_enrichment.get("needs_mdl", False):
        return "dt_mdl_schema_retrieval"
    
    # If we have metrics and decision tree is enabled, generate artifacts
    # Default to False since control taxonomy and metrics enrichment already exist
    resolved_metrics = state.get("resolved_metrics", [])
    if resolved_metrics and state.get("dt_use_llm_generation", False):
        return "dt_decision_tree_generation"
    
    return "dt_scoring_validator"


def _route_after_decision_tree_generation(state: EnhancedCompliancePipelineState) -> str:
    """After decision tree generation, route based on whether calculation is needed."""
    needs_calculation = state.get("needs_calculation", True)
    if needs_calculation:
        return "calculation_needs_assessment"
    return "dt_scoring_validator"


def _route_after_mdl_schema_retrieval(state: EnhancedCompliancePipelineState) -> str:
    """
    After MDL schema retrieval, route to calculation needs assessment.
    Calculation planning is MDL-specific, so it runs after schema retrieval.
    """
    # After MDL, check if we should generate decision tree artifacts
    # Default to False since control taxonomy and metrics enrichment already exist
    resolved_metrics = state.get("resolved_metrics", [])
    if resolved_metrics and state.get("dt_use_llm_generation", False):
        return "dt_decision_tree_generation"
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
    Note: Decision tree enrichment now happens in dt_metrics_retrieval_node.
    """
    return "dt_scoring_validator"


def _route_after_scoring(state: EnhancedCompliancePipelineState) -> str:
    """
    After scoring, route to the correct execution branch(es) based on template.

    Template A (detection_focused) → detection_engineer only
    Template B (triage_focused)    → triage_engineer only
    Template C (full_chain)        → detection_engineer first, then triage
    Dashboard generation intent    → dashboard_context_discoverer

    For simplicity in LangGraph (single edge per node), we use a sequencing
    pattern: detection_engineer always runs before triage_engineer when both
    are needed; the triage_engineer node checks expected_outputs and skips
    gracefully if not needed.
    """
    # NEW: Dashboard generation bypasses detection/triage engineers
    intent = state.get("intent", "")
    if intent == "dashboard_generation":
        return "dt_dashboard_context_discoverer"
    
    expected = state.get("dt_expected_outputs", {})
    template = state.get("dt_playbook_template", "A")

    if template == "B" or (not expected.get("siem_rules", True) and expected.get("metric_recommendations", False)):
        return "dt_metric_feasibility_filter"
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
    - If validation failed and under max iterations → validation_reset → re-run detection_engineer
    - If validation failed at max iterations → proceed to metric validator anyway (with warnings)
    - If validation passed → proceed to metric calculation validator
    
    NOTE: State mutations moved to dt_validation_reset_node. This function is now pure.
    """
    passed = state.get("dt_siem_validation_passed", True)
    iteration = state.get("dt_validation_iteration", 0)

    # If SIEM validation failed and under max iterations, go through validation_reset then re-run detection_engineer
    if not passed and iteration < MAX_REFINEMENT_ITERATIONS:
        logger.info(f"SIEM validation failed (iteration {iteration + 1}/{MAX_REFINEMENT_ITERATIONS}), routing to validation_reset...")
        return "dt_validation_reset"
    
    # If validation failed but at max iterations, proceed anyway (will have warnings)
    if not passed and iteration >= MAX_REFINEMENT_ITERATIONS:
        logger.warning(f"SIEM validation failed after {MAX_REFINEMENT_ITERATIONS} iterations, proceeding to metric validator with warnings")

    # After SIEM validation (passed or max iterations reached), validate metrics from detection engineer
    # Mark that we're validating detection engineer metrics (this will be set in validation_reset if needed)
    state["dt_validating_detection_metrics"] = True
    return "dt_metric_calculation_validator"


def _route_after_triage_engineer(state: EnhancedCompliancePipelineState) -> str:
    """After triage engineer, always validate metrics."""
    return "dt_metric_calculation_validator"


def _route_after_playbook_assembler(state: EnhancedCompliancePipelineState) -> str:
    """
    After playbook assembler, route to unified format converter if:
    - leen request is True, OR
    - medallion plan exists, OR
    - we have metrics and schemas (to generate gold model plan)
    """
    is_leen_request = state.get("is_leen_request", False)
    has_medallion_plan = bool(state.get("dt_medallion_plan", {}).get("entries"))
    
    # Check if we have metrics and schemas to generate gold model plan
    metric_recommendations = state.get("dt_metric_recommendations", [])
    resolved_metrics = state.get("resolved_metrics", [])
    resolved_schemas = state.get("dt_resolved_schemas", [])
    
    # Also check dt_scored_context for schemas if dt_resolved_schemas is empty
    if not resolved_schemas:
        scored_context = state.get("dt_scored_context", {})
        resolved_schemas = scored_context.get("resolved_schemas", [])
    
    has_metrics = bool(metric_recommendations or resolved_metrics) and (
        len(metric_recommendations) > 0 or len(resolved_metrics) > 0
    )
    has_schemas = bool(resolved_schemas) and len(resolved_schemas) > 0
    can_generate_plan = has_metrics and has_schemas
    
    logger.info(
        f"_route_after_playbook_assembler: is_leen_request={is_leen_request}, "
        f"has_medallion_plan={has_medallion_plan}, can_generate_plan={can_generate_plan} "
        f"(has_metrics={has_metrics}, has_schemas={has_schemas})"
    )
    
    if is_leen_request or has_medallion_plan or can_generate_plan:
        return "dt_unified_format_converter"
    return "end"


def _route_after_validation_reset(state: EnhancedCompliancePipelineState) -> str:
    """
    After validation reset node, route to the appropriate next node based on context.
    
    This function determines where to go after state has been reset/incremented.
    """
    siem_validation_passed = state.get("dt_siem_validation_passed", True)
    metric_validation_passed = state.get("dt_metric_validation_passed", True)
    validating_detection = state.get("dt_validating_detection_metrics", False)
    iteration = state.get("dt_validation_iteration", 0)
    template = state.get("dt_playbook_template", "A")
    
    # If we came from SIEM validator and validation failed, retry detection_engineer
    if not siem_validation_passed and iteration <= MAX_REFINEMENT_ITERATIONS:
        return "dt_detection_engineer"
    
    # If we came from metric validator and validation failed, retry appropriate engineer
    if not metric_validation_passed and iteration <= MAX_REFINEMENT_ITERATIONS:
        if validating_detection:
            return "dt_detection_engineer"
        else:
            return "dt_triage_engineer"
    
    # If we came from metric validator and validation passed
    if metric_validation_passed:
        if validating_detection:
            # Detection phase passed - check if triage needed
            if template == "C":
                return "dt_metric_feasibility_filter"
            return "dt_playbook_assembler"
        else:
            # Triage phase passed - go to assembler
            return "dt_playbook_assembler"
    
    # Default fallback
    return "dt_playbook_assembler"


def _route_after_metric_validator(state: EnhancedCompliancePipelineState) -> str:
    """
    After metric validation:
    - If validating detection engineer metrics:
      - Passed → check if triage needed (template C) or go to assembler
      - Failed + under max iterations → validation_reset → re-run detection_engineer
      - Failed + at max iterations → assembler with warnings
    - If validating triage engineer metrics:
      - Passed → assembler
      - Failed + under max iterations → validation_reset → re-run triage_engineer
      - Failed + at max iterations → assembler with warnings
    
    NOTE: State mutations moved to dt_validation_reset_node. This function is now pure.
    """
    passed = state.get("dt_metric_validation_passed", True)
    iteration = state.get("dt_validation_iteration", 0)
    template = state.get("dt_playbook_template", "A")
    validating_detection = state.get("dt_validating_detection_metrics", False)

    # If validation failed and under max iterations, go through validation_reset then re-run the appropriate engineer
    if not passed and iteration < MAX_REFINEMENT_ITERATIONS:
        logger.info(f"Metric validation failed (iteration {iteration + 1}/{MAX_REFINEMENT_ITERATIONS}), routing to validation_reset...")
        if validating_detection:
            return "dt_validation_reset"  # Will route to dt_detection_engineer after reset
        else:
            return "dt_validation_reset"  # Will route to dt_triage_engineer after reset
    
    # If validation failed but at max iterations, proceed to assembler with warnings
    if not passed and iteration >= MAX_REFINEMENT_ITERATIONS:
        logger.warning(f"Metric validation failed after {MAX_REFINEMENT_ITERATIONS} iterations, proceeding to assembler with warnings")
        # If template C, still try triage (but it might also fail)
        if validating_detection and template == "C":
            return "dt_triage_engineer"
        return "dt_playbook_assembler"

    # If validating detection engineer metrics and passed
    if validating_detection:
        # Go through validation_reset to clear flag and reset iteration, then route based on template
        if template == "C":
            return "dt_validation_reset"  # Will route to dt_metric_feasibility_filter after reset
        return "dt_validation_reset"  # Will route to dt_playbook_assembler after reset

    # If validating triage engineer metrics and passed, go to assembler
    return "dt_validation_reset"  # Will route to dt_playbook_assembler after reset


# ============================================================================
# Dashboard generation routing functions
# ============================================================================

MAX_DASHBOARD_VALIDATION_ITERATIONS = 2


def _route_after_dashboard_validator(state: EnhancedCompliancePipelineState) -> str:
    """
    Route after dashboard question validation.
    
    If validation failed (CRITICAL failures) and under max iterations, 
    route back to question generator. Otherwise proceed to assembler.
    """
    status = state.get("dt_dashboard_validation_status", "pass")
    iteration = state.get("dt_dashboard_validation_iteration", 0)
    
    if status == "fail" and iteration < MAX_DASHBOARD_VALIDATION_ITERATIONS:
        state["dt_dashboard_validation_iteration"] = iteration + 1
        return "dt_dashboard_question_generator"
    
    return "dt_dashboard_assembler"


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
    workflow.add_node("dt_metrics_format_converter",  instrument_langgraph_node(dt_metrics_format_converter_node, "dt_metrics_format_converter", "detection_triage"))
    workflow.add_node("dt_mdl_schema_retrieval",       instrument_langgraph_node(dt_mdl_schema_retrieval_node, "dt_mdl_schema_retrieval", "detection_triage"))
    workflow.add_node("dt_decision_tree_generation",  instrument_langgraph_node(dt_decision_tree_generation_node, "dt_decision_tree_generation", "detection_triage"))
    workflow.add_node("calculation_needs_assessment", instrument_langgraph_node(calculation_needs_assessment_node, "calculation_needs_assessment", "detection_triage"))
    workflow.add_node("calculation_planner",          instrument_langgraph_node(calculation_planner_node, "calculation_planner", "detection_triage"))
    workflow.add_node("dt_metric_decision_node",      instrument_langgraph_node(dt_metric_decision_node, "dt_metric_decision_node", "detection_triage"))
    workflow.add_node("dt_scoring_validator",          instrument_langgraph_node(dt_scoring_validator_node, "dt_scoring_validator", "detection_triage"))
    workflow.add_node("dt_metric_feasibility_filter",   instrument_langgraph_node(dt_metric_feasibility_filter_node, "dt_metric_feasibility_filter", "detection_triage"))
    workflow.add_node("dt_detection_engineer",         instrument_langgraph_node(dt_detection_engineer_node, "dt_detection_engineer", "detection_triage"))
    workflow.add_node("dt_siem_rule_validator",        instrument_langgraph_node(dt_siem_rule_validator_node, "dt_siem_rule_validator", "detection_triage"))
    workflow.add_node("dt_triage_engineer",            instrument_langgraph_node(dt_triage_engineer_node, "dt_triage_engineer", "detection_triage"))
    workflow.add_node("dt_metric_calculation_validator", instrument_langgraph_node(dt_metric_calculation_validator_node, "dt_metric_calculation_validator", "detection_triage"))
    workflow.add_node("dt_validation_reset",             instrument_langgraph_node(dt_validation_reset_node, "dt_validation_reset", "detection_triage"))
    workflow.add_node("dt_playbook_assembler",         instrument_langgraph_node(dt_playbook_assembler_node, "dt_playbook_assembler", "detection_triage"))
    workflow.add_node("dt_unified_format_converter",  instrument_langgraph_node(dt_unified_format_converter_node, "dt_unified_format_converter", "detection_triage"))
    workflow.add_node("cubejs_schema_generation",      instrument_langgraph_node(cubejs_schema_generation_node, "cubejs_schema_generation", "detection_triage"))

    # Dashboard generation nodes
    workflow.add_node("dt_dashboard_context_discoverer", instrument_langgraph_node(dt_dashboard_context_discoverer_node, "dt_dashboard_context_discoverer", "detection_triage"))
    workflow.add_node("dt_dashboard_clarifier",         instrument_langgraph_node(dt_dashboard_clarifier_node, "dt_dashboard_clarifier", "detection_triage"))
    workflow.add_node("dt_dashboard_question_generator", instrument_langgraph_node(dt_dashboard_question_generator_node, "dt_dashboard_question_generator", "detection_triage"))
    workflow.add_node("dt_dashboard_question_validator", instrument_langgraph_node(dt_dashboard_question_validator_node, "dt_dashboard_question_validator", "detection_triage"))
    workflow.add_node("dt_dashboard_assembler",         instrument_langgraph_node(dt_dashboard_assembler_node, "dt_dashboard_assembler", "detection_triage"))

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
            "dt_metrics_format_converter": "dt_metrics_format_converter",
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_decision_tree_generation": "dt_decision_tree_generation",
            "dt_scoring_validator":    "dt_scoring_validator",
        },
    )
    
    # After format converter, route to MDL or decision tree or scoring
    workflow.add_conditional_edges(
        "dt_metrics_format_converter",
        _route_after_format_converter,
        {
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_decision_tree_generation": "dt_decision_tree_generation",
            "dt_scoring_validator": "dt_scoring_validator",
        },
    )

    # After MDL schema retrieval, route to decision tree generation or calculation needs assessment
    workflow.add_conditional_edges(
        "dt_mdl_schema_retrieval",
        _route_after_mdl_schema_retrieval,
        {
            "dt_decision_tree_generation": "dt_decision_tree_generation",
            "calculation_needs_assessment": "calculation_needs_assessment",
        },
    )
    
    # After decision tree generation, route to calculation needs assessment or scoring
    # Note: Decision tree enrichment is now integrated into dt_metrics_retrieval_node
    workflow.add_conditional_edges(
        "dt_decision_tree_generation",
        _route_after_decision_tree_generation,
        {
            "calculation_needs_assessment": "calculation_needs_assessment",
            "dt_scoring_validator": "dt_scoring_validator",
        },
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
    # Note: Decision tree enrichment is now integrated into dt_metrics_retrieval_node
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
            "dt_metric_feasibility_filter": "dt_metric_feasibility_filter",
            "dt_dashboard_context_discoverer": "dt_dashboard_context_discoverer",
        },
    )

    workflow.add_edge("dt_metric_feasibility_filter", "dt_triage_engineer")

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
            "dt_validation_reset": "dt_validation_reset",  # refinement loop
        },
    )
    
    workflow.add_conditional_edges(
        "dt_validation_reset",
        _route_after_validation_reset,
        {
            "dt_detection_engineer": "dt_detection_engineer",
            "dt_triage_engineer": "dt_triage_engineer",
            "dt_metric_feasibility_filter": "dt_metric_feasibility_filter",
            "dt_playbook_assembler": "dt_playbook_assembler",
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
            "dt_validation_reset": "dt_validation_reset",  # refinement loop (goes through reset first)
            "dt_triage_engineer": "dt_triage_engineer",   # direct route (max iterations reached)
            "dt_playbook_assembler": "dt_playbook_assembler",  # direct route (max iterations reached)
        },
    )

    # After playbook assembler, route to unified format converter if leen request, else end
    workflow.add_conditional_edges(
        "dt_playbook_assembler",
        _route_after_playbook_assembler,
        {
            "dt_unified_format_converter": "dt_unified_format_converter",
            "end": END,
        },
    )
    
    # After unified format converter, route to cubejs if we have gold SQL, else end
    def _route_after_unified_converter(state: EnhancedCompliancePipelineState) -> str:
        gold_sql = state.get("dt_generated_gold_model_sql", [])
        if gold_sql and len(gold_sql) > 0:
            return "cubejs_schema_generation"
        return "end"

    workflow.add_conditional_edges(
        "dt_unified_format_converter",
        _route_after_unified_converter,
        {
            "cubejs_schema_generation": "cubejs_schema_generation",
            "end": END,
        },
    )

    workflow.add_edge("cubejs_schema_generation", END)

    # ── Dashboard generation workflow edges ─────────────────────────────────
    workflow.add_edge("dt_dashboard_context_discoverer", "dt_dashboard_clarifier")
    workflow.add_edge("dt_dashboard_clarifier", "dt_dashboard_question_generator")
    workflow.add_edge("dt_dashboard_question_generator", "dt_dashboard_question_validator")
    
    workflow.add_conditional_edges(
        "dt_dashboard_question_validator",
        _route_after_dashboard_validator,
        {
            "dt_dashboard_question_generator": "dt_dashboard_question_generator",  # refinement loop
            "dt_dashboard_assembler": "dt_dashboard_assembler",
        },
    )
    
    # Dashboard assembler routes to unified format converter (for LEEN) before END,
    # so gold model plan and SQL generation run for dashboard intent too
    workflow.add_conditional_edges(
        "dt_dashboard_assembler",
        _route_after_playbook_assembler,
        {
            "dt_unified_format_converter": "dt_unified_format_converter",
            "end": END,
        },
    )

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

    Example — modify route_from_profile_resolver in detectiontriageworkflows/workflow.py:

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
        existing_workflow: The StateGraph from detectiontriageworkflows.build_compliance_workflow()

    Returns:
        The same StateGraph with DT nodes added (mutated in place).
    """
    existing_workflow.add_node("dt_intent_classifier",          instrument_langgraph_node(dt_intent_classifier_node, "dt_intent_classifier", "detection_triage"))
    existing_workflow.add_node("dt_planner",                    instrument_langgraph_node(dt_planner_node, "dt_planner", "detection_triage"))
    existing_workflow.add_node("dt_framework_retrieval",        instrument_langgraph_node(dt_framework_retrieval_node, "dt_framework_retrieval", "detection_triage"))
    existing_workflow.add_node("dt_metrics_retrieval",          instrument_langgraph_node(dt_metrics_retrieval_node, "dt_metrics_retrieval", "detection_triage"))
    existing_workflow.add_node("dt_metrics_format_converter",  instrument_langgraph_node(dt_metrics_format_converter_node, "dt_metrics_format_converter", "detection_triage"))
    existing_workflow.add_node("dt_mdl_schema_retrieval",       instrument_langgraph_node(dt_mdl_schema_retrieval_node, "dt_mdl_schema_retrieval", "detection_triage"))
    existing_workflow.add_node("dt_decision_tree_generation",  instrument_langgraph_node(dt_decision_tree_generation_node, "dt_decision_tree_generation", "detection_triage"))
    existing_workflow.add_node("calculation_needs_assessment", instrument_langgraph_node(calculation_needs_assessment_node, "calculation_needs_assessment", "detection_triage"))
    existing_workflow.add_node("calculation_planner",          instrument_langgraph_node(calculation_planner_node, "calculation_planner", "detection_triage"))
    existing_workflow.add_node("dt_metric_decision_node",      instrument_langgraph_node(dt_metric_decision_node, "dt_metric_decision_node", "detection_triage"))
    existing_workflow.add_node("dt_scoring_validator",          instrument_langgraph_node(dt_scoring_validator_node, "dt_scoring_validator", "detection_triage"))
    existing_workflow.add_node("dt_metric_feasibility_filter", instrument_langgraph_node(dt_metric_feasibility_filter_node, "dt_metric_feasibility_filter", "detection_triage"))
    existing_workflow.add_node("dt_detection_engineer",         instrument_langgraph_node(dt_detection_engineer_node, "dt_detection_engineer", "detection_triage"))
    existing_workflow.add_node("dt_siem_rule_validator",        instrument_langgraph_node(dt_siem_rule_validator_node, "dt_siem_rule_validator", "detection_triage"))
    existing_workflow.add_node("dt_triage_engineer",            instrument_langgraph_node(dt_triage_engineer_node, "dt_triage_engineer", "detection_triage"))
    existing_workflow.add_node("dt_metric_calculation_validator", instrument_langgraph_node(dt_metric_calculation_validator_node, "dt_metric_calculation_validator", "detection_triage"))
    existing_workflow.add_node("dt_playbook_assembler",         instrument_langgraph_node(dt_playbook_assembler_node, "dt_playbook_assembler", "detection_triage"))
    existing_workflow.add_node("dt_unified_format_converter",  instrument_langgraph_node(dt_unified_format_converter_node, "dt_unified_format_converter", "detection_triage"))
    
    # Dashboard generation nodes
    existing_workflow.add_node("dt_dashboard_context_discoverer", instrument_langgraph_node(dt_dashboard_context_discoverer_node, "dt_dashboard_context_discoverer", "detection_triage"))
    existing_workflow.add_node("dt_dashboard_clarifier",         instrument_langgraph_node(dt_dashboard_clarifier_node, "dt_dashboard_clarifier", "detection_triage"))
    existing_workflow.add_node("dt_dashboard_question_generator", instrument_langgraph_node(dt_dashboard_question_generator_node, "dt_dashboard_question_generator", "detection_triage"))
    existing_workflow.add_node("dt_dashboard_question_validator", instrument_langgraph_node(dt_dashboard_question_validator_node, "dt_dashboard_question_validator", "detection_triage"))
    existing_workflow.add_node("dt_dashboard_assembler",         instrument_langgraph_node(dt_dashboard_assembler_node, "dt_dashboard_assembler", "detection_triage"))

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
            "dt_metrics_format_converter": "dt_metrics_format_converter",
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_decision_tree_generation": "dt_decision_tree_generation",
            "dt_scoring_validator":    "dt_scoring_validator",
        },
    )
    
    # After format converter, route to MDL or decision tree or scoring
    existing_workflow.add_conditional_edges(
        "dt_metrics_format_converter",
        _route_after_format_converter,
        {
            "dt_mdl_schema_retrieval": "dt_mdl_schema_retrieval",
            "dt_decision_tree_generation": "dt_decision_tree_generation",
            "dt_scoring_validator": "dt_scoring_validator",
        },
    )
    # After MDL schema retrieval, route to decision tree generation or calculation needs assessment
    existing_workflow.add_conditional_edges(
        "dt_mdl_schema_retrieval",
        _route_after_mdl_schema_retrieval,
        {
            "dt_decision_tree_generation": "dt_decision_tree_generation",
            "calculation_needs_assessment": "calculation_needs_assessment",
        },
    )
    
    # After decision tree generation, route to calculation needs assessment or scoring
    # Note: Decision tree enrichment is now integrated into dt_metrics_retrieval_node
    existing_workflow.add_conditional_edges(
        "dt_decision_tree_generation",
        _route_after_decision_tree_generation,
        {
            "calculation_needs_assessment": "calculation_needs_assessment",
            "dt_scoring_validator": "dt_scoring_validator",
        },
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
    # Note: Decision tree enrichment is now integrated into dt_metrics_retrieval_node
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
            "dt_metric_feasibility_filter": "dt_metric_feasibility_filter",
            "dt_dashboard_context_discoverer": "dt_dashboard_context_discoverer",
        },
    )
    existing_workflow.add_edge("dt_metric_feasibility_filter", "dt_triage_engineer")
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
            "dt_metric_feasibility_filter": "dt_metric_feasibility_filter",  # template C → triage
            "dt_playbook_assembler": "dt_playbook_assembler",
        },
    )
    # After playbook assembler, route to unified format converter if leen request, else to artifact_assembler
    def _route_after_playbook_assembler_integration(state: EnhancedCompliancePipelineState) -> str:
        """After playbook assembler in integration, route to converter if leen request, else artifact_assembler."""
        is_leen_request = state.get("is_leen_request", False)
        if is_leen_request:
            return "dt_unified_format_converter"
        return "artifact_assembler"
    
    existing_workflow.add_conditional_edges(
        "dt_playbook_assembler",
        _route_after_playbook_assembler_integration,
        {
            "dt_unified_format_converter": "dt_unified_format_converter",
            "artifact_assembler": "artifact_assembler",
        },
    )
    
    # Unified format converter routes back to artifact_assembler for unified output
    existing_workflow.add_edge("dt_unified_format_converter", "artifact_assembler")
    
    # Dashboard generation workflow edges
    existing_workflow.add_edge("dt_dashboard_context_discoverer", "dt_dashboard_clarifier")
    existing_workflow.add_edge("dt_dashboard_clarifier", "dt_dashboard_question_generator")
    existing_workflow.add_edge("dt_dashboard_question_generator", "dt_dashboard_question_validator")
    
    existing_workflow.add_conditional_edges(
        "dt_dashboard_question_validator",
        _route_after_dashboard_validator,
        {
            "dt_dashboard_question_generator": "dt_dashboard_question_generator",  # refinement loop
            "dt_dashboard_assembler": "dt_dashboard_assembler",
        },
    )
    
    # Dashboard assembler routes back to artifact_assembler for unified output
    existing_workflow.add_edge("dt_dashboard_assembler", "artifact_assembler")

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
    is_leen_request: bool = False,
    silver_gold_tables_only: bool = False,
    generate_sql: bool = False,
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
        is_leen_request:        Set to True when request comes from leen (enables format conversion).
        silver_gold_tables_only: Set to True to skip source/bronze tables, only use silver and gold.
        generate_sql:           Set to True to generate SQL for gold models (dbt-compatible).

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
        
        # Dashboard generation fields
        "dt_dashboard_context": None,
        "dt_dashboard_available_tables": [],
        "dt_dashboard_reference_patterns": [],
        "dt_dashboard_clarification_request": None,
        "dt_dashboard_clarification_response": None,
        "dt_dashboard_candidate_questions": [],
        "dt_dashboard_validated_questions": [],
        "dt_dashboard_validation_status": None,
        "dt_dashboard_validation_report": None,
        "dt_dashboard_user_selections": [],
        "dt_dashboard_assembled": None,
        "dt_dashboard_validation_iteration": 0,
        "dt_validating_detection_metrics": False,
        
        # Metric decision tree fields (from get_metric_decision_state_extensions)
        **get_metric_decision_state_extensions(),
        
        # Decision tree control flags
        "dt_use_decision_tree": True,  # Enable decision tree enrichment in metrics retrieval
        "dt_use_llm_generation": False,  # Disable LLM generation for now
        
        # Decision tree generation fields (for future use)
        "dt_generated_groups": [],
        "dt_generated_group_relationships": [],
        "dt_generated_taxonomy": [],
        "dt_generated_enrichments": [],
        "dt_generation_cache_key": None,
        "dt_generation_source": "static_fallback",
        
        # Leen integration flags
        # Note: These should be set by the caller if LEEN mode is needed
        # Default to False, but can be overridden by test/caller
        "is_leen_request": is_leen_request,  # Set to True when request comes from leen
        "silver_gold_tables_only": silver_gold_tables_only,  # Set to True to skip source/bronze tables, only use silver and gold
        "dt_generate_sql": bool(generate_sql),  # Set to True to generate SQL for gold models (explicit bool conversion)
        "dt_generated_gold_model_sql": [],  # Generated SQL models (populated if dt_generate_sql=True)
        "dt_gold_model_artifact_name": None,  # Artifact name for generated SQL models
        "goal_metric_definitions": [],  # Planner format: metric definitions without table mapping
        "goal_metrics": [],  # Planner format: metrics with table mapping
        "planner_siem_rules": [],  # Planner format: SIEM rules
        "planner_metric_recommendations": [],  # Planner format: metric recommendations
        "planner_execution_plan": {},  # Planner format: execution plan
        "planner_medallion_plan": {},  # Planner format: medallion plan

        # CubeJS generation (when gold SQL exists)
        "output_format": "cubejs",  # Set to "cubejs" to enable Cube.js schema generation
        "cubejs_schema_files": [],
        "cubejs_generation_errors": [],
    }


if __name__ == "__main__":
    app = get_detection_triage_app()
    print("Detection & Triage workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")
