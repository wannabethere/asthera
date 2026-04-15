"""
Area Confirmation Node

Phase 0E: After area matching (with scoping context), confirms area with user.
"""
import logging
from typing import Dict, Any, List

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType
from app.conversation.config import VerticalConversationConfig

logger = logging.getLogger(__name__)


def area_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Area confirmation node - confirms matched recommendation area with user.
    
    State reads: csod_area_matches, csod_selected_concepts, user_query
    State writes: csod_conversation_checkpoint (CONFIRMATION type)
    resume_with_field: csod_confirmed_area_id
    """
    area_matches = state.get("csod_area_matches", [])
    selected_concepts = state.get("csod_selected_concepts", [])
    user_query = state.get("user_query", "")

    # If area was already confirmed (resume after user selection), skip creating a new checkpoint.
    # This prevents an infinite loop when the workflow re-runs the node on resume.
    confirmed_area_id = state.get("csod_confirmed_area_id")
    if confirmed_area_id:
        logger.info(f"Area already confirmed ({confirmed_area_id}), skipping area_confirm checkpoint")
        state["csod_checkpoint_resolved"] = True
        # Promote the confirmed area to csod_primary_area if not already set
        if not state.get("csod_primary_area") and area_matches:
            match = next((a for a in area_matches if a.get("area_id") == confirmed_area_id), area_matches[0])
            state["csod_primary_area"] = {
                "area_id": match.get("area_id", ""),
                "display_name": match.get("display_name", ""),
                "metrics": match.get("metrics", []),
                "kpis": match.get("kpis", []),
                "data_requirements": match.get("data_requirements", []),
                "causal_paths": match.get("causal_paths", []),
            }
        return state

    if not area_matches:
        # ── Safety-net: pull directly from csod_llm_resolved_areas ─────────────
        # This handles the case where area_matcher couldn't populate csod_area_matches
        # but csod_intent_confirm already resolved areas via the LLM planner.
        llm_resolved: Dict[str, Any] = state.get("csod_llm_resolved_areas") or {}
        confirmed_concept_ids: List[str] = state.get("csod_confirmed_concept_ids") or []
        if confirmed_concept_ids:
            # Try each concept in order; accept first concept that has non-empty area list
            for cid in confirmed_concept_ids:
                candidate_areas = (
                    llm_resolved.get(str(cid))
                    or llm_resolved.get(cid)
                    or []
                )
                # Filter out degenerate entries with empty area_id
                candidate_areas = [a for a in candidate_areas if a.get("area_id")]
                if candidate_areas:
                    area_matches = candidate_areas[:3]
                    logger.warning(
                        "area_confirm: csod_area_matches was empty — recovered %d area(s) "
                        "from csod_llm_resolved_areas[%s]",
                        len(area_matches), cid,
                    )
                    # Write back so downstream nodes (metric_narration etc.) see them too
                    state["csod_area_matches"] = area_matches
                    break

    if not area_matches:
        # Last-resort: pull from area registry directly using concept ids
        confirmed_concept_ids_final: List[str] = state.get("csod_confirmed_concept_ids") or []
        if confirmed_concept_ids_final:
            try:
                from app.ingestion.mdl_intent_resolver import _load_area_registry
                area_reg = _load_area_registry()
                rec_map = area_reg.get("concept_recommendations", {})
                for cid in confirmed_concept_ids_final:
                    registry_areas = rec_map.get(cid, {}).get("recommendation_areas", [])
                    valid = [a for a in registry_areas if a.get("area_id")]
                    if valid:
                        area_matches = valid[:3]
                        state["csod_area_matches"] = area_matches
                        logger.warning(
                            "area_confirm: populated %d area(s) from registry for concept '%s' "
                            "(all upstream area resolution paths failed)",
                            len(area_matches), cid,
                        )
                        break
            except Exception as exc:
                logger.error("area_confirm: registry fallback failed: %s", exc)

    if not area_matches:
        logger.error(
            "area_confirm: no area matches found via any path "
            "(concept_ids=%s, llm_resolved_keys=%s) — emitting rephrase fallback",
            state.get("csod_confirmed_concept_ids"),
            list((state.get("csod_llm_resolved_areas") or {}).keys())[:5],
        )
        checkpoint = ConversationCheckpoint(
            phase="area_confirm",
            turn=ConversationTurn(
                phase="area_confirm",
                turn_type=TurnOutputType.CONFIRMATION,
                message=(
                    "I had trouble identifying a relevant analysis area for your question. "
                    "Could you rephrase or add more context?"
                ),
                options=[
                    {"id": "rephrase", "label": "Let me rephrase", "action": "rephrase"},
                ],
            ),
            resume_with_field="user_query",
        )
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
        return state

    # ── Auto-confirm when only one area is available ──────────────────────────
    if len(area_matches) == 1:
        primary_area = area_matches[0]
        state["csod_confirmed_area_id"] = primary_area.get("area_id", "")
        state["csod_primary_area"] = {
            "area_id": primary_area.get("area_id", ""),
            "display_name": primary_area.get("display_name", ""),
            "metrics": primary_area.get("metrics", []),
            "kpis": primary_area.get("kpis", []),
            "data_requirements": primary_area.get("data_requirements", []),
            "causal_paths": primary_area.get("causal_paths", []),
        }
        state["csod_checkpoint_resolved"] = True
        logger.info(
            "area_confirm: single area '%s' — auto-confirmed, skipping checkpoint",
            state["csod_confirmed_area_id"],
        )
        return state

    # Build area options (up to 3) with rich fields for the frontend
    primary_area = area_matches[0]
    project_tables: dict = state.get("csod_resolved_project_tables") or {}

    area_options = [
        {
            "id": area_dict.get("area_id", ""),
            "label": area_dict.get("display_name", ""),
            "description": area_dict.get("description", ""),
            "area_id": area_dict.get("area_id", ""),
            "metrics": area_dict.get("metrics", [])[:4],
            "kpis": area_dict.get("kpis", [])[:3],
            "sample_questions": area_dict.get("natural_language_questions", [])[:2],
            "dashboard_axes": area_dict.get("dashboard_axes", [])[:3],
            # Attach MDL table details for each resolved project so the frontend
            # and downstream nodes know which tables back this area
            "project_tables": project_tables,
        }
        for area_dict in area_matches[:3]
    ]

    checkpoint = ConversationCheckpoint(
        phase="area_confirm",
        turn=ConversationTurn(
            phase="area_confirm",
            turn_type=TurnOutputType.CONFIRMATION,
            message=(
                f"I understand you're asking about {user_query}. "
                f"I've identified {len(area_matches)} relevant analysis area(s). "
                f"Which one should I focus on?"
            ),
            options=area_options,
            metadata={
                "primary_area_id": primary_area.get("area_id", ""),
                "area_matches": area_matches[:3],
            },
        ),
        resume_with_field="csod_confirmed_area_id",
    )

    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    logger.info(f"Area confirmation checkpoint created for {len(area_matches)} areas")
    return state
