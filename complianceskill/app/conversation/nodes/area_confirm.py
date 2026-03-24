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
    
    Uses _generate_area_confirmation() ported from archived/csod/csod_planner_workflow_legacy.py.
    
    State reads: csod_area_matches, csod_selected_concepts, user_query
    State writes: csod_area_confirmation, csod_conversation_checkpoint (CONFIRMATION type)
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
        logger.error("area_confirm: no area matches in state — LLM resolver should have populated these")
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
    
    # Generate confirmation message using existing function
    try:
        from app.agents.csod.csod_planner_workflow import _generate_area_confirmation
        from app.ingestion.registry_vector_lookup import RecommendationAreaMatch
        
        # Convert area_matches to RecommendationAreaMatch objects for _generate_area_confirmation
        area_match_objects = []
        for area_dict in area_matches:
            # Create a minimal RecommendationAreaMatch object
            area_match_objects.append(RecommendationAreaMatch(
                area_id=area_dict.get("area_id", ""),
                concept_id=area_dict.get("concept_id", ""),
                display_name=area_dict.get("display_name", ""),
                description=area_dict.get("description", ""),
                score=area_dict.get("score", 0.0),
                metrics=area_dict.get("metrics", []),
                kpis=area_dict.get("kpis", []),
                filters=area_dict.get("filters", []),
                dashboard_axes=area_dict.get("dashboard_axes", []),
                causal_paths=area_dict.get("causal_paths", []),
                natural_language_questions=area_dict.get("natural_language_questions", []),
                data_requirements=area_dict.get("data_requirements", []),
            ))
        
        confirmation = _generate_area_confirmation(
            user_query=user_query,
            selected_concepts=selected_concepts,
            area_matches=area_match_objects,
        )
        
        state["csod_area_confirmation"] = confirmation
        
        # Build area options (up to 3) — include description, metrics, kpis, and sample questions
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
            }
            for area_dict in area_matches[:3]
        ]

        checkpoint = ConversationCheckpoint(
            phase="area_confirm",
            turn=ConversationTurn(
                phase="area_confirm",
                turn_type=TurnOutputType.CONFIRMATION,
                message=confirmation.get("message", "I've identified relevant analysis areas. Which one should I focus on?"),
                options=area_options,
                metadata={
                    "primary_area_id": confirmation.get("primary_area_id", ""),
                    "area_matches": area_matches[:3],
                },
            ),
            resume_with_field="csod_confirmed_area_id",
        )
        
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
        
        logger.info(f"Area confirmation checkpoint created for {len(area_matches)} areas")
        
    except Exception as e:
        logger.error(f"Error generating area confirmation: {e}", exc_info=True)
        # Fallback confirmation — still include rich fields
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
                    f"I've identified {len(area_matches)} relevant analysis areas. "
                    f"Which one should I focus on?"
                ),
                options=area_options,
            ),
            resume_with_field="csod_confirmed_area_id",
        )
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
    
    return state
