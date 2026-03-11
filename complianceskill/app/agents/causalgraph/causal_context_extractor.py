"""
Causal Context Extractor — Bridge Layer

Translates causal graph structure into exactly the signals the dashboard decision tree
and metrics recommender expect. This is the contract boundary between causal engine
and CSOD workflow.

Based on causal_dashboard_design_doc.md Section 7 (Bridge Layer).
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def extract_causal_context(
    causal_graph: Dict[str, Any],
    graph_metadata: Dict[str, Any],
    proposed_nodes: List[Dict[str, Any]],
    proposed_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extract causal context signals from the assembled graph.
    
    Returns:
        Dict with keys:
        - causal_signals: derived decision signals (focus_area, complexity, etc.)
        - causal_graph_boost_focus_areas: focus areas confirmed by causal graph
        - causal_graph_panel_data: graph data for dashboard panel
        - causal_node_index: metric_ref → node metadata mapping
    """
    try:
        # Extract terminal nodes (outcomes)
        terminal_nodes = [
            n for n in proposed_nodes 
            if n.get("node_type") == "terminal" or n.get("is_outcome", False)
        ]
        
        # Extract root nodes
        root_nodes = [
            n for n in proposed_nodes 
            if n.get("node_type") == "root"
        ]
        
        # Extract colliders
        collider_nodes = [
            n for n in proposed_nodes 
            if n.get("node_type") == "collider" or n.get("collider_warning", False)
        ]
        
        # Extract confounders
        confounder_nodes = [
            n for n in proposed_nodes 
            if n.get("node_type") == "confounder"
        ]
        
        # Derive focus area from primary terminal node category
        derived_focus_area = _derive_focus_area(terminal_nodes)
        
        # Derive complexity from graph depth and confidence
        derived_complexity = _derive_complexity(proposed_edges, graph_metadata)
        
        # Derive metric profile hint
        causal_metric_profile_hint = _derive_metric_profile(proposed_nodes)
        
        # Build hot paths
        hot_paths = _build_hot_paths(proposed_nodes, proposed_edges, root_nodes, terminal_nodes)
        
        # Build latent node warnings
        latent_nodes = [
            {
                "node_id": n["node_id"],
                "metric_ref": n.get("metric_ref", ""),
                "latent_proxy": n.get("latent_proxy"),
                "missing_reason": "No silver table available",
            }
            for n in proposed_nodes
            if not n.get("observable", True)
        ]
        
        # Build causal node index (metric_ref → node metadata)
        causal_node_index = {
            n.get("metric_ref", n["node_id"]): {
                "node_id": n["node_id"],
                "node_type": n.get("node_type", "mediator"),
                "category": n.get("category", ""),
                "temporal_grain": n.get("temporal_grain", "monthly"),
                "collider_warning": n.get("collider_warning", False),
                "is_outcome": n.get("is_outcome", False),
            }
            for n in proposed_nodes
        }
        
        # Determine if causal graph should be shown
        mean_confidence = graph_metadata.get("mean_edge_confidence", 0.5)
        node_count = len(proposed_nodes)
        observable_ratio = graph_metadata.get("observable_node_ratio", 0.0)
        show_causal_graph = (
            mean_confidence > 0.55 and
            node_count >= 4 and
            observable_ratio > 0.40
        )
        
        # Build covered focus areas (from terminal node categories)
        covered_focus_areas = list({
            _category_to_focus_area(n.get("category", ""))
            for n in terminal_nodes
            if n.get("category")
        })
        
        return {
            "causal_signals": {
                "derived_focus_area": derived_focus_area,
                "derived_complexity": derived_complexity,
                "causal_metric_profile_hint": causal_metric_profile_hint,
                "show_causal_graph": show_causal_graph,
            },
            "causal_graph_boost_focus_areas": covered_focus_areas,
            "causal_graph_panel_data": {
                "graph_data": causal_graph,
                "hot_paths": hot_paths,
                "latent_nodes": latent_nodes,
                "graph_confidence": mean_confidence,
                "observable_ratio": observable_ratio,
                "terminal_node_ids": [n["node_id"] for n in terminal_nodes],
                "collider_node_ids": [n["node_id"] for n in collider_nodes],
                "confounder_node_ids": [n["node_id"] for n in confounder_nodes],
            } if show_causal_graph else None,
            "causal_node_index": causal_node_index,
        }
    
    except Exception as e:
        logger.error(f"extract_causal_context failed: {e}", exc_info=True)
        return {
            "causal_signals": {},
            "causal_graph_boost_focus_areas": [],
            "causal_graph_panel_data": None,
            "causal_node_index": {},
        }


def _derive_focus_area(terminal_nodes: List[Dict[str, Any]]) -> Optional[str]:
    """
    Derive focus area from primary terminal node category.
    
    Mapping from terminal node category → focus_area vocabulary.
    """
    if not terminal_nodes:
        return None
    
    # Sort by observable=False first, then in_degree (most causally complex)
    # For now, use first terminal's category
    primary_terminal = terminal_nodes[0]
    category = primary_terminal.get("category", "")
    
    # Category → focus_area mapping
    category_lower = category.lower()
    if "attrition" in category_lower or "retention" in category_lower:
        return "risk_exposure"
    elif "compliance" in category_lower:
        return "compliance_posture"
    elif "vulnerability" in category_lower:
        return "vulnerability_management"
    elif "incident" in category_lower:
        return "incident_response"
    elif "training" in category_lower or "learning" in category_lower:
        return "training_completion"
    elif "engagement" in category_lower:
        return "learner_engagement"
    elif "access" in category_lower:
        return "access_control"
    elif "pipeline" in category_lower:
        return "pipeline_health"
    else:
        return "compliance_posture"  # default


def _derive_complexity(
    proposed_edges: List[Dict[str, Any]],
    graph_metadata: Dict[str, Any],
) -> str:
    """
    Derive complexity from graph depth × edge confidence.
    
    Formula:
        max_causal_path_depth ≥ 4 AND mean_confidence ≥ 0.65  → "high"
        max_causal_path_depth ≥ 2 AND mean_confidence ≥ 0.45  → "medium"
        otherwise                                               → "low"
    """
    mean_confidence = graph_metadata.get("mean_edge_confidence", 0.5)
    
    # Estimate max path depth from edge count and node count
    # Simple heuristic: if we have many edges relative to nodes, paths are longer
    node_count = graph_metadata.get("node_count", 0)
    edge_count = graph_metadata.get("edge_count", 0)
    
    if node_count == 0:
        return "low"
    
    # Rough estimate: avg edges per node gives us path depth hint
    avg_edges_per_node = edge_count / node_count if node_count > 0 else 0
    estimated_depth = int(avg_edges_per_node * 1.5)  # heuristic
    
    if estimated_depth >= 4 and mean_confidence >= 0.65:
        return "high"
    elif estimated_depth >= 2 and mean_confidence >= 0.45:
        return "medium"
    else:
        return "low"


def _derive_metric_profile(proposed_nodes: List[Dict[str, Any]]) -> str:
    """
    Derive metric profile hint from dominant temporal grain.
    
    Formula:
        dominant_grain = daily AND observable_ratio > 0.70   → "trend_heavy"
        dominant_grain = monthly OR quarterly                 → "scorecard"
        otherwise                                             → "mixed"
    """
    if not proposed_nodes:
        return "mixed"
    
    # Count grains
    grain_counts = {}
    observable_count = 0
    for n in proposed_nodes:
        grain = n.get("temporal_grain", "monthly")
        grain_counts[grain] = grain_counts.get(grain, 0) + 1
        if n.get("observable", True):
            observable_count += 1
    
    observable_ratio = observable_count / len(proposed_nodes) if proposed_nodes else 0
    
    # Find dominant grain
    dominant_grain = max(grain_counts.items(), key=lambda x: x[1])[0] if grain_counts else "monthly"
    
    if dominant_grain == "daily" and observable_ratio > 0.70:
        return "trend_heavy"
    elif dominant_grain in ("monthly", "quarterly"):
        return "scorecard"
    else:
        return "mixed"


def _build_hot_paths(
    proposed_nodes: List[Dict[str, Any]],
    proposed_edges: List[Dict[str, Any]],
    root_nodes: List[Dict[str, Any]],
    terminal_nodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build hot paths: top 3 root-to-terminal paths sorted by mean edge confidence.
    """
    if not root_nodes or not terminal_nodes:
        return []
    
    # Build a simple graph structure
    node_dict = {n["node_id"]: n for n in proposed_nodes}
    edges_by_source = {}
    for e in proposed_edges:
        src = e.get("source_node", "")
        if src not in edges_by_source:
            edges_by_source[src] = []
        edges_by_source[src].append(e)
    
    hot_paths = []
    
    # Find paths from roots to terminals
    for root in root_nodes[:3]:  # Limit to top 3 roots
        root_id = root["node_id"]
        for terminal in terminal_nodes[:3]:  # Limit to top 3 terminals
            terminal_id = terminal["node_id"]
            
            # Simple path finding (DFS)
            path = _find_path(root_id, terminal_id, edges_by_source, node_dict)
            if path and len(path) > 1:
                # Calculate path confidence and lag
                path_confidence = _calculate_path_confidence(path, proposed_edges)
                lag_total = _calculate_path_lag(path, proposed_edges)
                
                hot_paths.append({
                    "path": path,
                    "path_confidence": path_confidence,
                    "lag_total_days": lag_total,
                })
    
    # Sort by confidence and return top 3
    hot_paths.sort(key=lambda p: p["path_confidence"], reverse=True)
    return hot_paths[:3]


def _find_path(
    start: str,
    end: str,
    edges_by_source: Dict[str, List[Dict[str, Any]]],
    node_dict: Dict[str, Dict[str, Any]],
    visited: Optional[set] = None,
    current_path: Optional[List[str]] = None,
) -> Optional[List[str]]:
    """Simple DFS path finding."""
    if visited is None:
        visited = set()
    if current_path is None:
        current_path = []
    
    if start == end:
        return current_path + [end]
    
    if start in visited:
        return None
    
    visited.add(start)
    current_path.append(start)
    
    for edge in edges_by_source.get(start, []):
        target = edge.get("target_node", "")
        if target in node_dict:
            result = _find_path(target, end, edges_by_source, node_dict, visited.copy(), current_path.copy())
            if result:
                return result
    
    return None


def _calculate_path_confidence(path: List[str], proposed_edges: List[Dict[str, Any]]) -> float:
    """Calculate mean confidence along a path."""
    if len(path) < 2:
        return 0.0
    
    confidences = []
    for i in range(len(path) - 1):
        src, tgt = path[i], path[i + 1]
        for e in proposed_edges:
            if (e.get("source_node", "") == src and 
                e.get("target_node", "") == tgt):
                confidences.append(e.get("confidence_score", 0.5))
                break
    
    return sum(confidences) / len(confidences) if confidences else 0.0


def _calculate_path_lag(path: List[str], proposed_edges: List[Dict[str, Any]]) -> int:
    """Calculate total lag along a path."""
    if len(path) < 2:
        return 0
    
    total_lag = 0
    for i in range(len(path) - 1):
        src, tgt = path[i], path[i + 1]
        for e in proposed_edges:
            if (e.get("source_node", "") == src and 
                e.get("target_node", "") == tgt):
                total_lag += e.get("lag_window_days", 14)
                break
    
    return total_lag


def _category_to_focus_area(category: str) -> str:
    """Map category to focus area."""
    category_lower = category.lower()
    if "attrition" in category_lower or "retention" in category_lower:
        return "risk_exposure"
    elif "compliance" in category_lower:
        return "compliance_posture"
    elif "vulnerability" in category_lower:
        return "vulnerability_management"
    elif "incident" in category_lower:
        return "incident_response"
    elif "training" in category_lower or "learning" in category_lower:
        return "training_completion"
    elif "engagement" in category_lower:
        return "learner_engagement"
    elif "access" in category_lower:
        return "access_control"
    elif "pipeline" in category_lower:
        return "pipeline_health"
    else:
        return "compliance_posture"  # default
