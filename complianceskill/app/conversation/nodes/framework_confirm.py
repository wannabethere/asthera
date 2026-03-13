"""
Framework Confirmation Node - Shared for Compliance and DT

If a framework signal is found in the user query (keyword match), presents CONFIRMATION turn.
If no signal found, presents DECISION turn with all framework options.
"""
import logging

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.security_helpers import create_checkpoint, detect_from_keywords, should_skip_node

logger = logging.getLogger(__name__)


def framework_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Framework confirmation node - shared for both agents.
    
    State reads: user_query, framework_id (if pre-extracted)
    State writes: compliance_conversation_checkpoint or dt_conversation_checkpoint (CONFIRMATION or DECISION)
    resume_with_field: framework_id
    
    Keyword signals: 'hipaa', 'phi' → HIPAA. 'nist', 'csf' → NIST CSF. 'soc 2', 'trust services' → SOC 2.
    'iso 27001' → ISO 27001. 'pci' → PCI DSS.
    
    Adjust option: If CONFIRMATION turn, user can select 'Use a different framework' → graph shows DECISION with all options.
    """
    user_query = state.get("user_query", "").lower()
    pre_extracted_framework = state.get("framework_id")
    
    # Check if framework is already confirmed
    if pre_extracted_framework and state.get(f"{config.state_key_prefix}_framework_confirmed", False):
        logger.info(f"Framework pre-confirmed: {pre_extracted_framework}, skipping")
        return state
    
    # Keyword matching for framework detection
    framework_keywords = {
        "hipaa": ["hipaa", "phi", "health insurance"],
        "nist_csf": ["nist", "csf", "cybersecurity framework"],
        "soc2": ["soc 2", "soc2", "trust services"],
        "iso27001": ["iso 27001", "iso27001", "iso/iec 27001"],
        "pci_dss": ["pci", "pci dss", "payment card"],
        "cis_controls": ["cis", "cis controls"],
    }
    
    detected_framework_id = detect_from_keywords(user_query, framework_keywords, config.framework_options)
    
    # Also check pre-extracted framework
    if not detected_framework_id and pre_extracted_framework:
        detected_framework_id = pre_extracted_framework
    
    if detected_framework_id:
        # High confidence - show CONFIRMATION turn
        framework_label = next(
            (opt["label"] for opt in config.framework_options if opt["id"] == detected_framework_id),
            detected_framework_id
        )
        
        turn = ConversationTurn(
            phase="framework_confirm",
            turn_type=TurnOutputType.CONFIRMATION,
            message=f"I will use {framework_label}. Is that correct?",
            options=[
                {
                    "id": "confirm",
                    "label": f"Yes — {framework_label} is correct",
                    "action": "confirm",
                    "framework_id": detected_framework_id,
                },
                {
                    "id": "adjust",
                    "label": "Use a different framework",
                    "action": "adjust",
                },
            ],
        )
    else:
        # Low confidence - show DECISION turn with all options
        turn = ConversationTurn(
            phase="framework_confirm",
            turn_type=TurnOutputType.DECISION,
            message="Which compliance framework should I use?",
            options=[
                {
                    "id": opt["id"],
                    "label": opt["label"],
                    "description": opt.get("description", ""),
                }
                for opt in config.framework_options
            ],
        )
    
    state = create_checkpoint(state, config, "framework_confirm", turn, "framework_id")
    
    logger.info(f"Framework confirmation checkpoint created (detected: {detected_framework_id})")
    
    return state
