"""
State model for MDL Reasoning and Planning Graph
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def list_reducer(current: Optional[List[Any]], updates: List[List[Any]]) -> List[Any]:
    """
    Reducer for list state keys that merges all updates.
    
    For fields typed as List[Dict[str, Any]] (like tables_found, entities_found),
    this reducer filters out non-dict items to maintain type consistency.
    """
    result = list(current) if current else []
    import logging
    logger = logging.getLogger(__name__)
    
    # Common dictionary keys that should be filtered out
    dict_keys_to_filter = {"table_name", "relevance_score", "description", "full_description", 
                          "comments", "ddl", "columns", "categories", "metadata", "content", 
                          "source", "edge_type", "target_entity_type", "target_entity_id", 
                          "target_entity_id", "reasoning", "search_query", "metadata_filters",
                          "edge_id", "source_entity_id", "source_entity_type"}
    
    for update in updates:
        if update:
            # Handle case where update is a dict (should be wrapped in list)
            if isinstance(update, dict):
                logger.warning(f"list_reducer: Received dict instead of list, wrapping: {list(update.keys())[:5]}...")
                # Wrap dict in list
                result.append(update)
            # Handle case where update is a list containing a dict
            elif isinstance(update, list):
                for item in update:
                    # Handle case where item is a dict (normal case)
                    if isinstance(item, dict):
                        result.append(item)
                    # Handle case where item is a string that looks like a dict key
                    elif isinstance(item, str) and item in dict_keys_to_filter:
                        logger.warning(f"list_reducer: Skipping dictionary key '{item}' that was incorrectly added to list")
                        continue
                    # Handle other types
                    else:
                        result.append(item)
            else:
                # Single item update
                if isinstance(update, dict):
                    result.append(update)
                elif isinstance(update, str) and update in dict_keys_to_filter:
                    logger.warning(f"list_reducer: Skipping dictionary key '{update}' that was incorrectly added to list")
                    continue
                else:
                    result.append(update)
    
    # Filter out dictionary keys and single characters
    filtered_result = []
    for item in result:
        if isinstance(item, dict):
            # Keep dictionaries
            filtered_result.append(item)
        elif isinstance(item, str):
            # Filter out dictionary keys and single characters
            if item in dict_keys_to_filter:
                logger.warning(f"list_reducer: Filtering out dictionary key '{item}'")
                continue
            elif len(item.strip()) == 1:
                logger.warning(f"list_reducer: Filtering out single character '{item}'")
                continue
            else:
                # Keep meaningful strings
                filtered_result.append(item)
        else:
            # Keep other types
            filtered_result.append(item)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_result = []
    for item in filtered_result:
        if isinstance(item, dict):
            # Try to find unique identifier
            item_id = item.get("id") or item.get("edge_id") or item.get("context_id") or item.get("table_name") or item.get("entity_id")
            if not item_id:
                item_id = str(item)
        elif isinstance(item, str):
            item_id = item
        else:
            item_id = str(item)
        
        if item_id not in seen:
            seen.add(item_id)
            unique_result.append(item)
    return unique_result


def dict_reducer(current: Optional[Dict[str, Any]], updates: List[Any]) -> Dict[str, Any]:
    """
    Reducer for dict state keys that merges all updates.
    
    Handles cases where updates might be:
    - A dictionary (normal case)
    - A list containing a dictionary (LangGraph wraps in list)
    - Dictionary keys as strings (error case - should not happen but we handle it)
    """
    result = dict(current) if current else {}
    import logging
    logger = logging.getLogger(__name__)
    
    for update in updates:
        if update:
            # Handle list containing dict (LangGraph sometimes wraps)
            if isinstance(update, list):
                for item in update:
                    if isinstance(item, dict):
                        result.update(item)
                    elif isinstance(item, str):
                        # String might be a key - log but don't process
                        logger.warning(f"dict_reducer: Received string in list update (likely a key): {item}")
            # Handle direct dict update
            elif isinstance(update, dict):
                result.update(update)
            elif isinstance(update, str):
                # String update - likely a dictionary key that was incorrectly extracted
                # Log with more detail to help debug
                logger.warning(f"dict_reducer: Skipping non-dict update (likely a dict key): {type(update)} - value: '{update}'")
                logger.debug(f"dict_reducer: Current result keys: {list(result.keys()) if result else 'empty'}")
            else:
                # Other types
                logger.warning(f"dict_reducer: Skipping non-dict update: {type(update)} - {str(update)[:100]}")
    return result


class MDLReasoningState(TypedDict, total=False):
    """State for MDL reasoning and planning workflow"""
    
    # User input
    user_question: str
    product_name: Optional[str]  # Snyk, Cornerstone, etc.
    products: Optional[List[str]]  # One or more products for table retrieval (used to rephrase MDL queries)
    project_id: Optional[str]  # Project ID for data queries
    actor: Optional[str]  # Actor making the request (e.g., "Data Engineer", "Compliance Officer")
    query_type: Optional[str]  # Query type: mdl, compliance, policy, risk, product, etc.
    
    # Step 1: Generic Context Breakdown (first step - identifies data sources)
    generic_breakdown: Optional[Dict[str, Any]]  # Generic context breakdown result (uses prompt_generator.py)
    
    # Step 2: MDL Table Curation (if query_type is mdl)
    context_breakdown: Optional[Dict[str, Any]]  # MDL table curation result (includes curated_tables, curated_tables_info, mdl_queries, mdl_results)
    identified_entities: Annotated[List[str], list_reducer]  # Entity names identified
    search_questions: Annotated[List[Dict[str, Any]], list_reducer]  # Search questions generated
    relevant_tables: Annotated[List[str], list_reducer]  # Curated table names from MDL curation
    mdl_queries: Annotated[List[str], list_reducer]  # Multiple MDL sub-queries to process in parallel
    
    # Step 3: Contextual Planning (identifies relevant edges for curated tables)
    contextual_plan: Optional[Dict[str, Any]]  # Contextual planning result (includes table_edges, reasoning)
    
    # Step 4: Edge-based Retrieval (retrieves data based on identified edges)
    # Step 5: Summary (final summary of all collected data)
    summary: Optional[Dict[str, Any]]  # Summary result (includes answer, key_tables, relationships, contexts, insights)
    
    # Step 2: Entity Identification
    tables_found: Annotated[List[Dict[str, Any]], list_reducer]  # Tables identified
    entities_found: Annotated[List[Dict[str, Any]], list_reducer]  # Entities identified
    entity_questions: Annotated[List[Dict[str, Any]], list_reducer]  # Natural language questions for entities
    
    # Step 2b: Table Pruning (after retrieval)
    pruned_tables: Annotated[List[Dict[str, Any]], list_reducer]  # Tables pruned based on user question
    table_context_queries: Annotated[List[Dict[str, Any]], list_reducer]  # Queries for table contexts
    table_relationship_queries: Annotated[List[Dict[str, Any]], list_reducer]  # Queries for table relationships
    
    # Step 3: Context Retrieval
    contexts_retrieved: Annotated[List[Dict[str, Any]], list_reducer]  # Contexts from contextual graph
    edges_discovered: Annotated[List[Dict[str, Any]], list_reducer]  # Edges discovered
    related_entities: Annotated[List[Dict[str, Any]], list_reducer]  # Related entities via edges
    
    # Step 4: Planning
    reasoning_plan: Optional[Dict[str, Any]]  # Final reasoning plan
    plan_components: Annotated[Dict[str, Any], dict_reducer]  # Plan components (product, controls, risks, metrics)
    
    # Natural language questions generated
    natural_language_questions: Annotated[List[str], list_reducer]  # Questions for retrieval
    
    # Workflow state
    current_step: str  # Current step in workflow
    status: str  # 'processing', 'completed', 'error'
    error: Optional[str]  # Error message if any
    
    # Messages for conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Final output
    final_result: Optional[Dict[str, Any]]  # Final structured result

