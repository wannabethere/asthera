"""
Persona Confirmation Node - Shared for Compliance and DT (Dashboard Intent Only)

Asks for persona (SOC analyst, CISO, compliance officer) when intent is dashboard_generation.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import create_checkpoint

logger = logging.getLogger(__name__)


def persona_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Persona confirmation node - asks for dashboard audience.
    
    State reads: intent (must be dashboard_generation)
    State writes: compliance_conversation_checkpoint or dt_conversation_checkpoint (DECISION type)
    resume_with_field: persona or dt_dashboard_persona
    """
    intent = state.get("intent", "")
    template = state.get("dt_playbook_template", "")
    
    # Only run for dashboard intent/template
    if intent != "dashboard_generation" and template != "dashboard":
        return state
    
    # Get persona template
    if "persona" not in config.scoping_question_templates:
        logger.warning("No persona template found, skipping persona confirmation")
        return state
    
    persona_template = config.scoping_question_templates["persona"]
    persona_key = persona_template.state_key
    
    # Check if already confirmed
    if state.get(persona_key):
        logger.info(f"Persona already set: {state.get(persona_key)}, skipping")
        return state
    
    turn = ConversationTurn(
        phase="persona_confirm",
        turn_type=TurnOutputType.DECISION,
        message="Who is this dashboard for?",
        options=[
            {"id": opt["id"], "label": opt["label"]}
            for opt in persona_template.options
        ],
    )
    
    state = create_checkpoint(state, config, "persona_confirm", turn, persona_key)
    
    logger.info("Persona confirmation checkpoint created")
    
    return state
