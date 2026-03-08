"""
Dashboard Decision Tree — LangGraph Node Integration

Two nodes that plug into any dashboard generation workflow:

1. dt_dashboard_decision_node
   - Resolves all seven decisions from state + user query
   - Applies destination gate (hard filter before scoring)
   - Scores enriched templates against resolved decisions
   - Writes ranked candidates + winning spec to state

2. dt_dashboard_decision_interactive_node  (optional)
   - Emits clarification questions when auto-resolve confidence is low
   - Consumes user responses and re-runs template scoring
   - Only activated when dt_dashboard_interactive_mode=True and confidence < 0.6

Insertion point in layout_advisor graph:
    retrieve_context → dt_dashboard_decision_node → spec_generation

Mirrors dt_metric_decision_nodes.py patterns exactly:
  enrich_*/dt_*/dt_*_interactive_node / _log_step / get_*_routing /
  get_*_state_extensions
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


# ============================================================================
# Template scoring engine
# ============================================================================

def _score_template(
    template: Dict[str, Any],
    decisions: Dict[str, Any],
    retrieved_boost: Dict[str, float],
) -> float:
    """
    Score one enriched template against resolved decisions.
    Max raw score = 115  (100 deterministic + 15 vector boost).

    Uses taxonomy for fuzzy matching (mirrors dt_metric_decision_nodes):
      - focus_area: matches taxonomy aliases (e.g. incident_response →
        incident_alert_lists_and_triage, investigation_detail_and timelines)
      - audience: matches taxonomy audience_levels (e.g. security_ops →
        security_ops_analyst, vulnerability_manager, soc_manager)

    Points table:
      category match          30
      focus_area match        20
      audience match          20
      metric_profile match    15
      complexity match        10
      interaction_mode match   5
      vector boost (RETRIEVAL POINT 1)  +15
    """
    score = 0.0

    cat = decisions.get("category", "")
    if cat and cat in template.get("category", ""):
        score += 30

    fa = decisions.get("focus_area", "")
    template_fas = template.get("focus_areas", []) or template.get("best_for", [])
    if fa:
        # Taxonomy-aware: match decision focus_area or its taxonomy aliases
        try:
            from .dashboard_taxonomy import get_focus_areas_for_scoring
            fa_set = get_focus_areas_for_scoring(fa)
        except Exception:
            fa_set = {fa}
        if any(
            any(m in (item or "") or (item or "") in m for m in fa_set)
            for item in template_fas
        ):
            score += 20

    audience = decisions.get("audience", "")
    template_audiences = template.get("audience_levels", [])
    if audience:
        # Taxonomy-aware: match decision audience or its taxonomy aliases
        try:
            from .dashboard_taxonomy import get_audiences_for_scoring
            aud_set = get_audiences_for_scoring(audience)
        except Exception:
            aud_set = {audience}
        if any(
            any(m in (a or "") or (a or "") in m for m in aud_set)
            for a in template_audiences
        ):
            score += 20

    mp = decisions.get("metric_profile", "mixed")
    if mp and mp in template.get("metric_profile_fit", []):
        score += 15

    complexity = decisions.get("complexity", "medium")
    template_complexity = template.get("complexity", "medium")
    complexity_order = {"low": 0, "medium": 1, "high": 2}
    if abs(complexity_order.get(complexity, 1) - complexity_order.get(template_complexity, 1)) <= 1:
        score += 10

    interaction = decisions.get("interaction_mode", "drill_down")
    if interaction and interaction in template.get("interaction_modes", []):
        score += 5

    # Vector boost from RETRIEVAL POINT 1
    score += retrieved_boost.get(template.get("template_id", ""), 0.0) * 15

    # Normalise to 0–1
    return round(score / 115, 4)


def _apply_destination_gate(
    templates: List[Dict[str, Any]],
    destination_type: str,
    destination_gate: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Hard-filter templates that do not support the resolved destination.
    Returns (passing, rejected) lists.
    api_json passes no templates — spec is emitted directly from metrics.
    """
    if destination_gate.get("emit_metric_spec_only"):
        return [], templates   # api_json: no layout templates needed

    passing, rejected = [], []
    for t in templates:
        supported = t.get("supported_destinations", ["embedded"])
        if destination_type in supported:
            passing.append(t)
        else:
            rejected.append(t)

    return passing, rejected


def _apply_destination_overrides(
    spec: Dict[str, Any],
    destination_type: str,
    destination_gate: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Transform the winning spec for the target destination after scoring.
    Mirrors destination adapter logic from the design doc.
    """
    spec = dict(spec)  # shallow copy

    excluded = destination_gate.get("excluded_primitives", [])
    if excluded:
        spec["primitives"] = [
            p for p in spec.get("primitives", []) if p not in excluded
        ]
        spec["has_chat"]  = spec.get("has_chat", False) and "chat_panel" not in excluded
        spec["has_graph"] = spec.get("has_graph", False) and "causal_graph" not in excluded

    if destination_type == "simple":
        spec["has_filters"] = False
        spec["max_panels"]  = destination_gate.get("max_panels", 2)

    elif destination_type == "slack_digest":
        spec["strip_only"]     = True
        spec["max_kpi_cells"]  = destination_gate.get("max_kpi_cells", 6)
        spec["has_filters"]    = False

    elif destination_type == "powerbi":
        spec["measure_format"] = destination_gate.get("measure_format", "dax")

    spec["destination_type"] = destination_type
    return spec


# ============================================================================
# Reusable helper  (mirrors enrich_metrics_with_decision_tree)
# ============================================================================

def enrich_dashboard_with_decision_tree(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reusable function — resolves dashboard decisions, gates templates,
    scores candidates, and stores the winning spec.

    Can be called from any workflow node:

        from dt_dashboard_decision_nodes import enrich_dashboard_with_decision_tree
        state = enrich_dashboard_with_decision_tree(state)

    Reads from state:
        user_query, intent, framework_id, output_format, persona, timeframe,
        selected_data_sources, data_enrichment, resolved_metrics,
        dt_enriched_templates        — list of EnrichedTemplate dicts
        dt_retrieved_template_boosts — {template_id: similarity_score} from vector store
        dt_dashboard_interactive_mode

    Writes to state:
        dt_dashboard_decisions       — resolved decision values with confidence
        dt_scored_templates          — all templates with composite scores
        dt_template_candidates       — top-3 after scoring
        dt_winning_template          — single best template spec
        dt_destination_gate          — applied gate config
        dt_coverage_gaps             — focus areas not covered by winning template
        dt_dropped_templates         — templates removed by destination gate
    """
    from dashboard_decision_tree import resolve_decisions, VALID_OPTIONS

    try:
        # ── Phase 1: Resolve decisions ────────────────────────────────
        decisions = resolve_decisions(state)
        state["dt_dashboard_decisions"] = decisions

        destination_type = decisions.get("destination_type", "embedded")
        destination_gate = decisions.get("destination_gate", {})

        logger.info(
            f"enrich_dashboard_with_decision_tree: "
            f"destination={destination_type}, category={decisions.get('category')}, "
            f"focus_area={decisions.get('focus_area')}, "
            f"confidence={decisions.get('auto_resolve_confidence', 0):.2f}, "
            f"registry_target={decisions.get('registry_target')}, "
            f"unresolved={decisions.get('unresolved', [])}"
        )

        # ── Phase 2: Destination gate ─────────────────────────────────
        enriched_templates = state.get("dt_enriched_templates", [])
        passing, dropped = _apply_destination_gate(
            enriched_templates, destination_type, destination_gate
        )
        state["dt_dropped_templates"] = dropped
        state["dt_destination_gate"]  = destination_gate

        logger.info(
            f"enrich_dashboard_with_decision_tree: "
            f"Destination gate ({destination_type}) — "
            f"{len(passing)} passing, {len(dropped)} dropped"
        )

        # ── Phase 3: Score ────────────────────────────────────────────
        retrieved_boosts = state.get("dt_retrieved_template_boosts", {})
        scored = []
        for t in passing:
            score = _score_template(t, decisions, retrieved_boosts)
            scored.append({**t, "composite_score": score})

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        state["dt_scored_templates"] = scored

        # ── Phase 4: Candidates (top-3) ───────────────────────────────
        candidates = scored[:3]
        state["dt_template_candidates"] = candidates

        # ── Phase 5: Winning template + destination overrides ─────────
        if candidates:
            winning_raw = dict(candidates[0])
            winning = _apply_destination_overrides(
                winning_raw, destination_type, destination_gate
            )
            # Inject decisions into winning spec
            winning["resolved_decisions"] = {
                k: v for k, v in decisions.items()
                if k in VALID_OPTIONS
            }
            state["dt_winning_template"] = winning
        else:
            state["dt_winning_template"] = None

        # ── Phase 6: Coverage gaps ────────────────────────────────────
        focus_area = decisions.get("focus_area", "")
        winning_fas = (
            candidates[0].get("focus_areas", []) if candidates else []
        )
        state["dt_coverage_gaps"] = (
            [focus_area] if focus_area and focus_area not in winning_fas else []
        )

        logger.info(
            f"enrich_dashboard_with_decision_tree: "
            f"Scored {len(scored)} templates, "
            f"top candidate: {candidates[0].get('template_id', 'none') if candidates else 'none'} "
            f"(score={candidates[0].get('composite_score', 0):.3f})" if candidates else
            f"Scored {len(scored)} templates, no candidates"
        )

    except Exception as exc:
        logger.error(
            f"enrich_dashboard_with_decision_tree failed: {exc}", exc_info=True
        )
        state.setdefault("dt_dashboard_decisions",  {})
        state.setdefault("dt_scored_templates",     [])
        state.setdefault("dt_template_candidates",  [])
        state.setdefault("dt_winning_template",     None)
        state.setdefault("dt_destination_gate",     {})
        state.setdefault("dt_coverage_gaps",        [])
        state.setdefault("dt_dropped_templates",    [])

    return state


# ============================================================================
# Node 1: Auto-resolve + gate + score  (primary node)
# ============================================================================

def dt_dashboard_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolves dashboard decisions, applies destination gate, scores templates,
    and selects the winning spec.

    Reads from state:
        user_query, intent, framework_id, output_format, persona, timeframe,
        selected_data_sources, data_enrichment, resolved_metrics,
        dt_enriched_templates, dt_retrieved_template_boosts

    Writes to state:
        dt_dashboard_decisions, dt_scored_templates, dt_template_candidates,
        dt_winning_template, dt_destination_gate, dt_coverage_gaps,
        dt_dropped_templates
    """
    try:
        state = enrich_dashboard_with_decision_tree(state)

        decisions   = state.get("dt_dashboard_decisions", {})
        candidates  = state.get("dt_template_candidates", [])
        winning     = state.get("dt_winning_template")
        coverage_gaps = state.get("dt_coverage_gaps", [])

        candidate_summary = ", ".join(
            f"{c.get('template_id', '?')}({c.get('composite_score', 0):.2f})"
            for c in candidates
        )

        _log_step(
            state,
            "dt_dashboard_decision",
            inputs={
                "enriched_templates_count": len(state.get("dt_enriched_templates", [])),
                "destination_type":         decisions.get("destination_type"),
                "category":                 decisions.get("category"),
                "focus_area":               decisions.get("focus_area"),
                "auto_resolve_confidence":  decisions.get("auto_resolve_confidence", 0),
            },
            outputs={
                "scored_count":    len(state.get("dt_scored_templates", [])),
                "candidates_count":len(candidates),
                "winning_template":winning.get("template_id") if winning else None,
                "coverage_gaps":   coverage_gaps,
            },
        )

        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"Dashboard Decision Tree: "
                f"destination={decisions.get('destination_type')}, "
                f"category={decisions.get('category')}, "
                f"focus_area={decisions.get('focus_area')}, "
                f"confidence={decisions.get('auto_resolve_confidence', 0):.2f}. "
                f"Candidates: [{candidate_summary}]. "
                f"Winner: {winning.get('template_id', 'none') if winning else 'none'}."
                + (f" Coverage gaps: {coverage_gaps}." if coverage_gaps else "")
            )
        ))

    except Exception as exc:
        logger.error(f"dt_dashboard_decision_node failed: {exc}", exc_info=True)
        state["error"] = f"Dashboard decision tree failed: {str(exc)}"
        state.setdefault("dt_dashboard_decisions",  {})
        state.setdefault("dt_scored_templates",     [])
        state.setdefault("dt_template_candidates",  [])
        state.setdefault("dt_winning_template",     None)
        state.setdefault("dt_destination_gate",     {})
        state.setdefault("dt_coverage_gaps",        [])
        state.setdefault("dt_dropped_templates",    [])

    return state


# ============================================================================
# Node 2: Interactive clarification  (optional)
# ============================================================================

def dt_dashboard_decision_interactive_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles interactive clarification when auto-resolve confidence is low.

    If dt_dashboard_clarification_response is populated (user answered):
      - Merges answers into decisions
      - Re-runs gate + scoring + selection

    If no response yet:
      - Emits clarification questions for the frontend via
        dt_dashboard_clarification_request

    Reads from state:
        dt_dashboard_decisions, dt_dashboard_clarification_response

    Writes to state:
        dt_dashboard_clarification_request  (if emitting questions)
        dt_dashboard_decisions              (updated with user answers)
        dt_scored_templates, dt_template_candidates, dt_winning_template
    """
    from dashboard_decision_tree import (
        get_clarification_questions,
        VALID_OPTIONS,
        OPTION_TAGS,
    )

    try:
        decisions     = state.get("dt_dashboard_decisions", {})
        user_response = state.get("dt_dashboard_clarification_response")

        if not user_response:
            # ── Emit clarification questions ──────────────────────────
            questions = get_clarification_questions(decisions)
            if not questions:
                logger.info(
                    "dt_dashboard_decision_interactive: "
                    "No clarifications needed, passing through"
                )
                return state

            state["dt_dashboard_clarification_request"] = {
                "questions": questions,
                "current_decisions": {
                    k: decisions.get(k)
                    for k in VALID_OPTIONS
                    if k in decisions
                },
                "message": (
                    "Some dashboard decisions have low confidence. "
                    "Please confirm or adjust:"
                ),
            }
            state.setdefault("messages", []).append(AIMessage(
                content=(
                    f"Dashboard Decision Tree: "
                    f"{len(questions)} questions need clarification. "
                    f"Low confidence on: {[q['key'] for q in questions]}"
                )
            ))
            return state

        # ── Process user response and re-score ────────────────────────
        logger.info(
            f"dt_dashboard_decision_interactive: "
            f"Processing user response: {user_response}"
        )
        updated = dict(decisions)

        for key, value in user_response.items():
            if value in VALID_OPTIONS.get(key, []):
                updated[key] = value
                updated.setdefault("confidences", {})[key] = 1.0

                # Merge tags from OPTION_TAGS
                option_tags = OPTION_TAGS.get(key, {}).get(value, {})
                if option_tags:
                    all_tags = updated.get("all_tags", {})
                    for tag_key, tag_val in option_tags.items():
                        if (
                            tag_key in all_tags
                            and isinstance(all_tags[tag_key], list)
                            and isinstance(tag_val, list)
                        ):
                            for v in tag_val:
                                if v not in all_tags[tag_key]:
                                    all_tags[tag_key].append(v)
                        else:
                            all_tags[tag_key] = tag_val
                    updated["all_tags"] = all_tags

        # Recalculate overall confidence
        confs = updated.get("confidences", {})
        req_confs = [
            confs.get(q.key, 0.3)
            for q in __import__(
                "dashboard_decision_tree", fromlist=["DECISION_QUESTIONS"]
            ).DECISION_QUESTIONS
            if q.required and q.key in confs
        ]
        updated["auto_resolve_confidence"] = (
            sum(req_confs) / len(req_confs) if req_confs else 0.0
        )
        updated["resolved_from"] = (
            decisions.get("resolved_from", []) + ["interactive"]
        )
        updated["unresolved"] = [
            k for k in decisions.get("unresolved", [])
            if k not in user_response
        ]

        state["dt_dashboard_decisions"] = updated

        # Re-run gate + scoring using updated decisions
        from dashboard_decision_tree import REGISTRY_TARGETS, DESTINATION_GATES

        dest      = updated.get("destination_type", "embedded")
        dest_gate = DESTINATION_GATES.get(dest, {})
        updated["destination_gate"]  = dest_gate
        updated["registry_target"]   = REGISTRY_TARGETS.get(updated.get("category", ""), "dashboard_registry")

        enriched   = state.get("dt_enriched_templates", [])
        boosts     = state.get("dt_retrieved_template_boosts", {})
        passing, dropped = _apply_destination_gate(enriched, dest, dest_gate)
        state["dt_dropped_templates"] = dropped

        scored = []
        for t in passing:
            s = _score_template(t, updated, boosts)
            scored.append({**t, "composite_score": s})
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        state["dt_scored_templates"]    = scored
        state["dt_template_candidates"] = scored[:3]
        state["dt_winning_template"] = (
            _apply_destination_overrides(dict(scored[0]), dest, dest_gate)
            if scored else None
        )

        # Clear clarification state
        state["dt_dashboard_clarification_request"]  = None
        state["dt_dashboard_clarification_response"] = None

        _log_step(
            state, "dt_dashboard_decision_interactive",
            inputs={"user_response": user_response},
            outputs={
                "updated_confidence": updated.get("auto_resolve_confidence"),
                "candidates_count":   len(state["dt_template_candidates"]),
                "winning_template":   (
                    state["dt_winning_template"].get("template_id")
                    if state["dt_winning_template"] else None
                ),
            },
        )
        state.setdefault("messages", []).append(AIMessage(
            content=(
                f"Dashboard Decision Tree (interactive): "
                f"Updated decisions. "
                f"Confidence now {updated.get('auto_resolve_confidence', 0):.2f}. "
                f"Winner: "
                f"{state['dt_winning_template'].get('template_id', 'none') if state['dt_winning_template'] else 'none'}."
            )
        ))

    except Exception as exc:
        logger.error(
            f"dt_dashboard_decision_interactive_node failed: {exc}", exc_info=True
        )
        state["error"] = f"Dashboard decision interactive failed: {str(exc)}"

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
    """Append a step record to state execution_steps."""
    state.setdefault("execution_steps", []).append({
        "step_name":  step_name,
        "agent_name": step_name,
        "timestamp":  datetime.utcnow().isoformat(),
        "status":     status,
        "inputs":     inputs,
        "outputs":    outputs,
        "error":      error,
    })


# ============================================================================
# Workflow wiring helpers
# ============================================================================

def get_dashboard_decision_routing(state: Dict[str, Any]) -> str:
    """
    Conditional routing after dt_dashboard_decision_node.

    Returns:
        "dt_dashboard_decision_interactive" — confidence low + interactive mode on
        "spec_generation"                   — proceed normally
    """
    decisions   = state.get("dt_dashboard_decisions", {})
    confidence  = decisions.get("auto_resolve_confidence", 1.0)
    interactive = state.get("dt_dashboard_interactive_mode", False)

    if confidence < 0.6 and interactive:
        return "dt_dashboard_decision_interactive"
    return "spec_generation"


def get_dashboard_decision_state_extensions() -> Dict[str, Any]:
    """
    Return state field defaults to add to initial state.

    Usage in layout_advisor graph:
        from dt_dashboard_decision_nodes import get_dashboard_decision_state_extensions
        initial_state.update(get_dashboard_decision_state_extensions())
    """
    return {
        "dt_dashboard_decisions":           {},
        "dt_scored_templates":              [],
        "dt_template_candidates":           [],
        "dt_winning_template":              None,
        "dt_destination_gate":              {},
        "dt_coverage_gaps":                 [],
        "dt_dropped_templates":             [],
        "dt_enriched_templates":            [],      # populated by retrieval node
        "dt_retrieved_template_boosts":     {},      # populated by retrieval node
        "dt_dashboard_interactive_mode":    False,
        "dt_dashboard_clarification_request":  None,
        "dt_dashboard_clarification_response": None,
    }
