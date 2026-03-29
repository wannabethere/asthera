"""
Metric Selection Node — lets the user review and select recommended metrics.

Placed AFTER skill_validator (Stage 4), BEFORE goal_intent.
Presents the recommended metrics/KPIs as a selectable list. The user can
keep all, deselect irrelevant ones, or confirm the set. Then the flow
continues to goal_intent ("how would you like to view these?").

If the user already confirmed metrics earlier (e.g., followup or
orchestrator pre-selected), this node passes through.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger


def csod_metric_selection_node(state: CSOD_State) -> CSOD_State:
    """
    Present recommended metrics/KPIs for user selection.

    Reads: csod_metric_recommendations, csod_kpi_recommendations, skill_validated_metrics
    Writes: csod_conversation_checkpoint (METRIC_SELECTION type),
            csod_selected_metric_ids (after user responds)

    On resume (user responded):
        Filters csod_metric_recommendations to only user-selected metrics.
    """
    logger.info(
        "[csod_metric_selection] Entry — interactive=%s, user_confirmed=%s, "
        "followup_sc=%s, selected_ids=%s, metrics=%d, kpis=%d",
        state.get("csod_interactive_checkpoints"),
        state.get("csod_metrics_user_confirmed"),
        state.get("csod_followup_short_circuit"),
        state.get("csod_selected_metric_ids") is not None,
        len(state.get("csod_metric_recommendations", []) or []),
        len(state.get("csod_kpi_recommendations", []) or []),
    )

    # Already selected — pass through
    if state.get("csod_metrics_user_confirmed"):
        logger.info("Metrics already confirmed by user — pass-through")
        return state

    # Followup short-circuit — skip selection
    if state.get("csod_followup_short_circuit"):
        logger.info("[csod_metric_selection] followup short-circuit — skipping")
        return state

    # Non-interactive mode (direct workflow invocation, orchestrator, or skip flag)
    # Auto-confirm when not in conversation mode
    if not state.get("csod_interactive_checkpoints", False):
        logger.info("[csod_metric_selection] non-interactive — auto-confirming")
        state["csod_metrics_user_confirmed"] = True
        return state

    # Check if user has already provided selections (resume path)
    selected_ids = state.get("csod_selected_metric_ids")
    if selected_ids is not None:
        # User responded — filter metrics to selected set
        logger.info("[csod_metric_selection] resume path — applying user selection: %s", selected_ids)
        _apply_user_selection(state, selected_ids)
        state["csod_metrics_user_confirmed"] = True
        return state

    # Build the selectable metric list
    metrics = state.get("csod_metric_recommendations", [])
    kpis = state.get("csod_kpi_recommendations", [])

    if not metrics and not kpis:
        # Nothing to select — pass through
        logger.info("[csod_metric_selection] no metrics or kpis found — auto-confirming")
        state["csod_metrics_user_confirmed"] = True
        return state

    # Build options for the checkpoint
    options = _build_metric_options(metrics, kpis)

    # Summary for the message
    metric_count = len(metrics)
    kpi_count = len(kpis)
    message = (
        f"I've identified {metric_count} metrics"
        + (f" and {kpi_count} KPIs" if kpi_count else "")
        + " for your analysis. Please review and select the ones you'd like to include:"
    )

    # Emit checkpoint
    from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

    checkpoint = ConversationCheckpoint(
        phase="metric_selection",
        turn=ConversationTurn(
            phase="metric_selection",
            turn_type=TurnOutputType.METRIC_NARRATION,
            message=message,
            options=options,
            metadata={
                "kind": "metric_selection",
                "metric_count": metric_count,
                "kpi_count": kpi_count,
                "allow_select_all": True,
                "allow_deselect": True,
                "placed_after_recommender": True,
            },
        ),
        resume_with_field="csod_selected_metric_ids",
    )
    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    _csod_log_step(
        state, "csod_metric_selection", "csod_metric_selection",
        inputs={"metrics": metric_count, "kpis": kpi_count},
        outputs={"checkpoint_emitted": True, "options": len(options)},
    )

    return state


def _build_metric_options(
    metrics: List[Dict[str, Any]],
    kpis: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build selectable options from recommended metrics and KPIs."""
    options: List[Dict[str, Any]] = []

    for i, m in enumerate(metrics[:20]):  # Cap at 20 for UI
        mid = m.get("metric_id") or m.get("name") or f"metric_{i}"
        name = m.get("name") or m.get("metric_id") or f"Metric {i+1}"
        desc = m.get("description") or m.get("natural_language_question") or ""

        # Include key fields for display
        option: Dict[str, Any] = {
            "id": str(mid),
            "label": str(name),
            "description": str(desc)[:200],
            "type": "metric",
            "selected": True,  # Pre-selected by default
        }

        # Add score/relevance if available
        score = m.get("composite_score") or m.get("score")
        if score:
            option["score"] = round(float(score), 2)

        # Add source table if available
        tables = m.get("source_schemas") or m.get("tables") or []
        if tables:
            option["source"] = str(tables[0]) if isinstance(tables[0], str) else str(tables[0].get("table_name", ""))

        options.append(option)

    for i, k in enumerate(kpis[:10]):  # Cap KPIs at 10
        kid = k.get("kpi_id") or k.get("name") or f"kpi_{i}"
        name = k.get("name") or k.get("kpi_id") or f"KPI {i+1}"
        desc = k.get("description") or ""

        options.append({
            "id": str(kid),
            "label": str(name),
            "description": str(desc)[:200],
            "type": "kpi",
            "selected": True,
        })

    return options


def _apply_user_selection(state: CSOD_State, selected_ids: Any) -> None:
    """Filter metrics and KPIs to only user-selected IDs."""
    if not isinstance(selected_ids, list):
        # "select_all" or invalid — keep everything
        logger.info("User selected all metrics (or invalid selection) — keeping all")
        return

    selected_set = set(str(sid) for sid in selected_ids)

    # Filter metrics
    metrics = state.get("csod_metric_recommendations", [])
    if metrics:
        filtered = [
            m for m in metrics
            if str(m.get("metric_id") or m.get("name", "")) in selected_set
        ]
        # Keep at least the selected ones; if none match IDs, keep all (safety)
        if filtered:
            state["csod_metric_recommendations"] = filtered
            logger.info("User selected %d of %d metrics", len(filtered), len(metrics))
        else:
            logger.warning("No metrics matched user selection IDs — keeping all %d", len(metrics))

    # Filter KPIs
    kpis = state.get("csod_kpi_recommendations", [])
    if kpis:
        filtered_kpis = [
            k for k in kpis
            if str(k.get("kpi_id") or k.get("name", "")) in selected_set
        ]
        if filtered_kpis:
            state["csod_kpi_recommendations"] = filtered_kpis
            logger.info("User selected %d of %d KPIs", len(filtered_kpis), len(kpis))

    # Also filter dt_scored_metrics if present (keeps downstream nodes consistent)
    dt_scored = state.get("dt_scored_metrics", [])
    if dt_scored:
        filtered_dt = [
            m for m in dt_scored
            if str(m.get("metric_id") or m.get("name", "")) in selected_set
        ]
        if filtered_dt:
            state["dt_scored_metrics"] = filtered_dt
