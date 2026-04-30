"""
Direct Question Selection Node.

After the question rephraser produces one or more rephrased questions, this node
pauses the graph and presents the questions to the user as a selectable list.

Pattern mirrors csod_metric_selection_node:
  - First pass:  emit ConversationCheckpoint → graph interrupts (interrupt_after)
  - Resume pass: user has provided csod_selected_question_ids → filter atomic questions,
                 then graph continues to csod_direct_sql_gateway

Only active when csod_planner_only=True (direct question flow).
Non-interactive context (csod_planner_only unset / False) auto-confirms.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger


def csod_direct_question_selection_node(state: CSOD_State) -> CSOD_State:
    """
    Present rephrased question(s) for user review before gateway dispatch.

    Reads:  csod_question_rephraser_output  — {rephrased_question, atomic_rephrased_questions, …}
            csod_direct_query_plan          — {planning_mode, …}
            csod_selected_question_ids      — set by adapter on resume
    Writes: csod_conversation_checkpoint, csod_checkpoint_resolved=False (first pass)
            csod_question_rephraser_output  — filtered to selected questions (resume pass)
            csod_direct_questions_confirmed — True when complete
    """
    logger.info(
        "[csod_direct_question_selection] entry — planner_only=%s confirmed=%s selected_ids=%s",
        state.get("csod_planner_only"),
        state.get("csod_direct_questions_confirmed"),
        state.get("csod_selected_question_ids") is not None,
    )

    # Already confirmed — pass through
    if state.get("csod_direct_questions_confirmed"):
        logger.info("[csod_direct_question_selection] already confirmed — pass-through")
        return state

    # Non-interactive: auto-confirm
    if not state.get("csod_planner_only"):
        logger.info("[csod_direct_question_selection] non-direct mode — auto-confirming")
        state["csod_direct_questions_confirmed"] = True
        return state

    # Resume path: user has submitted their selection
    selected_ids = state.get("csod_selected_question_ids")
    if selected_ids is not None:
        logger.info(
            "[csod_direct_question_selection] resume — applying selection: %s", selected_ids
        )
        _apply_question_selection(state, selected_ids)
        state["csod_direct_questions_confirmed"] = True
        return state

    # First pass: build options and emit checkpoint
    rephraser_output: Dict[str, Any] = state.get("csod_question_rephraser_output") or {}
    plan: Dict[str, Any] = state.get("csod_direct_query_plan") or {}
    planning_mode: str = rephraser_output.get("planning_mode") or plan.get("planning_mode") or "single_direct"
    atomic: List[Dict[str, Any]] = rephraser_output.get("atomic_rephrased_questions") or []
    primary_question: str = rephraser_output.get("rephrased_question") or ""

    options = _build_question_options(primary_question, atomic, planning_mode)

    if not options:
        logger.info("[csod_direct_question_selection] no questions to show — auto-confirming")
        state["csod_direct_questions_confirmed"] = True
        return state

    if len(options) == 1:
        message = (
            "I've rephrased your question for precise analysis. "
            "Please confirm this is what you'd like to explore:"
        )
    else:
        message = (
            f"I've broken your request into {len(options)} sub-questions. "
            "Select the ones you'd like answered:"
        )

    from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

    checkpoint = ConversationCheckpoint(
        phase="direct_question_selection",
        turn=ConversationTurn(
            phase="direct_question_selection",
            turn_type=TurnOutputType.METRIC_NARRATION,
            message=message,
            options=options,
            metadata={
                "kind": "direct_question_selection",
                "planning_mode": planning_mode,
                "question_count": len(options),
                "allow_select_all": True,
                "allow_deselect": len(options) > 1,
            },
        ),
        resume_with_field="csod_selected_question_ids",
    )
    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    _csod_log_step(
        state, "csod_direct_question_selection", "csod_direct_question_selection",
        inputs={"planning_mode": planning_mode, "question_count": len(options)},
        outputs={"checkpoint_emitted": True},
    )

    return state


def _build_question_options(
    primary_question: str,
    atomic: List[Dict[str, Any]],
    planning_mode: str,
) -> List[Dict[str, Any]]:
    options: List[Dict[str, Any]] = []

    if atomic and planning_mode in ("multi_question", "causal_rca", "compare_segments"):
        for idx, aq in enumerate(atomic[:10]):
            q = aq.get("rephrased_question") or aq.get("original_question") or f"Question {idx + 1}"
            options.append({
                "id": f"q_{idx}",
                "label": q[:120],
                "description": q,
                "type": "question",
                "selected": True,
            })
    elif primary_question:
        options.append({
            "id": "q_0",
            "label": primary_question[:120],
            "description": primary_question,
            "type": "question",
            "selected": True,
        })

    return options


def _apply_question_selection(state: CSOD_State, selected_ids: Any) -> None:
    """
    Filter atomic questions in csod_question_rephraser_output to the selected set.
    If selected_ids is not a list (e.g. "select_all"), keep all questions.
    """
    if not isinstance(selected_ids, list):
        logger.info("[csod_direct_question_selection] select_all — keeping all questions")
        return

    selected_set = set(str(sid) for sid in selected_ids)
    rephraser_output: Dict[str, Any] = state.get("csod_question_rephraser_output") or {}
    atomic: List[Dict[str, Any]] = rephraser_output.get("atomic_rephrased_questions") or []

    if not atomic:
        # Single-question flow: nothing to filter
        return

    filtered = [aq for idx, aq in enumerate(atomic) if f"q_{idx}" in selected_set]
    if filtered:
        rephraser_output["atomic_rephrased_questions"] = filtered
        state["csod_question_rephraser_output"] = rephraser_output
        logger.info(
            "[csod_direct_question_selection] filtered to %d of %d atomic questions",
            len(filtered), len(atomic),
        )
    else:
        logger.warning(
            "[csod_direct_question_selection] no atomic questions matched selection %s — keeping all",
            selected_ids,
        )
