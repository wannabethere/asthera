"""
Alert Router for handling both AlertService and AlertCompatibilityService requests

This router provides endpoints for both the native alert service functionality
and the compatibility layer for main.py integration.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import traceback
import uuid
from datetime import datetime

from app.services.writers.alert_service import (
    AlertRequest, AlertResponse, AlertRequestType, AlertPriority,
    AlertCreate, AlertResponseCompatibility, Configs, Condition,
    AlertSet, AlertCombination, FeedManagementRequest
)
from app.services.service_container import SQLServiceContainer

# Create router
router = APIRouter(prefix="/alerts", tags=["alerts"])


# =============================================================================
# SERVICE CONTAINER ACCESS
# =============================================================================

def get_alert_service():
    """Get the AlertService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("alert_service")

def get_alert_compatibility_service():
    """Get the AlertCompatibilityService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("alert_compatibility_service")


# =============================================================================
# REQUEST MODELS
# =============================================================================

# Note: We use AlertCreate from the service models instead of custom request models
# AlertCreate has the structure: input, config, session_id, project_id, etc.

class BatchAlertCreateRequest(BaseModel):
    """Request model for batch alert creation"""
    alerts: List[AlertCreate] = Field(..., description="List of AlertCreate requests")
    project_id: Optional[str] = Field(None, description="Default project ID for all alerts")


class FeedCreationRequest(BaseModel):
    """Request model for creating a feed with AlertCreate requests"""
    feed_id: str = Field(..., description="Unique identifier for the feed")
    feed_name: str = Field(..., description="Human-readable name for the feed")
    project_id: str = Field(..., description="Project identifier")
    alerts: List[AlertCreate] = Field(..., description="List of AlertCreate requests for the feed")
    description: Optional[str] = Field(None, description="Description of the feed")
    data_description: Optional[str] = Field(None, description="Description of the data")
    alert_sets: Optional[List[AlertSet]] = Field(None, description="Alert sets for the feed")
    global_configuration: Optional[Dict[str, Any]] = Field(None, description="Global configuration for the feed")
    notification_settings: Optional[Dict[str, Any]] = Field(None, description="Notification settings")
    schedule_settings: Optional[Dict[str, Any]] = Field(None, description="Schedule settings")
    priority: AlertPriority = Field(AlertPriority.MEDIUM, description="Alert priority")
    tags: Optional[List[str]] = Field(None, description="Tags for the feed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Configuration overrides")


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AlertCompatibilityResponse(BaseModel):
    """Response model for alert compatibility endpoints - all endpoints use this"""
    success: bool
    data: Optional[AlertResponseCompatibility] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# ALERT SERVICE ENDPOINTS (Native Service)
# =============================================================================

@router.post("/service/create-single", response_model=AlertCompatibilityResponse)
async def create_single_alert(
    request: AlertCreate
):
    """Create a single alert using the compatibility service."""
    try:
        compatibility_service = get_alert_compatibility_service()
        result = await compatibility_service.process_alert_create(request)
        
        return AlertCompatibilityResponse(
            success=True,
            data=result,
            metadata={
                "endpoint": "create_single_alert",
                "processed_at": datetime.now().isoformat(),
                "service_created": result.service_created,
                "project_id": result.project_id,
                "session_id": result.session_id
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating single alert: {str(e)}"
        )


@router.post("/service/create-multiple", response_model=List[AlertCompatibilityResponse])
async def create_multiple_alerts(
    request: BatchAlertCreateRequest
):
    """Create multiple alerts using the compatibility service."""
    try:
        compatibility_service = get_alert_compatibility_service()
        results = []
        
        for alert in request.alerts:
            # Use provided project_id or fall back to individual alert's project_id
            project_id = request.project_id or alert.project_id
            result = await compatibility_service.process_alert_create(alert, project_id)
            
            results.append(AlertCompatibilityResponse(
                success=True,
                data=result,
                metadata={
                    "endpoint": "create_multiple_alerts",
                    "processed_at": datetime.now().isoformat(),
                    "service_created": result.service_created,
                    "project_id": result.project_id,
                    "session_id": result.session_id
                }
            ))
        
        return results
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating multiple alerts: {str(e)}"
        )


@router.post("/service/create-feed", response_model=List[AlertCompatibilityResponse])
async def create_feed(
    request: FeedCreationRequest
):
    """Create a feed using the compatibility service with AlertCreate requests."""
    try:
        compatibility_service = get_alert_compatibility_service()
        results = []
        
        # Process each alert in the feed
        for alert in request.alerts:
            # Set the project_id from the feed request if not set in the alert
            if not alert.project_id:
                alert.project_id = request.project_id
            
            result = await compatibility_service.process_alert_create(alert, request.project_id)
            
            results.append(AlertCompatibilityResponse(
                success=True,
                data=result,
                metadata={
                    "endpoint": "create_feed",
                    "processed_at": datetime.now().isoformat(),
                    "service_created": result.service_created,
                    "project_id": result.project_id,
                    "session_id": result.session_id,
                    "feed_id": request.feed_id,
                    "feed_name": request.feed_name
                }
            ))
        
        return results
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating feed: {str(e)}"
        )


@router.post("/service/process-request", response_model=AlertCompatibilityResponse)
async def process_alert_request(
    request: AlertCreate
):
    """Process a generic alert request using the compatibility service."""
    try:
        compatibility_service = get_alert_compatibility_service()
        result = await compatibility_service.process_alert_create(request)
        
        return AlertCompatibilityResponse(
            success=True,
            data=result,
            metadata={
                "endpoint": "process_alert_request",
                "processed_at": datetime.now().isoformat(),
                "service_created": result.service_created,
                "project_id": result.project_id,
                "session_id": result.session_id
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing alert request: {str(e)}"
        )


# =============================================================================
# ALERT COMPATIBILITY ENDPOINTS (Main.py Integration)
# =============================================================================

@router.post("/compatibility/create", response_model=AlertCompatibilityResponse)
async def create_alert_compatibility(
    alert_create: AlertCreate,
    project_id: Optional[str] = None
):
    """Create an alert using the compatibility service (main.py integration)."""
    try:
        compatibility_service = get_alert_compatibility_service()
        result = await compatibility_service.process_alert_create(
            alert_create=alert_create,
            project_id=project_id
        )
        
        return AlertCompatibilityResponse(
            success=True,
            data=result,
            metadata={
                "endpoint": "create_alert_compatibility",
                "processed_at": datetime.now().isoformat(),
                "service_created": result.service_created,
                "project_id": result.project_id,
                "session_id": result.session_id
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating alert with compatibility service: {str(e)}"
        )




@router.post("/compatibility/create-from-response", response_model=AlertCompatibilityResponse)
async def create_alerts_from_response(
    alert_response: AlertResponseCompatibility,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """Create alerts from AlertResponseCompatibility using the compatibility service."""
    try:
        compatibility_service = get_alert_compatibility_service()
        result = await compatibility_service.create_alerts_from_response(
            alert_response=alert_response,
            project_id=project_id,
            session_id=session_id
        )
        
        return AlertCompatibilityResponse(
            success=True,
            data=result,
            metadata={
                "endpoint": "create_alerts_from_response",
                "processed_at": datetime.now().isoformat(),
                "service_created": result.service_created,
                "project_id": result.project_id,
                "session_id": result.session_id
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating alerts from response: {str(e)}"
        )


# =============================================================================
# MAIN.PY COMPATIBILITY ENDPOINTS (Exact API Match)
# =============================================================================

@router.post("/ask/alertbuilder/ai")
async def ai_alert_create(
    alert: AlertCreate
):
    """Main.py compatibility endpoint - exact API match."""
    try:
        compatibility_service = get_alert_compatibility_service()
        # Process the request
        result = await compatibility_service.process_alert_create(alert)
        
        return {
            "response": result.dict(),
            "session_id": result.session_id,
            "conversation_history": {
                "total_messages": 1,
                "system_messages": 0,
                "human_messages": 1,
                "ai_messages": 0,
                "conversations_count": 1
            },
            "has_stored_configs": alert.config is not None,
            "service_created": result.service_created,
            "service_metadata": result.service_metadata
        }
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing alert request: {str(e)}"
        )




@router.post("/ask/alertbuilder/ai/debug")
async def debug_request(request_data: dict):
    """Debug endpoint to test request validation - main.py compatibility."""
    try:
        alert = AlertCreate(**request_data)
        return {
            "status": "valid",
            "parsed_data": alert.dict(),
            "configs_present": alert.config is not None
        }
    except Exception as e:
        return {
            "status": "invalid",
            "error": str(e),
            "error_details": str(e.__dict__ if hasattr(e, '__dict__') else 'No details')
        }


@router.post("/ask/alertbuilder/ai/clear-session")
async def clear_session(session_id: str):
    """Clear a specific session - main.py compatibility."""
    # For compatibility, we'll return a success response
    # In a real implementation, you might want to track sessions
    return {
        "message": "Session cleared successfully",
        "session_id": session_id
    }


@router.get("/ask/alertbuilder/ai/sessions")
async def list_sessions():
    """List all active sessions - main.py compatibility."""
    # For compatibility, we'll return empty sessions
    # In a real implementation, you might want to track active sessions
    return {
        "active_sessions": 0,
        "session_ids": []
    }


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for alert services."""
    try:
        # Check if services are available
        alert_service = get_alert_service()
        compatibility_service = get_alert_compatibility_service()
        
        return {
            "status": "healthy",
            "services": {
                "alert_service": "available",
                "alert_compatibility_service": "available"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/service/info")
async def get_service_info():
    """Get information about the alert service."""
    try:
        alert_service = get_alert_service()
        return {
            "service_type": "AlertService",
            "pipeline_container_available": hasattr(alert_service, '_pipeline_container'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting service info: {str(e)}"
        )


@router.get("/compatibility/info")
async def get_compatibility_info():
    """Get information about the alert compatibility service."""
    try:
        compatibility_service = get_alert_compatibility_service()
        return {
            "service_type": "AlertCompatibilityService",
            "underlying_service_available": compatibility_service.get_underlying_alert_service() is not None,
            "compatibility_wrapper_available": compatibility_service.get_compatibility_wrapper() is not None,
            "default_project_id": compatibility_service.compatibility_wrapper.default_project_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting compatibility service info: {str(e)}"
        )


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@router.post("/compatibility/batch-create", response_model=List[AlertCompatibilityResponse])
async def batch_create_alerts(
    request: BatchAlertCreateRequest
):
    """Create multiple alerts in batch using the compatibility service."""
    try:
        compatibility_service = get_alert_compatibility_service()
        results = []
        
        for alert in request.alerts:
            # Use provided project_id or fall back to individual alert's project_id
            project_id = request.project_id or alert.project_id
            result = await compatibility_service.process_alert_create(alert, project_id)
            
            results.append(AlertCompatibilityResponse(
                success=True,
                data=result,
                metadata={
                    "endpoint": "batch_create_alerts",
                    "processed_at": datetime.now().isoformat(),
                    "service_created": result.service_created,
                    "project_id": result.project_id,
                    "session_id": result.session_id
                }
            ))
        
        return results
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error in batch alert creation: {str(e)}"
        )


