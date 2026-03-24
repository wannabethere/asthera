"""
Conditional edge routing for the main CSOD data analysis pipeline.

Pipeline stages (for UI flow display):
  Stage 1 — INTENT & PLANNING
  Stage 2 — RETRIEVAL (MDL, CCE, Metrics)
  Stage 3 — DECISIONS (Scoring, DT, Layout)
  Stage 4 — ANALYSIS (Recommender, Validator, Format)
  Stage 5 — OUTPUT (Execution Agents, Assembly, Narration)
"""
import logging
from typing import Optional

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.csod.executor_registry import should_short_circuit_after_mdl

logger = logging.getLogger(__name__)

# Intents that use the layout resolver before metrics recommender
LAYOUT_INTENTS = frozenset({
    "metrics_dashboard_plan",
    "metrics_recommender_with_gold_plan",
    "data_planner",
    "metric_kpi_advisor",
    "dashboard_generation_for_persona",
})


# ── Shared helper ─────────────────────────────────────────────────────────────

def _short_circuit(state: EnhancedCompliancePipelineState) -> Optional[str]:
    """Return 'csod_output_assembler' if followup short-circuit is active, else None."""
    if state.get("csod_followup_short_circuit"):
        return "csod_output_assembler"
    return None


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_followup_router(state: EnhancedCompliancePipelineState) -> str:
    return state.get("csod_followup_graph_route") or "csod_intent_classifier"


def route_after_schema_retrieval(state: EnhancedCompliancePipelineState) -> str:
    intent = state.get("csod_intent", "")
    if should_short_circuit_after_mdl(intent):
        if intent == "data_discovery":
            return "data_discovery_agent"
        if intent == "data_quality_analysis":
            return "data_quality_inspector"
    return "csod_metric_qualification"


def route_after_metric_qualification(state: EnhancedCompliancePipelineState) -> str:
    """After unified scoring + DT: route to layout, execution target, or recommender."""
    intent = state.get("csod_intent", "")

    # Direct execution targets that bypass recommender
    if intent == "data_lineage":
        return "data_lineage_tracer"
    if intent == "compliance_test_generator":
        return "csod_compliance_test_generator"
    if intent == "dashboard_generation_for_persona":
        return "csod_layout_resolver"

    # Intents that go through layout resolver first
    if intent in LAYOUT_INTENTS:
        return "csod_layout_resolver"

    # All other analysis intents → skill recommender → metrics recommender
    return "skill_recommender_prep"


def route_after_layout_resolver(state: EnhancedCompliancePipelineState) -> str:
    return "skill_recommender_prep"


def route_after_metrics_recommender(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    return "skill_validator"


def route_after_skill_validator(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    # User selects metrics → then picks output format
    return "csod_metric_selection"


def route_after_output_format_selector(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    if state.get("csod_intent") == "data_planner":
        return "data_pipeline_planner"
    return "csod_data_science_insights_enricher"


def route_after_insights_enricher(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
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
    sc = _short_circuit(state)
    if sc:
        return sc
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
    sc = _short_circuit(state)
    if sc:
        return sc
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
    sc = _short_circuit(state)
    if sc:
        return sc
    gold_sql = state.get("csod_generated_gold_model_sql", [])
    if gold_sql and len(gold_sql) > 0:
        return "cubejs_schema_generation"
    return "csod_scheduler"


def route_after_cubejs(state: EnhancedCompliancePipelineState) -> str:
    return "csod_scheduler"


def route_after_dashboard_generator(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    return "csod_data_science_insights_enricher"


def route_after_compliance_test_generator(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    return "csod_scheduler"


def route_after_scheduler(state: EnhancedCompliancePipelineState) -> str:
    return "csod_output_assembler"


def route_after_data_lineage_tracer(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    return "csod_scheduler"


def route_after_data_pipeline_planner(state: EnhancedCompliancePipelineState) -> str:
    sc = _short_circuit(state)
    if sc:
        return sc
    return "csod_scheduler"
