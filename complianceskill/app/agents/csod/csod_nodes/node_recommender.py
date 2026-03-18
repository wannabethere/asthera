"""Metrics recommender."""
import json

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.csod.csod_tool_integration import (
    csod_format_scored_context_for_prompt,
    csod_get_tools_for_agent,
)
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)

def csod_metrics_recommender_node(state: CSOD_State) -> CSOD_State:
    """
    Generates metric recommendations with optional gold plan.
    
    Uses decision tree enriched metrics to guide recommendations based on:
    - use_case (e.g., lms_learning_target, soc2_audit)
    - goal (e.g., training_completion, compliance_posture)
    - focus_area (e.g., learning_management, compliance_training)
    - audience, timeframe, metric_type
    
    Used for intents: metrics_dashboard_plan, metrics_recommender_with_gold_plan
    """
    try:
        logger.info(
            "[CSOD pipeline] csod_metrics_recommender: generating metric "
            "recommendations (intent=%s)",
            state.get("csod_intent", ""),
        )
        try:
            prompt_text = load_prompt("03_metrics_recommender", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError as e:
            logger.error(f"CSOD metrics recommender prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD metrics recommender prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '03_metrics_recommender.md'}. "
                f"Please ensure the prompt file exists."
            )

        tools = csod_get_tools_for_agent("csod_metrics_recommender", state=state, conditional=True)
        use_tool_calling = bool(tools)

        scored_context = state.get("csod_scored_context", {})
        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")

        # ── Include causal graph context if available ────────────────────
        causal_graph_context = ""
        causal_nodes = state.get("csod_causal_nodes", [])
        causal_edges = state.get("csod_causal_edges", [])
        causal_metadata = state.get("csod_causal_graph_metadata", {})
        causal_signals = state.get("causal_signals", {})
        causal_node_index = state.get("causal_node_index", {})
        
        if causal_nodes or causal_edges:
            # Get hot paths from panel data
            panel_data = state.get("causal_graph_panel_data", {})
            hot_paths = panel_data.get("hot_paths", []) if panel_data else []
            
            causal_graph_context = f"""
CAUSAL GRAPH CONTEXT (from causal graph creator):
- Nodes assembled: {len(causal_nodes)}
- Edges assembled: {len(causal_edges)}
- Focus area: {causal_signals.get('derived_focus_area', 'N/A')}
- Complexity: {causal_signals.get('derived_complexity', 'medium')}
- Terminal nodes (outcomes): {causal_metadata.get('terminal_node_ids', [])}
- Collider warnings: {causal_metadata.get('collider_node_ids', [])}
- Confounders: {causal_metadata.get('confounder_node_ids', [])}
- Hot paths: {len(hot_paths)} identified

Top causal nodes (by node type):
{json.dumps([{
    "node_id": n.get("node_id", ""),
    "metric_ref": n.get("metric_ref", ""),
    "category": n.get("category", ""),
    "node_type": n.get("node_type", ""),
    "is_outcome": n.get("is_outcome", False),
    "collider_warning": n.get("collider_warning", False),
    "description": n.get("description", "")[:200],
    "observable": n.get("observable", True),
} for n in sorted(causal_nodes, key=lambda n: (
    0 if n.get("node_type") == "terminal" else
    1 if n.get("node_type") == "root" else
    2
))[:15]], indent=2)}

Top causal edges (by confidence):
{json.dumps([{
    "edge_id": e.get("edge_id", ""),
    "source": e.get("source_node", ""),
    "target": e.get("target_node", ""),
    "direction": e.get("direction", ""),
    "confidence": e.get("confidence_score", 0),
    "lag_days": e.get("lag_window_days", 14),
    "mechanism": e.get("mechanism", "")[:150],
} for e in sorted(causal_edges, key=lambda e: e.get("confidence_score", 0), reverse=True)[:15]], indent=2)}

Hot paths (root → terminal causal chains):
{json.dumps([{
    "path": hp.get("path", []),
    "path_confidence": hp.get("path_confidence", 0),
    "lag_total_days": hp.get("lag_total_days", 0),
} for hp in hot_paths[:3]], indent=2)}

IMPORTANT: Use causal graph insights to:
1. Prioritize metrics that are terminal nodes (outcomes) - these are what the business cares about
2. Identify confounders that must be controlled when comparing metrics
3. Avoid using collider nodes as filters - they create spurious associations
4. Consider lag windows when recommending time-based metrics
5. Use mechanism descriptions to understand why metrics are causally related
6. Follow hot paths - these are the most confident causal chains from root causes to outcomes
7. Use causal_node_index to override chart types (terminal → gauge, root → line_trend, etc.)
"""
        
        # ── Include decision tree context if available ────────────────────
        decision_tree_context = ""
        dt_decisions = state.get("dt_metric_decisions", {})
        dt_scored_metrics = state.get("dt_scored_metrics", [])
        dt_metric_groups = state.get("dt_metric_groups", [])
        
        if dt_decisions:
            decision_tree_context = f"""
DECISION TREE CONTEXT:
- Use Case: {dt_decisions.get('use_case', 'N/A')} (confidence: {dt_decisions.get('use_case_confidence', 0):.2f})
- Goal: {dt_decisions.get('goal', 'N/A')} (confidence: {dt_decisions.get('goal_confidence', 0):.2f})
- Focus Area: {dt_decisions.get('focus_area', 'N/A')} (confidence: {dt_decisions.get('focus_area_confidence', 0):.2f})
- Audience: {dt_decisions.get('audience', 'N/A')} (confidence: {dt_decisions.get('audience_confidence', 0):.2f})
- Timeframe: {dt_decisions.get('timeframe', 'N/A')} (confidence: {dt_decisions.get('timeframe_confidence', 0):.2f})
- Metric Type: {dt_decisions.get('metric_type', 'N/A')} (confidence: {dt_decisions.get('metric_type_confidence', 0):.2f})
- Overall Confidence: {dt_decisions.get('auto_resolve_confidence', 0):.2f}
"""
        
        if dt_scored_metrics:
            # Use decision tree scored metrics instead of raw resolved_metrics
            # These are already ranked by decision tree alignment
            top_scored = sorted(dt_scored_metrics, key=lambda m: m.get("composite_score", 0), reverse=True)[:15]
            decision_tree_context += f"""
DECISION TREE SCORED METRICS (top {len(top_scored)} by composite score):
{json.dumps([{
    "metric_id": m.get("metric_id") or m.get("id", ""),
    "name": m.get("name", ""),
    "composite_score": m.get("composite_score", 0),
    "score_breakdown": m.get("score_breakdown", {}),
    "goals": m.get("goals", []),
    "use_cases": m.get("use_cases", []),
    "focus_areas": m.get("focus_areas", []),
} for m in top_scored], indent=2)}
"""
        
        if dt_metric_groups:
            decision_tree_context += f"""
DECISION TREE METRIC GROUPS ({len(dt_metric_groups)} groups):
{json.dumps([{
    "group_name": g.get("group_name", ""),
    "goal": g.get("goal", ""),
    "total_assigned": g.get("total_assigned", 0),
    "top_metrics": [m.get("metric_id") or m.get("id", "") for m in g.get("metrics", [])[:5]],
} for g in dt_metric_groups], indent=2)}
"""

        context_str = csod_format_scored_context_for_prompt(
            scored_context,
            include_schemas=True,
            include_metrics=True,
            include_kpis=True,
        )

        human_message = f"""User Query: {user_query}
Intent: {intent}
{causal_graph_context}
{decision_tree_context}
SCORED CONTEXT:
{context_str}

Generate metric recommendations following your instructions.
Use the decision tree context to prioritize metrics that align with the resolved use_case, goal, and focus_area.
Prioritize metrics from the decision tree scored metrics list when available.
Note: Medallion plan will be generated separately by csod_medallion_planner_node.
Note: Data science insights will be generated separately by csod_data_science_insights_enricher node.

Return JSON with metric_recommendations, kpi_recommendations, and table_recommendations only."""

        response_content = _llm_invoke(
            state, "csod_metrics_recommender", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=10,
        )

        result = _parse_json_response(response_content, {})

        state["csod_metric_recommendations"] = result.get("metric_recommendations", [])
        state["csod_kpi_recommendations"] = result.get("kpi_recommendations", [])
        state["csod_table_recommendations"] = result.get("table_recommendations", [])
        
        # Note: medallion_plan is now generated by a separate csod_medallion_planner_node
        # Note: data_science_insights are now generated by a separate csod_data_science_insights_enricher node
        # Do not generate them here

        _csod_log_step(
            state, "csod_metrics_recommendation", "csod_metrics_recommender",
            inputs={
                "intent": intent,
                "scored_metrics_count": len(scored_context.get("scored_metrics", [])),
                "decision_tree_enabled": bool(dt_decisions),
                "decision_tree_use_case": dt_decisions.get("use_case", ""),
                "decision_tree_goal": dt_decisions.get("goal", ""),
            },
            outputs={
                "metric_recommendations_count": len(state["csod_metric_recommendations"]),
                "kpi_recommendations_count": len(state["csod_kpi_recommendations"]),
                "table_recommendations_count": len(state["csod_table_recommendations"]),
                "decision_tree_groups_used": len(dt_metric_groups),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Metrics recommender: {len(state['csod_metric_recommendations'])} metrics, "
                f"{len(state['csod_kpi_recommendations'])} KPIs"
            )
        ))

    except Exception as e:
        logger.error(f"csod_metrics_recommender_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD metrics recommender failed: {str(e)}"
        state.setdefault("csod_metric_recommendations", [])
        state.setdefault("csod_kpi_recommendations", [])

    return state
