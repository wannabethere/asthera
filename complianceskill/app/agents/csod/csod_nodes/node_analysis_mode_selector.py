"""
Analysis Mode Selector Node — human-in-the-loop checkpoint.

Placed after skill_analysis_planner (before CCE/retrieval), this node
asks the user whether they want a direct answer or want to explore and
plan metrics. The choice sets csod_direct_analysis_mode which routes
the pipeline downstream:

  "direct"  → after retrieval, route to csod_question_rephraser
  "explore" → continue normal metrics/gap/dashboard planning path

Persona-driven defaults:
  executive / director / ceo → suggest "direct"
  analyst / data_scientist   → suggest "explore"
  default                    → "direct"

Skipped for data-intelligence intents (they have single fixed paths).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger

# Intents with a fixed single path — never show this checkpoint
_SKIP_INTENTS = frozenset({
    "data_discovery",
    "data_quality_analysis",
    "data_lineage",
    "compliance_test_generator",
    "question_rephraser",  # already on the direct path
})

# Personas for which "direct" is the stronger default
_DIRECT_PERSONAS = frozenset({
    "executive",
    "director",
    "ceo",
    "cto",
    "vp",
    "manager",
    "lead",
})


def _default_mode_for_persona(persona: str | None) -> str:
    """Return 'direct' or 'explore' based on persona signal."""
    if not persona:
        return "direct"
    p = persona.lower()
    if any(token in p for token in _DIRECT_PERSONAS):
        return "direct"
    if any(token in p for token in ("analyst", "scientist", "engineer", "developer")):
        return "explore"
    return "direct"


def csod_analysis_mode_selector_node(state: CSOD_State) -> CSOD_State:
    """
    Checkpoint: ask user whether they want direct analysis or metrics exploration.

    Reads:  csod_intent, csod_persona, csod_analysis_mode_selection,
            csod_interactive_checkpoints, csod_followup_short_circuit
    Writes: csod_direct_analysis_mode ("direct" | "explore" | None),
            csod_conversation_checkpoint, csod_checkpoint_resolved
    resume_with_field: csod_analysis_mode_selection
    """
    from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

    intent = state.get("csod_intent", "")
    persona = state.get("csod_persona") or ""

    # Skip for intents that have deterministic single paths
    if intent in _SKIP_INTENTS:
        logger.info("[analysis_mode_selector] skipping for intent=%s", intent)
        return state

    # Followup short-circuit — skip
    if state.get("csod_followup_short_circuit"):
        logger.info("[analysis_mode_selector] followup short-circuit — skipping")
        return state

    # Already resolved (resume path or repeated pass)
    if state.get("csod_direct_analysis_mode") is not None:
        logger.info(
            "[analysis_mode_selector] mode already set: %s",
            state["csod_direct_analysis_mode"],
        )
        return state

    # ── Resume path: user responded ──────────────────────────────────────
    user_selection = state.get("csod_analysis_mode_selection")
    if user_selection is not None:
        mode = "direct" if str(user_selection).lower() == "direct" else "explore"
        logger.info("[analysis_mode_selector] resume — user chose: %s → mode=%s", user_selection, mode)
        state["csod_direct_analysis_mode"] = mode
        state["csod_checkpoint_resolved"] = True
        state["csod_conversation_checkpoint"] = None
        _csod_log_step(
            state, "csod_analysis_mode_selector", "csod_analysis_mode_selector",
            inputs={"user_selection": user_selection},
            outputs={"csod_direct_analysis_mode": mode},
        )
        return state

    # ── Non-interactive path: auto-select via persona ─────────────────────
    if not state.get("csod_interactive_checkpoints", False):
        auto_mode = _default_mode_for_persona(persona)
        logger.info(
            "[analysis_mode_selector] non-interactive — persona=%s → auto_mode=%s",
            persona, auto_mode,
        )
        state["csod_direct_analysis_mode"] = auto_mode
        return state

    # ── Interactive path: emit checkpoint ────────────────────────────────
    default_mode = _default_mode_for_persona(persona)
    persona_hint = ""
    if persona:
        persona_hint = f" Based on your role as **{persona}**, I'd suggest the direct answer."

    message = (
        "How would you like to approach this analysis?"
        + persona_hint
        + " You can always switch after seeing the results."
    )

    options = [
        {
            "id": "direct",
            "label": "Get a direct answer",
            "description": (
                "I'll scope your question to the relevant data and give you "
                "a precise, actionable result — a SQL query, trend insight, or RCA."
            ),
            "recommended": default_mode == "direct",
        },
        {
            "id": "explore",
            "label": "Explore & plan metrics",
            "description": (
                "I'll recommend metrics, surface gaps, and help you design a "
                "dashboard or gold model — full analytical planning."
            ),
            "recommended": default_mode == "explore",
        },
    ]

    checkpoint = ConversationCheckpoint(
        phase="analysis_mode_selector",
        turn=ConversationTurn(
            phase="analysis_mode_selector",
            turn_type=TurnOutputType.DECISION,
            message=message,
            options=options,
            metadata={
                "kind": "analysis_mode_selector",
                "intent": intent,
                "persona": persona,
                "default_mode": default_mode,
            },
        ),
        resume_with_field="csod_analysis_mode_selection",
    )

    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    logger.info(
        "[analysis_mode_selector] checkpoint emitted — intent=%s, default=%s",
        intent, default_mode,
    )
    _csod_log_step(
        state, "csod_analysis_mode_selector", "csod_analysis_mode_selector",
        inputs={"intent": intent, "persona": persona},
        outputs={"checkpoint_emitted": True, "default_mode": default_mode},
    )
    return state
