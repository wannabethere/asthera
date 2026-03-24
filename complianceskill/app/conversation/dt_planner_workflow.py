"""
Detection & Triage Conversation Planner Workflow

Conversation turn engine for the DT workflow. Collects user context (template, framework,
datasources, scoping) before firing downstream agents.

Graph topology:
    dt_template_confirm_node (NEW - interrupt - first question)
      → dt_framework_confirm_node (NEW - interrupt)
        → dt_datasource_scoping_node (NEW - interrupt)
          → dt_scope_node (NEW - interrupt - main fix)
            → dt_persona_confirm_node (NEW - interrupt, dashboard only)
              → dt_intent_classifier (existing, with bypass)
                → dt_planner (existing)
                  → [DT pipeline]
"""
import logging
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.security_config import SecurityConversationConfig
from app.conversation.nodes.dt_template_confirm import dt_template_confirm_node
from app.conversation.nodes.framework_confirm import framework_confirm_node
from app.conversation.nodes.datasource_scoping import datasource_scoping_node
from app.conversation.nodes.dt_scope import dt_scope_node
from app.conversation.nodes.persona_confirm import persona_confirm_node

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


def dt_workflow_router_node(
    state: EnhancedCompliancePipelineState,
    config: SecurityConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    DT workflow router - unpacks scoping answers and sets playbook_resolved_intent.
    
    After dt_scoping_answers are collected, dt_planner_node receives them via state.
    Three additions needed:
    - Read dt_scoping_answers and copy severity_filter, time_window, environment, threat_scenario into compliance_profile
    - Read generate_sql from dt_scoping_answers and write it to state.dt_generate_sql
    - Set compliance_profile.playbook_resolved_intent = True (triggers bypass)
    """
    scoping_answers = state.get("dt_scoping_answers", {})
    template = state.get("dt_playbook_template")
    framework_id = state.get("framework_id")
    selected_data_sources = state.get("selected_data_sources", [])
    persona = state.get("dt_dashboard_persona")
    
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
        })
    
    # Read generate_sql from scoping_answers
    generate_sql_value = scoping_answers.get("generate_sql")
    if generate_sql_value:
        # Convert "yes"/"no" to boolean
        state["dt_generate_sql"] = generate_sql_value == "yes" or generate_sql_value is True
    
    # Set persona if collected (dashboard template)
    if persona:
        state["dt_dashboard_persona"] = persona
        compliance_profile["persona"] = persona
    
    # Set selected_data_sources
    if selected_data_sources:
        compliance_profile["selected_data_sources"] = selected_data_sources
        state["selected_data_sources"] = selected_data_sources
    
    # Set template and framework
    if template:
        state["dt_playbook_template"] = template
    if framework_id:
        state["framework_id"] = framework_id
    
    state["compliance_profile"] = compliance_profile
    
    logger.info(f"DT workflow router: template={template}, framework={framework_id}")
    
    return state


def build_dt_conversation_planner(config: SecurityConversationConfig) -> StateGraph:
    """
    Build the DT conversation planner workflow with interrupt mechanism.
    
    Args:
        config: SecurityConversationConfig instance for DT
    
    Returns:
        Un-compiled StateGraph
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    checkpoint_key = f"{config.state_key_prefix}_conversation_checkpoint"
    resolved_key = f"{config.state_key_prefix}_checkpoint_resolved"
    
    # Add nodes
    workflow.add_node("dt_template_confirm", _wrap_node(dt_template_confirm_node, config))
    workflow.add_node("dt_framework_confirm", _wrap_node(framework_confirm_node, config))
    workflow.add_node("dt_datasource_scoping", _wrap_node(datasource_scoping_node, config))
    workflow.add_node("dt_scope", _wrap_node(dt_scope_node, config))
    workflow.add_node("dt_persona_confirm", _wrap_node(persona_confirm_node, config))
    workflow.add_node("dt_workflow_router", _wrap_node(dt_workflow_router_node, config))
    
    # Set entry point
    workflow.set_entry_point("dt_template_confirm")
    
    # Add edges with interrupt routing
    def route_after_template(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    workflow.add_conditional_edges(
        "dt_template_confirm",
        route_after_template,
        {
            "interrupt": END,
            "continue": "dt_framework_confirm",
        },
    )
    
    def route_after_framework(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    workflow.add_conditional_edges(
        "dt_framework_confirm",
        route_after_framework,
        {
            "interrupt": END,
            "continue": "dt_datasource_scoping",
        },
    )
    
    def route_after_datasource(state: EnhancedCompliancePipelineState) -> str:
        return _route_with_interrupt(state, checkpoint_key, resolved_key)
    
    workflow.add_conditional_edges(
        "dt_datasource_scoping",
        route_after_datasource,
        {
            "interrupt": END,
            "continue": "dt_scope",
        },
    )
    
    def route_after_scope(state: EnhancedCompliancePipelineState) -> str:
        # Check if persona is needed (dashboard template)
        template = state.get("dt_playbook_template", "")
        if template == "dashboard":
            # Check if persona already set
            if not state.get("dt_dashboard_persona"):
                result = _route_with_interrupt(state, checkpoint_key, resolved_key)
                if result == "interrupt":
                    return "interrupt"
                return "dt_persona_confirm"
        # Skip persona, go to workflow_router
        return "dt_workflow_router"
    
    workflow.add_conditional_edges(
        "dt_scope",
        route_after_scope,
        {
            "interrupt": END,
            "dt_persona_confirm": "dt_persona_confirm",
            "dt_workflow_router": "dt_workflow_router",
        },
    )
    
    def route_after_persona(state: EnhancedCompliancePipelineState) -> str:
        result = _route_with_interrupt(state, checkpoint_key, resolved_key)
        if result == "continue":
            return "dt_workflow_router"
        return result
    
    workflow.add_conditional_edges(
        "dt_persona_confirm",
        route_after_persona,
        {
            "interrupt": END,
            "continue": "dt_workflow_router",
        },
    )
    
    workflow.add_edge("dt_workflow_router", END)
    
    return workflow


def create_dt_conversation_planner_app(
    config: SecurityConversationConfig,
    checkpointer=None,
) -> Any:
    """
    Create and compile the DT conversation planner workflow.
    
    Args:
        config: SecurityConversationConfig instance for DT
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver)
    
    Returns:
        Compiled LangGraph application
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    workflow = build_dt_conversation_planner(config)
    return workflow.compile(checkpointer=checkpointer)
