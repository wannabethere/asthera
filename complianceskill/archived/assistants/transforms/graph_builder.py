"""
LangGraph builder for the Transforms (Agentic Silver) assistant.

Human-in-the-loop flow:
1. User sets goal -> intent_and_playbook (break down intents, identify playbooks, key concepts per source)
2. interrupt: wait for user to select playbooks, source topics, compliance (hardcode workday/cornerstone, SOC2 for now)
3. identify_feature_buckets: LLM maps goal + compliance + playbook + topic selection -> feature buckets
4. fetch_data_models: vector store (stub) fetches data models relevant to buckets and selected sources
5. process_selection_qa -> interrupt: wait_for_build_confirm (user selects continue + buckets)
6. On resume -> build_features (LaneFeatureExecutor per bucket with mdl_cornerstone_features) -> structured_graph (LLM) -> process_build_qa -> END

Conversational state and memory: use get_transforms_config(thread_id) and pass
the same thread_id to invoke; checkpointer (default MemorySaver; Postgres/vector
store for optimization) persists state for start and back via get_state / get_state_history.
"""
import logging
from typing import Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from app.assistants.transforms.state import TransformsAssistantState
from app.assistants.transforms.store import (
    DEFAULT_SELECTED_SOURCES,
    DEFAULT_COMPLIANCE_FRAMEWORK,
    AVAILABLE_FEATURE_BUCKETS,
)
from app.assistants.transforms.nodes import (
    IntentAndPlaybookNode,
    IdentifyFeatureBucketsNode,
    FetchDataModelsNode,
    ProcessSelectionQANode,
    BuildFeaturesNode,
    StructuredGraphNode,
    ProcessBuildQANode,
)
from app.assistants.transforms.memory import get_checkpointer

logger = logging.getLogger(__name__)


def _wait_for_selection_node(state: TransformsAssistantState) -> dict:
    """Pause for user to select playbook, source topics, and optionally compliance. Resume value becomes selection."""
    payload = {
        "message": "Please select a playbook and source topics.",
        "intents": state.get("intents", []),
        "key_concepts_by_source": state.get("key_concepts_by_source", {}),
        "suggested_playbooks": state.get("suggested_playbooks", []),
        "source_categories": state.get("source_categories", []),
    }
    selection = interrupt(payload)
    if not isinstance(selection, dict):
        selection = {}
    source_ids = selection.get("selected_source_ids") or DEFAULT_SELECTED_SOURCES
    compliance = selection.get("selected_compliance_framework") or DEFAULT_COMPLIANCE_FRAMEWORK
    return {
        "selected_playbook_id": selection.get("selected_playbook_id"),
        "selected_source_ids": source_ids,
        "selected_compliance_framework": compliance,
    }


def _wait_for_build_confirm_node(state: TransformsAssistantState) -> dict:
    """Pause for user to select continue and optionally which buckets to build. Resume value sets selected_bucket_ids_for_build."""
    feature_buckets = state.get("feature_buckets") or []
    allowed = set(AVAILABLE_FEATURE_BUCKETS)
    payload = {
        "message": "Select buckets to build and continue, or continue with all suggested buckets.",
        "feature_buckets": feature_buckets,
        "qa_response": state.get("qa_response", ""),
        "next_steps": state.get("feature_bucket_next_steps", ""),
    }
    selection = interrupt(payload)
    if not isinstance(selection, dict):
        selection = {}
    if selection.get("action") != "continue":
        bucket_ids = list(feature_buckets)
    else:
        bucket_ids = selection.get("selected_bucket_ids") or selection.get("selected_bucket_ids_for_build") or feature_buckets
    bucket_ids = [b for b in bucket_ids if b in allowed]
    if not bucket_ids:
        bucket_ids = list(feature_buckets)[:5]
    return {"selected_bucket_ids_for_build": bucket_ids}


def build_transforms_graph(
    use_checkpointing: bool = True,
    *,
    checkpointer: Optional[Any] = None,
    intent_and_playbook_node: Optional[Any] = None,
    identify_feature_buckets_node: Optional[Any] = None,
    fetch_data_models_node: Optional[Any] = None,
    process_selection_node: Optional[Any] = None,
    build_features_node: Optional[Any] = None,
    structured_graph_node: Optional[Any] = None,
    process_build_node: Optional[Any] = None,
) -> Any:
    """
    Build the Transforms assistant graph with conversational memory.

    Flow: START -> intent_and_playbook -> wait_for_selection (interrupt)
          -> on resume -> identify_feature_buckets (LLM) -> fetch_data_models -> process_selection_qa
          -> wait_for_build_confirm (interrupt)
          -> on resume -> build_features (LaneFeatureExecutor per bucket with mdl_cornerstone_features)
          -> process_build_qa -> END.

    Invoke: pass goal; on first resume pass selected_playbook_id, selected_source_ids;
    on second resume pass action "continue" and optionally selected_bucket_ids.

    Args:
        use_checkpointing: If True, use checkpointer (required for interrupt and memory).
        checkpointer: Optional; if None and use_checkpointing, uses in-memory.
        intent_and_playbook_node: Optional override for intent/playbook node.
        identify_feature_buckets_node: Optional override for feature-buckets node.
        fetch_data_models_node: Optional override for fetch-data-models node.
        process_selection_node: Optional override for process selection/QA node.
    build_features_node: Optional override for build-features node.
    structured_graph_node: Optional override for structured-graph (LLM) node.
    process_build_node: Optional override for process build/QA node.

    Returns:
        Compiled graph. Invoke with {"goal": "..."} and config=get_transforms_config(thread_id).
        First interrupt: resume with selected_playbook_id, selected_source_ids, selected_compliance_framework.
        Second interrupt: resume with action "continue", optional selected_bucket_ids.
    """
    workflow = StateGraph(TransformsAssistantState)

    intent_node = intent_and_playbook_node or IntentAndPlaybookNode()
    feature_buckets_node = identify_feature_buckets_node or IdentifyFeatureBucketsNode()
    fetch_models_node = fetch_data_models_node or FetchDataModelsNode()
    process_qa = process_selection_node or ProcessSelectionQANode()
    build_features = build_features_node or BuildFeaturesNode()
    structured_graph = structured_graph_node or StructuredGraphNode()
    process_build_qa = process_build_node or ProcessBuildQANode()

    workflow.add_node("intent_and_playbook", intent_node)
    workflow.add_node("wait_for_selection", _wait_for_selection_node)
    workflow.add_node("identify_feature_buckets", feature_buckets_node)
    workflow.add_node("fetch_data_models", fetch_models_node)
    workflow.add_node("process_selection_qa", process_qa)
    workflow.add_node("wait_for_build_confirm", _wait_for_build_confirm_node)
    workflow.add_node("build_features", build_features)
    workflow.add_node("structured_graph", structured_graph)
    workflow.add_node("process_build_qa", process_build_qa)

    workflow.add_edge("intent_and_playbook", "wait_for_selection")
    workflow.add_edge("wait_for_selection", "identify_feature_buckets")
    workflow.add_edge("identify_feature_buckets", "fetch_data_models")
    workflow.add_edge("fetch_data_models", "process_selection_qa")
    workflow.add_edge("process_selection_qa", "wait_for_build_confirm")
    workflow.add_edge("wait_for_build_confirm", "build_features")
    workflow.add_edge("build_features", "structured_graph")
    workflow.add_edge("structured_graph", "process_build_qa")
    workflow.add_edge("process_build_qa", END)

    workflow.set_entry_point("intent_and_playbook")

    if use_checkpointing:
        cp = get_checkpointer(checkpointer)
        return workflow.compile(checkpointer=cp)
    return workflow.compile()


def create_transforms_graph(
    use_checkpointing: bool = True,
    *,
    checkpointer: Optional[Any] = None,
) -> Any:
    """Factory: create the Transforms assistant graph with checkpointing and optional custom checkpointer."""
    return build_transforms_graph(use_checkpointing=use_checkpointing, checkpointer=checkpointer)
