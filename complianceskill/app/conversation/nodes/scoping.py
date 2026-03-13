"""
Scoping Node - The Main Fix

Phase 0C: Asks scoping questions based on area filters.
This is the missing node that causes scoping_answers to always be empty.
"""
import logging
from typing import Dict, Any, List

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType, TurnQuestion
from app.conversation.config import VerticalConversationConfig
from app.ingestion.registry_vector_lookup import resolve_scoping_to_areas

logger = logging.getLogger(__name__)


def scoping_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Scoping node - asks user for scoping context before area matching.
    
    This node:
    1. Runs a preliminary area lookup (without scoping context) to get area.filters[]
    2. Resolves each filter_name against config.scoping_question_templates
    3. Always includes config.always_include_filters
    4. Caps at config.max_scoping_questions_per_turn
    5. Writes a SCOPING turn checkpoint and stops
    
    State reads: csod_area_matches (preliminary), csod_confirmed_concept_ids
    State writes: csod_conversation_checkpoint (SCOPING type)
    resume_with_field: csod_scoping_answers
    
    On resume: csod_scoping_answers is populated. Graph continues to area_matcher,
    which now runs with full scoping context.
    """
    confirmed_concept_ids = state.get("csod_confirmed_concept_ids", [])
    preliminary_area_matches = state.get("csod_preliminary_area_matches", [])
    
    if not confirmed_concept_ids:
        logger.warning("No confirmed concepts for scoping - skipping")
        state["csod_scoping_complete"] = True
        return state
    
    # Use preliminary area matches from state (set by preliminary_area_matcher_node)
    if not preliminary_area_matches:
        logger.warning("No preliminary areas found - skipping scoping")
        state["csod_scoping_complete"] = True
        return state
    
    try:
        primary_area = preliminary_area_matches[0]
        area_filters = primary_area.get("filters", [])
        
        # If no filters, skip scoping
        if not area_filters:
            logger.info("Area has no filters - scoping complete")
            state["csod_scoping_complete"] = True
            return state
        
        # Build list of questions to ask
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
        
        logger.info(f"Scoping checkpoint created with {len(questions_to_ask)} questions")
        
    except Exception as e:
        logger.error(f"Error in scoping node: {e}", exc_info=True)
        # On error, skip scoping and continue
        state["csod_scoping_complete"] = True
        state["csod_scoping_answers"] = {}
    
    return state
