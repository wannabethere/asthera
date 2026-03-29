"""
CSOD Output Pipeline — deploy-time graph invoked after Phase 1 preview.

Streamlined output flow:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  csod_goal_intent → csod_output_format_selector                    │
  │    → csod_medallion_planner → csod_gold_model_sql_generator        │
  │    → cubejs_schema_generation (if gold SQL produced)               │
  │    → csod_scheduler → csod_output_assembler                        │
  │    → csod_completion_narration → END                               │
  └─────────────────────────────────────────────────────────────────────┘

Receives full Phase 1 state (metrics, schemas, selections) as input.
Called by the middleware adapter when the user hits "deploy".
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.csod.csod_nodes import (
    csod_gold_model_sql_generator_node,
    csod_medallion_planner_node,
    csod_output_assembler_node,
    csod_output_format_selector_node,
    csod_completion_narration_node,
    csod_scheduler_node,
)
from app.agents.csod.csod_nodes.node_goal_intent import csod_goal_intent_node
from app.agents.csod.workflows import csod_main_routing as R
from app.agents.shared import cubejs_schema_generation_node
from app.agents.state import EnhancedCompliancePipelineState
from app.core.telemetry import instrument_langgraph_node


def build_csod_output_workflow() -> StateGraph:
    """
    Output pipeline: goal_intent → format → medallion → gold SQL → CubeJS → scheduler → assembler.

    Nodes removed vs legacy Phase 2:
      - csod_data_science_insights_enricher (folded into recommender)
      - calculation_planner (removed)
      - csod_compliance_test_generator (moved to Phase 1)
      - data_lineage_tracer (moved to Phase 1)
      - data_pipeline_planner (removed)
      - csod_dashboard_generator (removed)
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    ins = lambda fn, name: instrument_langgraph_node(fn, name, "csod_output")

    # ── OUTPUT SELECTION ─────────────────────────────────────────────────
    workflow.add_node("csod_goal_intent",           ins(csod_goal_intent_node, "csod_goal_intent"))
    workflow.add_node("csod_output_format_selector", ins(csod_output_format_selector_node, "csod_output_format_selector"))

    # ── EXECUTION AGENTS ─────────────────────────────────────────────────
    workflow.add_node("csod_medallion_planner",         ins(csod_medallion_planner_node, "csod_medallion_planner"))
    workflow.add_node("csod_gold_model_sql_generator",  ins(csod_gold_model_sql_generator_node, "csod_gold_model_sql_generator"))
    workflow.add_node("cubejs_schema_generation",       ins(cubejs_schema_generation_node, "cubejs_schema_generation"))
    workflow.add_node("csod_scheduler",                 ins(csod_scheduler_node, "csod_scheduler"))

    # ── ASSEMBLY & NARRATION ─────────────────────────────────────────────
    workflow.add_node("csod_output_assembler",     ins(csod_output_assembler_node, "csod_output_assembler"))
    workflow.add_node("csod_completion_narration", ins(csod_completion_narration_node, "csod_completion_narration"))

    # ══════════════════════════════════════════════════════════════════════
    # EDGES
    # ══════════════════════════════════════════════════════════════════════

    workflow.set_entry_point("csod_goal_intent")

    workflow.add_edge("csod_goal_intent", "csod_output_format_selector")

    # Format selector → medallion planner (if metrics exist) or assembler
    workflow.add_conditional_edges(
        "csod_output_format_selector",
        R.route_after_output_format_selector_v2,
        {
            "csod_medallion_planner": "csod_medallion_planner",
            "csod_output_assembler": "csod_output_assembler",
        },
    )

    # Medallion → gold SQL or scheduler
    workflow.add_conditional_edges(
        "csod_medallion_planner",
        R.route_after_medallion_planner,
        {
            "csod_gold_model_sql_generator": "csod_gold_model_sql_generator",
            "csod_scheduler": "csod_scheduler",
            "csod_output_assembler": "csod_output_assembler",
        },
    )

    # Gold SQL → CubeJS or scheduler
    workflow.add_conditional_edges(
        "csod_gold_model_sql_generator",
        R.route_after_gold_model_sql_generator,
        {
            "cubejs_schema_generation": "cubejs_schema_generation",
            "csod_scheduler": "csod_scheduler",
            "csod_output_assembler": "csod_output_assembler",
        },
    )

    # CubeJS → scheduler
    workflow.add_conditional_edges(
        "cubejs_schema_generation",
        R.route_after_cubejs,
        {"csod_scheduler": "csod_scheduler"},
    )

    # Scheduler → assembler
    workflow.add_conditional_edges(
        "csod_scheduler",
        R.route_after_scheduler,
        {"csod_output_assembler": "csod_output_assembler"},
    )

    # Assembly → narration → END
    workflow.add_edge("csod_output_assembler", "csod_completion_narration")
    workflow.add_edge("csod_completion_narration", END)

    return workflow


def create_csod_output_app(checkpointer=None):
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_csod_output_workflow().compile(checkpointer=checkpointer)


def get_csod_output_app():
    return create_csod_output_app()
