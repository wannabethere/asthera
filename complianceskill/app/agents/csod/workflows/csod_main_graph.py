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
from langgraph.graph import END, StateGraph

from app.core.checkpointer_provider import get_checkpointer

from app.agents.csod.csod_nodes import (
    csod_analysis_planner_node,
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
    # STAGE 5: OUTPUT — Execution Agents (streamlined)
    # Generate gold DBT models, CubeJS schemas, schedule
    # =====================================================================
    workflow.add_node("csod_medallion_planner",         ins(csod_medallion_planner_node, "csod_medallion_planner"))
    workflow.add_node("csod_gold_model_sql_generator",  ins(csod_gold_model_sql_generator_node, "csod_gold_model_sql_generator"))
    workflow.add_node("cubejs_schema_generation",       ins(cubejs_schema_generation_node, "cubejs_schema_generation"))
    workflow.add_node("csod_scheduler",                 ins(csod_scheduler_node, "csod_scheduler"))

    # ── Data intelligence nodes (route early after MDL schema retrieval) ─
    workflow.add_node("data_discovery_agent",           ins(csod_data_discovery_node, "data_discovery_agent"))
    workflow.add_node("data_quality_inspector",         ins(csod_data_quality_inspector_node, "data_quality_inspector"))
    workflow.add_node("data_lineage_tracer",            ins(csod_data_lineage_tracer_node, "data_lineage_tracer"))
    workflow.add_node("csod_compliance_test_generator", ins(csod_compliance_test_generator_node, "csod_compliance_test_generator"))

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
            # Dashboard/test/lineage followups route to their nodes
            "csod_compliance_test_generator": "csod_compliance_test_generator",
            "data_discovery_agent": "data_discovery_agent",
            "data_quality_inspector": "data_quality_inspector",
            "data_lineage_tracer": "data_lineage_tracer",
            # Dashboard followup → route to recommender (dashboard_generator removed)
            "csod_dashboard_generator": "csod_metrics_recommender",
            # Re-entry points for backward navigation
            "csod_metric_selection": "csod_metric_selection",
            "csod_planner": "csod_planner",
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
            "data_lineage_tracer": "data_lineage_tracer",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
        },
    )
    workflow.add_edge("data_discovery_agent", "csod_output_assembler")
    workflow.add_edge("data_quality_inspector", "csod_output_assembler")
    workflow.add_edge("data_lineage_tracer", "csod_output_assembler")
    workflow.add_edge("csod_compliance_test_generator", "csod_output_assembler")

    # =====================================================================
    # EDGES — Stage 3: Decisions
    # =====================================================================
    # Metric qualification → layout resolver or recommender
    workflow.add_conditional_edges(
        "csod_metric_qualification",
        R.route_after_metric_qualification,
        {
            "csod_layout_resolver": "csod_layout_resolver",
            "skill_recommender_prep": "skill_recommender_prep",
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
    # EDGES — Stage 5: Output (streamlined)
    # =====================================================================
    # Format selector → medallion planner or assembler
    workflow.add_conditional_edges(
        "csod_output_format_selector",
        R.route_after_output_format_selector_v2,
        {
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_output_assembler": "csod_output_assembler",
        },
    )

    # Medallion → gold SQL → CubeJS → scheduler → assembler
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
        checkpointer = get_checkpointer()
    return build_csod_workflow().compile(checkpointer=checkpointer)


def create_csod_interactive_app(checkpointer=None):
    """
    Create CSOD Phase 1 workflow with interactive checkpoint support.

    Compiles Phase 1 (planner-only) graph with interrupt_after on
    csod_cross_concept_check and csod_metric_selection so LangGraph
    pauses for human-in-the-loop selections.  Phase 1 ends at
    metric_selection → END; previews are generated separately.
    """
    if checkpointer is None:
        checkpointer = get_checkpointer()
    return build_csod_phase1_workflow().compile(
        checkpointer=checkpointer,
        interrupt_after=[
            "csod_cross_concept_check",   # asks user about cross-concept areas (if found)
            "csod_metric_selection",       # asks user to confirm/select recommended metrics
        ],
    )


def get_csod_app():
    """Get the Phase 1 (planner-only) CSOD app."""
    return create_csod_phase1_app()


_csod_interactive_app_cache = None

def get_csod_interactive_app():
    """Get the Phase 1 CSOD app with interactive checkpoints (cached singleton)."""
    global _csod_interactive_app_cache
    if _csod_interactive_app_cache is None:
        _csod_interactive_app_cache = build_csod_phase1_workflow().compile(
            checkpointer=get_checkpointer(),
            interrupt_after=[
                "csod_cross_concept_check",
                "csod_metric_selection",
            ],
        )
    return _csod_interactive_app_cache


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 GRAPH — Intent → CCE → Metrics/Adhoc → Selection → Preview → END
#
# Stops after metric selection + SQL preview.  Returns state with:
#   csod_metric_recommendations, csod_metric_previews, csod_sql_agent_results
# The caller (UI / orchestrator) then triggers Phase 2 with output format.
# ══════════════════════════════════════════════════════════════════════════════

def build_csod_phase1_workflow() -> StateGraph:
    """
    Phase 1: Pure planner pipeline — produces recommendations / NL queries, no execution.

    Schema-first flow:
      intent → skill → early MDL retrieval → analysis planner → CCE → metrics → qualification
      → recommender → validator → metric_selection → END

    Three convergence paths → END:
      normal/layout  → metrics_retrieval → qualification → [layout?]
                     → recommender → validator → metric_selection → END
      adhoc/RCA      → adhoc_query_planner → metric_selection → END
      data_intel     → {discovery|quality|lineage|test} → END

    Previews are generated by a separate preview_generator endpoint called
    by the frontend after Phase 1 completes.
    """
    from app.agents.csod.csod_nodes.node_sql_agent import (
        csod_sql_agent_adhoc_node,
    )

    workflow = StateGraph(EnhancedCompliancePipelineState)
    ins = lambda fn, name: instrument_langgraph_node(fn, name, "csod_p1")

    # ── STAGE 1: INTENT & SKILL ──────────────────────────────────────────
    workflow.add_node("csod_followup_router",    ins(csod_followup_router_node, "csod_followup_router"))
    workflow.add_node("csod_intent_classifier",  ins(csod_intent_classifier_node, "csod_intent_classifier"))
    workflow.add_node("skill_intent_identifier", ins(skill_intent_identifier_node, "skill_intent_identifier"))
    workflow.add_node("skill_analysis_planner",  ins(skill_analysis_planner_node, "skill_analysis_planner"))

    # ── STAGE 2: EARLY MDL RETRIEVAL + ANALYSIS PLANNER ──────────────────
    workflow.add_node("csod_mdl_schema_retrieval_early", ins(csod_mdl_schema_retrieval_node, "csod_mdl_schema_retrieval_early"))
    workflow.add_node("csod_analysis_planner",           ins(csod_analysis_planner_node, "csod_analysis_planner"))

    # ── STAGE 3: CAUSAL + ENRICHMENT ─────────────────────────────────────
    workflow.add_node("csod_causal_graph",        ins(csod_causal_graph_node, "csod_causal_graph"))
    workflow.add_node("csod_cross_concept_check", ins(csod_cross_concept_check_node, "csod_cross_concept_check"))
    workflow.add_node("csod_metrics_retrieval",   ins(csod_metrics_retrieval_node, "csod_metrics_retrieval"))

    # ── STAGE 4: DECISIONS ───────────────────────────────────────────────
    workflow.add_node("csod_metric_qualification", ins(csod_metric_qualification_node, "csod_metric_qualification"))
    workflow.add_node("csod_layout_resolver",      ins(csod_layout_resolver_node, "csod_layout_resolver"))

    # ── STAGE 5: ANALYSIS ────────────────────────────────────────────────
    workflow.add_node("skill_recommender_prep",   ins(skill_recommender_node, "skill_recommender_prep"))
    workflow.add_node("csod_metrics_recommender", ins(csod_metrics_recommender_node, "csod_metrics_recommender"))
    workflow.add_node("skill_validator",          ins(skill_validator_node, "skill_validator"))
    workflow.add_node("csod_metric_selection",    ins(csod_metric_selection_node, "csod_metric_selection"))

    # ── ADHOC QUERY PLANNER (generates NL queries, no SQL execution) ────
    workflow.add_node("csod_sql_agent_adhoc",   ins(csod_sql_agent_adhoc_node, "csod_sql_agent_adhoc"))

    # ── Data intelligence nodes (route early after analysis planner) ─────
    workflow.add_node("data_discovery_agent",  ins(csod_data_discovery_node, "data_discovery_agent"))
    workflow.add_node("data_quality_inspector", ins(csod_data_quality_inspector_node, "data_quality_inspector"))
    workflow.add_node("data_lineage_tracer",   ins(csod_data_lineage_tracer_node, "data_lineage_tracer"))
    workflow.add_node("csod_compliance_test_generator", ins(csod_compliance_test_generator_node, "csod_compliance_test_generator"))

    # ══════════════════════════════════════════════════════════════════════
    # EDGES
    # ══════════════════════════════════════════════════════════════════════

    workflow.set_entry_point("csod_followup_router")

    # Stage 1 edges — followup router can re-enter at any stage
    workflow.add_conditional_edges(
        "csod_followup_router",
        R.route_after_followup_router,
        {
            "csod_intent_classifier": "csod_intent_classifier",
            "csod_metrics_retrieval": "csod_metrics_retrieval",
            "csod_metrics_recommender": "csod_metrics_recommender",
            "data_discovery_agent": "data_discovery_agent",
            "data_quality_inspector": "data_quality_inspector",
            # Re-entry points for backward navigation
            "csod_metric_selection": "csod_metric_selection",
            "csod_analysis_planner": "csod_analysis_planner",
        },
    )
    workflow.add_edge("csod_intent_classifier", "skill_intent_identifier")
    workflow.add_edge("skill_intent_identifier", "skill_analysis_planner")

    # Stage 2 edges — early MDL retrieval then schema-grounded analysis planner
    workflow.add_edge("skill_analysis_planner", "csod_mdl_schema_retrieval_early")
    workflow.add_edge("csod_mdl_schema_retrieval_early", "csod_analysis_planner")

    # After analysis planner: data-intel intents short-circuit, else → causal graph
    workflow.add_conditional_edges(
        "csod_analysis_planner",
        R.route_after_analysis_planner,
        {
            "csod_causal_graph": "csod_causal_graph",
            "data_discovery_agent": "data_discovery_agent",
            "data_quality_inspector": "data_quality_inspector",
            "data_lineage_tracer": "data_lineage_tracer",
            "csod_compliance_test_generator": "csod_compliance_test_generator",
        },
    )

    # Stage 3 edges — CCE then conditional split
    workflow.add_edge("csod_causal_graph", "csod_cross_concept_check")

    # ── KEY SPLIT: after CCE, adhoc/RCA → SQL agent first, else → metrics retrieval
    #    Both paths converge: SQL agent → metrics_retrieval → qualification → recommender
    workflow.add_conditional_edges(
        "csod_cross_concept_check",
        R.route_after_cross_concept_check_phase1,
        {
            "csod_metrics_retrieval": "csod_metrics_retrieval",
            "csod_sql_agent_adhoc": "csod_sql_agent_adhoc",
        },
    )

    # Adhoc/RCA: SQL agent generates per-step queries, THEN feeds into metrics pipeline
    workflow.add_edge("csod_sql_agent_adhoc", "csod_metrics_retrieval")

    # Both paths: metrics → qualification (MDL schemas already in state from early retrieval)
    workflow.add_edge("csod_metrics_retrieval", "csod_metric_qualification")

    # Data intelligence → END (these don't go through metric selection)
    workflow.add_edge("data_discovery_agent", END)
    workflow.add_edge("data_quality_inspector", END)
    workflow.add_edge("data_lineage_tracer", END)
    workflow.add_edge("csod_compliance_test_generator", END)

    # Stage 4 edges
    workflow.add_conditional_edges(
        "csod_metric_qualification",
        R.route_after_metric_qualification,
        {
            "csod_layout_resolver": "csod_layout_resolver",
            "skill_recommender_prep": "skill_recommender_prep",
        },
    )
    workflow.add_conditional_edges(
        "csod_layout_resolver",
        R.route_after_layout_resolver,
        {"skill_recommender_prep": "skill_recommender_prep"},
    )

    # Stage 5 edges
    workflow.add_edge("skill_recommender_prep", "csod_metrics_recommender")
    workflow.add_conditional_edges(
        "csod_metrics_recommender",
        R.route_after_metrics_recommender,
        {
            "skill_validator": "skill_validator",
            # _short_circuit() returns "csod_output_assembler" — alias to metric_selection
            "csod_output_assembler": "csod_metric_selection",
        },
    )
    workflow.add_conditional_edges(
        "skill_validator",
        R.route_after_skill_validator,
        {
            "csod_metric_selection": "csod_metric_selection",
            "csod_output_assembler": "csod_metric_selection",
        },
    )

    # All paths converge: metric selection → END
    # (Preview generation happens via separate endpoint called by frontend)
    workflow.add_edge("csod_metric_selection", END)

    return workflow


def create_csod_phase1_app(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()
    return build_csod_phase1_workflow().compile(checkpointer=checkpointer)


def get_csod_phase1_app():
    return create_csod_phase1_app()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 (OUTPUT) — now lives in csod_output_graph.py
# Backward-compat aliases kept here for existing callers.
# ══════════════════════════════════════════════════════════════════════════════

from app.agents.csod.workflows.csod_output_graph import (
    build_csod_output_workflow,
    create_csod_output_app,
    get_csod_output_app,
)

# Deprecated aliases — use csod_output_graph directly
build_csod_phase2_workflow = build_csod_output_workflow
create_csod_phase2_app = create_csod_output_app
get_csod_phase2_app = get_csod_output_app
