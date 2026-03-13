"""
Execution Preview Node - Compliance Phase 0F

Specific to the compliance workflow. After scoping is complete, this node summarises the execution
plan that the planner would generate — the sequence of specialist agents that will run — and
presents it as an EXECUTION_PREVIEW turn. User approves or adjusts before planner_node fires.
"""
import logging
from typing import Dict, Any, List

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType
from app.conversation.security_config import SecurityConversationConfig

logger = logging.getLogger(__name__)


def execution_preview_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Execution preview node - shows execution plan before planner fires.
    
    State reads: intent, framework_id, compliance_scoping_answers
    State writes: compliance_conversation_checkpoint (EXECUTION_PREVIEW type)
    resume_with_field: compliance_execution_confirmed
    
    The preview is template-based (no LLM call). intent=gap_analysis always runs gap_analysis_node.
    intent=cross_framework_mapping always runs cross_framework_mapper_node. Full-planner intents
    preview the planned agent chain: framework_analyzer → detection_engineer → playbook_writer → test_generator.
    
    Approve option: sets compliance_execution_confirmed=True. Graph continues to intent_classifier (with bypass) → profile_resolver → downstream agents.
    Adjust option: sets resume_with_field=intent. Graph resumes at intent_confirm_node — user picks a different intent.
    """
    intent = state.get("intent", "")
    framework_id = state.get("framework_id", "")
    checkpoint_key = f"{config.state_key_prefix}_conversation_checkpoint"
    resolved_key = f"{config.state_key_prefix}_checkpoint_resolved"
    
    # Build execution plan based on intent (template-based, no LLM)
    execution_steps = []
    
    if intent == "gap_analysis":
        execution_steps = [
            {"agent": "gap_analysis", "description": "Analyze compliance gaps against framework controls"}
        ]
    elif intent == "cross_framework_mapping":
        execution_steps = [
            {"agent": "cross_framework_mapper", "description": "Map controls across multiple frameworks"}
        ]
    elif intent == "risk_control_mapping":
        execution_steps = [
            {"agent": "risk_control_mapper", "description": "Map risks to applicable controls"}
        ]
    elif intent == "dashboard_generation":
        execution_steps = [
            {"agent": "dashboard_generator", "description": "Generate compliance dashboard with KPIs and metrics"}
        ]
    else:
        # Full planner intents (detection_engineering and others)
        execution_steps = [
            {"agent": "framework_analyzer", "description": "Analyze framework controls and requirements"},
            {"agent": "detection_engineer", "description": "Generate SIEM rules and detection logic"},
            {"agent": "playbook_writer", "description": "Write response playbooks"},
            {"agent": "test_generator", "description": "Generate validation test scripts"},
        ]
    
    # Build preview message
    framework_label = next(
        (opt["label"] for opt in config.framework_options if opt["id"] == framework_id),
        framework_id
    ) if framework_id else "the selected framework"
    
    message = (
        f"I will analyze your compliance posture against {framework_label} and generate the following:\n\n"
    )
    for i, step in enumerate(execution_steps, 1):
        message += f"{i}. {step['description']}\n"
    message += "\nDoes this plan look good, or would you like to adjust anything?"
    
    checkpoint = ConversationCheckpoint(
        phase="execution_preview",
        turn=ConversationTurn(
            phase="execution_preview",
            turn_type=TurnOutputType.EXECUTION_PREVIEW,
            message=message,
            options=[
                {
                    "id": "approve",
                    "label": "Yes, proceed",
                    "action": "approve",
                },
                {
                    "id": "adjust",
                    "label": "Let me adjust",
                    "action": "adjust",
                },
            ],
            metadata={
                "execution_steps": execution_steps,
                "intent": intent,
                "framework_id": framework_id,
            },
        ),
        resume_with_field="compliance_execution_confirmed",
    )
    
    state[checkpoint_key] = checkpoint.to_dict()
    state[resolved_key] = False
    
    logger.info(f"Execution preview checkpoint created for intent: {intent}")
    
    return state
