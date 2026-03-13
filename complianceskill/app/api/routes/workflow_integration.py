"""
Workflow Integration API Routes

Provides endpoints to invoke downstream workflows after conversation Phase 0 completes.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.conversation.integration import (
    invoke_workflow_after_conversation,
    map_conversation_state_to_dt_initial_state,
    map_conversation_state_to_compliance_initial_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["workflow-integration"])


class InvokeWorkflowRequest(BaseModel):
    """Request to invoke downstream workflow after conversation."""
    session_id: str
    conversation_state: Dict[str, Any]  # Final state from conversation engine
    workflow_type: Optional[str] = None  # Override target_workflow if needed


class InvokeWorkflowResponse(BaseModel):
    """Response from workflow invocation."""
    session_id: str
    workflow_type: str
    final_state: Dict[str, Any]
    success: bool
    error: Optional[str] = None


@router.post("/invoke-after-conversation", response_model=InvokeWorkflowResponse)
async def invoke_workflow_after_conversation_endpoint(
    request: InvokeWorkflowRequest
) -> InvokeWorkflowResponse:
    """
    Invoke downstream workflow after conversation Phase 0 completes.
    
    This endpoint takes the final state from the conversation engine and
    automatically invokes the appropriate downstream workflow (DT, Compliance, CSOD, etc.).
    
    Request body:
    {
        "session_id": "session-123",
        "conversation_state": {
            "csod_target_workflow": "dt_workflow",
            "compliance_profile": {...},
            "active_project_id": "...",
            ...
        },
        "workflow_type": "dt_workflow"  // Optional override
    }
    """
    try:
        conversation_state = request.conversation_state
        target_workflow = request.workflow_type or conversation_state.get("csod_target_workflow")
        
        if not target_workflow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No target_workflow specified in conversation_state or workflow_type"
            )
        
        # Override target_workflow if provided
        if request.workflow_type:
            conversation_state["csod_target_workflow"] = request.workflow_type
        
        # Invoke downstream workflow
        final_state = invoke_workflow_after_conversation(conversation_state)
        
        return InvokeWorkflowResponse(
            session_id=request.session_id,
            workflow_type=target_workflow,
            final_state=final_state,
            success=True,
        )
    
    except Exception as e:
        logger.error(f"Error invoking workflow after conversation: {e}", exc_info=True)
        return InvokeWorkflowResponse(
            session_id=request.session_id,
            workflow_type=request.workflow_type or "unknown",
            final_state={},
            success=False,
            error=str(e),
        )


@router.post("/map-to-dt-state")
async def map_to_dt_state_endpoint(
    conversation_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Map conversation state to DT workflow initial state.
    
    Useful for testing or manual workflow invocation.
    """
    try:
        dt_state = map_conversation_state_to_dt_initial_state(conversation_state)
        return dt_state
    except Exception as e:
        logger.error(f"Error mapping to DT state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/map-to-compliance-state")
async def map_to_compliance_state_endpoint(
    conversation_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Map conversation state to Compliance workflow initial state.
    
    Useful for testing or manual workflow invocation.
    """
    try:
        compliance_state = map_conversation_state_to_compliance_initial_state(conversation_state)
        return compliance_state
    except Exception as e:
        logger.error(f"Error mapping to Compliance state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
