"""
Alert Router for handling both AlertService and AlertCompatibilityService requests

This router provides endpoints for both the native alert service functionality
and the compatibility layer for main.py integration.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
import traceback
import uuid
from datetime import datetime

from app.services.writers.alert_service import (
    AlertRequest, AlertResponse, AlertRequestType, AlertPriority,
    AlertCreate, AlertResponseCompatibility, Configs, Condition,
    AlertSet, AlertCombination, FeedManagementRequest
)
from app.core.dependencies import get_alert_service, get_alert_compatibility_service

# Create router
router = APIRouter(prefix="/alerts", tags=["alerts"])


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================
# Dependencies are now imported from app.core.dependencies


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AlertServiceResponse(BaseModel):
    """Response model for alert service endpoints"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AlertCompatibilityResponse(BaseModel):
    """Response model for alert compatibility endpoints"""
    success: bool
    data: Optional[AlertResponseCompatibility] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# ALERT SERVICE ENDPOINTS (Native Service)
# =============================================================================

@router.post("/service/create-single", response_model=AlertServiceResponse)
async def create_single_alert(
    sql_queries: List[str],
    natural_language_query: str,
    alert_request: str,
    project_id: str,
    data_description: Optional[str] = None,
    session_id: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    configuration: Optional[Dict[str, Any]] = None,
    alert_service = Depends(get_alert_service)
):
    """Create a single alert using the native alert service."""
    try:
        result = await alert_service.create_single_alert(
            sql_queries=sql_queries,
            natural_language_query=natural_language_query,
            alert_request=alert_request,
            project_id=project_id,
            data_description=data_description,
            session_id=session_id,
            additional_context=additional_context,
            configuration=configuration
        )
        
        return AlertServiceResponse(
            success=True,
            data=result.dict(),
            metadata={
                "endpoint": "create_single_alert",
                "processed_at": datetime.now().isoformat(),
                "request_type": result.request_type
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating single alert: {str(e)}"
        )


@router.post("/service/create-feed", response_model=AlertServiceResponse)
async def create_feed(
    feed_id: str,
    feed_name: str,
    project_id: str,
    alert_combinations: List[AlertCombination],
    description: Optional[str] = None,
    data_description: Optional[str] = None,
    alert_sets: Optional[List[AlertSet]] = None,
    global_configuration: Optional[Dict[str, Any]] = None,
    notification_settings: Optional[Dict[str, Any]] = None,
    schedule_settings: Optional[Dict[str, Any]] = None,
    priority: AlertPriority = AlertPriority.MEDIUM,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    configuration: Optional[Dict[str, Any]] = None,
    alert_service = Depends(get_alert_service)
):
    """Create a feed using the native alert service."""
    try:
        result = await alert_service.create_feed(
            feed_id=feed_id,
            feed_name=feed_name,
            project_id=project_id,
            alert_combinations=alert_combinations,
            description=description,
            data_description=data_description,
            alert_sets=alert_sets,
            global_configuration=global_configuration,
            notification_settings=notification_settings,
            schedule_settings=schedule_settings,
            priority=priority,
            tags=tags,
            metadata=metadata,
            configuration=configuration
        )
        
        return AlertServiceResponse(
            success=True,
            data=result.dict(),
            metadata={
                "endpoint": "create_feed",
                "processed_at": datetime.now().isoformat(),
                "request_type": result.request_type
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating feed: {str(e)}"
        )


@router.post("/service/process-request", response_model=AlertServiceResponse)
async def process_alert_request(
    request: AlertRequest,
    alert_service = Depends(get_alert_service)
):
    """Process a generic alert request using the native alert service."""
    try:
        result = await alert_service.process_request(request)
        
        return AlertServiceResponse(
            success=True,
            data=result.dict(),
            metadata={
                "endpoint": "process_alert_request",
                "processed_at": datetime.now().isoformat(),
                "request_type": result.request_type
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
    project_id: Optional[str] = None,
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Create an alert using the compatibility service (main.py integration)."""
    try:
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
    session_id: Optional[str] = None,
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Create alerts from AlertResponseCompatibility using the compatibility service."""
    try:
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
    alert: AlertCreate,
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Main.py compatibility endpoint - exact API match."""
    try:
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
async def health_check(
    alert_service = Depends(get_alert_service),
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Health check endpoint for alert services."""
    try:
        # Check if services are available
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
async def get_service_info(alert_service = Depends(get_alert_service)):
    """Get information about the alert service."""
    try:
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
async def get_compatibility_info(compatibility_service = Depends(get_alert_compatibility_service)):
    """Get information about the alert compatibility service."""
    try:
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
    alerts: List[AlertCreate],
    project_id: Optional[str] = None,
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Create multiple alerts in batch using the compatibility service."""
    try:
        results = []
        for alert in alerts:
            result = await compatibility_service.process_alert_create(
                alert_create=alert,
                project_id=project_id
            )
            results.append(AlertCompatibilityResponse(
                success=True,
                data=result,
                metadata={
                    "endpoint": "batch_create_alerts",
                    "processed_at": datetime.now().isoformat(),
                    "service_created": result.service_created
                }
            ))
        
        return results
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error in batch alert creation: {str(e)}"
        )
