"""
CSOD Workflow Integration for Causal Graph Creator

Extends the CSOD workflow to integrate the causal graph creator module.
This provides a seamless integration pattern similar to csod_workflow_integration.py
but uses the new causalgraph module.

Integration points:
1. Adds causal_graph_creator node after metrics_recommender
2. Routes based on causal_graph_enabled feature flag
3. Enriches metrics recommender with causal insights
4. Provides causal context for dashboard generation
"""
import logging
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage

from app.agents.csod.csod_state import CSODWorkflowState
from app.agents.causalgraph import causal_graph_creator_node

logger = logging.getLogger(__name__)

CSOD_State = CSODWorkflowState


# ============================================================================
# CSOD Causal Graph Entry Node
# ============================================================================

def csod_causal_graph_entry_node(state: CSOD_State) -> CSOD_State:
    """
    Entry node that bridges CSOD workflow state to causal graph creator.
    
    This node:
    1. Bootstraps causal graph state from CSOD recommendations
    2. Calls causal_graph_creator_node
    3. Maps causal graph outputs back to CSOD state fields
    4. Enriches metrics recommender with causal insights
    
    Integration contract:
        Input from CSOD:
            - csod_metric_recommendations → causal_metric_registry
            - csod_retrieved_metrics → additional metrics
            - csod_resolved_schemas → causal_schema_definitions
            - csod_data_sources_in_scope → causal_available_data_sources
        
        Output to CSOD:
            - causal_proposed_nodes → csod_causal_nodes
            - causal_proposed_edges → csod_causal_edges
            - causal_graph_metadata → csod_causal_graph_metadata
            - causal_signals → for metrics recommender enrichment
            - causal_node_index → for chart type overrides
    """
    try:
        causal_enabled = state.get("csod_causal_graph_enabled", False)
        if not causal_enabled:
            logger.debug("Causal graph disabled, skipping entry node")
            return state
        
        user_query = state.get("user_query", "")
        if not user_query:
            logger.warning("No user query for causal graph creation")
            return state
        
        # Bootstrap metric registry from CSOD recommendations
        metric_recommendations = state.get("csod_metric_recommendations", [])
        retrieved_metrics = state.get("csod_retrieved_metrics", [])
        
        # Merge and deduplicate
        all_metrics = []
        seen_ids = set()
        for m in metric_recommendations + retrieved_metrics:
            mid = m.get("metric_id") or m.get("id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                all_metrics.append(m)
        
        # Build causal graph state
        causal_state = {
            "user_query": user_query,
            "causal_vertical": state.get("causal_vertical", "lms"),
            "metric_registry": all_metrics,
            "causal_metric_registry": all_metrics,
            "schema_definitions": {},  # Can be bootstrapped from csod_resolved_schemas
            "corpus": [],  # Can be loaded from config
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
        state["csod_causal_nodes"] = causal_state.get("causal_proposed_nodes", [])
        state["csod_causal_edges"] = causal_state.get("causal_proposed_edges", [])
        state["csod_causal_graph_metadata"] = causal_state.get("causal_graph_metadata", {})
        state["csod_causal_retrieval_stats"] = causal_state.get("causal_retrieval_stats", {})
        
        # Causal context for downstream nodes
        state["causal_signals"] = causal_state.get("causal_signals", {})
        state["causal_graph_boost_focus_areas"] = causal_state.get("causal_graph_boost_focus_areas", [])
        state["causal_graph_panel_data"] = causal_state.get("causal_graph_panel_data")
        state["causal_node_index"] = causal_state.get("causal_node_index", {})
        
        # Update messages
        if "messages" in causal_state:
            state["messages"].extend(causal_state["messages"])
        
        logger.info(
            f"csod_causal_graph_entry_node: Created graph with "
            f"{len(state['csod_causal_nodes'])} nodes, "
            f"{len(state['csod_causal_edges'])} edges"
        )
        
    except Exception as e:
        logger.error(f"csod_causal_graph_entry_node failed: {e}", exc_info=True)
        state["error"] = f"CausalGraphEntry failed: {str(e)}"
        state.setdefault("csod_causal_nodes", [])
        state.setdefault("csod_causal_edges", [])
        state.setdefault("csod_causal_graph_metadata", {})
    
    return state


# ============================================================================
# Enhanced Metrics Recommender with Causal Insights
# ============================================================================

def enrich_metrics_with_causal_insights(
    state: CSOD_State,
    metric_recommendations: list,
) -> list:
    """
    Enrich metric recommendations with causal graph insights.
    
    Adds causal role, relationships, and warnings to each metric.
    """
    causal_nodes = state.get("csod_causal_nodes", [])
    causal_edges = state.get("csod_causal_edges", [])
    causal_node_index = state.get("causal_node_index", {})
    
    if not causal_nodes:
        return metric_recommendations
    
    # Build lookup
    node_by_metric_ref = {
        n.get("metric_ref", n["node_id"]): n
        for n in causal_nodes
    }
    
    # Build edge lookups
    edges_by_source = {}
    edges_by_target = {}
    for e in causal_edges:
        src = e.get("source_node", "")
        tgt = e.get("target_node", "")
        if src not in edges_by_source:
            edges_by_source[src] = []
        edges_by_source[src].append(e)
        if tgt not in edges_by_target:
            edges_by_target[tgt] = []
        edges_by_target[tgt].append(e)
    
    enriched = []
    for metric in metric_recommendations:
        metric_id = metric.get("metric_id") or metric.get("id", "")
        node_info = causal_node_index.get(metric_id) or node_by_metric_ref.get(metric_id)
        
        if node_info:
            # Add causal metadata
            if isinstance(node_info, dict):
                metric["causal_role"] = node_info.get("node_type", "mediator")
                metric["causal_observable"] = node_info.get("observable", True)
                metric["causal_temporal_grain"] = node_info.get("temporal_grain", "monthly")
                
                if node_info.get("collider_warning", False):
                    metric["causal_warning"] = (
                        "COLLIDER: This metric is caused by multiple independent factors. "
                        "Do not use as a filter in cross-team comparisons."
                    )
                
                # Add chart type hint
                if node_info.get("chart_type_hint"):
                    metric["recommended_chart_type"] = node_info["chart_type_hint"]
        
        enriched.append(metric)
    
    return enriched
