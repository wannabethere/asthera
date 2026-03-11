"""
CSOD Metric Advisor Workflow with Causal Graph Integration

A focused workflow for metric/KPI recommendations enriched with causal graph insights.
Uses the causal graph creator to understand relationships and provide reasoning-based recommendations.

Graph topology:
    csod_intent_classifier
      → csod_planner
        → csod_mdl_schema_retrieval
          → csod_metrics_retrieval
            → csod_scoring_validator
              → csod_causal_graph (if enabled)
                → csod_metrics_recommender
                  → csod_metric_advisor (NEW)
                    → csod_output_assembler
                      → END

New intent:
    metric_kpi_advisor — Recommend metrics + KPIs with causal reasoning

This workflow is CSOD-specific and uses the general-purpose causal graph creator
from the causalgraph module.
"""
import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.csod.csod_nodes import (
    csod_intent_classifier_node,
    csod_planner_node,
    csod_mdl_schema_retrieval_node,
    csod_metrics_retrieval_node,
    csod_scoring_validator_node,
    csod_causal_graph_node,
    csod_metrics_recommender_node,
    csod_output_assembler_node,
)
from app.agents.causalgraph.csod_metric_advisor import csod_metric_advisor_node

logger = logging.getLogger(__name__)

# Intent constant
ADVISOR_INTENT = "metric_kpi_advisor"


# ============================================================================
# Routing functions
# ============================================================================

def _route_after_planner(state: EnhancedCompliancePipelineState) -> str:
    return "csod_mdl_schema_retrieval"


def _route_after_schema_retrieval(state: EnhancedCompliancePipelineState) -> str:
    return "csod_metrics_retrieval"


def _route_after_metrics_retrieval(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scoring_validator"


def _route_after_scoring(state: EnhancedCompliancePipelineState) -> str:
    """After scoring, route to causal graph if enabled, then to metrics recommender."""
    causal_enabled = state.get("csod_causal_graph_enabled", False)
    if causal_enabled:
        return "csod_causal_graph"
    return "csod_metrics_recommender"


def _route_after_causal_graph(state: EnhancedCompliancePipelineState) -> str:
    """After causal graph, route to metrics recommender."""
    return "csod_metrics_recommender"


def _route_after_metrics_recommender(state: EnhancedCompliancePipelineState) -> str:
    """After metrics recommender, route to metric advisor."""
    intent = state.get("csod_intent", "")
    if intent == ADVISOR_INTENT:
        return "csod_metric_advisor"
    return "csod_output_assembler"


def _route_after_metric_advisor(state: EnhancedCompliancePipelineState) -> str:
    """After metric advisor, route to output assembler."""
    return "csod_output_assembler"


def _route_after_assembler(state: EnhancedCompliancePipelineState) -> str:
    return "end"


# ============================================================================
# Workflow builder
# ============================================================================

def build_csod_metric_advisor_workflow() -> StateGraph:
    """
    Build the CSOD metric advisor workflow with causal graph integration.
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    # Add nodes
    workflow.add_node("csod_intent_classifier", csod_intent_classifier_node)
    workflow.add_node("csod_planner", csod_planner_node)
    workflow.add_node("csod_mdl_schema_retrieval", csod_mdl_schema_retrieval_node)
    workflow.add_node("csod_metrics_retrieval", csod_metrics_retrieval_node)
    workflow.add_node("csod_scoring_validator", csod_scoring_validator_node)
    workflow.add_node("csod_causal_graph", csod_causal_graph_node)
    workflow.add_node("csod_metrics_recommender", csod_metrics_recommender_node)
    workflow.add_node("csod_metric_advisor", csod_metric_advisor_node)
    workflow.add_node("csod_output_assembler", csod_output_assembler_node)
    
    # Set entry point
    workflow.set_entry_point("csod_intent_classifier")
    
    # Add edges
    # Fixed edge: intent_classifier → planner (sequential, not concurrent)
    workflow.add_edge("csod_intent_classifier", "csod_planner")
    
    # Conditional edge: planner → mdl_schema_retrieval
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
            "csod_causal_graph": "csod_causal_graph",
            "csod_metrics_recommender": "csod_metrics_recommender",
        },
    )
    workflow.add_conditional_edges(
        "csod_causal_graph",
        _route_after_causal_graph,
        {"csod_metrics_recommender": "csod_metrics_recommender"},
    )
    workflow.add_conditional_edges(
        "csod_metrics_recommender",
        _route_after_metrics_recommender,
        {
            "csod_metric_advisor": "csod_metric_advisor",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "csod_metric_advisor",
        _route_after_metric_advisor,
        {"csod_output_assembler": "csod_output_assembler"},
    )
    workflow.add_conditional_edges(
        "csod_output_assembler",
        _route_after_assembler,
        {"end": END},
    )
    
    return workflow


# ============================================================================
# App factory
# ============================================================================

def create_csod_metric_advisor_app(checkpointer=None):
    """
    Create and compile the CSOD metric advisor workflow.
    
    Args:
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).
    Returns:
        Compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_csod_metric_advisor_workflow().compile(checkpointer=checkpointer)


def get_csod_metric_advisor_app():
    """Convenience: return default CSOD metric advisor app."""
    return create_csod_metric_advisor_app()


# ============================================================================
# Initial state factory
# ============================================================================

def create_csod_metric_advisor_initial_state(
    user_query: str,
    session_id: str,
    active_project_id: str = None,
    selected_data_sources: list = None,
    compliance_profile: dict = None,
    causal_graph_enabled: bool = True,
    causal_vertical: str = "lms",
) -> Dict[str, Any]:
    """
    Build initial state for the CSOD metric advisor workflow.
    
    Args:
        user_query: Natural language query about metrics/KPIs
        session_id: Unique session identifier
        active_project_id: ProjectId for GoldStandardTable lookup
        selected_data_sources: Data source IDs
        compliance_profile: Full compliance profile dict
        causal_graph_enabled: Enable causal graph (default: True for advisor)
        causal_vertical: Vertical identifier (default: "lms")
    
    Returns:
        Initial state dict
    """
    from app.agents.csod.csod_workflow import create_csod_initial_state
    
    # Build base CSOD state
    base_state = create_csod_initial_state(
        user_query=user_query,
        session_id=session_id,
        active_project_id=active_project_id,
        selected_data_sources=selected_data_sources,
        compliance_profile=compliance_profile,
        causal_graph_enabled=causal_graph_enabled,
        causal_vertical=causal_vertical,
    )
    
    # Override intent to trigger advisor path
    base_state["csod_intent"] = ADVISOR_INTENT
    
    # Add advisor-specific fields
    base_state["csod_reasoning_plan"] = {}
    base_state["csod_advisor_output"] = None
    
    return base_state


if __name__ == "__main__":
    app = get_csod_metric_advisor_app()
    print("CSOD Metric Advisor workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")
