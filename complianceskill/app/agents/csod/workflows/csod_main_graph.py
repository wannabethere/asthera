"""
Main CSOD Data Analysis Pipeline — bucketed into logical stages.

Pipeline Stages:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  STAGE 1: INTENT & PLANNING                                        │
  │  Classify user query → refine with skill → produce execution plan  │
  │  Nodes: followup_router, intent_classifier, skill_intent,          │
  │         skill_planner, csod_planner                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 2: RETRIEVAL (MDL, CCE, Example Metrics)                    │
  │  Fetch causal graph, schemas, metrics from vector stores           │
  │  Nodes: causal_graph, cross_concept_check, metrics_retrieval,      │
  │         mdl_schema_retrieval                                       │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 3: DECISIONS (Scoring, DT Qualification, Layout)            │
  │  Score, qualify, group, and layout-order the retrieved metrics      │
  │  Nodes: metric_qualification, layout_resolver                      │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 4: ANALYSIS (Skill Recommender, Metrics, Validator)         │
  │  Skill-augmented metric recommendation + post-validation            │
  │  Nodes: skill_recommender_prep, metrics_recommender,               │
  │         skill_validator, output_format_selector                    │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 5: OUTPUT (Execution Agents + Assembly)                     │
  │  Generate insights, plans, SQL, dashboards, tests, schedules       │
  │  Nodes: insights_enricher, calculation_planner, medallion_planner, │
  │         gold_sql, cubejs, dashboard_generator, test_generator,     │
  │         data_pipeline_planner, scheduler, lineage_tracer,          │
  │         data_discovery, data_quality                               │
  │  Then: output_assembler → completion_narration → END               │
  └─────────────────────────────────────────────────────────────────────┘
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.csod.csod_nodes import (
    csod_compliance_test_generator_node,
    csod_causal_graph_node,
    csod_cross_concept_check_node,
    csod_dashboard_generator_node,
    csod_data_discovery_node,
    csod_data_lineage_tracer_node,
    csod_data_pipeline_planner_node,
    csod_data_quality_inspector_node,
    csod_data_science_insights_enricher_node,
    csod_gold_model_sql_generator_node,
    csod_intent_classifier_node,
    csod_mdl_schema_retrieval_node,
    csod_medallion_planner_node,
    csod_metric_qualification_node,
    csod_metrics_recommender_node,
    csod_metrics_retrieval_node,
    csod_output_assembler_node,
    csod_output_format_selector_node,
    csod_completion_narration_node,
    csod_planner_node,
    csod_scheduler_node,
    csod_layout_resolver_node,
)
from app.agents.csod.csod_nodes.node_followup import csod_followup_router_node
from app.agents.csod.csod_nodes.node_goal_intent import csod_goal_intent_node
from app.agents.csod.csod_nodes.node_metric_selection import csod_metric_selection_node
from app.agents.skills.nodes import (
    skill_intent_identifier_node,
    skill_analysis_planner_node,
    skill_recommender_node,
    skill_validator_node,
)
from app.agents.csod.workflows import csod_main_routing as R
from app.agents.shared import calculation_planner_node, cubejs_schema_generation_node
from app.agents.state import EnhancedCompliancePipelineState
from app.core.telemetry import instrument_langgraph_node


def build_csod_workflow() -> StateGraph:
    workflow = StateGraph(EnhancedCompliancePipelineState)
    ins = lambda fn, name: instrument_langgraph_node(fn, name, "csod")

    # =====================================================================
    # STAGE 1: INTENT & PLANNING
    # Classify → skill-refine → plan execution steps
    # =====================================================================
    workflow.add_node("csod_followup_router",   ins(csod_followup_router_node, "csod_followup_router"))
    workflow.add_node("csod_intent_classifier", ins(csod_intent_classifier_node, "csod_intent_classifier"))
    workflow.add_node("skill_intent_identifier", ins(skill_intent_identifier_node, "skill_intent_identifier"))
    workflow.add_node("skill_analysis_planner", ins(skill_analysis_planner_node, "skill_analysis_planner"))
    workflow.add_node("csod_planner",           ins(csod_planner_node, "csod_planner"))

    # =====================================================================
    # STAGE 2: RETRIEVAL (MDL, CCE, Example Metrics)
    # Fetch causal graph topology, metric registry hits, MDL schemas
    # =====================================================================
    workflow.add_node("csod_causal_graph",        ins(csod_causal_graph_node, "csod_causal_graph"))
    workflow.add_node("csod_cross_concept_check", ins(csod_cross_concept_check_node, "csod_cross_concept_check"))
    workflow.add_node("csod_metrics_retrieval",   ins(csod_metrics_retrieval_node, "csod_metrics_retrieval"))
    workflow.add_node("csod_mdl_schema_retrieval", ins(csod_mdl_schema_retrieval_node, "csod_mdl_schema_retrieval"))

    # =====================================================================
    # STAGE 3: DECISIONS (Scoring, DT Qualification, Layout)
    # Score + qualify + group + layout-order retrieved metrics
    # =====================================================================
    workflow.add_node("csod_metric_qualification", ins(csod_metric_qualification_node, "csod_metric_qualification"))
    workflow.add_node("csod_layout_resolver",      ins(csod_layout_resolver_node, "csod_layout_resolver"))

    # =====================================================================
    # STAGE 4: ANALYSIS (Skill Recommender → Metrics → Validator)
    # Skill-augmented recommendation + post-validation + format selection
    # =====================================================================
    workflow.add_node("skill_recommender_prep",    ins(skill_recommender_node, "skill_recommender_prep"))
    workflow.add_node("csod_metrics_recommender",  ins(csod_metrics_recommender_node, "csod_metrics_recommender"))
    workflow.add_node("skill_validator",           ins(skill_validator_node, "skill_validator"))
    workflow.add_node("csod_metric_selection",       ins(csod_metric_selection_node, "csod_metric_selection"))
    workflow.add_node("csod_goal_intent",           ins(csod_goal_intent_node, "csod_goal_intent"))
    workflow.add_node("csod_output_format_selector", ins(csod_output_format_selector_node, "csod_output_format_selector"))

    # =====================================================================
    # STAGE 5: OUTPUT — Execution Agents
    # Generate insights, plans, SQL, dashboards, tests, schedules
    # =====================================================================
    workflow.add_node("csod_data_science_insights_enricher", ins(csod_data_science_insights_enricher_node, "csod_data_science_insights_enricher"))
    workflow.add_node("calculation_planner",       ins(calculation_planner_node, "calculation_planner"))
    workflow.add_node("csod_medallion_planner",    ins(csod_medallion_planner_node, "csod_medallion_planner"))
    workflow.add_node("csod_gold_model_sql_generator", ins(csod_gold_model_sql_generator_node, "csod_gold_model_sql_generator"))
    workflow.add_node("cubejs_schema_generation",  ins(cubejs_schema_generation_node, "cubejs_schema_generation"))
    workflow.add_node("csod_dashboard_generator",  ins(csod_dashboard_generator_node, "csod_dashboard_generator"))
    workflow.add_node("csod_compliance_test_generator", ins(csod_compliance_test_generator_node, "csod_compliance_test_generator"))
    workflow.add_node("data_pipeline_planner",     ins(csod_data_pipeline_planner_node, "data_pipeline_planner"))
    workflow.add_node("csod_scheduler",            ins(csod_scheduler_node, "csod_scheduler"))
    workflow.add_node("data_lineage_tracer",       ins(csod_data_lineage_tracer_node, "data_lineage_tracer"))
    workflow.add_node("data_discovery_agent",      ins(csod_data_discovery_node, "data_discovery_agent"))
    workflow.add_node("data_quality_inspector",    ins(csod_data_quality_inspector_node, "data_quality_inspector"))

    # ── STAGE 5: OUTPUT — Assembly & Narration ────────────────────────────
    workflow.add_node("csod_output_assembler",     ins(csod_output_assembler_node, "csod_output_assembler"))
    workflow.add_node("csod_completion_narration", ins(csod_completion_narration_node, "csod_completion_narration"))

    # =====================================================================
    # EDGES — Stage 1: Intent & Planning
    # =====================================================================
    workflow.set_entry_point("csod_followup_router")

    workflow.add_conditional_edges(
        "csod_followup_router",
        R.route_after_followup_router,
        {
            "csod_intent_classifier": "csod_intent_classifier",
            # Followup short-circuits (skip to later stages)
            "csod_metrics_retrieval": "csod_metrics_retrieval",
            "csod_metrics_recommender": "csod_metrics_recommender",
            "csod_dashboard_generator": "csod_dashboard_generator",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
            "data_discovery_agent": "data_discovery_agent",
            "data_quality_inspector": "data_quality_inspector",
            "data_lineage_tracer": "data_lineage_tracer",
        },
    )

    # Intent → skill refinement → skill data plan → execution planner
    workflow.add_edge("csod_intent_classifier", "skill_intent_identifier")
    workflow.add_edge("skill_intent_identifier", "skill_analysis_planner")
    workflow.add_edge("skill_analysis_planner", "csod_planner")

    # =====================================================================
    # EDGES — Stage 2: Retrieval
    # =====================================================================
    # Planner → CCE → cross-concept enrichment → metrics → MDL schemas
    workflow.add_edge("csod_planner", "csod_causal_graph")
    workflow.add_edge("csod_causal_graph", "csod_cross_concept_check")
    workflow.add_edge("csod_cross_concept_check", "csod_metrics_retrieval")
    workflow.add_edge("csod_metrics_retrieval", "csod_mdl_schema_retrieval")

    # Data intelligence intents short-circuit after retrieval
    workflow.add_conditional_edges(
        "csod_mdl_schema_retrieval",
        R.route_after_schema_retrieval,
        {
            "csod_metric_qualification": "csod_metric_qualification",
            "data_discovery_agent": "data_discovery_agent",
            "data_quality_inspector": "data_quality_inspector",
        },
    )
    workflow.add_edge("data_discovery_agent", "csod_output_assembler")
    workflow.add_edge("data_quality_inspector", "csod_output_assembler")

    # =====================================================================
    # EDGES — Stage 3: Decisions
    # =====================================================================
    # Metric qualification → layout resolver or direct execution
    workflow.add_conditional_edges(
        "csod_metric_qualification",
        R.route_after_metric_qualification,
        {
            "csod_layout_resolver": "csod_layout_resolver",
            "skill_recommender_prep": "skill_recommender_prep",
            "csod_dashboard_generator": "csod_dashboard_generator",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
            "data_lineage_tracer": "data_lineage_tracer",
        },
    )
    workflow.add_conditional_edges(
        "csod_layout_resolver",
        R.route_after_layout_resolver,
        {"skill_recommender_prep": "skill_recommender_prep"},
    )

    # =====================================================================
    # EDGES — Stage 4: Analysis
    # =====================================================================
    # Skill recommender → metrics recommender → skill validator → format selector
    workflow.add_edge("skill_recommender_prep", "csod_metrics_recommender")
    workflow.add_conditional_edges(
        "csod_metrics_recommender",
        R.route_after_metrics_recommender,
        {
            "skill_validator": "skill_validator",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "skill_validator",
        R.route_after_skill_validator,
        {
            "csod_metric_selection": "csod_metric_selection",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    # User selects metrics → picks output format → format selector
    workflow.add_edge("csod_metric_selection", "csod_goal_intent")
    workflow.add_edge("csod_goal_intent", "csod_output_format_selector")

    # =====================================================================
    # EDGES — Stage 5: Output Execution Agents
    # =====================================================================
    # Format selector → execution chain
    workflow.add_conditional_edges(
        "csod_output_format_selector",
        R.route_after_output_format_selector,
        {
            "csod_data_science_insights_enricher": "csod_data_science_insights_enricher",
            "data_pipeline_planner": "data_pipeline_planner",
            "csod_output_assembler": "csod_output_assembler",
        },
    )

    # Insights → calculation → medallion → gold SQL → CubeJS → scheduler
    workflow.add_conditional_edges(
        "csod_data_science_insights_enricher",
        R.route_after_insights_enricher,
        {
            "calculation_planner": "calculation_planner",
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_scheduler": "csod_scheduler",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "calculation_planner",
        R.route_after_calculation_planner,
        {
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_scheduler": "csod_scheduler",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "csod_medallion_planner",
        R.route_after_medallion_planner,
        {
            "csod_gold_model_sql_generator": "csod_gold_model_sql_generator",
            "csod_scheduler": "csod_scheduler",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "csod_gold_model_sql_generator",
        R.route_after_gold_model_sql_generator,
        {
            "cubejs_schema_generation": "cubejs_schema_generation",
            "csod_scheduler": "csod_scheduler",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "cubejs_schema_generation",
        R.route_after_cubejs,
        {"csod_scheduler": "csod_scheduler"},
    )

    # Direct execution agents (dashboard, tests, lineage, pipeline)
    workflow.add_conditional_edges(
        "csod_dashboard_generator",
        R.route_after_dashboard_generator,
        {
            "csod_data_science_insights_enricher": "csod_data_science_insights_enricher",
            "csod_output_assembler": "csod_output_assembler",
        },
    )
    workflow.add_conditional_edges(
        "csod_compliance_test_generator",
        R.route_after_compliance_test_generator,
        {"csod_scheduler": "csod_scheduler", "csod_output_assembler": "csod_output_assembler"},
    )
    workflow.add_conditional_edges(
        "data_lineage_tracer",
        R.route_after_data_lineage_tracer,
        {"csod_scheduler": "csod_scheduler", "csod_output_assembler": "csod_output_assembler"},
    )
    workflow.add_conditional_edges(
        "data_pipeline_planner",
        R.route_after_data_pipeline_planner,
        {"csod_scheduler": "csod_scheduler", "csod_output_assembler": "csod_output_assembler"},
    )
    workflow.add_conditional_edges(
        "csod_scheduler",
        R.route_after_scheduler,
        {"csod_output_assembler": "csod_output_assembler"},
    )

    # ── STAGE 5: Assembly & Narration → END ───────────────────────────────
    workflow.add_edge("csod_output_assembler", "csod_completion_narration")
    workflow.add_edge("csod_completion_narration", END)

    return workflow


def create_csod_app(checkpointer=None):
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_csod_workflow().compile(checkpointer=checkpointer)


def get_csod_app():
    return create_csod_app()
