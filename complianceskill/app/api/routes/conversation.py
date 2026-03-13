"""
Conversation API Routes

Handles multi-turn conversation flow with interrupt/resume protocol.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.conversation.verticals.lms_config import LMS_CONVERSATION_CONFIG
from app.conversation.planner_workflow import create_conversation_planner_app
from app.conversation.turn import ConversationCheckpoint
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])

# Store app instances (in production, use Redis or similar)
_conversation_apps = {}
_checkpointers = {}


def get_conversation_app(vertical_id: str = "lms"):
    """Get or create conversation app for vertical."""
    if vertical_id not in _conversation_apps:
        # For now, only LMS is supported
        if vertical_id == "lms":
            config = LMS_CONVERSATION_CONFIG
        else:
            raise ValueError(f"Unsupported vertical: {vertical_id}")
        
        checkpointer = MemorySaver()  # In production, use Redis
        _checkpointers[vertical_id] = checkpointer
        _conversation_apps[vertical_id] = create_conversation_planner_app(
            config=config,
            checkpointer=checkpointer,
        )
    
    return _conversation_apps[vertical_id], _checkpointers[vertical_id]


class ConversationTurnRequest(BaseModel):
    """Request to start or continue a conversation."""
    session_id: str
    user_query: Optional[str] = None  # Only for first turn
    response: Optional[Dict[str, Any]] = None  # User response for resume
    vertical_id: str = "lms"


class ConversationTurnResponse(BaseModel):
    """Response from conversation turn."""
    session_id: str
    phase: str
    turn: Optional[Dict[str, Any]] = None  # ConversationTurn as dict
    is_complete: bool
    csod_initial_state: Optional[Dict[str, Any]] = None  # Final state when complete


@router.post("/turn", response_model=ConversationTurnResponse)
async def conversation_turn(request: ConversationTurnRequest) -> ConversationTurnResponse:
    """
    Handle a conversation turn - start new conversation or resume from checkpoint.
    
    First turn: Provide user_query, session_id
    Subsequent turns: Provide response with field and value, session_id
    
    Request body:
    {
        "session_id": "abc-123",
        "user_query": "Why is our compliance rate dropping?",  // First turn only
        "response": {  // Subsequent turns only
            "field": "csod_scoping_answers",
            "value": {
                "org_unit": "department",
                "time_window": "last_quarter"
            }
        },
        "vertical_id": "lms"
    }
    """
    try:
        app, checkpointer = get_conversation_app(request.vertical_id)
        thread_id = request.session_id
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Check if this is a resume (has response) or new conversation
        if request.response:
            # Resume from checkpoint
            resume_field = request.response.get("field")
            resume_value = request.response.get("value")
            
            if not resume_field:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="response.field is required for resume"
                )
            
            # Get current state
            state_snapshot = app.get_state(config)
            if not state_snapshot or not state_snapshot.values:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No state found for session {thread_id}"
                )
            
            current_state = state_snapshot.values
            
            # Inject user response into state
            if resume_field == "csod_scoping_answers":
                # Merge scoping answers
                existing = current_state.get("csod_scoping_answers", {})
                if isinstance(resume_value, dict):
                    existing.update(resume_value)
                    current_state["csod_scoping_answers"] = existing
                else:
                    current_state["csod_scoping_answers"] = resume_value
            else:
                # Direct assignment
                current_state[resume_field] = resume_value
            
            # Mark checkpoint as resolved
            current_state["csod_checkpoint_resolved"] = True
            
            # Resume graph execution
            result = app.invoke(current_state, config)
            
        else:
            # New conversation - first turn
            if not request.user_query:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="user_query is required for first turn"
                )
            
            # Create initial state
            initial_state = {
                "user_query": request.user_query,
                "session_id": thread_id,
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
            
            # Invoke graph
            result = app.invoke(initial_state, config)
        
        # Check if there's a checkpoint (interrupt)
        checkpoint_data = result.get("csod_conversation_checkpoint")
        checkpoint_resolved = result.get("csod_checkpoint_resolved", False)
        
        if checkpoint_data and not checkpoint_resolved:
            # Graph paused at checkpoint - return turn to user
            checkpoint = ConversationCheckpoint.from_dict(checkpoint_data)
            
            return ConversationTurnResponse(
                session_id=thread_id,
                phase=checkpoint.phase,
                turn=checkpoint.turn.to_dict() if hasattr(checkpoint.turn, "to_dict") else checkpoint_data["turn"],
                is_complete=False,
            )
        
        # Graph completed - all turns done
        # Check if workflow_router set target_workflow
        target_workflow = result.get("csod_target_workflow")
        
        if target_workflow:
            # Optionally invoke downstream workflow automatically
            # For now, return the state so caller can invoke downstream workflow
            # To auto-invoke, uncomment the following:
            # try:
            #     from app.conversation.integration import invoke_workflow_after_conversation
            #     final_state = invoke_workflow_after_conversation(result)
            #     return ConversationTurnResponse(
            #         session_id=thread_id,
            #         phase="completed",
            #         is_complete=True,
            #         csod_initial_state=final_state,
            #     )
            # except Exception as e:
            #     logger.error(f"Error invoking downstream workflow: {e}", exc_info=True)
            #     # Fall through to return conversation state
            
            # Return final state for downstream workflow invocation
            return ConversationTurnResponse(
                session_id=thread_id,
                phase="confirmed",
                is_complete=True,
                csod_initial_state=result,
            )
        else:
            # Should not happen, but handle gracefully
            logger.warning(f"Graph completed but no target_workflow set for session {thread_id}")
            return ConversationTurnResponse(
                session_id=thread_id,
                phase="confirmed",
                is_complete=True,
                csod_initial_state=result,
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in conversation turn: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
