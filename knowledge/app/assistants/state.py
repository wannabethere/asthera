"""
State model for Contextual Assistants
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def last_value_reducer(current: Optional[str], updates: List[str]) -> str:
    """
    Reducer for state keys that take the last value when multiple nodes write concurrently.
    
    This allows multiple nodes to write to the same state key in parallel without causing
    an InvalidUpdateError. The last value in the updates list wins.
    
    Args:
        current: Current value (may be None)
        updates: List of values written by parallel nodes
        
    Returns:
        The last value from the updates list, or current value if no updates
    """
    if updates:
        return updates[-1]
    return current if current is not None else ""


def last_optional_value_reducer(current: Optional[str], updates: List[Optional[str]]) -> Optional[str]:
    """
    Reducer for Optional[str] state keys that takes the last value when multiple nodes write concurrently.
    
    This allows multiple nodes to write to Optional[str] state keys in parallel without causing
    an InvalidUpdateError. The last non-None value in the updates list wins, or None if all are None.
    
    Args:
        current: Current value (may be None)
        updates: List of values written by parallel nodes (may contain None)
        
    Returns:
        The last non-None value from the updates list, or the last value if all are None,
        or current value if no updates
    """
    if updates:
        # Return the last value (even if None) - this preserves the last write
        return updates[-1]
    return current


class ContextualAssistantState(TypedDict, total=False):
    """State for contextual assistant workflows"""
    
    # User input
    query: str
    session_id: Optional[str]
    user_context: Optional[Dict[str, Any]]  # User's organizational/situational context
    project_id: Optional[str]  # Project ID for data assistance queries
    skip_deep_research: bool  # If True, skip deep research and table-specific reasoning, just return curated tables
    
    # Intent understanding
    intent: Optional[str]  # 'question', 'analysis', 'writing', 'graph_query'
    intent_confidence: float
    intent_details: Optional[Dict[str, Any]]
    actor_type: str  # 'data_scientist', 'business_analyst', 'product_manager', 'executive', 'consultant'
    
    # Context retrieval
    context_ids: List[str]  # Active context IDs from contextual graph
    context_metadata: List[Dict[str, Any]]  # Context details
    reasoning_plan: Optional[Dict[str, Any]]  # Reasoning plan from retrieval agent
    
    # Contextual reasoning
    reasoning_result: Optional[Dict[str, Any]]  # Result from contextual graph reasoning
    reasoning_path: List[Dict[str, Any]]  # Multi-hop reasoning path
    
    # Q&A Agent results
    qa_answer: Optional[str]
    qa_sources: List[Dict[str, Any]]
    qa_confidence: float
    
    # Executor Agent results
    executor_result: Optional[Dict[str, Any]]  # Results from executor node
    executor_output: Optional[str]  # Formatted executor output
    executor_actions: List[Dict[str, Any]]  # Actions performed
    
    # Writer Agent results
    written_content: Optional[str]
    content_type: Optional[str]  # 'report', 'summary', 'analysis', 'recommendation'
    content_metadata: Optional[Dict[str, Any]]
    writer_decision: Optional[str]  # 'summary', 'return_result' - decision made by writer
    
    # Graph routing
    selected_graph_id: Optional[str]  # If routing to another graph
    graph_input: Optional[Dict[str, Any]]  # Input for sub-graph
    
    # Messages for conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Workflow state
    current_node: Annotated[str, last_value_reducer]  # Uses reducer to handle concurrent writes
    next_node: Annotated[Optional[str], last_optional_value_reducer]  # Uses reducer to handle concurrent writes
    status: Annotated[str, last_value_reducer]  # Uses reducer to handle concurrent writes
    error: Annotated[Optional[str], last_optional_value_reducer]  # Uses reducer to handle concurrent writes
    
    # Pipeline integration
    pipeline_results: Dict[str, Any]  # Results from various pipelines
    
    # Data assistance specific
    data_knowledge: Optional[Dict[str, Any]]  # Retrieved schemas, metrics, and controls
    generated_metrics: List[Dict[str, Any]]  # Generated metrics from schema definitions
    
    # MDL reasoning integration
    mdl_summary: Optional[Dict[str, Any]]  # MDL reasoning summary
    mdl_final_result: Optional[Dict[str, Any]]  # MDL reasoning final result
    mdl_curated_tables: List[Dict[str, Any]]  # Curated tables from MDL reasoning
    mdl_contexts_retrieved: List[Dict[str, Any]]  # Contexts retrieved from MDL reasoning
    mdl_edges_discovered: List[Dict[str, Any]]  # Edges discovered from MDL reasoning
    mdl_contextual_plan: Optional[Dict[str, Any]]  # Contextual plan from MDL reasoning
    suggested_tables: List[Dict[str, Any]]  # Suggested tables from MDL reasoning (for data knowledge retrieval)
    table_suggestion_strategy: Optional[str]  # Strategy/reasoning for table suggestions
    generic_breakdown: Optional[Dict[str, Any]]  # Generic breakdown from MDL reasoning (includes evidence gathering planning)
    
    # Deep research integration
    deep_research_review: Optional[Dict[str, Any]]  # Deep research review results with recommended features, evidence gathering plan, data gaps
    deep_research_edges: List[Dict[str, Any]]  # Contextual edges retrieved and used in deep research for richer context
    
    # Table-specific reasoning
    table_specific_reasoning: Optional[Dict[str, Any]]  # Table-specific reasoning results with insights for each curated table
    
    # Final output
    final_answer: Optional[str]
    final_output: Optional[Dict[str, Any]]  # Structured output

