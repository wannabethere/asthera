"""
Concept Confirmation Node

Phase 0B: After concept resolution, confirms matched concepts with user.
"""
import logging
from typing import Dict, Any

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType, TurnQuestion
from app.conversation.config import VerticalConversationConfig

logger = logging.getLogger(__name__)


def concept_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Concept confirmation node - shows matched concepts to user for confirmation.
    
    State reads: csod_concept_matches, csod_selected_datasource
    State writes: csod_conversation_checkpoint (CONFIRMATION type)
    resume_with_field: csod_confirmed_concept_ids
    """
    concept_matches = state.get("csod_concept_matches", [])
    
    if not concept_matches:
        # Zero-match fallback: ask user to rephrase
        checkpoint = ConversationCheckpoint(
            phase="concept_confirm",
            turn=ConversationTurn(
                phase="concept_confirm",
                turn_type=TurnOutputType.CONFIRMATION,
                message=(
                    "I couldn't find a clear match for your question. Could you rephrase it "
                    "or provide more context about what you're trying to understand?"
                ),
                options=[
                    {"id": "rephrase", "label": "Let me rephrase", "action": "rephrase"},
                ],
            ),
            resume_with_field="user_query",  # Will resume at concept_resolver with new query
        )
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
        return state
    
    # Format top matched concept for confirmation
    primary_concept = concept_matches[0]
    concept_name = primary_concept.get("display_name", primary_concept.get("concept_id", "this concept"))
    
    # Build confirmation message
    message = (
        f"I understand you're asking about {concept_name}. "
        f"Is that the right focus, or would you like me to look at something else?"
    )
    
    # Build options
    options = [
        {
            "id": "confirm_primary",
            "label": f"Yes — {concept_name} is right",
            "action": "confirm",
            "concept_ids": [primary_concept["concept_id"]],
        },
    ]
    
    # Add "Add another area" option if there are additional concepts
    if len(concept_matches) > 1:
        additional_concepts = concept_matches[1:3]  # Up to 2 more
        additional_options = [
            {
                "id": f"add_{c.get('concept_id', '')}",
                "label": c.get("display_name", c.get("concept_id", "")),
                "concept_id": c.get("concept_id", ""),
            }
            for c in additional_concepts
        ]
        options.append({
            "id": "add_another",
            "label": "Add another area",
            "action": "multi_select",
            "sub_options": additional_options,
        })
    
    options.append({
        "id": "rephrase",
        "label": "Let me rephrase",
        "action": "rephrase",
    })
    
    checkpoint = ConversationCheckpoint(
        phase="concept_confirm",
        turn=ConversationTurn(
            phase="concept_confirm",
            turn_type=TurnOutputType.CONFIRMATION,
            message=message,
            options=options,
            metadata={
                "concept_matches": concept_matches[:3],  # Top 3 for reference
            },
        ),
        resume_with_field="csod_confirmed_concept_ids",
    )
    
    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False
    
    logger.info(f"Concept confirmation checkpoint created for {len(concept_matches)} matches")
    
    return state
