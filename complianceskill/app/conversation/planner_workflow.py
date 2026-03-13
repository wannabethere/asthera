"""
Conversation Planner Workflow - Generic Multi-Turn Conversation Engine

This workflow replaces csod_planner_workflow.py with a generic conversation turn engine
that supports interrupts and multi-turn interactions.

Graph topology:
    datasource_selector
      → concept_resolver
        → preliminary_area_matcher (lightweight, no scoping)
          → concept_confirm_node (NEW - interrupt)
            → scoping_node (NEW - interrupt - main fix)
              → area_matcher (re-runs with scoping)
                → area_confirm_node (NEW - interrupt)
                  → metric_narration_node (NEW - interrupt)
                    → workflow_router
                      → [invoke downstream workflow]
                        → END
"""
import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.config import VerticalConversationConfig
from app.conversation.turn import ConversationCheckpoint
from app.conversation.nodes.concept_confirm import concept_confirm_node
from app.conversation.nodes.scoping import scoping_node
from app.conversation.nodes.area_confirm import area_confirm_node
from app.conversation.nodes.metric_narration import metric_narration_node
from app.ingestion.registry_vector_lookup import (
    resolve_intent_to_concept,
    resolve_scoping_to_areas,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Planner Nodes (existing nodes from csod_planner_workflow.py)
# ============================================================================

def datasource_selector_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step A: Datasource selection.
    
    If datasource is not yet selected, prompts user to select.
    If already selected, passes through to concept resolver.
    """
    selected_datasource = state.get("csod_selected_datasource")
    user_message = state.get("user_query", "").lower()
    
    if not selected_datasource:
        # Try to match from user message
        for ds in config.supported_datasources:
            if ds["id"] in user_message or ds.get("display_name", "").lower() in user_message:
                selected_datasource = ds["id"]
                break
        
        # Default to first datasource if not specified
        if not selected_datasource and config.supported_datasources:
            selected_datasource = config.supported_datasources[0]["id"]
            logger.info(f"No datasource specified, defaulting to {selected_datasource}")
    
    state["csod_selected_datasource"] = selected_datasource
    state["csod_available_datasources"] = config.supported_datasources
    
    # Add checkpoint for user interaction if needed
    if not state.get("csod_datasource_confirmed"):
        from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType
        
        checkpoint = ConversationCheckpoint(
            phase="datasource_select",
            turn=ConversationTurn(
                phase="datasource_select",
                turn_type=TurnOutputType.DECISION,
                message="Which platform are you analyzing today?",
                options=[
                    {
                        "id": ds["id"],
                        "label": ds.get("display_name", ds["id"]),
                        "description": ds.get("description", ""),
                    }
                    for ds in config.supported_datasources
                ],
            ),
            resume_with_field="csod_datasource_confirmed",
        )
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
        return state
    
    state["csod_datasource_confirmed"] = True
    return state


def concept_resolver_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step B: Concept resolution using L1 collection.
    
    Resolves user query to concepts and extracts project_ids, mdl_table_refs.
    """
    user_query = state.get("user_query", "")
    selected_datasource = state.get("csod_selected_datasource", "")
    
    if not user_query:
        logger.warning("No user query provided for concept resolution")
        state["csod_concept_matches"] = []
        return state
    
    # Resolve concepts using L1 collection
    try:
        concept_matches = resolve_intent_to_concept(
            user_query=user_query,
            connected_source_ids=[selected_datasource] if selected_datasource else [],
            top_k=5,
        )
        
        # Extract resolved information
        selected_concepts = []
        all_project_ids = []
        all_mdl_table_refs = []
        
        for match in concept_matches[:3]:  # Top 3 concepts
            selected_concepts.append({
                "concept_id": match.concept_id,
                "display_name": match.display_name,
                "score": match.score,
                "coverage_confidence": match.coverage_confidence,
            })
            all_project_ids.extend(match.project_ids)
            all_mdl_table_refs.extend(match.mdl_table_refs)
        
        # Deduplicate
        all_project_ids = list(set(all_project_ids))
        all_mdl_table_refs = list(set(all_mdl_table_refs))
        
        state["csod_concept_matches"] = [
            {
                "concept_id": m.concept_id,
                "display_name": m.display_name,
                "score": m.score,
                "coverage_confidence": m.coverage_confidence,
                "project_ids": m.project_ids,
                "mdl_table_refs": m.mdl_table_refs,
            }
            for m in concept_matches
        ]
        state["csod_selected_concepts"] = selected_concepts
        state["csod_resolved_project_ids"] = all_project_ids
        state["csod_resolved_mdl_table_refs"] = all_mdl_table_refs
        
        # Set primary project_id (first match)
        if all_project_ids:
            state["csod_primary_project_id"] = all_project_ids[0]
        
        logger.info(
            f"Resolved {len(selected_concepts)} concepts, "
            f"{len(all_project_ids)} project_ids, "
            f"{len(all_mdl_table_refs)} mdl_table_refs"
        )
        
    except Exception as e:
        logger.error(f"Error in concept resolution: {e}", exc_info=True)
        state["csod_concept_matches"] = []
        state["csod_selected_concepts"] = []
        state["csod_resolved_project_ids"] = []
        state["csod_resolved_mdl_table_refs"] = []
    
    return state


def preliminary_area_matcher_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Preliminary area matcher - lightweight first-pass lookup without scoping.
    
    Used by scoping_node to determine which filters to ask about.
    """
    confirmed_concept_ids = state.get("csod_confirmed_concept_ids", [])
    
    if not confirmed_concept_ids:
        state["csod_preliminary_area_matches"] = []
        return state
    
    primary_concept_id = confirmed_concept_ids[0]
    
    try:
        # Lightweight lookup - no scoping context
        preliminary_areas = resolve_scoping_to_areas(
            scoping_answers={},  # Empty - preliminary pass
            confirmed_concept_id=primary_concept_id,
            top_k=1,  # Just need primary area
        )
        
        state["csod_preliminary_area_matches"] = [
            {
                "area_id": a.area_id,
                "concept_id": a.concept_id,
                "display_name": a.display_name,
                "score": a.score,
                "filters": a.filters,
            }
            for a in preliminary_areas
        ]
        
    except Exception as e:
        logger.error(f"Error in preliminary area matching: {e}", exc_info=True)
        state["csod_preliminary_area_matches"] = []
    
    return state


def area_matcher_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step D: Recommendation area matching using L2 collection.
    
    Now runs WITH scoping context (scoping_answers populated).
    """
    confirmed_concept_ids = state.get("csod_confirmed_concept_ids", [])
    scoping_answers = state.get("csod_scoping_answers", {})
    
    if not confirmed_concept_ids:
        logger.warning("No confirmed concepts for area matching")
        state["csod_area_matches"] = []
        return state
    
    primary_concept_id = confirmed_concept_ids[0]
    
    try:
        # Resolve recommendation areas using L2 collection WITH scoping context
        area_matches = resolve_scoping_to_areas(
            scoping_answers=scoping_answers,  # Now populated!
            confirmed_concept_id=primary_concept_id,
            top_k=3,
        )
        
        state["csod_area_matches"] = [
            {
                "area_id": a.area_id,
                "concept_id": a.concept_id,
                "display_name": a.display_name,
                "score": a.score,
                "metrics": a.metrics,
                "kpis": a.kpis,
                "filters": a.filters,
                "causal_paths": a.causal_paths,
                "data_requirements": a.data_requirements,
            }
            for a in area_matches
        ]
        
        # Set primary area (first match)
        if area_matches:
            primary_area = area_matches[0]
            state["csod_primary_area"] = {
                "area_id": primary_area.area_id,
                "display_name": primary_area.display_name,
                "metrics": primary_area.metrics,
                "kpis": primary_area.kpis,
                "data_requirements": primary_area.data_requirements,
                "causal_paths": primary_area.causal_paths,
            }
        
        logger.info(f"Matched {len(area_matches)} recommendation areas with scoping context")
        
    except Exception as e:
        logger.error(f"Error in area matching: {e}", exc_info=True)
        state["csod_area_matches"] = []
    
    return state


def workflow_router_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Final: Route to appropriate downstream workflow.
    
    Updated to populate compliance_profile with scoping fields and metric narration.
    """
    user_query = state.get("user_query", "").lower()
    primary_area = state.get("csod_primary_area", {})
    confirmed_area_id = state.get("csod_confirmed_area_id")
    metric_narration = state.get("csod_metric_narration", "")
    scoping_answers = state.get("csod_scoping_answers", {})
    
    # Check if this is a metric advisor request
    advisor_keywords = ["advisor", "recommend", "suggest", "what metrics", "which kpis", "help me choose"]
    is_advisor_request = any(kw in user_query for kw in advisor_keywords)
    
    # Also check if user explicitly wants advisor workflow
    use_advisor = state.get("csod_use_advisor_workflow", False)
    
    if is_advisor_request or use_advisor:
        state["csod_target_workflow"] = "csod_metric_advisor_workflow"
        state["csod_intent"] = "metric_kpi_advisor"
    else:
        state["csod_target_workflow"] = config.default_workflow
        # Intent will be determined by csod_intent_classifier in the main workflow
    
    # Prepare state for downstream workflow
    # Build compliance_profile with resolved context
    compliance_profile = state.get("compliance_profile", {})
    
    # Add registry-resolved context
    compliance_profile.update({
        "selected_concepts": [c["concept_id"] for c in state.get("csod_selected_concepts", [])],
        "selected_area_ids": [a["area_id"] for a in state.get("csod_area_matches", [])],
        "priority_metrics": primary_area.get("metrics", []),
        "priority_kpis": primary_area.get("kpis", []),
        "data_requirements": primary_area.get("data_requirements", []),
        "causal_paths": primary_area.get("causal_paths", []),
        "active_mdl_tables": state.get("csod_resolved_mdl_table_refs", []),
    })
    
    # CRITICAL: Set lexy_metric_narration - triggers intent bypass
    if metric_narration:
        compliance_profile["lexy_metric_narration"] = metric_narration
    
    # CRITICAL: Unpack scoping_answers into compliance_profile top-level keys
    # These are read by csod_planner_node when building filter_context
    if scoping_answers:
        compliance_profile.update({
            "time_window": scoping_answers.get("time_window"),
            "org_unit": scoping_answers.get("org_unit"),
            "training_type": scoping_answers.get("training_type"),
            "deadline_window": scoping_answers.get("deadline_window"),
            "delivery_method": scoping_answers.get("delivery_method"),
            "audit_window": scoping_answers.get("audit_window"),
            "course_scope": scoping_answers.get("course_scope"),
            "user_status": scoping_answers.get("user_status"),
        })
    
    # Set csod_intent from confirmed area if not already set
    if not state.get("csod_intent") and confirmed_area_id:
        # Could extract intent from area metadata if available
        pass
    
    state["compliance_profile"] = compliance_profile
    
    # Set active_project_id for downstream workflow
    if state.get("csod_primary_project_id"):
        state["active_project_id"] = state["csod_primary_project_id"]
    
    # Set selected_data_sources
    selected_datasource = state.get("csod_selected_datasource", "")
    if selected_datasource:
        state["selected_data_sources"] = [selected_datasource]
    
    logger.info(f"Routing to {state['csod_target_workflow']}")
    
    return state


# ============================================================================
# Generic Routing Function - The Interrupt Mechanism
# ============================================================================

def _route_with_interrupt(state: EnhancedCompliancePipelineState) -> str:
    """
    Generic routing function used at every conversation node.
    
    Checks if checkpoint is set and not resolved - if so, route to 'interrupt' (END).
    Otherwise, clear checkpoint and route to 'continue'.
    """
    checkpoint_data = state.get("csod_conversation_checkpoint")
    
    if checkpoint_data and not state.get("csod_checkpoint_resolved"):
        return "interrupt"  # → END, API handles client interaction
    
    # Clear checkpoint and continue
    state["csod_conversation_checkpoint"] = None
    state["csod_checkpoint_resolved"] = False
    
    return "continue"


# ============================================================================
# Node Wrappers (to inject config)
# ============================================================================

def _wrap_node(node_func, config: VerticalConversationConfig):
    """Wrap a node function to inject config."""
    def wrapped(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
        return node_func(state, config)
    return wrapped


# ============================================================================
# Workflow Builder
# ============================================================================

def build_conversation_planner_workflow(config: VerticalConversationConfig) -> StateGraph:
    """
    Build the conversation planner workflow with interrupt mechanism.
    
    Args:
        config: VerticalConversationConfig instance
    
    Returns:
        Un-compiled StateGraph
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    # Add nodes
    workflow.add_node("datasource_selector", _wrap_node(datasource_selector_node, config))
    workflow.add_node("concept_resolver", _wrap_node(concept_resolver_node, config))
    workflow.add_node("preliminary_area_matcher", _wrap_node(preliminary_area_matcher_node, config))
    workflow.add_node("concept_confirm", _wrap_node(concept_confirm_node, config))
    workflow.add_node("scoping", _wrap_node(scoping_node, config))
    workflow.add_node("area_matcher", _wrap_node(area_matcher_node, config))
    workflow.add_node("area_confirm", _wrap_node(area_confirm_node, config))
    workflow.add_node("metric_narration", _wrap_node(metric_narration_node, config))
    workflow.add_node("workflow_router", _wrap_node(workflow_router_node, config))
    
    # Set entry point
    workflow.set_entry_point("datasource_selector")
    
    # Add edges with interrupt routing
    workflow.add_conditional_edges(
        "datasource_selector",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "concept_resolver",
        },
    )
    
    workflow.add_edge("concept_resolver", "preliminary_area_matcher")
    workflow.add_edge("preliminary_area_matcher", "concept_confirm")
    
    workflow.add_conditional_edges(
        "concept_confirm",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "scoping",
        },
    )
    
    workflow.add_conditional_edges(
        "scoping",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "area_matcher",
        },
    )
    
    workflow.add_edge("area_matcher", "area_confirm")
    
    workflow.add_conditional_edges(
        "area_confirm",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "metric_narration",
        },
    )
    
    workflow.add_conditional_edges(
        "metric_narration",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "workflow_router",
        },
    )
    
    workflow.add_edge("workflow_router", END)
    
    return workflow


# ============================================================================
# App Factory
# ============================================================================

def create_conversation_planner_app(
    config: VerticalConversationConfig,
    checkpointer=None,
) -> Any:
    """
    Create and compile the conversation planner workflow.
    
    Args:
        config: VerticalConversationConfig instance
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver)
    
    Returns:
        Compiled LangGraph application
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    workflow = build_conversation_planner_workflow(config)
    return workflow.compile(checkpointer=checkpointer)
