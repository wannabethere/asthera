"""
CSOD Preview Generator Graph
=============================

Standalone graph invoked AFTER Phase 1 completes.  Accepts the Phase 1 state
(metrics, KPIs, tables, resolved schemas, concepts) and produces
``csod_metric_previews`` — rich preview cards with dummy data, Vega-Lite
chart specs, LLM-generated summaries, and insights.

Called by the frontend via ``csod-preview-generator`` agent after Phase 1
returns ``workflow_complete``.
"""

from langgraph.graph import END, StateGraph

from app.agents.csod.csod_nodes.node_sql_agent import csod_sql_agent_preview_node
from app.agents.state import EnhancedCompliancePipelineState
from app.core.telemetry import instrument_langgraph_node


def build_csod_preview_workflow() -> StateGraph:
    """
    Single-node graph: preview_generator → END.

    Reads from state:
      csod_metric_recommendations, csod_kpi_recommendations,
      csod_table_recommendations, csod_resolved_schemas,
      csod_selected_metric_ids, csod_intent, user_query

    Writes to state:
      csod_metric_previews (list of preview card dicts)
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    ins = lambda fn, name: instrument_langgraph_node(fn, name, "csod_preview")

    workflow.add_node(
        "csod_preview_generator",
        ins(csod_sql_agent_preview_node, "csod_preview_generator"),
    )

    workflow.set_entry_point("csod_preview_generator")
    workflow.add_edge("csod_preview_generator", END)

    return workflow


def create_csod_preview_app(checkpointer=None):
    # No default MemorySaver — preview generation is handled by
    # generate_previews_stream() which streams results directly.
    # The graph is only compiled here for agent registration.
    return build_csod_preview_workflow().compile(checkpointer=checkpointer)


def get_csod_preview_app():
    return create_csod_preview_app()
