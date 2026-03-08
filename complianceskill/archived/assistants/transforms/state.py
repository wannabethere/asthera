"""
State for the Transforms (Agentic Silver) assistant.

Human-in-the-loop LangGraph: user sets a goal -> playbook suggestion + source categories
-> wait for user selection -> QA response.

Conversational state and memory: use configurable.thread_id for persistence;
messages are accumulated via add_messages. Checkpointer (MemorySaver, Postgres, etc.)
stores checkpoints so you can get_state / get_state_history for start and back.
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TransformsAssistantState(TypedDict, total=False):
    """State for the feature-generation / compliance automation chat assistant."""

    goal: Optional[str]
    session_id: Optional[str]
    thread_id: Optional[str]

    intents: List[str]
    intent_thinking: Optional[str]
    key_concepts_by_source: Dict[str, List[str]]

    suggested_playbooks: List[Dict[str, Any]]
    playbook_thinking: Optional[str]
    source_categories: List[Dict[str, Any]]
    source_categories_thinking: Optional[str]

    selected_playbook_id: Optional[str]
    selected_source_ids: List[str]
    selected_compliance_framework: Optional[str]
    compliance_feature_instructions: Optional[Dict[str, Any]]

    feature_buckets: List[str]
    feature_bucket_thinking: Optional[str]
    feature_bucket_next_steps: Optional[str]
    relevant_example_ids: List[str]

    retrieved_data_models: List[Dict[str, Any]]
    data_models_thinking: Optional[str]

    selected_bucket_ids_for_build: List[str]
    generated_features_by_bucket: Dict[str, Any]
    build_features_thinking: Optional[str]
    build_status: Optional[str]

    agent_thinking: List[Dict[str, Any]]

    messages: Annotated[Sequence[BaseMessage], add_messages]

    qa_response: Optional[str]
    status: Optional[str]
    error: Optional[str]

    delivery_outcomes: Optional[Dict[str, Any]]
    structured_graph_spec: Optional[Dict[str, Any]]
    strategy_graph: Optional[Dict[str, Any]]
    reasoning_plan_steps: List[Dict[str, Any]]
    example_sources: List[Dict[str, Any]]
