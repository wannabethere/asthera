"""
Causal Graph Nodes for CSOD Workflow

Provides LangGraph nodes for causal graph construction and integration
with CSOD metrics recommender workflow.
"""
import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage

from .vector_causal_graph_builder import vector_causal_graph_node
from .causal_context_extractor import extract_causal_context

logger = logging.getLogger(__name__)


def causal_graph_creator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main causal graph creator node for CSOD workflow.
    
    This node:
    1. Retrieves causal nodes and edges using vector search
    2. Assembles graph using LLM
    3. Extracts causal context for metrics recommender
    4. Populates state with causal graph data
    
    Reads from state:
        user_query, causal_vertical, metric_registry, cce_db_url
    
    Writes to state:
        causal_proposed_nodes, causal_proposed_edges, causal_graph_metadata,
        causal_signals, causal_graph_panel_data, causal_node_index
    """
    try:
        # Step 1: Build causal graph using vector retrieval + LLM assembly
        state = vector_causal_graph_node(state)
        
        # Step 2: Extract causal context for metrics recommender
        proposed_nodes = state.get("causal_proposed_nodes", [])
        proposed_edges = state.get("causal_proposed_edges", [])
        graph_metadata = state.get("causal_graph_metadata", {})
        causal_graph = state.get("causal_graph", {})
        
        if proposed_nodes and proposed_edges:
            causal_context = extract_causal_context(
                causal_graph=causal_graph,
                graph_metadata=graph_metadata,
                proposed_nodes=proposed_nodes,
                proposed_edges=proposed_edges,
            )
            
            # Merge causal context into state
            state["causal_signals"] = causal_context.get("causal_signals", {})
            state["causal_graph_boost_focus_areas"] = causal_context.get("causal_graph_boost_focus_areas", [])
            state["causal_graph_panel_data"] = causal_context.get("causal_graph_panel_data")
            state["causal_node_index"] = causal_context.get("causal_node_index", {})
            
            logger.info(
                f"causal_graph_creator_node: extracted context with "
                f"focus_area={causal_context.get('causal_signals', {}).get('derived_focus_area')}, "
                f"complexity={causal_context.get('causal_signals', {}).get('derived_complexity')}"
            )
        else:
            # No graph built, set empty context
            state["causal_signals"] = {}
            state["causal_graph_boost_focus_areas"] = []
            state["causal_graph_panel_data"] = None
            state["causal_node_index"] = {}
        
        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"[CausalGraphCreator] Built graph with {len(proposed_nodes)} nodes, "
                f"{len(proposed_edges)} edges | "
                f"Focus area: {state.get('causal_signals', {}).get('derived_focus_area', 'N/A')}"
            )
        ))
        
    except Exception as e:
        logger.error(f"causal_graph_creator_node failed: {e}", exc_info=True)
        state["error"] = f"CausalGraphCreator failed: {str(e)}"
        state.setdefault("causal_proposed_nodes", [])
        state.setdefault("causal_proposed_edges", [])
        state.setdefault("causal_signals", {})
        state.setdefault("causal_graph_panel_data", None)
        state.setdefault("causal_node_index", {})
    
    return state
