"""Routing for CSOD metric advisor workflow (narrower graph)."""
from app.agents.state import EnhancedCompliancePipelineState
from app.agents.csod.executor_registry import should_short_circuit_after_mdl

ADVISOR_INTENT = "metric_kpi_advisor"


def route_after_planner(state: EnhancedCompliancePipelineState) -> str:
    return "csod_spine_precheck"


def route_after_spine_precheck(state: EnhancedCompliancePipelineState) -> str:
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
    intent = state.get("csod_intent", "")
    if causal_enabled:
        return "csod_causal_graph"
    if intent == "data_lineage":
        return "data_lineage_tracer"
    return "csod_metrics_recommender"


def route_after_causal_graph(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    if intent == "data_lineage":
        return "data_lineage_tracer"
    return "csod_metrics_recommender"


def route_after_metrics_recommender(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    if intent == "data_planner":
        return "data_pipeline_planner"
    if intent == ADVISOR_INTENT:
        return "csod_metric_advisor"
    return "csod_output_assembler"


def route_after_metric_advisor(state: EnhancedCompliancePipelineState) -> str:
    return "csod_output_assembler"


def route_after_assembler(state: EnhancedCompliancePipelineState) -> str:
    return "end"
