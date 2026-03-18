"""Conditional edge routing for the main CSOD recommender workflow."""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.csod.executor_registry import should_short_circuit_after_mdl

logger = logging.getLogger(__name__)


def route_after_planner(state: EnhancedCompliancePipelineState) -> str:
    return "csod_mdl_schema_retrieval"


def route_after_schema_retrieval(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    if should_short_circuit_after_mdl(intent):
        if intent == "data_discovery":
            return "data_discovery_agent"
        if intent == "data_quality_analysis":
            return "data_quality_inspector"
    return "csod_metrics_retrieval"


def route_after_metrics_retrieval(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scoring_validator"


def route_after_scoring(state: EnhancedCompliancePipelineState) -> str:
    return "decision_tree_resolver"


def route_after_dt_resolver(state: EnhancedCompliancePipelineState) -> str:
    causal_enabled = state.get("csod_causal_graph_enabled", False)
    if causal_enabled:
        return "csod_causal_graph"
    return route_after_causal_graph(state)


def route_after_causal_graph(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    if intent == "data_lineage":
        return "data_lineage_tracer"
    if intent in ("metrics_dashboard_plan", "metrics_recommender_with_gold_plan", "data_planner"):
        return "csod_metrics_recommender"
    if intent == "dashboard_generation_for_persona":
        return "csod_dashboard_generator"
    if intent == "compliance_test_generator":
        return "csod_compliance_test_generator"
    logger.warning("Unknown intent '%s', defaulting to metrics_recommender", intent)
    return "csod_metrics_recommender"


def route_after_metrics_recommender(state: EnhancedCompliancePipelineState) -> str:
    if state.get("csod_intent") == "data_planner":
        return "data_pipeline_planner"
    return "csod_data_science_insights_enricher"


def route_after_insights_enricher(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    metric_recommendations = state.get("csod_metric_recommendations", [])
    data_science_insights = state.get("csod_data_science_insights", [])
    if metric_recommendations or data_science_insights:
        return "calculation_planner"
    needs_gold_plan = (
        intent == "metrics_recommender_with_gold_plan"
        or (metric_recommendations and len(metric_recommendations) > 0)
    )
    if needs_gold_plan:
        return "csod_medallion_planner"
    return "csod_scheduler"


def route_after_calculation_planner(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    metric_recommendations = state.get("csod_metric_recommendations", [])
    needs_gold_plan = (
        intent == "metrics_recommender_with_gold_plan"
        or (metric_recommendations and len(metric_recommendations) > 0)
    )
    if needs_gold_plan:
        return "csod_medallion_planner"
    return "csod_scheduler"


def route_after_medallion_planner(state: EnhancedCompliancePipelineState) -> str:
    plan = state.get("csod_medallion_plan", {})
    needs_sql = (
        state.get("csod_generate_sql", False)
        and plan.get("requires_gold_model", False)
        and (plan.get("specifications") or [])
    )
    if needs_sql:
        return "csod_gold_model_sql_generator"
    return "csod_scheduler"


def route_after_gold_model_sql_generator(state: EnhancedCompliancePipelineState) -> str:
    gold_sql = state.get("csod_generated_gold_model_sql", [])
    if gold_sql and len(gold_sql) > 0:
        return "cubejs_schema_generation"
    return "csod_scheduler"


def route_after_cubejs(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scheduler"


def route_after_dashboard_generator(state: EnhancedCompliancePipelineState) -> str:
    return "csod_data_science_insights_enricher"


def route_after_compliance_test_generator(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scheduler"


def route_after_scheduler(state: EnhancedCompliancePipelineState) -> str:
    return "csod_output_assembler"


def route_after_data_lineage_tracer(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scheduler"


def route_after_data_pipeline_planner(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scheduler"


def route_after_assembler(state: EnhancedCompliancePipelineState) -> str:
    return "end"
