"""
DT Template Confirmation Node - DT Phase 0A (First Question)

The most important new node in the DT conversation planner. Always runs first — before framework,
before datasource, before anything else. The template selection directly determines which branches
of the DT pipeline fire.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import create_checkpoint, should_skip_node

logger = logging.getLogger(__name__)


def dt_template_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    DT template confirmation node - first question in DT conversation.
    
    State reads: user_query, dt_playbook_template (if pre-set in API context)
    State writes: dt_conversation_checkpoint (DECISION type — large cards, always shown)
    resume_with_field: dt_playbook_template
    
    Never skipped: Even if query contains 'detection', the template still needs explicit confirmation
    — 'detection' could mean A or C.
    
    Skip condition: dt_playbook_template is already set in state AND api_context.confirmed=True.
    This allows programmatic pre-fill from the calling service.
    """
    # Skip if template is pre-set and confirmed via API context
    if should_skip_node(state, config, "dt_playbook_template", "confirmed"):
        logger.info(f"Template pre-set and confirmed: {state.get('dt_playbook_template')}, skipping")
        return state
    
    # Always show DECISION turn with all template options
    turn = ConversationTurn(
        phase="dt_template_confirm",
        turn_type=TurnOutputType.DECISION,
        message="What type of detection and triage output do you need?",
        options=[
            {
                "id": opt["id"],
                "label": opt["label"],
                "description": opt.get("description", ""),
            }
            for opt in config.template_options or []
        ],
    )
    
    state = create_checkpoint(state, config, "dt_template_confirm", turn, "dt_playbook_template")
    
    logger.info("DT template confirmation checkpoint created")
    
    return state
