"""
Cross-Concept Check Node

Phase 1F (post-CCE): After the causal graph runs, check whether other high-scoring areas
from different concepts could enrich the analysis. Presents a checkpoint when cross-concept
opportunities are found.

State reads:  csod_area_matches, csod_primary_area, csod_confirmed_concept_ids,
              csod_causal_nodes, csod_cross_concept_confirmed, csod_additional_area_ids
State writes: csod_cross_concept_areas, csod_conversation_checkpoint,
              csod_checkpoint_resolved, csod_cross_concept_confirmed (fast-path)
resume_with_field: csod_cross_concept_confirmed
"""
import logging
from typing import Any, Dict, List, Optional

from app.agents.csod.csod_nodes._helpers import CSOD_State, logger

_MIN_CROSS_CONCEPT_SCORE = 0.4  # minimum area score to surface as a cross-concept suggestion


def _get_primary_concept_id(state: CSOD_State) -> Optional[str]:
    """Return the primary confirmed concept ID."""
    confirmed_ids = state.get("csod_confirmed_concept_ids") or []
    if confirmed_ids:
        return confirmed_ids[0]
    primary_area = state.get("csod_primary_area") or {}
    return primary_area.get("concept_id")


def _find_cross_concept_areas(state: CSOD_State, primary_concept_id: str) -> List[Dict[str, Any]]:
    """
    Find high-scoring areas from concepts OTHER than the primary concept.

    Pulls from csod_area_matches (set by the planner graph area matcher).
    Also considers causal node domains to amplify cross-concept signals.
    """
    area_matches = state.get("csod_area_matches") or []
    causal_nodes = state.get("csod_causal_nodes") or []

    # Collect domain signals from causal graph nodes
    causal_domains: set = set()
    for node in causal_nodes:
        d = node.get("domain") or node.get("concept_id") or ""
        if d:
            causal_domains.add(d.lower())

    cross_areas = []
    for match in area_matches:
        concept_id = match.get("concept_id", "")
        if concept_id == primary_concept_id:
            continue  # same concept — skip

        score = float(match.get("score", 0.0))

        # Boost score if causal graph found signals from this concept's domain
        if concept_id.lower() in causal_domains:
            score = min(score + 0.15, 1.0)

        if score >= _MIN_CROSS_CONCEPT_SCORE:
            cross_areas.append({
                "area_id": match.get("area_id", ""),
                "concept_id": concept_id,
                "display_name": match.get("display_name", match.get("area_id", "")),
                "description": match.get("description", ""),
                "score": round(score, 3),
                "metrics": (match.get("metrics") or [])[:5],
                "kpis": (match.get("kpis") or [])[:3],
                "causal_paths": (match.get("causal_paths") or [])[:3],
            })

    # Sort by score descending, take top 4
    cross_areas.sort(key=lambda x: x["score"], reverse=True)
    return cross_areas[:4]


def csod_cross_concept_check_node(state: CSOD_State) -> CSOD_State:
    """
    Cross-concept check — surfaces analytical areas from other concepts that could
    enrich the current analysis based on CCE results and area registry scores.

    Fast-paths when:
    - csod_cross_concept_confirmed is True (user already responded or chose to skip)
    - no cross-concept areas found
    """
    from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

    # Fast-path: already confirmed
    if state.get("csod_cross_concept_confirmed"):
        logger.info("[cross_concept_check] Already confirmed — skipping checkpoint")
        state["csod_checkpoint_resolved"] = True
        state["csod_conversation_checkpoint"] = None
        return state

    primary_concept_id = _get_primary_concept_id(state)
    if not primary_concept_id:
        logger.info("[cross_concept_check] No primary concept — skipping")
        state["csod_cross_concept_confirmed"] = True
        state["csod_checkpoint_resolved"] = True
        return state

    cross_areas = _find_cross_concept_areas(state, primary_concept_id)

    if not cross_areas:
        logger.info(
            "[cross_concept_check] No cross-concept areas found (primary_concept=%s) — skipping",
            primary_concept_id,
        )
        state["csod_cross_concept_confirmed"] = True
        state["csod_checkpoint_resolved"] = True
        return state

    logger.info(
        "[cross_concept_check] Found %d cross-concept areas for primary_concept=%s",
        len(cross_areas),
        primary_concept_id,
    )

    # Build options for checkpoint UI
    options = [
        {
            "area_id": a["area_id"],
            "concept_id": a["concept_id"],
            "label": a["display_name"],
            "description": a["description"],
            "score": a["score"],
        }
        for a in cross_areas
    ]

    primary_area = state.get("csod_primary_area") or {}
    primary_area_name = primary_area.get("display_name") or primary_area.get("area_id") or primary_concept_id

    message = (
        f"The causal analysis revealed connections that may span multiple analytical domains. "
        f"Your primary focus is **{primary_area_name}**. "
        f"The following areas from related domains could enrich your analysis — "
        f"select any you'd like to include, or skip to continue."
    )

    checkpoint = ConversationCheckpoint(
        phase="cross_concept_check",
        turn=ConversationTurn(
            phase="cross_concept_check",
            turn_type=TurnOutputType.CROSS_CONCEPT_CHECK,
            message=message,
            options=options,
            metadata={
                "primary_concept_id": primary_concept_id,
                "primary_area_name": primary_area_name,
                "cross_concept_areas": cross_areas,
            },
        ),
        resume_with_field="csod_cross_concept_confirmed",
    )

    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    # Store the full cross_areas list so it's available after user confirms
    state["csod_cross_concept_areas"] = cross_areas

    logger.info("[cross_concept_check] Checkpoint created with %d options", len(options))
    return state
