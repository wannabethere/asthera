"""
Example: Using Conversation Engine with MDL/DT Workflows

This example shows how to:
1. Run conversation Phase 0
2. Handle multi-turn conversation with interrupts
3. Map conversation state to DT workflow initial state
4. Invoke DT workflow with conversation context
"""
import logging
from app.conversation.verticals.lms_config import LMS_CONVERSATION_CONFIG
from app.conversation.integration import (
    create_dt_conversation_config,
    map_conversation_state_to_dt_initial_state,
    invoke_workflow_after_conversation,
)
from app.conversation.planner_workflow import create_conversation_planner_app
from app.agents.mdlworkflows.dt_workflow import get_detection_triage_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_csod_workflow():
    """Example 1: Using conversation engine with CSOD workflows (already configured)."""
    logger.info("=== Example 1: CSOD Workflow ===")
    
    # Create conversation app with LMS config
    conversation_app = create_conversation_planner_app(LMS_CONVERSATION_CONFIG)
    
    # Initial state
    initial_state = {
        "user_query": "Why is our compliance training rate dropping?",
        "session_id": "session-csod-001",
        "csod_selected_datasource": None,
        "csod_datasource_confirmed": False,
        "csod_concept_matches": [],
        "csod_selected_concepts": [],
        "csod_confirmed_concept_ids": [],
        "csod_scoping_answers": {},
        "csod_scoping_complete": False,
        "csod_area_matches": [],
        "csod_preliminary_area_matches": [],
        "csod_primary_area": {},
        "csod_confirmed_area_id": None,
        "csod_metric_narration": None,
        "csod_metric_narration_confirmed": False,
        "csod_conversation_checkpoint": None,
        "csod_checkpoint_resolved": False,
        "compliance_profile": {},
        "active_project_id": None,
        "selected_data_sources": [],
    }
    
    config = {"configurable": {"thread_id": initial_state["session_id"]}}
    
    # Run conversation (this will pause at checkpoints)
    result = conversation_app.invoke(initial_state, config)
    
    # Check for checkpoint
    checkpoint = result.get("csod_conversation_checkpoint")
    if checkpoint and not result.get("csod_checkpoint_resolved"):
        logger.info(f"Conversation paused at checkpoint: {checkpoint.get('phase')}")
        logger.info("User needs to respond before continuing...")
        return result
    
    # If conversation complete, invoke downstream workflow
    if result.get("csod_target_workflow"):
        logger.info(f"Conversation complete. Invoking {result['csod_target_workflow']}")
        final_state = invoke_workflow_after_conversation(result)
        logger.info("Downstream workflow completed!")
        return final_state
    
    return result


def example_2_dt_workflow():
    """Example 2: Using conversation engine with DT workflows."""
    logger.info("=== Example 2: DT Workflow ===")
    
    # Create DT conversation config
    dt_config = create_dt_conversation_config()
    
    # Create conversation app
    conversation_app = create_conversation_planner_app(dt_config)
    
    # Initial state
    initial_state = {
        "user_query": "Generate SIEM rules for SOC2 compliance",
        "session_id": "session-dt-001",
        "csod_selected_datasource": None,
        "csod_datasource_confirmed": False,
        "csod_concept_matches": [],
        "csod_selected_concepts": [],
        "csod_confirmed_concept_ids": [],
        "csod_scoping_answers": {},
        "csod_scoping_complete": False,
        "csod_area_matches": [],
        "csod_preliminary_area_matches": [],
        "csod_primary_area": {},
        "csod_confirmed_area_id": None,
        "csod_metric_narration": None,
        "csod_metric_narration_confirmed": False,
        "csod_conversation_checkpoint": None,
        "csod_checkpoint_resolved": False,
        "compliance_profile": {},
        "active_project_id": None,
        "selected_data_sources": [],
    }
    
    config = {"configurable": {"thread_id": initial_state["session_id"]}}
    
    # Run conversation Phase 0
    conversation_result = conversation_app.invoke(initial_state, config)
    
    # Check for checkpoint
    checkpoint = conversation_result.get("csod_conversation_checkpoint")
    if checkpoint and not conversation_result.get("csod_checkpoint_resolved"):
        logger.info(f"Conversation paused at checkpoint: {checkpoint.get('phase')}")
        logger.info("User needs to respond before continuing...")
        return conversation_result
    
    # If conversation complete, map to DT initial state and invoke
    if conversation_result.get("csod_target_workflow") == "dt_workflow":
        logger.info("Conversation complete. Mapping to DT initial state...")
        
        # Map conversation state to DT initial state
        dt_initial_state = map_conversation_state_to_dt_initial_state(conversation_result)
        
        logger.info(f"Mapped state: framework={dt_initial_state.get('framework_id')}, "
                   f"project={dt_initial_state.get('active_project_id')}")
        
        # Get DT workflow app
        dt_app = get_detection_triage_app()
        
        # Run DT workflow
        logger.info("Invoking DT workflow...")
        dt_result = dt_app.invoke(dt_initial_state, config)
        
        logger.info("DT workflow completed!")
        return dt_result
    
    return conversation_result


def example_3_multi_turn_conversation():
    """Example 3: Handling multi-turn conversation with user responses."""
    logger.info("=== Example 3: Multi-Turn Conversation ===")
    
    conversation_app = create_conversation_planner_app(LMS_CONVERSATION_CONFIG)
    session_id = "session-multiturn-001"
    config = {"configurable": {"thread_id": session_id}}
    
    # Turn 1: Initial query
    initial_state = {
        "user_query": "Why is our compliance rate dropping?",
        "session_id": session_id,
        "csod_selected_datasource": None,
        "csod_datasource_confirmed": False,
        "csod_concept_matches": [],
        "csod_selected_concepts": [],
        "csod_confirmed_concept_ids": [],
        "csod_scoping_answers": {},
        "csod_scoping_complete": False,
        "csod_area_matches": [],
        "csod_preliminary_area_matches": [],
        "csod_primary_area": {},
        "csod_confirmed_area_id": None,
        "csod_metric_narration": None,
        "csod_metric_narration_confirmed": False,
        "csod_conversation_checkpoint": None,
        "csod_checkpoint_resolved": False,
        "compliance_profile": {},
        "active_project_id": None,
        "selected_data_sources": [],
    }
    
    result = conversation_app.invoke(initial_state, config)
    
    # Check for checkpoint
    checkpoint = result.get("csod_conversation_checkpoint")
    if checkpoint and not result.get("csod_checkpoint_resolved"):
        logger.info(f"Turn 1: Paused at {checkpoint.get('phase')}")
        
        # Simulate user response (in real app, this comes from API)
        if checkpoint.get("phase") == "scoping":
            # User provides scoping answers
            result["csod_scoping_answers"] = {
                "org_unit": "department",
                "time_window": "last_quarter",
                "training_type": "mandatory",
            }
            result["csod_checkpoint_resolved"] = True
            
            # Turn 2: Resume with user response
            logger.info("Turn 2: Resuming with user scoping answers...")
            result = conversation_app.invoke(result, config)
            
            # Check for next checkpoint
            checkpoint = result.get("csod_conversation_checkpoint")
            if checkpoint and not result.get("csod_checkpoint_resolved"):
                logger.info(f"Turn 2: Paused at {checkpoint.get('phase')}")
                # Continue with more user responses...
            else:
                logger.info("Turn 2: Conversation complete!")
                if result.get("csod_target_workflow"):
                    final_state = invoke_workflow_after_conversation(result)
                    logger.info("Downstream workflow completed!")
                    return final_state
    
    return result


if __name__ == "__main__":
    # Run examples
    # example_1_csod_workflow()
    # example_2_dt_workflow()
    example_3_multi_turn_conversation()
