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
    Direct analysis mode is disabled. Always force "explore" path.

    No checkpoint emitted; downstream routing should treat
    csod_direct_analysis_mode == "explore" as the only path.
    """
    if state.get("csod_direct_analysis_mode") != "explore":
        logger.info(
            "[analysis_mode_selector] forcing explore mode (intent=%s)",
            state.get("csod_intent", ""),
        )
        state["csod_direct_analysis_mode"] = "explore"
    state["csod_checkpoint_resolved"] = True
    state["csod_conversation_checkpoint"] = None
    return state
