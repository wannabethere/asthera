"""
Metric Decision Tree — LangGraph Node Integration

Two nodes that plug into the DT workflow:

1. dt_metric_decision_node
   - Auto-resolves decisions from state + user query
   - Scores all resolved_metrics against decisions
   - Groups metrics into goal-aligned insight groups
   - Stores results in state for downstream consumption

2. dt_metric_decision_interactive_node (optional)
   - Emits clarification questions when auto-resolve confidence is low
   - Consumes user responses and re-runs scoring with updated decisions
   - Only activated when dt_metric_interactive_mode=True and confidence < 0.6

Insertion point in dt_workflow.py:
    calculation_planner → dt_metric_decision_node → dt_scoring_validator

Both nodes follow the same patterns as existing dt_nodes.py (logging,
error handling, state mutation, AIMessage appending).
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


# ============================================================================
# Reusable Tool/Helper Function
# ============================================================================

def enrich_metrics_with_decision_tree(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reusable tool function to enrich metrics with decision tree logic.
    
    This function can be called from any workflow node to:
    1. Resolve decisions (auto-resolve from state + user query)
    2. Score all resolved_metrics against decisions
    3. Group metrics into goal-aligned insight groups
    4. Store results in state for downstream consumption
    
    Args:
        state: State dict containing resolved_metrics, controls, risks, etc.
    
    Returns:
        Updated state dict with decision tree enrichments:
        - dt_metric_decisions: resolved decision values with confidence
        - dt_scored_metrics: all metrics with composite scores
        - dt_metric_groups: grouped metric recommendations
        - dt_metric_coverage_report: coverage validation report
        - dt_metric_dropped: metrics below threshold
    
    Usage:
        # From any node or workflow:
        from app.agents.decision_trees.dt_metric_decision_nodes import enrich_metrics_with_decision_tree
        state = enrich_metrics_with_decision_tree(state)
        
        # Or disable it in state:
        state["dt_use_decision_tree"] = False
    """
    from .metric_decision_tree import resolve_decisions
    from .metric_scoring import score_all_metrics, apply_thresholds
    from .metric_grouping import group_metrics, get_required_groups

    try:
        # ── Phase 1: Resolve decisions ───────────────────────────────
        decisions = resolve_decisions(state)
        state["dt_metric_decisions"] = decisions

        logger.info(
            f"enrich_metrics_with_decision_tree: Resolved decisions — "
            f"use_case={decisions.get('use_case')}, "
            f"goal={decisions.get('goal')}, "
            f"focus_area={decisions.get('focus_area')}, "
            f"confidence={decisions.get('auto_resolve_confidence', 0):.2f}, "
            f"unresolved={decisions.get('unresolved', [])}"
        )

        # ── Phase 2: Merge LLM enrichments into metrics (if available) ──
        resolved_metrics = state.get("resolved_metrics", [])
        llm_enrichments = state.get("dt_generated_enrichments", [])
        
        # Merge enrichments into metrics
        if llm_enrichments:
            enrichment_map = {e.get("metric_id", ""): e for e in llm_enrichments}
            for metric in resolved_metrics:
                metric_id = metric.get("id") or metric.get("metric_id", "")
                enrichment = enrichment_map.get(metric_id)
                if enrichment:
                    # Merge enrichment fields
                    enrich_data = enrichment.get("enrichment", enrichment)
                    if enrich_data.get("goals"):
                        metric["goals"] = enrich_data["goals"].get("values", [])
                    if enrich_data.get("focus_areas"):
                        metric["focus_areas"] = enrich_data["focus_areas"].get("values", [])
                    if enrich_data.get("use_cases"):
                        metric["use_cases"] = enrich_data["use_cases"].get("values", [])
                    if enrich_data.get("audience_levels"):
                        metric["audience_levels"] = enrich_data["audience_levels"].get("values", [])
                    if enrich_data.get("metric_type"):
                        metric["metric_type"] = enrich_data["metric_type"].get("value", "")
                    if enrich_data.get("aggregation_windows"):
                        metric["aggregation_windows"] = enrich_data["aggregation_windows"].get("values", [])
                    if enrich_data.get("group_affinity"):
                        metric["group_affinity"] = enrich_data["group_affinity"].get("values", [])
                    # Store hints for scoring
                    if enrich_data.get("control_evidence_hints"):
                        metric["control_evidence_hints"] = enrich_data["control_evidence_hints"]
                    if enrich_data.get("risk_quantification_hints"):
                        metric["risk_quantification_hints"] = enrich_data["risk_quantification_hints"]
                    if enrich_data.get("scenario_detection_hints"):
                        metric["scenario_detection_hints"] = enrich_data["scenario_detection_hints"]
                    metric["enrichment_source"] = "llm_generated"
        
        # ── Phase 3: Score all metrics ───────────────────────────────
        scored_context = state.get("dt_scored_context", {})
        data_sources_in_scope = (
            state.get("dt_data_sources_in_scope", [])
            or state.get("selected_data_sources", [])
        )
        
        # Merge LLM-generated taxonomy into scored_context for control scoring
        llm_taxonomy = state.get("dt_generated_taxonomy", [])
        if llm_taxonomy:
            # Add taxonomy to controls in scored_context
            taxonomy_map = {t.get("control_code", ""): t for t in llm_taxonomy}
            for ctrl in scored_context.get("controls", []):
                code = ctrl.get("code") or ctrl.get("control_code", "")
                taxonomy = taxonomy_map.get(code)
                if taxonomy:
                    ctrl["llm_taxonomy"] = taxonomy

        if not resolved_metrics:
            logger.warning("enrich_metrics_with_decision_tree: No resolved_metrics in state, skipping scoring")
            state["dt_scored_metrics"] = []
            state["dt_metric_groups"] = []
            state["dt_metric_coverage_report"] = {"total_metrics_scored": 0}
            state["dt_metric_dropped"] = []
            return state

        scored_metrics = score_all_metrics(
            metrics=resolved_metrics,
            decisions=decisions,
            scored_context=scored_context,
            data_sources_in_scope=data_sources_in_scope,
        )

        state["dt_scored_metrics"] = scored_metrics

        # ── Phase 4: Apply thresholds ────────────────────────────────
        use_case = decisions.get("use_case", "soc2_audit")
        required_groups = get_required_groups(use_case)

        included, candidates, dropped = apply_thresholds(
            scored_metrics=scored_metrics,
            include_threshold=0.50,
            candidate_threshold=0.35,
            required_groups=required_groups,
            min_metrics_per_group=3,
            min_total_metrics=5,
        )

        state["dt_metric_dropped"] = dropped

        logger.info(
            f"enrich_metrics_with_decision_tree: Thresholds — "
            f"{len(included)} included, {len(candidates)} candidates, "
            f"{len(dropped)} dropped"
        )

        # ── Phase 5: Group metrics (using LLM-generated groups if available) ──
        llm_generated_groups = state.get("dt_generated_groups", [])
        grouping_result = group_metrics(
            scored_metrics=included,
            decisions=decisions,
            llm_generated_groups=llm_generated_groups if llm_generated_groups else None,
        )

        state["dt_metric_groups"] = grouping_result.get("groups", [])
        state["dt_metric_coverage_report"] = grouping_result.get("coverage_report", {})

        # Also store the full grouping result in context_cache for downstream access
        context_cache = state.get("context_cache", {})
        context_cache["metric_decision_result"] = {
            "decision_summary": grouping_result.get("decision_summary", {}),
            "groups": grouping_result.get("groups", []),
            "overflow_metrics": grouping_result.get("overflow_metrics", []),
            "coverage_report": grouping_result.get("coverage_report", {}),
        }
        state["context_cache"] = context_cache

        logger.info(
            f"enrich_metrics_with_decision_tree: Grouped into {len(grouping_result.get('groups', []))} groups"
        )

    except Exception as e:
        logger.error(f"enrich_metrics_with_decision_tree failed: {e}", exc_info=True)
        # Don't fail the entire node if enrichment fails - just log and continue
        state.setdefault("dt_metric_decisions", {})
        state.setdefault("dt_scored_metrics", [])
        state.setdefault("dt_metric_groups", [])
        state.setdefault("dt_metric_coverage_report", {})
        state.setdefault("dt_metric_dropped", [])

    return state


# ============================================================================
# Node 1: Auto-resolve + Score + Group (kept for backward compatibility)
# ============================================================================

def dt_metric_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolves decision tree questions, scores metrics, and groups results.
    
    This node is kept for backward compatibility. It now delegates to
    enrich_metrics_with_decision_tree() helper function.
    
    Reads from state:
        user_query, intent, framework_id, data_enrichment, dt_scored_context,
        resolved_metrics, dt_data_sources_in_scope, dt_metric_interactive_mode

    Writes to state:
        dt_metric_decisions       — resolved decision values with confidence
        dt_scored_metrics         — all metrics with composite scores
        dt_metric_groups          — grouped metric recommendations
        dt_metric_coverage_report — coverage validation report
        dt_metric_dropped         — metrics below threshold
    """
    try:
        # Delegate to the reusable helper function
        state = enrich_metrics_with_decision_tree(state)
        
        # Add node-specific logging and messaging
        decisions = state.get("dt_metric_decisions", {})
        groups = state.get("dt_metric_groups", [])
        coverage = state.get("dt_metric_coverage_report", {})
        
        group_summary = ", ".join(
            f"{g['group_name']}({g['total_assigned']})"
            for g in groups if g.get("total_assigned", 0) > 0
        )
        
        _log_step(
            state,
            "dt_metric_decision",
            inputs={
                "resolved_metrics_count": len(state.get("resolved_metrics", [])),
                "use_case": decisions.get("use_case", ""),
                "auto_resolve_confidence": decisions.get("auto_resolve_confidence", 0),
            },
            outputs={
                "scored_count": len(state.get("dt_scored_metrics", [])),
                "included_count": len([m for m in state.get("dt_scored_metrics", []) if m.get("composite_score", 0) >= 0.50]),
                "dropped_count": len(state.get("dt_metric_dropped", [])),
                "groups_count": len(groups),
                "coverage": coverage,
            },
        )

        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"Metric Decision Tree: use_case={decisions.get('use_case', 'unknown')}, "
                f"confidence={decisions.get('auto_resolve_confidence', 0):.2f}. "
                f"Scored {len(state.get('dt_scored_metrics', []))} metrics. "
                f"Groups: {group_summary}. "
                f"Coverage: {coverage.get('groups_with_full_coverage', 0)} full, "
                f"{coverage.get('groups_with_partial_coverage', 0)} partial."
            )
        ))

    except Exception as e:
        logger.error(f"dt_metric_decision_node failed: {e}", exc_info=True)
        state["error"] = f"Metric decision tree failed: {str(e)}"
        state.setdefault("dt_metric_decisions", {})
        state.setdefault("dt_scored_metrics", [])
        state.setdefault("dt_metric_groups", [])
        state.setdefault("dt_metric_coverage_report", {})
        state.setdefault("dt_metric_dropped", [])

    return state


# ============================================================================
# Node 2: Interactive clarification (optional)
# ============================================================================

def dt_metric_decision_interactive_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles interactive clarification when auto-resolve confidence is low.

    If dt_metric_clarification_response is populated (user answered questions),
    merges answers into decisions and re-runs scoring + grouping.

    If no response yet, emits clarification questions for the frontend.

    Reads from state:
        dt_metric_decisions, dt_metric_clarification_response

    Writes to state:
        dt_metric_clarification_request  — questions to show user (if no response)
        dt_metric_decisions              — updated with user answers (if response)
        dt_metric_groups                 — re-grouped after updated decisions
    """
    from .metric_decision_tree import (
        resolve_decisions,
        get_clarification_questions,
        VALID_OPTIONS,
    )
    from .metric_scoring import score_all_metrics, apply_thresholds
    from .metric_grouping import group_metrics, get_required_groups

    try:
        decisions = state.get("dt_metric_decisions", {})
        user_response = state.get("dt_metric_clarification_response")

        if not user_response:
            # ── Emit clarification questions ─────────────────────────
            questions = get_clarification_questions(decisions)

            if not questions:
                logger.info("dt_metric_decision_interactive: No clarifications needed, passing through")
                return state

            state["dt_metric_clarification_request"] = {
                "questions": questions,
                "current_decisions": {
                    k: v for k, v in decisions.items()
                    if k in ("use_case", "goal", "focus_area", "audience", "timeframe", "metric_type")
                },
                "message": "Some decisions have low confidence. Please confirm or adjust:",
            }

            state.setdefault("messages", []).append(AIMessage(
                content=(
                    f"Metric Decision Tree: {len(questions)} questions need clarification. "
                    f"Low confidence on: {[q['key'] for q in questions]}"
                )
            ))
            return state

        # ── Process user response and re-score ───────────────────────
        logger.info(f"dt_metric_decision_interactive: Processing user response: {user_response}")

        # Merge user answers into decisions
        updated_decisions = dict(decisions)
        for key, value in user_response.items():
            valid_opts = VALID_OPTIONS.get(key, [])
            if value in valid_opts:
                updated_decisions[key] = value
                updated_decisions.setdefault("confidences", {})[key] = 1.0
                # Update tags from OPTION_TAGS
                from .metric_decision_tree import OPTION_TAGS
                option_tags = OPTION_TAGS.get(key, {}).get(value, {})
                if option_tags:
                    all_tags = updated_decisions.get("all_tags", {})
                    for tag_key, tag_val in option_tags.items():
                        if tag_key in all_tags and isinstance(all_tags[tag_key], list) and isinstance(tag_val, list):
                            # Merge lists, deduplicate
                            for v in tag_val:
                                if v not in all_tags[tag_key]:
                                    all_tags[tag_key].append(v)
                        else:
                            all_tags[tag_key] = tag_val
                    updated_decisions["all_tags"] = all_tags

        # Recalculate confidence
        confidences = updated_decisions.get("confidences", {})
        required_confs = [
            confidences.get(k, 0.3)
            for k in ("use_case", "goal", "focus_area")
        ]
        updated_decisions["auto_resolve_confidence"] = (
            sum(required_confs) / len(required_confs) if required_confs else 0.0
        )
        updated_decisions["resolved_from"] = decisions.get("resolved_from", []) + ["interactive"]
        updated_decisions["unresolved"] = [
            k for k in decisions.get("unresolved", [])
            if k not in user_response
        ]

        state["dt_metric_decisions"] = updated_decisions

        # Re-run scoring with updated decisions
        resolved_metrics = state.get("resolved_metrics", [])
        scored_context = state.get("dt_scored_context", {})
        data_sources_in_scope = state.get("dt_data_sources_in_scope", [])

        scored_metrics = score_all_metrics(
            metrics=resolved_metrics,
            decisions=updated_decisions,
            scored_context=scored_context,
            data_sources_in_scope=data_sources_in_scope,
        )
        state["dt_scored_metrics"] = scored_metrics

        use_case = updated_decisions.get("use_case", "soc2_audit")
        required_groups = get_required_groups(use_case)

        included, candidates, dropped = apply_thresholds(
            scored_metrics=scored_metrics,
            required_groups=required_groups,
        )
        state["dt_metric_dropped"] = dropped

        grouping_result = group_metrics(included, updated_decisions)
        state["dt_metric_groups"] = grouping_result.get("groups", [])
        state["dt_metric_coverage_report"] = grouping_result.get("coverage_report", {})

        # Clear clarification state
        state["dt_metric_clarification_request"] = None
        state["dt_metric_clarification_response"] = None

        _log_step(
            state, "dt_metric_decision_interactive",
            inputs={"user_response": user_response},
            outputs={
                "updated_confidence": updated_decisions.get("auto_resolve_confidence"),
                "groups_count": len(grouping_result.get("groups", [])),
            },
        )

        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"Metric Decision Tree (interactive): Updated with user input. "
                f"Confidence now {updated_decisions.get('auto_resolve_confidence', 0):.2f}. "
                f"Re-grouped into {len(grouping_result.get('groups', []))} groups."
            )
        ))

    except Exception as e:
        logger.error(f"dt_metric_decision_interactive_node failed: {e}", exc_info=True)
        state["error"] = f"Metric decision interactive failed: {str(e)}"

    return state


# ============================================================================
# Helpers
# ============================================================================

def _log_step(
    state: Dict[str, Any],
    step_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    status: str = "completed",
    error: Optional[str] = None,
) -> None:
    """Append a step record to state execution_steps (same as dt_nodes._dt_log_step)."""
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": step_name,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "inputs": inputs,
        "outputs": outputs,
        "error": error,
    })


# ============================================================================
# Workflow wiring helper
# ============================================================================

def get_metric_decision_routing(state: Dict[str, Any]) -> str:
    """
    Conditional routing after dt_metric_decision_node.

    Returns:
        "dt_metric_decision_interactive" — if confidence is low and interactive mode on
        "dt_scoring_validator"           — otherwise (proceed normally)
    """
    decisions = state.get("dt_metric_decisions", {})
    confidence = decisions.get("auto_resolve_confidence", 1.0)
    interactive = state.get("dt_metric_interactive_mode", False)

    if confidence < 0.6 and interactive:
        return "dt_metric_decision_interactive"
    return "dt_scoring_validator"


def get_metric_decision_state_extensions() -> Dict[str, Any]:
    """
    Return the state field defaults that should be added to create_dt_initial_state().

    Usage in dt_workflow.py:
        from .dt_metric_decision_nodes import get_metric_decision_state_extensions
        initial_state.update(get_metric_decision_state_extensions())
    """
    return {
        "dt_metric_decisions": {},
        "dt_scored_metrics": [],
        "dt_metric_groups": [],
        "dt_metric_coverage_report": {},
        "dt_metric_dropped": [],
        "dt_metric_interactive_mode": False,
        "dt_metric_clarification_request": None,
        "dt_metric_clarification_response": None,
    }
