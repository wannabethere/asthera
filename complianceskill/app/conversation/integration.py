"""
Conversation Engine Integration Helpers

Provides utilities to integrate the conversation engine as Phase 0
before MDL workflows and Detection & Triage workflows.
"""
import logging
from typing import Dict, Any, Optional
from uuid import uuid4

from app.conversation.config import VerticalConversationConfig
from app.conversation.planner_workflow import create_conversation_planner_app
from app.conversation.turn import ConversationCheckpoint

logger = logging.getLogger(__name__)


def map_conversation_state_to_dt_initial_state(
    conversation_state: Dict[str, Any],
    user_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map conversation engine output state to Detection & Triage workflow initial state.
    
    The conversation engine populates:
    - compliance_profile (with scoping answers, metrics, etc.)
    - active_project_id
    - selected_data_sources
    - user_query
    
    These map to DT workflow fields:
    - framework_id (from compliance_profile or user query)
    - selected_data_sources
    - active_project_id
    - compliance_profile
    
    Args:
        conversation_state: Final state from conversation planner workflow
        user_query: Original user query (if not in state)
    
    Returns:
        Initial state dict for DT workflow
    """
    from app.agents.mdlworkflows.dt_workflow import create_dt_initial_state
    
    # Extract values from conversation state
    compliance_profile = conversation_state.get("compliance_profile", {})
    active_project_id = conversation_state.get("active_project_id")
    selected_data_sources = conversation_state.get("selected_data_sources", [])
    query = user_query or conversation_state.get("user_query", "")
    session_id = conversation_state.get("session_id", "")
    
    # Extract framework_id from compliance_profile if available
    framework_id = compliance_profile.get("framework_id")
    
    # If no framework_id, try to infer from user query or use default
    if not framework_id:
        query_lower = query.lower()
        if "soc2" in query_lower or "soc 2" in query_lower:
            framework_id = "soc2_type2"
        elif "iso" in query_lower:
            framework_id = "iso27001"
        elif "nist" in query_lower:
            framework_id = "nist_csf"
        # Add more framework detection logic as needed
    
    # Create DT initial state
    dt_state = create_dt_initial_state(
        user_query=query,
        session_id=session_id,
        framework_id=framework_id,
        selected_data_sources=selected_data_sources,
        active_project_id=active_project_id,
        compliance_profile=compliance_profile,
    )
    
    # Merge any additional fields from conversation state
    # (e.g., resolved metrics, concepts, etc.)
    dt_state.update({
        "csod_resolved_project_ids": conversation_state.get("csod_resolved_project_ids", []),
        "csod_resolved_mdl_table_refs": conversation_state.get("csod_resolved_mdl_table_refs", []),
        "csod_selected_concepts": conversation_state.get("csod_selected_concepts", []),
        "csod_primary_area": conversation_state.get("csod_primary_area", {}),
    })
    if conversation_state.get("dt_reasoning_trace") is not None:
        dt_state["dt_reasoning_trace"] = conversation_state["dt_reasoning_trace"]
    
    logger.info(f"Mapped conversation state to DT initial state: framework={framework_id}, project={active_project_id}")
    
    return dt_state


def map_conversation_state_to_compliance_initial_state(
    conversation_state: Dict[str, Any],
    user_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map conversation engine output state to Compliance workflow initial state.
    
    Args:
        conversation_state: Final state from conversation planner workflow
        user_query: Original user query (if not in state)
    
    Returns:
        Initial state dict for Compliance workflow
    """
    from app.agents.detectiontriageworkflows.workflow import create_compliance_initial_state
    
    compliance_profile = conversation_state.get("compliance_profile", {})
    active_project_id = conversation_state.get("active_project_id")
    selected_data_sources = conversation_state.get("selected_data_sources", [])
    query = user_query or conversation_state.get("user_query", "")
    session_id = conversation_state.get("session_id", "")
    
    framework_id = compliance_profile.get("framework_id")
    
    compliance_state = create_compliance_initial_state(
        user_query=query,
        session_id=session_id,
        framework_id=framework_id,
        selected_data_sources=selected_data_sources,
        active_project_id=active_project_id,
        compliance_profile=compliance_profile,
    )
    
    # Merge additional fields
    compliance_state.update({
        "csod_resolved_project_ids": conversation_state.get("csod_resolved_project_ids", []),
        "csod_resolved_mdl_table_refs": conversation_state.get("csod_resolved_mdl_table_refs", []),
    })
    
    return compliance_state


def invoke_workflow_after_conversation(
    conversation_state: Dict[str, Any],
    dt_app=None,
    compliance_app=None,
    csod_app=None,
) -> Dict[str, Any]:
    """
    Invoke the appropriate downstream workflow after conversation completes.
    
    Uses csod_target_workflow from conversation state to determine which workflow to run.
    
    Args:
        conversation_state: Final state from conversation planner (is_complete=True)
        dt_app: Optional DT workflow app (will create if None)
        compliance_app: Optional Compliance workflow app (will create if None)
        csod_app: Optional CSOD workflow app (will create if None)
    
    Returns:
        Final state from downstream workflow
    """
    target_workflow = conversation_state.get("csod_target_workflow", "csod_workflow")
    if target_workflow == "csod_metric_advisor_workflow":
        logger.info(
            "csod_metric_advisor_workflow is retired; invoking csod_workflow instead"
        )
        target_workflow = "csod_workflow"

    if target_workflow == "csod_workflow":
        from app.agents.csod.csod_workflow import (
            get_csod_app,
            create_csod_initial_state,
        )
        
        if csod_app is None:
            csod_app = get_csod_app()
        
        initial_state = create_csod_initial_state(
            user_query=conversation_state.get("user_query", ""),
            session_id=conversation_state.get("session_id", ""),
            active_project_id=conversation_state.get("active_project_id"),
            selected_data_sources=conversation_state.get("selected_data_sources", []),
            compliance_profile=conversation_state.get("compliance_profile", {}),
            causal_graph_enabled=conversation_state.get("csod_causal_graph_enabled", False),
            causal_vertical="lms",
        )
        initial_state.update(conversation_state)
        
        # Create config with thread_id for checkpointer (required by LangGraph)
        session_id = conversation_state.get("session_id") or str(uuid4())
        config = {"configurable": {"thread_id": session_id}}
        
        logger.info("Invoking csod_workflow after conversation")
        return csod_app.invoke(initial_state, config=config)
    
    elif target_workflow == "dt_workflow" or target_workflow == "detection_triage":
        from app.agents.mdlworkflows.dt_workflow import (
            get_detection_triage_app,
        )
        
        if dt_app is None:
            dt_app = get_detection_triage_app()
        
        initial_state = map_conversation_state_to_dt_initial_state(conversation_state)
        
        # Create config with thread_id for checkpointer (required by LangGraph)
        session_id = conversation_state.get("session_id") or str(uuid4())
        config = {"configurable": {"thread_id": session_id}}
        
        logger.info("Invoking dt_workflow after conversation")
        return dt_app.invoke(initial_state, config=config)
    
    elif target_workflow == "compliance_workflow":
        from app.agents.detectiontriageworkflows.workflow import (
            get_compliance_app,
        )
        
        if compliance_app is None:
            compliance_app = get_compliance_app()
        
        initial_state = map_conversation_state_to_compliance_initial_state(conversation_state)
        
        # Create config with thread_id for checkpointer (required by LangGraph)
        session_id = conversation_state.get("session_id") or str(uuid4())
        config = {"configurable": {"thread_id": session_id}}
        
        logger.info("Invoking compliance_workflow after conversation")
        return compliance_app.invoke(initial_state, config=config)
    
    else:
        raise ValueError(f"Unknown target workflow: {target_workflow}")


def create_dt_conversation_config() -> VerticalConversationConfig:
    """
    Create conversation config for Detection & Triage workflows.
    
    This config can be used to run conversation Phase 0 before DT workflows.
    """
    from app.conversation.config import VerticalConversationConfig, ScopingQuestionTemplate
    
    # DT-specific scoping templates
    dt_scoping_templates = {
        "framework": ScopingQuestionTemplate(
            filter_name="framework",
            question_id="framework",
            label="Which compliance framework are you working with?",
            interaction_mode="single",
            options=[
                {"id": "soc2_type2", "label": "SOC 2 Type II"},
                {"id": "iso27001", "label": "ISO 27001"},
                {"id": "nist_csf", "label": "NIST CSF"},
                {"id": "pci_dss", "label": "PCI DSS"},
            ],
            state_key="framework_id",
            required=True,
        ),
        "time_period": ScopingQuestionTemplate(
            filter_name="time_period",
            question_id="time_period",
            label="What time window matters most to you?",
            interaction_mode="single",
            options=[
                {"id": "last_30d", "label": "Last 30 days"},
                {"id": "last_quarter", "label": "Last quarter"},
                {"id": "ytd", "label": "Year to date"},
                {"id": "yoy", "label": "Comparing this year to last year"},
            ],
            state_key="time_window",
            required=False,
        ),
        "severity": ScopingQuestionTemplate(
            filter_name="severity",
            question_id="severity",
            label="What severity level are you most concerned about?",
            interaction_mode="multi",
            options=[
                {"id": "critical", "label": "Critical"},
                {"id": "high", "label": "High"},
                {"id": "medium", "label": "Medium"},
                {"id": "low", "label": "Low"},
            ],
            state_key="severity",
            required=False,
        ),
    }
    
    return VerticalConversationConfig(
        vertical_id="dt",
        display_name="Detection & Triage",
        l1_collection="dt_concepts_l1",  # Would need to be created
        l2_collection="dt_areas_l2",  # Would need to be created
        supported_datasources=[
            {
                "id": "qualys",
                "display_name": "Qualys",
                "description": "Vulnerability management platform",
            },
            {
                "id": "snyk",
                "display_name": "Snyk",
                "description": "Security scanning platform",
            },
            {
                "id": "wiz",
                "display_name": "Wiz",
                "description": "Cloud security platform",
            },
        ],
        scoping_question_templates=dt_scoping_templates,
        always_include_filters=["framework", "time_period"],
        intent_to_workflow={
            "siem_rule_generation": "dt_workflow",
            "detection_engineering": "dt_workflow",
            "triage_engineering": "dt_workflow",
        },
        default_workflow="dt_workflow",
        max_scoping_questions_per_turn=3,
    )
