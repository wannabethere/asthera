"""
Helper functions for security conversation nodes.

Common patterns extracted to reduce duplication.
"""
import logging
from typing import Dict, Any, List, Optional

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType, TurnQuestion
from app.conversation.security_config import SecurityConversationConfig

logger = logging.getLogger(__name__)


def create_checkpoint(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
    phase: str,
    turn: ConversationTurn,
    resume_with_field: str,
) -> EnhancedCompliancePipelineState:
    """
    Helper to create and set a checkpoint in state.
    
    Args:
        state: Pipeline state
        config: Security conversation config
        phase: Phase identifier
        turn: Conversation turn to show
        resume_with_field: Field to inject user response into
    
    Returns:
        Updated state with checkpoint set
    """
    checkpoint_key = f"{config.state_key_prefix}_conversation_checkpoint"
    resolved_key = f"{config.state_key_prefix}_checkpoint_resolved"
    
    checkpoint = ConversationCheckpoint(
        phase=phase,
        turn=turn,
        resume_with_field=resume_with_field,
    )
    
    state[checkpoint_key] = checkpoint.to_dict()
    state[resolved_key] = False
    
    return state


def should_skip_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
    check_field: str,
    check_condition: Optional[str] = None,
) -> bool:
    """
    Check if a node should be skipped based on pre-resolved state.
    
    Args:
        state: Pipeline state
        config: Security conversation config
        check_field: Field to check in state
        check_condition: Optional condition key in api_context (e.g., "confirmed", "datasources_confirmed")
    
    Returns:
        True if node should be skipped
    """
    value = state.get(check_field)
    if not value:
        return False
    
    # If check_condition is provided, verify it's set in api_context
    if check_condition is not None:
        api_context = state.get("api_context", {})
        if not api_context.get(check_condition, False):
            return False
    
    # Check if already confirmed via compliance_profile
    if state.get("compliance_profile", {}).get("playbook_resolved_intent"):
        return True
    
    return False


def build_scoping_questions(
    config: SecurityConversationConfig,
    filter_names: List[str],
    framework_id: Optional[str] = None,
) -> List[TurnQuestion]:
    """
    Build scoping questions from filter names.
    
    Args:
        config: Security conversation config
        filter_names: List of filter names to ask about
        framework_id: Optional framework ID to exclude from secondary_frameworks
    
    Returns:
        List of TurnQuestion objects
    """
    questions: List[TurnQuestion] = []
    seen_filters = set()
    
    # Handle secondary_frameworks specially - exclude primary framework
    if "secondary_frameworks" in filter_names and framework_id:
        if "secondary_frameworks" in config.scoping_question_templates:
            template = config.scoping_question_templates["secondary_frameworks"]
            available_frameworks = [
                {"id": opt["id"], "label": opt["label"]}
                for opt in config.framework_options
                if opt["id"] != framework_id
            ]
            if available_frameworks:
                questions.append(TurnQuestion(
                    id=template.question_id,
                    label=template.label,
                    interaction_mode=template.interaction_mode,
                    options=available_frameworks,
                    state_key=template.state_key,
                    required=template.required,
                ))
                seen_filters.add("secondary_frameworks")
    
    # Add other filters
    for filter_name in filter_names:
        if filter_name in seen_filters:
            continue
        
        if filter_name in config.scoping_question_templates:
            template = config.scoping_question_templates[filter_name]
            questions.append(TurnQuestion(
                id=template.question_id,
                label=template.label,
                interaction_mode=template.interaction_mode,
                options=template.options,
                state_key=template.state_key,
                required=template.required,
            ))
            seen_filters.add(filter_name)
        else:
            logger.debug(f"Unknown filter_name '{filter_name}' - skipping")
    
    # Cap at max_scoping_questions_per_turn
    if len(questions) > config.max_scoping_questions_per_turn:
        questions = questions[:config.max_scoping_questions_per_turn]
        logger.info(f"Capped scoping questions to {config.max_scoping_questions_per_turn}")
    
    return questions


def detect_from_keywords(
    query: str,
    keyword_map: Dict[str, List[str]],
    options: List[Dict[str, str]],
) -> Optional[str]:
    """
    Detect a value from query using keyword matching.
    
    Args:
        query: User query (lowercased)
        keyword_map: Map of value_id -> list of keywords
        options: List of option dicts with 'id' field
    
    Returns:
        Detected value ID or None
    """
    for value_id, keywords in keyword_map.items():
        if any(kw in query for kw in keywords):
            # Verify it exists in options
            if any(opt["id"] == value_id for opt in options):
                return value_id
    return None
