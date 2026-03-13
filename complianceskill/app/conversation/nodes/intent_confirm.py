"""
Intent Confirmation Node - Compliance Phase 0A

The first node in the compliance conversation planner. Runs before intent_classifier.
Checks whether intent is already inferrable from the query with high confidence.
If yes, presents it as a CONFIRMATION turn. If not, presents the full DECISION turn with all intent options.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import create_checkpoint, detect_from_keywords, should_skip_node

logger = logging.getLogger(__name__)


def intent_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Intent confirmation node - first question in compliance conversation.
    
    State reads: user_query, intent (if pre-resolved by API context)
    State writes: compliance_conversation_checkpoint (DECISION or CONFIRMATION type)
    resume_with_field: intent
    
    High-confidence signal: keywords like 'gap analysis', 'detect', 'dashboard' resolve to CONFIRMATION.
    Ambiguous queries get DECISION.
    
    On resume: state.intent is set. Graph continues to framework_confirm_node.
    """
    user_query = state.get("user_query", "").lower()
    
    # Check if intent is already pre-resolved and confirmed
    if should_skip_node(state, config, "intent"):
        logger.info(f"Intent pre-resolved: {state.get('intent')}, skipping confirmation")
        return state
    
    # Keyword matching for high-confidence intent detection
    intent_keywords = {
        "gap_analysis": ["gap", "missing", "not implemented", "compliance gap"],
        "detection_engineering": ["detect", "siem", "rule", "query", "sigma"],
        "risk_control_mapping": ["risk", "control", "map risk"],
        "cross_framework_mapping": ["cross framework", "multiple framework", "map across"],
        "dashboard_generation": ["dashboard", "visualize", "show me", "metrics"],
    }
    
    detected_intent = detect_from_keywords(user_query, intent_keywords, config.intent_options)
    
    if detected_intent:
        # High confidence - show CONFIRMATION turn
        intent_label = next(
            (opt["label"] for opt in config.intent_options if opt["id"] == detected_intent),
            detected_intent
        )
        
        turn = ConversationTurn(
            phase="intent_confirm",
            turn_type=TurnOutputType.CONFIRMATION,
            message=f"I understand you want to {intent_label.lower()}. Is that correct?",
            options=[
                {
                    "id": "confirm",
                    "label": f"Yes — {intent_label} is correct",
                    "action": "confirm",
                    "intent": detected_intent,
                },
                {
                    "id": "adjust",
                    "label": "Let me choose a different option",
                    "action": "adjust",
                },
            ],
        )
    else:
        # Low confidence - show DECISION turn with all options
        turn = ConversationTurn(
            phase="intent_confirm",
            turn_type=TurnOutputType.DECISION,
            message="What would you like me to help you with?",
            options=[
                {
                    "id": opt["id"],
                    "label": opt["label"],
                    "description": opt.get("description", ""),
                }
                for opt in config.intent_options
            ],
        )
    
    state = create_checkpoint(state, config, "intent_confirm", turn, "intent")
    
    logger.info(f"Intent confirmation checkpoint created (detected: {detected_intent})")
    
    return state
