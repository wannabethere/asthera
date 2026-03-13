"""
DT Scoping Node - DT Phase 0D (Main Fix)

The missing scoping node for the DT workflow. Builds scoping questions based on the confirmed
template and framework. Template A/C always ask threat_scenario and severity. Template B (triage-only)
skips threat_scenario. Dashboard template asks persona.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import build_scoping_questions, create_checkpoint

logger = logging.getLogger(__name__)


def dt_scope_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    DT scoping node - main fix for DT workflow.
    
    State reads: dt_playbook_template (confirmed), framework_id (confirmed)
    State writes: dt_conversation_checkpoint (SCOPING type)
    resume_with_field: dt_scoping_answers
    
    Filters always included: time_period
    Filters for template A/C: + severity, threat_scenario, environment
    Filters for template B: + severity, environment (threat_scenario skipped — triage is reactive)
    Filters for dashboard template: + persona (as DECISION question)
    
    is_leen_request and generate_sql: collected here as single-select yes/no options. Both default to False.
    """
    template = state.get("dt_playbook_template", "A")
    checkpoint_key = f"{config.state_key_prefix}_conversation_checkpoint"
    resolved_key = f"{config.state_key_prefix}_checkpoint_resolved"
    
    # Build list of filter names to ask about
    filter_names_to_ask = list(config.always_include_filters)  # Start with always_include_filters
    
    # Add template-specific filters
    if template in ["A", "C"]:
        # Detection-focused templates: ask about threat scenario
        filter_names_to_ask.extend(["severity", "threat_scenario", "environment"])
    elif template == "B":
        # Triage-only: skip threat_scenario (triage is reactive)
        filter_names_to_ask.extend(["severity", "environment"])
    # Note: persona for dashboard template is handled separately in persona_confirm_node
    
    # Always add is_leen_request and generate_sql for all templates
    filter_names_to_ask.extend(["is_leen_request", "generate_sql"])
    
    # Build questions using helper
    questions_to_ask = build_scoping_questions(config, filter_names_to_ask)
    
    # If no questions, skip scoping
    if not questions_to_ask:
        logger.info("No scoping questions to ask - scoping complete")
        state[f"{config.state_key_prefix}_scoping_complete"] = True
        return state
    
    # Create checkpoint using helper
    turn = ConversationTurn(
        phase="dt_scoping",
        turn_type=TurnOutputType.SCOPING,
        message="A few more questions to make sure I'm looking in the right place:",
        questions=questions_to_ask,
    )
    
    state = create_checkpoint(
        state, config, "dt_scoping", turn, "dt_scoping_answers"
    )
    
    logger.info(f"DT scoping checkpoint created with {len(questions_to_ask)} questions")
    
    return state
