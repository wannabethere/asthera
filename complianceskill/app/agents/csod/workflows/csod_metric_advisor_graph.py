"""CSOD metric advisor LangGraph (causal + dedicated advisor node)."""
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph

from app.core.checkpointer_provider import get_checkpointer

from app.agents.causalgraph.csod_metric_advisor import csod_metric_advisor_node
from app.agents.csod.csod_nodes import (
    csod_causal_graph_node,
    csod_data_discovery_node,
    csod_data_lineage_tracer_node,
    csod_data_pipeline_planner_node,
    csod_data_quality_inspector_node,
    csod_decision_tree_resolver_node,
    csod_mdl_schema_retrieval_node,
    csod_metrics_recommender_node,
    csod_metrics_retrieval_node,
    csod_output_assembler_node,
    csod_planner_node,
    csod_scoring_validator_node,
    csod_spine_precheck_node,
)
from app.agents.csod.workflows.csod_initial_state import create_csod_initial_state
from app.agents.csod.workflows.csod_metric_advisor_routing import (
    ADVISOR_INTENT,
    route_after_assembler,
    route_after_causal_graph,
    route_after_dt_resolver,
    route_after_metric_advisor,
    route_after_metrics_recommender,
    route_after_metrics_retrieval,
    route_after_planner,
    route_after_schema_retrieval,
    route_after_scoring,
    route_after_spine_precheck,
)
from app.agents.state import EnhancedCompliancePipelineState


def build_csod_metric_advisor_workflow() -> StateGraph:
    workflow = StateGraph(EnhancedCompliancePipelineState)
    workflow.add_node("csod_planner", csod_planner_node)
    workflow.add_node("csod_spine_precheck", csod_spine_precheck_node)
    workflow.add_node("csod_mdl_schema_retrieval", csod_mdl_schema_retrieval_node)
    workflow.add_node("csod_metrics_retrieval", csod_metrics_retrieval_node)
    workflow.add_node("csod_scoring_validator", csod_scoring_validator_node)
    workflow.add_node("decision_tree_resolver", csod_decision_tree_resolver_node)
    workflow.add_node("csod_causal_graph", csod_causal_graph_node)
    workflow.add_node("csod_metrics_recommender", csod_metrics_recommender_node)
    workflow.add_node("csod_metric_advisor", csod_metric_advisor_node)
    workflow.add_node("csod_output_assembler", csod_output_assembler_node)
    workflow.add_node("data_discovery_agent", csod_data_discovery_node)
    workflow.add_node("data_quality_inspector", csod_data_quality_inspector_node)
    workflow.add_node("data_lineage_tracer", csod_data_lineage_tracer_node)
    workflow.add_node("data_pipeline_planner", csod_data_pipeline_planner_node)

    # Intent is preset to ADVISOR_INTENT in create_csod_metric_advisor_initial_state — skip classifier
    workflow.set_entry_point("csod_planner")
    workflow.add_conditional_edges("csod_planner", route_after_planner, {"csod_spine_precheck": "csod_spine_precheck"})
    workflow.add_conditional_edges(
        "csod_spine_precheck",
        route_after_spine_precheck,
        {"csod_mdl_schema_retrieval": "csod_mdl_schema_retrieval"},
    )
    workflow.add_conditional_edges(
        "csod_mdl_schema_retrieval",
        route_after_schema_retrieval,
        {
            "csod_metrics_retrieval": "csod_metrics_retrieval",
            "data_discovery_agent": "data_discovery_agent",
            "data_quality_inspector": "data_quality_inspector",
        },
    )
    workflow.add_edge("data_discovery_agent", "csod_output_assembler")
    workflow.add_edge("data_quality_inspector", "csod_output_assembler")
    workflow.add_conditional_edges(
        "csod_metrics_retrieval",
        route_after_metrics_retrieval,
        {"csod_scoring_validator": "csod_scoring_validator"},
    )
    workflow.add_conditional_edges(
        "csod_scoring_validator",
        route_after_scoring,
        {"decision_tree_resolver": "decision_tree_resolver"},
    )
    workflow.add_conditional_edges(
        "decision_tree_resolver",
        route_after_dt_resolver,
        {
            "csod_causal_graph": "csod_causal_graph",
            "csod_metrics_recommender": "csod_metrics_recommender",
            "data_lineage_tracer": "data_lineage_tracer",
        },
    )
    workflow.add_conditional_edges(
        "csod_causal_graph",
        route_after_causal_graph,
        {"csod_metrics_recommender": "csod_metrics_recommender", "data_lineage_tracer": "data_lineage_tracer"},
    )
    workflow.add_edge("data_lineage_tracer", "csod_output_assembler")
    workflow.add_conditional_edges(
        "csod_metrics_recommender",
        route_after_metrics_recommender,
        {
            "csod_metric_advisor": "csod_metric_advisor",
            "csod_output_assembler": "csod_output_assembler",
            "data_pipeline_planner": "data_pipeline_planner",
        },
    )
    workflow.add_edge("data_pipeline_planner", "csod_output_assembler")
    workflow.add_conditional_edges(
        "csod_metric_advisor",
        route_after_metric_advisor,
        {"csod_output_assembler": "csod_output_assembler"},
    )
    workflow.add_conditional_edges("csod_output_assembler", route_after_assembler, {"end": END})
    return workflow


def create_csod_metric_advisor_app(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()
    return build_csod_metric_advisor_workflow().compile(checkpointer=checkpointer)


def get_csod_metric_advisor_app():
    return create_csod_metric_advisor_app()


def create_csod_metric_advisor_initial_state(
    user_query: str,
    session_id: str,
    active_project_id: Optional[str] = None,
    selected_data_sources: Optional[List[Any]] = None,
    compliance_profile: Optional[Dict[str, Any]] = None,
    causal_graph_enabled: bool = True,
    causal_vertical: str = "lms",
) -> Dict[str, Any]:
    base_state = create_csod_initial_state(
        user_query=user_query,
        session_id=session_id,
        active_project_id=active_project_id,
        selected_data_sources=selected_data_sources,
        compliance_profile=compliance_profile,
        causal_graph_enabled=causal_graph_enabled,
        causal_vertical=causal_vertical,
    )
    base_state["csod_intent"] = ADVISOR_INTENT
    base_state["csod_reasoning_plan"] = {}
    base_state["csod_advisor_output"] = None
    return base_state
