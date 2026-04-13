"""
Compliance Conversation Planner Workflow

Conversation turn engine for the Compliance workflow. Collects user context (intent, framework,
datasources, scoping) before firing downstream agents.

Graph topology:
    intent_confirm_node (NEW - interrupt)
      → framework_confirm_node (NEW - interrupt)
        → datasource_scoping_node (NEW - interrupt)
          → compliance_scope_node (NEW - interrupt - main fix)
            → persona_confirm_node (NEW - interrupt, dashboard only)
              → execution_preview_node (NEW - interrupt)
                → intent_classifier (existing, with bypass)
                  → profile_resolver (existing)
                    → [downstream agents]
"""
import logging
from typing import Any

from langgraph.graph import StateGraph, END
from app.core.checkpointer_provider import get_checkpointer

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.intent_confirm import intent_confirm_node
from app.conversation.nodes.framework_confirm import framework_confirm_node
from app.conversation.nodes.datasource_scoping import datasource_scoping_node
from app.conversation.nodes.compliance_scope import compliance_scope_node
from app.conversation.nodes.persona_confirm import persona_confirm_node
from app.conversation.nodes.execution_preview import execution_preview_node

logger = logging.getLogger(__name__)


def _route_with_interrupt(state: EnhancedCompliancePipelineState, checkpoint_key: str, resolved_key: str) -> str:
    """
    Generic routing function used at every conversation node.
    
    Checks if checkpoint is set and not resolved - if so, route to 'interrupt' (END).
    Otherwise, clear checkpoint and route to 'continue'.
    """
    checkpoint = state.get(checkpoint_key)
    
    if checkpoint and not state.get(resolved_key):
        return "interrupt"  # → END, API handles client interaction
    
    # Clear checkpoint and continue
    state[checkpoint_key] = None
    state[resolved_key] = False
    
    return "continue"


def _wrap_node(node_func, config: SecurityConversationConfig):
    """Wrap a node function to inject config."""
    def wrapped(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
        return node_func(state, config)
    return wrapped


def workflow_router_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Workflow router - unpacks scoping answers and sets playbook_resolved_intent.
    
    After scoping answers are collected, workflow_router must unpack them into the
    compliance_profile and set playbook_resolved_intent to trigger the bypass.
    """
    scoping_answers = state.get("compliance_scoping_answers", {})
    intent = state.get("intent")
    selected_data_sources = state.get("selected_data_sources", [])
    persona = state.get("persona")
    
    # Build compliance_profile
    compliance_profile = state.get("compliance_profile", {})
    
    # Set playbook_resolved_intent to trigger bypass
    compliance_profile["playbook_resolved_intent"] = True
    
    # Unpack scoping answers into compliance_profile top-level keys
    if scoping_answers:
        compliance_profile.update({
            "severity_filter": scoping_answers.get("severity_filter"),
            "time_window": scoping_answers.get("time_window"),
            "environment": scoping_answers.get("environment"),
            "threat_scenario": scoping_answers.get("threat_scenario"),
            "assessment_scope": scoping_answers.get("assessment_scope"),
            "secondary_framework_ids": scoping_answers.get("secondary_framework_ids"),
            "asset_type": scoping_answers.get("asset_type"),
        })
    
    # Set persona if collected (dashboard intent)
    if persona:
        compliance_profile["persona"] = persona
    
    # Set selected_data_sources
    if selected_data_sources:
        compliance_profile["selected_data_sources"] = selected_data_sources
        state["selected_data_sources"] = selected_data_sources
    
    # Set intent
    if intent:
        state["intent"] = intent
    
    state["compliance_profile"] = compliance_profile
    
    logger.info(f"Workflow router: intent={intent}, framework={state.get('framework_id')}")
    
    return state


def build_compliance_conversation_planner(config: SecurityConversationConfig) -> StateGraph:
    """
    Build the compliance conversation planner workflow with interrupt mechanism.
    
    Args:
        config: SecurityConversationConfig instance for compliance
    
    Returns:
        Un-compiled StateGraph
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    checkpoint_key = f"{config.state_key_prefix}_conversation_checkpoint"
    resolved_key = f"{config.state_key_prefix}_checkpoint_resolved"
    
    # Add nodes
    workflow.add_node("intent_confirm", _wrap_node(intent_confirm_node, config))
    workflow.add_node("framework_confirm", _wrap_node(framework_confirm_node, config))
    workflow.add_node("datasource_scoping", _wrap_node(datasource_scoping_node, config))
    workflow.add_node("compliance_scope", _wrap_node(compliance_scope_node, config))
    workflow.add_node("persona_confirm", _wrap_node(persona_confirm_node, config))
    workflow.add_node("execution_preview", _wrap_node(execution_preview_node, config))
    workflow.add_node("workflow_router", _wrap_node(workflow_router_node, config))
    
    # Set entry point
    workflow.set_entry_point("intent_confirm")
    
    # Add edges with interrupt routing
    def route_after_intent(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    workflow.add_conditional_edges(
        "intent_confirm",
        route_after_intent,
        {
            "interrupt": END,
            "continue": "framework_confirm",
        },
    )
    
    def route_after_framework(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    workflow.add_conditional_edges(
        "framework_confirm",
        route_after_framework,
        {
            "interrupt": END,
            "continue": "datasource_scoping",
        },
    )
    
    def route_after_datasource(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    workflow.add_conditional_edges(
        "datasource_scoping",
        route_after_datasource,
        {
            "interrupt": END,
            "continue": "compliance_scope",
        },
    )
    
    def route_after_scope(state: EnhancedCompliancePipelineState) -> str:
        # Check if persona is needed (dashboard intent)
        intent = state.get("intent", "")
        if intent == "dashboard_generation":
            # Check if persona already set
            if not state.get("persona"):
                result = _route_with_interrupt(state, checkpoint_key, resolved_key)
                if result == "interrupt":
                    return "interrupt"
                return "persona_confirm"
        # Skip persona, go to execution_preview or workflow_router
        if config.requires_execution_preview:
            return "execution_preview"
        return "workflow_router"
    
    workflow.add_conditional_edges(
        "compliance_scope",
        route_after_scope,
        {
            "interrupt": END,
            "persona_confirm": "persona_confirm",
            "execution_preview": "execution_preview",
            "workflow_router": "workflow_router",
        },
    )
    
    def route_after_persona(state: EnhancedCompliancePipelineState) -> str:
        result = _route_with_interrupt(state, checkpoint_key, resolved_key)
        if result == "interrupt":
            return "interrupt"
        # After persona, go to execution_preview or workflow_router
        if config.requires_execution_preview:
            return "execution_preview"
        return "workflow_router"
    
    workflow.add_conditional_edges(
        "persona_confirm",
        route_after_persona,
        {
            "interrupt": END,
            "execution_preview": "execution_preview",
            "workflow_router": "workflow_router",
        },
    )
    
    def route_after_execution_preview(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    if config.requires_execution_preview:
        workflow.add_conditional_edges(
            "execution_preview",
            route_after_execution_preview,
            {
                "interrupt": END,
                "continue": "workflow_router",
            },
        )
    
    workflow.add_edge("workflow_router", END)
    
    return workflow


def create_compliance_conversation_planner_app(
    config: SecurityConversationConfig,
    checkpointer=None,
) -> Any:
    """
    Create and compile the compliance conversation planner workflow.
    
    Args:
        config: SecurityConversationConfig instance for compliance
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver)
    
    Returns:
        Compiled LangGraph application
    """
    if checkpointer is None:
        checkpointer = get_checkpointer()
    
    workflow = build_compliance_conversation_planner(config)
    return workflow.compile(checkpointer=checkpointer)
