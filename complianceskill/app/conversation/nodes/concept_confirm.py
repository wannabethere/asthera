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

    # Resume / payload merge: user already chose concepts — do not recreate this checkpoint
    confirmed_ids = [
        str(x) for x in (state.get("csod_confirmed_concept_ids") or []) if x
    ]
    if not confirmed_ids:
        cr = (state.get("csod_checkpoint_responses") or {}).get("concept_select")
        if isinstance(cr, dict) and cr.get("csod_confirmed_concept_ids"):
            confirmed_ids = [str(x) for x in cr["csod_confirmed_concept_ids"] if x]

    # Frontend sends csod_concepts_confirmed=True but omits the IDs — derive from preserved selected_concepts
    if not confirmed_ids and state.get("csod_concepts_confirmed"):
        selected_concepts = state.get("csod_selected_concepts") or []
        if selected_concepts:
            confirmed_ids = [
                str(c.get("concept_id"))
                for c in selected_concepts
                if isinstance(c, dict) and c.get("concept_id")
            ]
            logger.info(f"Derived confirmed_ids from csod_selected_concepts: {confirmed_ids}")
        elif concept_matches:
            # Last resort: use top concept match
            confirmed_ids = [str(concept_matches[0].get("concept_id", ""))]
            logger.info(f"Derived confirmed_ids from top concept_match: {confirmed_ids}")

    if confirmed_ids and concept_matches:
        selected = [
            {
                "concept_id": m["concept_id"],
                "display_name": m.get("display_name", m["concept_id"]),
                "score": m.get("score", 0.0),
                "coverage_confidence": m.get("coverage_confidence", 0.0),
            }
            for m in concept_matches
            if isinstance(m, dict) and str(m.get("concept_id")) in set(confirmed_ids)
        ]
        state["csod_selected_concepts"] = selected
        state["csod_confirmed_concept_ids"] = confirmed_ids
        state["csod_concepts_confirmed"] = True
        state["csod_conversation_checkpoint"] = None
        state["csod_checkpoint_resolved"] = True
        all_pids: list = []
        all_refs: list = []
        for m in concept_matches:
            if isinstance(m, dict) and str(m.get("concept_id")) in set(confirmed_ids):
                all_pids.extend(m.get("project_ids") or [])
                all_refs.extend(m.get("mdl_table_refs") or [])
        state["csod_resolved_project_ids"] = list(dict.fromkeys(all_pids))
        state["csod_resolved_mdl_table_refs"] = list(dict.fromkeys(all_refs))
        if all_pids:
            state["csod_primary_project_id"] = all_pids[0]
        logger.info("Concepts already confirmed (%s); skipping concept_confirm checkpoint", confirmed_ids)
        return state

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
