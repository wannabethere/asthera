"""Main CSOD LangGraph: metrics recommender, dashboard, compliance, data intelligence paths."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.csod.csod_nodes import (
    csod_compliance_test_generator_node,
    csod_causal_graph_node,
    csod_dashboard_generator_node,
    csod_data_discovery_node,
    csod_data_lineage_tracer_node,
    csod_data_pipeline_planner_node,
    csod_data_quality_inspector_node,
    csod_data_science_insights_enricher_node,
    csod_decision_tree_resolver_node,
    csod_gold_model_sql_generator_node,
    csod_intent_classifier_node,
    csod_mdl_schema_retrieval_node,
    csod_medallion_planner_node,
    csod_metrics_recommender_node,
    csod_metrics_retrieval_node,
    csod_output_assembler_node,
    csod_planner_node,
    csod_scheduler_node,
    csod_scoring_validator_node,
)
from app.agents.csod.workflows import csod_main_routing as R
from app.agents.shared import calculation_planner_node, cubejs_schema_generation_node
from app.agents.state import EnhancedCompliancePipelineState
from app.core.telemetry import instrument_langgraph_node


def build_csod_workflow() -> StateGraph:
    workflow = StateGraph(EnhancedCompliancePipelineState)
    ins = lambda fn, name: instrument_langgraph_node(fn, name, "csod")

    workflow.add_node("csod_intent_classifier", ins(csod_intent_classifier_node, "csod_intent_classifier"))
    workflow.add_node("csod_planner", ins(csod_planner_node, "csod_planner"))
    workflow.add_node("csod_mdl_schema_retrieval", ins(csod_mdl_schema_retrieval_node, "csod_mdl_schema_retrieval"))
    workflow.add_node("csod_metrics_retrieval", ins(csod_metrics_retrieval_node, "csod_metrics_retrieval"))
    workflow.add_node("csod_scoring_validator", ins(csod_scoring_validator_node, "csod_scoring_validator"))
    workflow.add_node("decision_tree_resolver", ins(csod_decision_tree_resolver_node, "decision_tree_resolver"))
    workflow.add_node("csod_causal_graph", ins(csod_causal_graph_node, "csod_causal_graph"))
    workflow.add_node("csod_metrics_recommender", ins(csod_metrics_recommender_node, "csod_metrics_recommender"))
    workflow.add_node("calculation_planner", ins(calculation_planner_node, "calculation_planner"))
    workflow.add_node("csod_medallion_planner", ins(csod_medallion_planner_node, "csod_medallion_planner"))
    workflow.add_node("csod_gold_model_sql_generator", ins(csod_gold_model_sql_generator_node, "csod_gold_model_sql_generator"))
    workflow.add_node("csod_data_science_insights_enricher", ins(csod_data_science_insights_enricher_node, "csod_data_science_insights_enricher"))
    workflow.add_node("csod_dashboard_generator", ins(csod_dashboard_generator_node, "csod_dashboard_generator"))
    workflow.add_node("csod_compliance_test_generator", ins(csod_compliance_test_generator_node, "csod_compliance_test_generator"))
    workflow.add_node("csod_scheduler", ins(csod_scheduler_node, "csod_scheduler"))
    workflow.add_node("csod_output_assembler", ins(csod_output_assembler_node, "csod_output_assembler"))
    workflow.add_node("cubejs_schema_generation", ins(cubejs_schema_generation_node, "cubejs_schema_generation"))
    workflow.add_node("data_discovery_agent", ins(csod_data_discovery_node, "data_discovery_agent"))
    workflow.add_node("data_quality_inspector", ins(csod_data_quality_inspector_node, "data_quality_inspector"))
    workflow.add_node("data_lineage_tracer", ins(csod_data_lineage_tracer_node, "data_lineage_tracer"))
    workflow.add_node("data_pipeline_planner", ins(csod_data_pipeline_planner_node, "data_pipeline_planner"))

    workflow.set_entry_point("csod_intent_classifier")
    workflow.add_edge("csod_intent_classifier", "csod_planner")

    workflow.add_conditional_edges("csod_planner", R.route_after_planner, {"csod_mdl_schema_retrieval": "csod_mdl_schema_retrieval"})
    workflow.add_conditional_edges(
        "csod_mdl_schema_retrieval",
        R.route_after_schema_retrieval,
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
        R.route_after_metrics_retrieval,
        {"csod_scoring_validator": "csod_scoring_validator"},
    )
    workflow.add_conditional_edges(
        "csod_scoring_validator",
        R.route_after_scoring,
        {"decision_tree_resolver": "decision_tree_resolver"},
    )
    workflow.add_conditional_edges(
        "decision_tree_resolver",
        R.route_after_dt_resolver,
        {
            "csod_causal_graph": "csod_causal_graph",
            "csod_metrics_recommender": "csod_metrics_recommender",
            "csod_dashboard_generator": "csod_dashboard_generator",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
            "data_lineage_tracer": "data_lineage_tracer",
        },
    )
    workflow.add_conditional_edges(
        "csod_causal_graph",
        R.route_after_causal_graph,
        {
            "csod_metrics_recommender": "csod_metrics_recommender",
            "csod_dashboard_generator": "csod_dashboard_generator",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
            "data_lineage_tracer": "data_lineage_tracer",
        },
    )
    workflow.add_conditional_edges(
        "data_lineage_tracer",
        R.route_after_data_lineage_tracer,
        {"csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "csod_metrics_recommender",
        R.route_after_metrics_recommender,
        {
            "csod_data_science_insights_enricher": "csod_data_science_insights_enricher",
            "data_pipeline_planner": "data_pipeline_planner",
        },
    )
    workflow.add_conditional_edges(
        "data_pipeline_planner",
        R.route_after_data_pipeline_planner,
        {"csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "csod_data_science_insights_enricher",
        R.route_after_insights_enricher,
        {
            "calculation_planner": "calculation_planner",
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_scheduler": "csod_scheduler",
        },
    )
    workflow.add_conditional_edges(
        "calculation_planner",
        R.route_after_calculation_planner,
        {"csod_medallion_planner": "csod_medallion_planner", "csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "csod_medallion_planner",
        R.route_after_medallion_planner,
        {"csod_gold_model_sql_generator": "csod_gold_model_sql_generator", "csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "csod_gold_model_sql_generator",
        R.route_after_gold_model_sql_generator,
        {"cubejs_schema_generation": "cubejs_schema_generation", "csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "cubejs_schema_generation",
        R.route_after_cubejs,
        {"csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "csod_dashboard_generator",
        R.route_after_dashboard_generator,
        {"csod_data_science_insights_enricher": "csod_data_science_insights_enricher"},
    )
    workflow.add_conditional_edges(
        "csod_compliance_test_generator",
        R.route_after_compliance_test_generator,
        {"csod_scheduler": "csod_scheduler"},
    )
    workflow.add_conditional_edges(
        "csod_scheduler",
        R.route_after_scheduler,
        {"csod_output_assembler": "csod_output_assembler"},
    )
    workflow.add_conditional_edges("csod_output_assembler", R.route_after_assembler, {"end": END})
    return workflow


def create_csod_app(checkpointer=None):
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_csod_workflow().compile(checkpointer=checkpointer)


def get_csod_app():
    return create_csod_app()
