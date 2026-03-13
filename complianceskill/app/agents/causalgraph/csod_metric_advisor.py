"""
CSOD Metric Advisor with Causal Graph Integration

Provides metric and KPI recommendations enriched with causal graph insights.
Uses the causal graph creator to understand relationships between metrics and
provide reasoning-based recommendations.

Based on csod_metric_advisor_workflow.py but enhanced with causal graph integration.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes import _csod_log_step, _llm_invoke, _parse_json_response
from app.agents.csod.csod_state import CSODWorkflowState
from app.core.dependencies import get_llm
from app.agents.causalgraph import causal_graph_creator_node, extract_causal_context

logger = logging.getLogger(__name__)

CSOD_State = CSODWorkflowState


# ============================================================================
# Metric Advisor Node with Causal Graph
# ============================================================================

def csod_metric_advisor_node(state: CSOD_State) -> CSOD_State:
    """
    CSOD Metric Advisor node that uses causal graph insights for recommendations.
    
    This node:
    1. Builds causal graph from user query and metric registry
    2. Extracts causal context (focus areas, hot paths, collider warnings)
    3. Uses causal insights to enhance metric recommendations
    4. Provides reasoning plan based on causal relationships
    
    Reads from state:
        user_query, csod_metric_recommendations, csod_retrieved_metrics,
        causal_vertical, csod_causal_graph_enabled
    
    Writes to state:
        csod_metric_recommendations (enriched with causal insights),
        csod_reasoning_plan, csod_advisor_output
    """
    try:
        user_query = state.get("user_query", "")
        causal_enabled = state.get("csod_causal_graph_enabled", False)
        
        if not causal_enabled:
            logger.info("Causal graph disabled, skipping metric advisor")
            return state
        
        # Step 1: Build causal graph using the causal graph creator
        # Bootstrap metric registry from CSOD recommendations
        metric_registry = state.get("csod_metric_recommendations", [])
        retrieved_metrics = state.get("csod_retrieved_metrics", [])
        
        # Merge metrics for causal graph
        all_metrics = []
        seen_ids = set()
        for m in metric_registry + retrieved_metrics:
            mid = m.get("metric_id") or m.get("id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                all_metrics.append(m)
        
        # Set up state for causal graph creator
        causal_state = {
            "user_query": user_query,
            "causal_vertical": state.get("causal_vertical", "lms"),
            "metric_registry": all_metrics,
            "causal_metric_registry": all_metrics,
            "cce_db_url": state.get("cce_db_url"),
            "causal_proposed_nodes": [],
            "causal_proposed_edges": [],
            "causal_graph_metadata": {},
            "causal_signals": {},
            "causal_graph_panel_data": None,
            "causal_node_index": {},
        }
        
        # Build causal graph
        causal_state = causal_graph_creator_node(causal_state)
        
        # Extract causal context
        proposed_nodes = causal_state.get("causal_proposed_nodes", [])
        proposed_edges = causal_state.get("causal_proposed_edges", [])
        graph_metadata = causal_state.get("causal_graph_metadata", {})
        causal_graph = causal_state.get("causal_graph", {})
        
        # Initialize causal_context to empty dict (will be populated if nodes/edges exist)
        causal_context = {}
        
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
            state["causal_proposed_nodes"] = proposed_nodes
            state["causal_proposed_edges"] = proposed_edges
            state["causal_graph_metadata"] = graph_metadata
        
        # Step 2: Enhance metric recommendations with causal insights
        enhanced_recommendations = _enhance_metrics_with_causal_insights(
            state=state,
            metric_recommendations=metric_registry,
            causal_nodes=proposed_nodes,
            causal_edges=proposed_edges,
            causal_context=causal_context if proposed_nodes else {},
        )
        
        state["csod_metric_recommendations"] = enhanced_recommendations
        
        # Step 3: Build reasoning plan
        reasoning_plan = _build_reasoning_plan(
            state=state,
            causal_nodes=proposed_nodes,
            causal_edges=proposed_edges,
            causal_context=causal_context if proposed_nodes else {},
        )
        
        state["csod_reasoning_plan"] = reasoning_plan
        
        # Step 3.5: Build metric/KPI relations from causal edges
        metric_kpi_relations = _build_metric_kpi_relations(
            enhanced_recommendations=enhanced_recommendations,
            causal_nodes=proposed_nodes,
            causal_edges=proposed_edges,
            kpi_recommendations=state.get("csod_kpi_recommendations", []),
        )
        state["csod_metric_kpi_relations"] = metric_kpi_relations
        
        # Step 4: Assemble advisor output
        advisor_output = {
            "intent_question": user_query,
            "metric_recommendations": enhanced_recommendations,
            "kpi_recommendations": state.get("csod_kpi_recommendations", []),
            "causal_graph": {
                "nodes": proposed_nodes,
                "edges": proposed_edges,
                "metadata": graph_metadata,
            } if proposed_nodes else None,
            "causal_insights": {
                "focus_area": causal_context.get("causal_signals", {}).get("derived_focus_area"),
                "complexity": causal_context.get("causal_signals", {}).get("derived_complexity"),
                "hot_paths": causal_context.get("causal_graph_panel_data", {}).get("hot_paths", []),
                "collider_warnings": [
                    n["node_id"] for n in proposed_nodes 
                    if n.get("collider_warning", False)
                ],
            } if proposed_nodes else {},
            "reasoning_plan": reasoning_plan,
            "metric_kpi_relations": metric_kpi_relations,
        }
        
        state["csod_advisor_output"] = advisor_output
        
        _csod_log_step(
            state,
            "csod_metric_advisor",
            "csod_metric_advisor",
            inputs={
                "query": user_query,
                "metric_count": len(metric_registry),
                "causal_enabled": causal_enabled,
            },
            outputs={
                "enhanced_metrics": len(enhanced_recommendations),
                "causal_nodes": len(proposed_nodes),
                "causal_edges": len(proposed_edges),
                "reasoning_plan": bool(reasoning_plan),
                "metric_kpi_relations": len(metric_kpi_relations.get("relations", [])),
            },
        )
        
        state["messages"].append(AIMessage(
            content=(
                f"[MetricAdvisor] Enhanced {len(enhanced_recommendations)} metrics with causal insights | "
                f"Causal graph: {len(proposed_nodes)} nodes, {len(proposed_edges)} edges | "
                f"Focus area: {causal_context.get('causal_signals', {}).get('derived_focus_area', 'N/A')}"
            )
        ))
        
    except Exception as e:
        logger.error(f"csod_metric_advisor_node failed: {e}", exc_info=True)
        state["error"] = f"MetricAdvisor failed: {str(e)}"
        state.setdefault("csod_metric_recommendations", [])
        state.setdefault("csod_reasoning_plan", {})
        state.setdefault("csod_metric_kpi_relations", {})
        state.setdefault("csod_advisor_output", {})
    
    return state


def _enhance_metrics_with_causal_insights(
    state: CSOD_State,
    metric_recommendations: List[Dict[str, Any]],
    causal_nodes: List[Dict[str, Any]],
    causal_edges: List[Dict[str, Any]],
    causal_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Enhance metric recommendations with causal graph insights.
    
    Adds:
    - Causal role (root, mediator, terminal, collider, confounder)
    - Causal relationships (which metrics drive/are driven by this)
    - Collider warnings
    - Hot path indicators
    """
    if not causal_nodes:
        return metric_recommendations
    
    # Build causal node index by metric_ref
    causal_index = {
        n.get("metric_ref", n["node_id"]): n
        for n in causal_nodes
    }
    
    # Build edge index by source/target
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
    
    enhanced = []
    for metric in metric_recommendations:
        metric_id = metric.get("metric_id") or metric.get("id", "")
        causal_node = causal_index.get(metric_id)
        
        if causal_node:
            # Add causal insights
            metric["causal_role"] = causal_node.get("node_type", "mediator")
            metric["causal_observable"] = causal_node.get("observable", True)
            metric["causal_temporal_grain"] = causal_node.get("temporal_grain", "monthly")
            
            if causal_node.get("collider_warning", False):
                metric["causal_warning"] = (
                    "COLLIDER: This metric is caused by multiple independent factors. "
                    "Do not use as a filter in cross-team comparisons."
                )
            
            # Find causal relationships
            node_id = causal_node["node_id"]
            upstream = edges_by_target.get(node_id, [])
            downstream = edges_by_source.get(node_id, [])
            
            metric["causal_upstream"] = [
                {
                    "metric_id": e.get("source_node", ""),
                    "relationship": e.get("direction", "positive"),
                    "lag_days": e.get("lag_window_days", 14),
                    "confidence": e.get("confidence_score", 0.5),
                }
                for e in upstream[:5]  # Top 5 upstream
            ]
            
            metric["causal_downstream"] = [
                {
                    "metric_id": e.get("target_node", ""),
                    "relationship": e.get("direction", "positive"),
                    "lag_days": e.get("lag_window_days", 14),
                    "confidence": e.get("confidence_score", 0.5),
                }
                for e in downstream[:5]  # Top 5 downstream
            ]
            
            # Check if on hot path
            hot_paths = causal_context.get("causal_graph_panel_data", {}).get("hot_paths", [])
            metric["on_hot_path"] = any(
                node_id in hp.get("path", [])
                for hp in hot_paths
            )
        else:
            # Metric not in causal graph - mark as unanalyzed
            metric["causal_role"] = "unanalyzed"
        
        enhanced.append(metric)
    
    return enhanced


def _build_metric_kpi_relations(
    enhanced_recommendations: List[Dict[str, Any]],
    causal_nodes: List[Dict[str, Any]],
    causal_edges: List[Dict[str, Any]],
    kpi_recommendations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build metric/KPI relations from causal graph edges.
    
    Extracts relationships between metrics and KPIs based on causal edges,
    providing a structured view of how metrics relate to each other.
    
    Returns:
        Dict with:
        - relations: List of relation objects with source, target, type, etc.
        - summary: Summary statistics
    """
    if not causal_edges:
        return {
            "relations": [],
            "summary": {
                "total_relations": 0,
                "metric_to_metric": 0,
                "metric_to_kpi": 0,
                "kpi_to_metric": 0,
            },
        }
    
    # Build metric/KPI ID maps
    metric_ids = {m.get("metric_id") or m.get("id", ""): m for m in enhanced_recommendations}
    kpi_ids = {k.get("kpi_id") or k.get("id", ""): k for k in kpi_recommendations}
    
    # Build node index for lookup
    node_index = {n["node_id"]: n for n in causal_nodes}
    
    relations = []
    metric_to_metric = 0
    metric_to_kpi = 0
    kpi_to_metric = 0
    
    for edge in causal_edges:
        source_id = edge.get("source_node", "")
        target_id = edge.get("target_node", "")
        
        if not source_id or not target_id:
            continue
        
        # Determine relation type
        source_is_metric = source_id in metric_ids
        source_is_kpi = source_id in kpi_ids
        target_is_metric = target_id in metric_ids
        target_is_kpi = target_id in kpi_ids
        
        relation_type = "metric_to_metric"
        if source_is_metric and target_is_kpi:
            relation_type = "metric_to_kpi"
            metric_to_kpi += 1
        elif source_is_kpi and target_is_metric:
            relation_type = "kpi_to_metric"
            kpi_to_metric += 1
        elif source_is_metric and target_is_metric:
            metric_to_metric += 1
        
        # Get node metadata
        source_node = node_index.get(source_id, {})
        target_node = node_index.get(target_id, {})
        
        relation = {
            "source_id": source_id,
            "source_name": source_node.get("metric_ref", source_id),
            "source_type": "kpi" if source_is_kpi else "metric",
            "target_id": target_id,
            "target_name": target_node.get("metric_ref", target_id),
            "target_type": "kpi" if target_is_kpi else "metric",
            "relation_type": relation_type,
            "direction": edge.get("direction", "positive"),
            "lag_days": edge.get("lag_window_days", 14),
            "confidence": edge.get("confidence_score", 0.5),
            "description": (
                f"{source_node.get('metric_ref', source_id)} "
                f"{'drives' if edge.get('direction') == 'positive' else 'inhibits'} "
                f"{target_node.get('metric_ref', target_id)}"
            ),
        }
        
        relations.append(relation)
    
    return {
        "relations": relations,
        "summary": {
            "total_relations": len(relations),
            "metric_to_metric": metric_to_metric,
            "metric_to_kpi": metric_to_kpi,
            "kpi_to_metric": kpi_to_metric,
        },
    }


def _build_reasoning_plan(
    state: CSOD_State,
    causal_nodes: List[Dict[str, Any]],
    causal_edges: List[Dict[str, Any]],
    causal_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a reasoning plan based on causal graph insights.
    
    Provides:
    - Analysis approach
    - Metric groups with causal relationships
    - Action triggers based on causal paths
    - Monitoring cadence recommendations
    - Gap acknowledgements
    """
    if not causal_nodes:
        return {
            "intent_question": state.get("user_query", ""),
            "analysis_approach": "Standard metric analysis (causal graph not available)",
            "metric_groups": [],
            "action_triggers": [],
            "monitoring_cadence": {},
            "gap_acknowledgements": [],
        }
    
    user_query = state.get("user_query", "")
    causal_signals = causal_context.get("causal_signals", {})
    hot_paths = causal_context.get("causal_graph_panel_data", {}).get("hot_paths", [])
    
    # Identify terminal nodes (outcomes)
    terminal_nodes = [n for n in causal_nodes if n.get("node_type") == "terminal"]
    root_nodes = [n for n in causal_nodes if n.get("node_type") == "root"]
    collider_nodes = [n for n in causal_nodes if n.get("collider_warning", False)]
    
    # Build metric groups from causal structure
    metric_groups = []
    if terminal_nodes:
        for terminal in terminal_nodes[:3]:  # Top 3 terminals
            # Find paths to this terminal
            terminal_id = terminal["node_id"]
            paths_to_terminal = [
                hp for hp in hot_paths
                if terminal_id in hp.get("path", [])
            ]
            
            # Collect metrics on paths
            related_metrics = set()
            for hp in paths_to_terminal:
                for node_id in hp.get("path", []):
                    related_metrics.add(node_id)
            
            metric_groups.append({
                "group_id": f"terminal_{terminal_id}",
                "group_name": f"Path to {terminal.get('metric_ref', terminal_id)}",
                "focus_area": terminal.get("category", ""),
                "metrics": list(related_metrics)[:10],
                "terminal_metric": terminal_id,
                "narrative": (
                    f"This group tracks the causal pathway leading to {terminal.get('metric_ref', terminal_id)}. "
                    f"Monitor upstream metrics to predict changes in this outcome."
                ),
                "monitoring_cadence": terminal.get("temporal_grain", "monthly"),
                "leading_indicators": [n["node_id"] for n in root_nodes if n["node_id"] in related_metrics],
                "lagging_indicators": [terminal_id],
            })
    
    # Build action triggers from causal edges
    action_triggers = []
    for edge in causal_edges[:10]:  # Top 10 edges
        if edge.get("confidence_score", 0) >= 0.65:
            action_triggers.append({
                "trigger_metric": edge.get("source_node", ""),
                "outcome_metric": edge.get("target_node", ""),
                "lag_days": edge.get("lag_window_days", 14),
                "direction": edge.get("direction", "positive"),
                "recommended_action": (
                    f"Monitor {edge.get('source_node', '')} for early warning. "
                    f"Changes will affect {edge.get('target_node', '')} within {edge.get('lag_window_days', 14)} days."
                ),
                "confidence": edge.get("confidence_score", 0.5),
            })
    
    # Collider warnings
    gap_acknowledgements = []
    if collider_nodes:
        for collider in collider_nodes:
            gap_acknowledgements.append({
                "type": "collider_warning",
                "metric_id": collider["node_id"],
                "message": (
                    f"{collider.get('metric_ref', collider['node_id'])} is a collider - "
                    "caused by multiple independent factors. Do not use as a filter."
                ),
            })
    
    # Unobservable nodes
    unobservable = [n for n in causal_nodes if not n.get("observable", True)]
    if unobservable:
        gap_acknowledgements.append({
            "type": "unobservable_metrics",
            "count": len(unobservable),
            "message": (
                f"{len(unobservable)} metrics in the causal model are not directly observable. "
                "Consider proxy metrics or additional data sources."
            ),
        })
    
    return {
        "intent_question": user_query,
        "analysis_approach": (
            f"Causal graph analysis with {len(causal_nodes)} nodes and {len(causal_edges)} edges. "
            f"Focus area: {causal_signals.get('derived_focus_area', 'N/A')}. "
            f"Complexity: {causal_signals.get('derived_complexity', 'medium')}."
        ),
        "metric_groups": metric_groups,
        "action_triggers": action_triggers,
        "monitoring_cadence": {
            "primary": causal_signals.get("derived_focus_area", "monthly"),
            "leading_indicators": "weekly",
            "outcomes": "monthly",
        },
        "gap_acknowledgements": gap_acknowledgements,
        "priority_order": [
            n["node_id"] for n in terminal_nodes[:5]  # Prioritize outcomes
        ],
    }
