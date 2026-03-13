"""
Compliance Scoping Node - Compliance Phase 0D (Main Fix)

The missing scoping node for the compliance workflow. Builds the scoping questions based on
the confirmed intent. Each intent has a different set of always_include_filters and optional filters.
Unknown filter names are silently skipped. Caps at max_scoping_questions_per_turn.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import build_scoping_questions, create_checkpoint

logger = logging.getLogger(__name__)


def compliance_scope_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Compliance scoping node - main fix for compliance workflow.
    
    State reads: intent, framework_id (confirmed), selected_data_sources (confirmed)
    State writes: compliance_conversation_checkpoint (SCOPING type)
    resume_with_field: compliance_scoping_answers
    
    Filters always included: severity, time_period
    Filters included for detection_engineering: + threat_scenario, environment
    Filters included for gap_analysis: + assessment_scope
    Filters included for cross_framework_mapping: + secondary_frameworks
    Filters included for dashboard_generation: + persona (as DECISION question)
    
    Empty filter case: sets compliance_scoping_complete=True, skips checkpoint. No unnecessary questions.
    """
    intent = state.get("intent", "")
    framework_id = state.get("framework_id")
    checkpoint_key = f"{config.state_key_prefix}_conversation_checkpoint"
    resolved_key = f"{config.state_key_prefix}_checkpoint_resolved"
    
    # Build list of filter names to ask about
    filter_names_to_ask = list(config.always_include_filters)  # Start with always_include_filters
    
    # Add intent-specific filters
    if intent == "detection_engineering":
        filter_names_to_ask.extend(["threat_scenario", "environment"])
    elif intent == "gap_analysis":
        filter_names_to_ask.append("assessment_scope")
    elif intent == "cross_framework_mapping":
        filter_names_to_ask.append("secondary_frameworks")
    # Note: persona for dashboard_generation is handled separately in persona_confirm_node
    
    # Build questions using helper
    questions_to_ask = build_scoping_questions(config, filter_names_to_ask, framework_id)
    
    # If no questions, skip scoping
    if not questions_to_ask:
        logger.info("No scoping questions to ask - scoping complete")
        state[f"{config.state_key_prefix}_scoping_complete"] = True
        return state
    
    # Create checkpoint using helper
    turn = ConversationTurn(
        phase="compliance_scoping",
        turn_type=TurnOutputType.SCOPING,
        message="A few more questions to make sure I'm looking in the right place:",
        questions=questions_to_ask,
    )
    
    state = create_checkpoint(
        state, config, "compliance_scoping", turn, "compliance_scoping_answers"
    )
    
    logger.info(f"Compliance scoping checkpoint created with {len(questions_to_ask)} questions")
    
    return state
