"""
Scoping Node - The Main Fix

Phase 0C: Asks scoping questions based on area filters.
This is the missing node that causes scoping_answers to always be empty.
"""
import logging
import re
from typing import Dict, Any, List, Optional

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType, TurnQuestion
from app.conversation.config import VerticalConversationConfig, ScopingQuestionTemplate
from app.ingestion.registry_vector_lookup import resolve_scoping_to_areas

logger = logging.getLogger(__name__)


def _extract_filter_hints(
    user_query: str,
    filter_names: List[str],
    templates: Dict[str, ScopingQuestionTemplate],
) -> Dict[str, str]:
    """
    Extract filter hints from user query using keyword pattern matching.
    Returns {filter_name: option_id} for recognized patterns.
    Only considers filters present in filter_names.

    The returned option_id is validated against the template's options list —
    if the extracted id is not a valid option we drop the hint.
    """
    q = user_query.lower()
    hints: Dict[str, str] = {}

    def _valid(filter_name: str, option_id: str) -> bool:
        tmpl = templates.get(filter_name)
        if not tmpl:
            return False
        return any(o["id"] == option_id for o in tmpl.options)

    # ── time_period ────────────────────────────────────────────────────────────
    if "time_period" in filter_names:
        if re.search(r"\b(last|past)\s+30\s+days?\b", q):
            hints["time_period"] = "last_30d"
        elif re.search(r"\b(last|past)\s+quarter\b|\bq[1-4]\b", q):
            hints["time_period"] = "last_quarter"
        elif re.search(r"\byear[\s-]to[\s-]date\b|\bytd\b|\bthis\s+year\b", q):
            hints["time_period"] = "ytd"
        elif re.search(
            r"\b(last|past)\s+(\d+\s+)?year\b|\b12\s+months?\b"
            r"|\bannual(ly)?\b|\byear[\s-]over[\s-]year\b|\byoy\b",
            q,
        ):
            hints["time_period"] = "yoy"

    # ── org_unit ───────────────────────────────────────────────────────────────
    if "org_unit" in filter_names:
        if re.search(
            r"\bwhole\s+(org|organi[sz]ation|company)\b"
            r"|\bentire\s+(org|organi[sz]ation|company)\b"
            r"|\bcompany[\s-]wide\b"
            r"|\ball\s+(employees?|staff|users?|learners?)\b"
            r"|\borgani[sz]ations?\b",   # "my organisation" → whole_org
            q,
        ):
            hints["org_unit"] = "whole_org"
        elif re.search(r"\bdepartment\b|\bdivision\b", q):
            hints["org_unit"] = "department"
        elif re.search(r"\brole\b|\bjob\s+famil\b", q):
            hints["org_unit"] = "role"
        elif re.search(r"\bmanager\b|\bdirect\s+reports?\b", q):
            hints["org_unit"] = "manager"

    # ── training_type ──────────────────────────────────────────────────────────
    if "training_type" in filter_names:
        if re.search(
            r"\bmandatory\b|\brequired\s+(training|course)\b"
            r"|\bregulatory\b|\bcompliance\s+training\b"
            r"|\bskill\s+compliance\b",
            q,
        ):
            hints["training_type"] = "mandatory"
        elif re.search(r"\bcertif(ication|ied|y)?\b", q):
            hints["training_type"] = "certification"

    # ── due_date_range ─────────────────────────────────────────────────────────
    if "due_date_range" in filter_names:
        if re.search(r"\bnext\s+30\s+days?\b", q):
            hints["due_date_range"] = "next_30d"
        elif re.search(r"\bnext\s+60\s+days?\b", q):
            hints["due_date_range"] = "next_60d"
        elif re.search(r"\bnext\s+90\s+days?\b", q):
            hints["due_date_range"] = "next_90d"
        elif re.search(r"\boverdue\b|\bpast\s+due\b", q):
            hints["due_date_range"] = "overdue"

    # ── audit_window ───────────────────────────────────────────────────────────
    if "audit_window" in filter_names:
        if re.search(r"\bnext\s+30\s+days?\b", q):
            hints["audit_window"] = "next_30d"
        elif re.search(r"\bnext\s+60\s+days?\b", q):
            hints["audit_window"] = "next_60d"
        elif re.search(r"\bnext\s+90\s+days?\b", q):
            hints["audit_window"] = "next_90d"
        elif re.search(r"\bpast\b|\balready\s+(passed|happened)\b", q):
            hints["audit_window"] = "past"

    # Drop any hint whose option_id is not actually in the template options
    return {k: v for k, v in hints.items() if _valid(k, v)}


def scoping_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Scoping node - asks user for scoping context before area matching.

    This node:
    1. Parses user_query for filter hints (time period, org unit, training type…)
    2. Runs a preliminary area lookup (without scoping context) to get area.filters[]
    3. Resolves each filter_name against config.scoping_question_templates
    4. Always includes config.always_include_filters
    5. Pre-populates matching questions with extracted filter hints as default_value
    6. Caps at config.max_scoping_questions_per_turn
    7. Writes a SCOPING turn checkpoint and stops

    State reads: csod_area_matches (preliminary), csod_confirmed_concept_ids, user_query
    State writes: csod_conversation_checkpoint (SCOPING type)
    resume_with_field: csod_scoping_answers

    On resume: csod_scoping_answers is populated. Graph continues to area_matcher,
    which now runs with full scoping context.
    """
    confirmed_concept_ids = state.get("csod_confirmed_concept_ids", [])
    preliminary_area_matches = state.get("csod_preliminary_area_matches", []) or []
    existing_scoping_answers = state.get("csod_scoping_answers")
    user_query = state.get("user_query", "")

    # If scoping answers exist (including empty {} from "Apply Defaults"), skip.
    # Check `is not None` — an empty dict is a valid "defaults applied" response.
    if existing_scoping_answers is not None and isinstance(existing_scoping_answers, dict):
        logger.info(
            "Scoping answers present (keys=%s, Apply Defaults=%s) — skipping scoping checkpoint",
            list(existing_scoping_answers.keys()),
            not existing_scoping_answers,
        )
        state["csod_scoping_complete"] = True
        state["csod_conversation_checkpoint"] = None
        state["csod_checkpoint_resolved"] = True
        return state

    # Also skip if csod_scoping_complete was set upstream (e.g. by _build_graph_input)
    if state.get("csod_scoping_complete"):
        logger.info("csod_scoping_complete already set — skipping scoping checkpoint")
        return state

    if not confirmed_concept_ids:
        logger.warning("No confirmed concepts for scoping - skipping")
        state["csod_scoping_complete"] = True
        return state

    try:
        # Get area-specific filters from the first preliminary match (if available).
        # Always-include filters are added regardless of area match results.
        if preliminary_area_matches:
            primary_area = preliminary_area_matches[0]
            area_filters = primary_area.get("filters", [])
        else:
            logger.info("No preliminary areas found — will still ask always_include_filters")
            area_filters = []

        # Extract filter hints from the user's question so we can pre-select options
        all_filter_names = list(config.always_include_filters) + [
            f for f in area_filters if f not in config.always_include_filters
        ]
        filter_hints = _extract_filter_hints(
            user_query=user_query,
            filter_names=all_filter_names,
            templates=config.scoping_question_templates,
        )
        if filter_hints:
            logger.info(f"Extracted filter hints from query: {filter_hints}")

        # Build list of questions to ask
        # Note: do NOT return early when area_filters is empty — always_include_filters
        # (e.g. org_unit, time_period) should always be offered regardless of whether
        # the matched area declares explicit filters.
        questions_to_ask: List[TurnQuestion] = []
        seen_filters = set()

        # Always include always_include_filters first
        for filter_name in config.always_include_filters:
            if filter_name in config.scoping_question_templates:
                template = config.scoping_question_templates[filter_name]
                questions_to_ask.append(TurnQuestion(
                    id=template.question_id,
                    label=template.label,
                    interaction_mode=template.interaction_mode,
                    options=template.options,
                    state_key=template.state_key,
                    required=template.required,
                    default_value=filter_hints.get(filter_name),
                ))
                seen_filters.add(filter_name)

        # Add questions for filters found in area.filters[]
        for filter_name in area_filters:
            if filter_name in seen_filters:
                continue  # Already added

            if filter_name in config.scoping_question_templates:
                template = config.scoping_question_templates[filter_name]
                questions_to_ask.append(TurnQuestion(
                    id=template.question_id,
                    label=template.label,
                    interaction_mode=template.interaction_mode,
                    options=template.options,
                    state_key=template.state_key,
                    required=template.required,
                    default_value=filter_hints.get(filter_name),
                ))
                seen_filters.add(filter_name)
            else:
                # Unknown filter_name - silently skipped (as per plan)
                logger.debug(f"Unknown filter_name '{filter_name}' - skipping")

        # Cap at max_scoping_questions_per_turn
        if len(questions_to_ask) > config.max_scoping_questions_per_turn:
            questions_to_ask = questions_to_ask[:config.max_scoping_questions_per_turn]
            logger.info(f"Capped scoping questions to {config.max_scoping_questions_per_turn}")

        # If no questions after all that, skip scoping
        if not questions_to_ask:
            logger.info("No scoping questions to ask - scoping complete")
            state["csod_scoping_complete"] = True
            return state

        hints_detected = [f for f in seen_filters if filter_hints.get(f)]
        logger.info(
            f"Scoping checkpoint: {len(questions_to_ask)} question(s), "
            f"pre-populated from query: {hints_detected or 'none'}"
        )

        # Create SCOPING turn checkpoint
        checkpoint = ConversationCheckpoint(
            phase="scoping",
            turn=ConversationTurn(
                phase="scoping",
                turn_type=TurnOutputType.SCOPING,
                message=(
                    "A few more questions to make sure I'm looking in the right place:"
                ),
                questions=questions_to_ask,
            ),
            resume_with_field="csod_scoping_answers",
        )

        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False

    except Exception as e:
        logger.error(f"Error in scoping node: {e}", exc_info=True)
        # On error, skip scoping and continue
        state["csod_scoping_complete"] = True
        state["csod_scoping_answers"] = {}

    return state
