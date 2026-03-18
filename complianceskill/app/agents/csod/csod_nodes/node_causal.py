"""Causal graph (CCE) enrichment."""
from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger

def csod_causal_graph_node(state: CSOD_State) -> CSOD_State:
    """
    Builds causal graph using the causal graph creator module.
    
    Uses hybrid retrieval (ChromaDB + Postgres) + LLM assembly to build
    a typed causal graph that enhances metric recommendations.
    
    Controlled via feature flag: csod_causal_graph_enabled
    
    This node now uses the full causal_graph_creator_node from the causalgraph module,
    which provides:
    - Vector retrieval of nodes and edges
    - LLM assembly for graph construction
    - Causal context extraction for downstream enrichment
    """
    try:
        # Check feature flag
        causal_enabled = state.get("csod_causal_graph_enabled", False)
        if not causal_enabled:
            logger.info(
                "[CSOD pipeline] csod_causal_graph: skipped "
                "(csod_causal_graph_enabled=False)"
            )
            state.setdefault("csod_causal_nodes", [])
            state.setdefault("csod_causal_edges", [])
            state.setdefault("csod_causal_graph_metadata", {})
            state.setdefault("csod_causal_retrieval_stats", {})
            return state

        logger.info(
            "[CSOD pipeline] csod_causal_graph: running causal enrichment "
            "(vertical=%s)",
            state.get("causal_vertical", "lms"),
        )
        
        user_query = state.get("user_query", "")
        vertical = state.get("causal_vertical", "lms")
        
        if not user_query:
            logger.warning("No user query available for causal graph")
            state.setdefault("csod_causal_nodes", [])
            state.setdefault("csod_causal_edges", [])
            return state
        
        # Prefer DT-qualified metrics when present (CCE operates on same set as execution spine)
        dt_scored = state.get("dt_scored_metrics", [])
        metric_recommendations = state.get("csod_metric_recommendations", [])
        retrieved_metrics = state.get("csod_retrieved_metrics", [])
        source_metrics = dt_scored if dt_scored else (metric_recommendations + retrieved_metrics)
        
        # Merge and deduplicate
        all_metrics = []
        seen_ids = set()
        for m in source_metrics:
            mid = m.get("metric_id") or m.get("id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                all_metrics.append(m)
        
        # Build causal graph state for the creator
        from app.agents.causalgraph import causal_graph_creator_node
        
        causal_state = {
            "user_query": user_query,
            "causal_vertical": vertical,
            "metric_registry": all_metrics,
            "causal_metric_registry": all_metrics,
            "schema_definitions": {},  # Can bootstrap from csod_resolved_schemas if needed
            "corpus": [],  # Can load from config
            "available_data_sources": state.get("csod_data_sources_in_scope", []),
            "cce_db_url": state.get("cce_db_url"),
            "causal_proposed_nodes": [],
            "causal_proposed_edges": [],
            "causal_graph_metadata": {},
            "causal_signals": {},
            "causal_graph_panel_data": None,
            "causal_node_index": {},
            "messages": state.get("messages", []),
        }
        
        # Call causal graph creator
        causal_state = causal_graph_creator_node(causal_state)
        
        # Map outputs back to CSOD state
        proposed_nodes = causal_state.get("causal_proposed_nodes", [])
        proposed_edges = causal_state.get("causal_proposed_edges", [])
        graph_metadata = causal_state.get("causal_graph_metadata", {})
        retrieval_stats = causal_state.get("causal_retrieval_stats", {})
        
        state["csod_causal_nodes"] = proposed_nodes
        state["csod_causal_edges"] = proposed_edges
        state["csod_causal_graph_metadata"] = graph_metadata
        state["csod_causal_retrieval_stats"] = retrieval_stats
        
        # Store causal context for metrics recommender enrichment
        state["causal_signals"] = causal_state.get("causal_signals", {})
        state["causal_graph_boost_focus_areas"] = causal_state.get("causal_graph_boost_focus_areas", [])
        state["causal_graph_panel_data"] = causal_state.get("causal_graph_panel_data")
        state["causal_node_index"] = causal_state.get("causal_node_index", {})
        
        # Update messages
        if "messages" in causal_state:
            new_messages = [
                msg for msg in causal_state["messages"]
                if msg not in state.get("messages", [])
            ]
            state["messages"].extend(new_messages)
        
        _csod_log_step(
            state, "csod_causal_graph", "csod_causal_graph",
            inputs={
                "user_query": user_query,
                "vertical": vertical,
                "metric_count": len(all_metrics),
            },
            outputs={
                "nodes_assembled": len(proposed_nodes),
                "edges_assembled": len(proposed_edges),
                "retrieval_stats": retrieval_stats,
                "focus_area": causal_state.get("causal_signals", {}).get("derived_focus_area"),
            },
        )
        
        state["messages"].append(AIMessage(
            content=(
                f"[CausalGraph] Assembled {len(proposed_nodes)} nodes, {len(proposed_edges)} edges | "
                f"Focus: {causal_state.get('causal_signals', {}).get('derived_focus_area', 'N/A')} | "
                f"vertical={vertical}"
            )
        ))
        
    except Exception as e:
        logger.error(f"csod_causal_graph_node failed: {e}", exc_info=True)
        state["error"] = f"CausalGraph failed: {str(e)}"
        state.setdefault("csod_causal_nodes", [])
        state.setdefault("csod_causal_edges", [])
        state.setdefault("csod_causal_graph_metadata", {})
        state.setdefault("csod_causal_retrieval_stats", {})
    
    return state

