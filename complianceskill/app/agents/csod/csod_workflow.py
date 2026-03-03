"""
CSOD Metrics, Tables, and KPIs Recommender Workflow

Standalone LangGraph workflow for the CSOD pipeline.
Similar architecture to DT workflow but focused on Cornerstone/Workday integrations.

Graph topology:
  csod_intent_classifier
    → csod_planner
      → csod_mdl_schema_retrieval
        → csod_metrics_retrieval
          → csod_scoring_validator
            → [Intent-specific routing]
              → csod_metrics_recommender (for metrics_dashboard_plan, metrics_recommender_with_gold_plan)
                → csod_data_science_insights_enricher (enrich metrics with insights)
                  → calculation_planner (evaluate both metrics and enriched insights with SQL functions)
                    → csod_medallion_planner (if metrics_recommender_with_gold_plan or metrics need gold models)
              → csod_dashboard_generator (for dashboard_generation_for_persona)
                → csod_data_science_insights_enricher (enrich dashboard metrics with insights)
                  → calculation_planner (evaluate dashboard metrics and enriched insights)
              → csod_compliance_test_generator (for compliance_test_generator)
            → csod_scheduler (optional)
              → csod_output_assembler
                → END
"""
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState

# CSOD-specific nodes
from app.agents.csod.csod_nodes import (
    csod_intent_classifier_node,
    csod_planner_node,
    csod_mdl_schema_retrieval_node,
    csod_metrics_retrieval_node,
    csod_scoring_validator_node,
    csod_metrics_recommender_node,
    csod_medallion_planner_node,
    csod_data_science_insights_enricher_node,
    csod_dashboard_generator_node,
    csod_compliance_test_generator_node,
    csod_scheduler_node,
    csod_output_assembler_node,
)
# Calculation planning nodes (shared with DT workflow)
from app.agents.dt_nodes import (
    calculation_planner_node,
)
from app.core.telemetry import instrument_langgraph_node

logger = logging.getLogger(__name__)


# ============================================================================
# Conditional routing functions
# ============================================================================

def _route_after_planner(state: EnhancedCompliancePipelineState) -> str:
    """After planning, always go to MDL schema retrieval."""
    return "csod_mdl_schema_retrieval"


def _route_after_schema_retrieval(state: EnhancedCompliancePipelineState) -> str:
    """After schema retrieval, go to metrics retrieval."""
    return "csod_metrics_retrieval"


def _route_after_metrics_retrieval(state: EnhancedCompliancePipelineState) -> str:
    """After metrics retrieval, go to scoring validator."""
    return "csod_scoring_validator"


def _route_after_scoring(state: EnhancedCompliancePipelineState) -> str:
    """
    After scoring, route based on intent:
    - metrics_dashboard_plan → metrics_recommender
    - metrics_recommender_with_gold_plan → metrics_recommender
    - dashboard_generation_for_persona → dashboard_generator
    - compliance_test_generator → compliance_test_generator
    """
    intent = state.get("csod_intent", "")
    
    if intent in ("metrics_dashboard_plan", "metrics_recommender_with_gold_plan"):
        return "csod_metrics_recommender"
    elif intent == "dashboard_generation_for_persona":
        return "csod_dashboard_generator"
    elif intent == "compliance_test_generator":
        return "csod_compliance_test_generator"
    else:
        # Default to metrics recommender
        logger.warning(f"Unknown intent '{intent}', defaulting to metrics_recommender")
        return "csod_metrics_recommender"


def _route_after_metrics_recommender(state: EnhancedCompliancePipelineState) -> str:
    """
    After metrics_recommender, go to data science insights enricher first.
    Calculation planner will run after insights enrichment to evaluate both metrics and enriched insights.
    """
    return "csod_data_science_insights_enricher"


def _route_after_insights_enricher(state: EnhancedCompliancePipelineState) -> str:
    """
    After insights enricher, route to calculation_planner to evaluate both metrics and enriched insights,
    then to medallion_planner if needed, otherwise to scheduler.
    """
    intent = state.get("csod_intent", "")
    metric_recommendations = state.get("csod_metric_recommendations", [])
    data_science_insights = state.get("csod_data_science_insights", [])
    
    # Always run calculation planner if we have metrics or insights (it can handle both)
    if metric_recommendations or data_science_insights:
        return "calculation_planner"
    else:
        # If no metrics or insights, skip calculation planner
        # Route to medallion planner if needed, otherwise scheduler
        needs_gold_plan = (
            intent == "metrics_recommender_with_gold_plan" or
            (metric_recommendations and len(metric_recommendations) > 0)
        )
        if needs_gold_plan:
            return "csod_medallion_planner"
        else:
            return "csod_scheduler"


def _route_after_calculation_planner(state: EnhancedCompliancePipelineState) -> str:
    """
    After calculation planner, route to medallion_planner if gold plan is needed,
    otherwise go to scheduler.
    """
    intent = state.get("csod_intent", "")
    metric_recommendations = state.get("csod_metric_recommendations", [])
    
    # Route to medallion planner if:
    # 1. Intent explicitly requests gold plan, OR
    # 2. We have metrics that likely need gold models (complex aggregations, multiple tables)
    needs_gold_plan = (
        intent == "metrics_recommender_with_gold_plan" or
        (metric_recommendations and len(metric_recommendations) > 0)
    )
    
    if needs_gold_plan:
        return "csod_medallion_planner"
    else:
        return "csod_scheduler"


def _route_after_insights_enricher(state: EnhancedCompliancePipelineState) -> str:
    """
    After insights enricher, route to medallion_planner if gold plan is needed,
    otherwise go to scheduler.
    """
    intent = state.get("csod_intent", "")
    metric_recommendations = state.get("csod_metric_recommendations", [])
    data_science_insights = state.get("csod_data_science_insights", [])
    
    # Route to medallion planner if:
    # 1. Intent explicitly requests gold plan, OR
    # 2. We have metrics that likely need gold models (complex aggregations, multiple tables)
    needs_gold_plan = (
        intent == "metrics_recommender_with_gold_plan" or
        (metric_recommendations and len(metric_recommendations) > 0)
    )
    
    if needs_gold_plan:
        return "csod_medallion_planner"
    else:
        return "csod_scheduler"


def _route_after_medallion_planner(state: EnhancedCompliancePipelineState) -> str:
    """After medallion planner, route to scheduler."""
    return "csod_scheduler"


def _route_after_dashboard_generator(state: EnhancedCompliancePipelineState) -> str:
    """
    After dashboard_generator, route to data science insights enricher to enrich dashboard metrics,
    then to scheduler.
    """
    return "csod_data_science_insights_enricher"


def _route_after_compliance_test_generator(state: EnhancedCompliancePipelineState) -> str:
    """
    After compliance_test_generator, route to scheduler (no insights needed for test cases).
    """
    return "csod_scheduler"


def _route_after_scheduler(state: EnhancedCompliancePipelineState) -> str:
    """After scheduler, go to output assembler."""
    return "csod_output_assembler"


def _route_after_assembler(state: EnhancedCompliancePipelineState) -> str:
    """After assembler, end the workflow."""
    return "end"


# ============================================================================
# Graph builder
# ============================================================================

def build_csod_workflow() -> StateGraph:
    """
    Build the CSOD LangGraph workflow.

    Returns:
        Un-compiled StateGraph (call .compile() to get the runnable app).
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)

    # ── Register nodes (with telemetry instrumentation) ─────────────────────
    workflow.add_node("csod_intent_classifier", instrument_langgraph_node(csod_intent_classifier_node, "csod_intent_classifier", "csod"))
    workflow.add_node("csod_planner", instrument_langgraph_node(csod_planner_node, "csod_planner", "csod"))
    workflow.add_node("csod_mdl_schema_retrieval", instrument_langgraph_node(csod_mdl_schema_retrieval_node, "csod_mdl_schema_retrieval", "csod"))
    workflow.add_node("csod_metrics_retrieval", instrument_langgraph_node(csod_metrics_retrieval_node, "csod_metrics_retrieval", "csod"))
    workflow.add_node("csod_scoring_validator", instrument_langgraph_node(csod_scoring_validator_node, "csod_scoring_validator", "csod"))
    workflow.add_node("csod_metrics_recommender", instrument_langgraph_node(csod_metrics_recommender_node, "csod_metrics_recommender", "csod"))
    workflow.add_node("calculation_planner", instrument_langgraph_node(calculation_planner_node, "calculation_planner", "csod"))
    workflow.add_node("csod_medallion_planner", instrument_langgraph_node(csod_medallion_planner_node, "csod_medallion_planner", "csod"))
    workflow.add_node("csod_data_science_insights_enricher", instrument_langgraph_node(csod_data_science_insights_enricher_node, "csod_data_science_insights_enricher", "csod"))
    workflow.add_node("csod_dashboard_generator", instrument_langgraph_node(csod_dashboard_generator_node, "csod_dashboard_generator", "csod"))
    workflow.add_node("csod_compliance_test_generator", instrument_langgraph_node(csod_compliance_test_generator_node, "csod_compliance_test_generator", "csod"))
    workflow.add_node("csod_scheduler", instrument_langgraph_node(csod_scheduler_node, "csod_scheduler", "csod"))
    workflow.add_node("csod_output_assembler", instrument_langgraph_node(csod_output_assembler_node, "csod_output_assembler", "csod"))

    # ── Entry point ──────────────────────────────────────────────────────────
    workflow.set_entry_point("csod_intent_classifier")

    # ── Fixed edges ──────────────────────────────────────────────────────────
    workflow.add_edge("csod_intent_classifier", "csod_planner")

    # ── Conditional edges ────────────────────────────────────────────────────
    workflow.add_conditional_edges(
        "csod_planner",
        _route_after_planner,
        {"csod_mdl_schema_retrieval": "csod_mdl_schema_retrieval"},
    )

    workflow.add_conditional_edges(
        "csod_mdl_schema_retrieval",
        _route_after_schema_retrieval,
        {"csod_metrics_retrieval": "csod_metrics_retrieval"},
    )

    workflow.add_conditional_edges(
        "csod_metrics_retrieval",
        _route_after_metrics_retrieval,
        {"csod_scoring_validator": "csod_scoring_validator"},
    )

    workflow.add_conditional_edges(
        "csod_scoring_validator",
        _route_after_scoring,
        {
            "csod_metrics_recommender": "csod_metrics_recommender",
            "csod_dashboard_generator": "csod_dashboard_generator",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
        },
    )

    workflow.add_conditional_edges(
        "csod_metrics_recommender",
        _route_after_metrics_recommender,
        {"csod_data_science_insights_enricher": "csod_data_science_insights_enricher"},
    )
    
    workflow.add_conditional_edges(
        "csod_data_science_insights_enricher",
        _route_after_insights_enricher,
        {
            "calculation_planner": "calculation_planner",
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_scheduler": "csod_scheduler",
        },
    )
    
    workflow.add_conditional_edges(
        "calculation_planner",
        _route_after_calculation_planner,
        {
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_scheduler": "csod_scheduler",
        },
    )
    
    workflow.add_conditional_edges(
        "csod_medallion_planner",
        _route_after_medallion_planner,
        {"csod_scheduler": "csod_scheduler"},
    )

    workflow.add_conditional_edges(
        "csod_dashboard_generator",
        _route_after_dashboard_generator,
        {"csod_data_science_insights_enricher": "csod_data_science_insights_enricher"},
    )

    workflow.add_conditional_edges(
        "csod_compliance_test_generator",
        _route_after_compliance_test_generator,
        {"csod_scheduler": "csod_scheduler"},
    )

    workflow.add_conditional_edges(
        "csod_scheduler",
        _route_after_scheduler,
        {"csod_output_assembler": "csod_output_assembler"},
    )

    workflow.add_conditional_edges(
        "csod_output_assembler",
        _route_after_assembler,
        {"end": END},
    )

    return workflow


# ============================================================================
# App factory functions
# ============================================================================

def create_csod_app(checkpointer=None):
    """
    Create and compile the CSOD application.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.
                      Defaults to MemorySaver (in-memory, suitable for dev).

    Returns:
        Compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    workflow = build_csod_workflow()
    return workflow.compile(checkpointer=checkpointer)


def get_csod_app():
    """Convenience: return a default CSOD app with in-memory checkpointer."""
    return create_csod_app()


# ============================================================================
# Initial state factory
# ============================================================================

def create_csod_initial_state(
    user_query: str,
    session_id: str,
    active_project_id: str = None,
    selected_data_sources: list = None,
    compliance_profile: dict = None,
    silver_gold_tables_only: bool = False,
) -> dict:
    """
    Build an initial state dict for the CSOD workflow.

    Args:
        user_query:             The user's natural language query.
        session_id:             Unique session identifier.
        active_project_id:      ProjectId for GoldStandardTable lookup.
        selected_data_sources:  List of confirmed data source IDs (e.g., ["cornerstone", "workday"]).
        compliance_profile:     Full compliance profile dict (optional).
        silver_gold_tables_only: Set to True to skip source/bronze tables, only use silver and gold.

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

        # CSOD-specific fields
        "csod_intent": None,
        "csod_persona": None,
        "csod_plan_summary": None,
        "csod_estimated_complexity": None,
        "csod_execution_plan": [],
        "csod_gap_notes": [],
        "csod_data_sources_in_scope": [],
        "csod_resolved_schemas": [],
        "csod_gold_standard_tables": [],
        "csod_retrieved_metrics": [],
        "csod_retrieved_kpis": [],
        "csod_scored_context": None,
        "csod_dropped_items": [],
        "csod_schema_gaps": [],
        "csod_scoring_threshold_applied": 0.5,
        "csod_metric_recommendations": [],
        "csod_kpi_recommendations": [],
        "csod_table_recommendations": [],
        "csod_data_science_insights": [],
        "csod_medallion_plan": {},
        "csod_unmeasured_requirements": [],
        "csod_dashboard_assembled": None,
        "csod_test_cases": [],
        "csod_test_queries": [],
        "csod_test_validation_passed": False,
        "csod_test_validation_failures": [],
        "csod_schedule_type": None,
        "csod_schedule_config": {},
        "csod_execution_frequency": None,
        "csod_validation_iteration": 0,
        "csod_metric_validation_passed": False,
        "csod_metric_validation_failures": [],
        "csod_metric_validation_warnings": [],
        "csod_assembled_output": None,

        # Planning
        "current_step_index": 0,
        "plan_completion_status": {},
        "context_cache": {},
        "iteration_count": 0,
        "max_iterations": 3,
        "validation_results": [],
        "refinement_history": [],

        # Data enrichment
        "data_enrichment": {
            "needs_mdl": True,
            "needs_metrics": True,
            "suggested_focus_areas": [],
            "metrics_intent": "current_state",
        },

        # Flags
        "silver_gold_tables_only": silver_gold_tables_only,
    }


if __name__ == "__main__":
    app = get_csod_app()
    print("CSOD workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")
