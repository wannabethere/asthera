"""
Security Orchestrator LangGraph — top-level workflow that dispatches
subtasks to CSOD (data analysis) and DT (detection/triage) sub-graphs.

Pipeline Stages:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  STAGE 1: CLASSIFICATION                                           │
  │  security_request_classifier → capability_router                   │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 2: PLANNING                                                 │
  │  hybrid_plan_builder                                               │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 3: DISPATCH                                                 │
  │  subtask_dispatcher (invokes CSOD and/or DT sub-graphs)            │
  ├─────────────────────────────────────────────────────────────────────┤
  │  STAGE 4: ASSEMBLY                                                 │
  │  subtask_result_merger → final_detection_artifact_assembler        │
  │  → final_validation → completion_narration → END                   │
  └─────────────────────────────────────────────────────────────────────┘
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.orchestrator.orchestrator_state import OrchestratorState
from app.agents.orchestrator.nodes import (
    security_request_classifier_node,
    capability_router_node,
    hybrid_plan_builder_node,
    subtask_dispatcher_node,
    subtask_result_merger_node,
    final_detection_artifact_assembler_node,
    final_validation_node,
    orchestrator_completion_narration_node,
)
from app.core.telemetry import instrument_langgraph_node


def build_orchestrator_workflow() -> StateGraph:
    """Build the top-level security orchestrator LangGraph."""
    workflow = StateGraph(OrchestratorState)
    ins = lambda fn, name: instrument_langgraph_node(fn, name, "orchestrator")

    # =====================================================================
    # STAGE 1: CLASSIFICATION
    # =====================================================================
    workflow.add_node("security_request_classifier", ins(security_request_classifier_node, "security_request_classifier"))
    workflow.add_node("capability_router",           ins(capability_router_node, "capability_router"))

    # =====================================================================
    # STAGE 2: PLANNING
    # =====================================================================
    workflow.add_node("hybrid_plan_builder", ins(hybrid_plan_builder_node, "hybrid_plan_builder"))

    # =====================================================================
    # STAGE 3: DISPATCH (invokes CSOD / DT sub-graphs)
    # =====================================================================
    workflow.add_node("subtask_dispatcher", ins(subtask_dispatcher_node, "subtask_dispatcher"))

    # =====================================================================
    # STAGE 4: ASSEMBLY & OUTPUT
    # =====================================================================
    workflow.add_node("subtask_result_merger",               ins(subtask_result_merger_node, "subtask_result_merger"))
    workflow.add_node("final_detection_artifact_assembler",  ins(final_detection_artifact_assembler_node, "final_detection_artifact_assembler"))
    workflow.add_node("final_validation",                    ins(final_validation_node, "final_validation"))
    workflow.add_node("completion_narration",                ins(orchestrator_completion_narration_node, "completion_narration"))

    # =====================================================================
    # EDGES — linear pipeline (orchestrator is always sequential)
    # =====================================================================
    workflow.set_entry_point("security_request_classifier")

    # Stage 1 → Stage 2
    workflow.add_edge("security_request_classifier", "capability_router")
    workflow.add_edge("capability_router", "hybrid_plan_builder")

    # Stage 2 → Stage 3
    workflow.add_edge("hybrid_plan_builder", "subtask_dispatcher")

    # Stage 3 → Stage 4
    workflow.add_edge("subtask_dispatcher", "subtask_result_merger")
    workflow.add_edge("subtask_result_merger", "final_detection_artifact_assembler")
    workflow.add_edge("final_detection_artifact_assembler", "final_validation")
    workflow.add_edge("final_validation", "completion_narration")
    workflow.add_edge("completion_narration", END)

    return workflow


def create_orchestrator_app(checkpointer=None):
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_orchestrator_workflow().compile(checkpointer=checkpointer)


def get_orchestrator_app():
    return create_orchestrator_app()
