"""
Alert Router for handling both AlertService and AlertCompatibilityService requests

This router provides endpoints for both the native alert service functionality
and the compatibility layer for main.py integration.
"""

from typing import Dict, Any, Optional, List, Union
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import traceback
import uuid
import re
from datetime import datetime

from app.services.writers.alert_service import (
    AlertRequest, AlertResponse, AlertRequestType, AlertPriority,
    AlertCreate, AlertResponseCompatibility, Configs, Condition,
    AlertSet, AlertCombination, FeedManagementRequest, SingleAlertRequest
)
from app.services.service_container import SQLServiceContainer
from app.core.sql_validation import (
    SQLValidationService, 
    SQLAlertConditionValidator,
    ValidationResult, 
    AlertConditionType, 
    ThresholdOperator,
    ThresholdType,
    LexyFeedCondition
)
from app.core.pandas_engine import PandasEngine

# Create router
router = APIRouter(prefix="/alerts", tags=["alerts"])

def _wrap_compat_result(result: AlertResponseCompatibility, endpoint: str, extra_metadata: Optional[Dict[str, Any]] = None) -> "AlertCompatibilityResponse":
    """Standardize success/error handling for compatibility endpoints."""
    result_type = getattr(result, "type", None)
    is_terminal_failure = result_type in {"error", "no_alerts_generated"}
    metadata: Dict[str, Any] = {
        "endpoint": endpoint,
        "processed_at": datetime.now().isoformat(),
        "service_created": getattr(result, "service_created", None),
        "project_id": getattr(result, "project_id", None),
        "session_id": getattr(result, "session_id", None),
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return AlertCompatibilityResponse(
        success=not is_terminal_failure,
        data=result,
        error=(getattr(result, "summary", None) if is_terminal_failure else None),
        metadata=metadata,
    )

def _extract_structured_context_from_combined_input(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort parser for the combined input format used by create-single endpoints.

    Expected format:
      Alert Request: ...

      Natural Language Query: ...

      SQL Query: ...
    """
    if not text or not isinstance(text, str):
        return None

    pattern = (
        r"Alert Request:\s*(?P<alert_request>.*?)(?:\n\s*\n+)"
        r"Natural Language Query:\s*(?P<natural_language_query>.*?)(?:\n\s*\n+)"
        r"SQL Query:\s*(?P<sql>.*)\s*$"
    )
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    return {
        "sql": (m.group("sql") or "").strip(),
        "natural_language_query": (m.group("natural_language_query") or "").strip(),
        "alert_request": (m.group("alert_request") or "").strip(),
    }

def _normalize_alert_create(alert: AlertCreate, project_id: Optional[str]) -> AlertCreate:
    """Make an AlertCreate behave like create-single: ensure project_id + additional_context when possible."""
    # Copy defensively (pydantic v2)
    normalized = alert.model_copy(deep=True) if hasattr(alert, "model_copy") else alert

    if project_id and not getattr(normalized, "project_id", None):
        normalized.project_id = project_id

    # If additional_context already has structured keys, keep it.
    ctx = (getattr(normalized, "additional_context", None) or {})
    has_structured = any(k in ctx for k in ("sql", "sql_query", "natural_language_query", "alert_request"))
    if not has_structured:
        extracted = _extract_structured_context_from_combined_input(getattr(normalized, "input", ""))
        if extracted:
            # Preserve any existing context fields
            merged = dict(ctx)
            merged.update(extracted)
            normalized.additional_context = merged

    return normalized


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


class SQLQueryPair(BaseModel):
    """SQL query pair model that accepts 'sql' field and maps to AlertCombination"""
    sql: str = Field(..., description="SQL query for the alert")
    natural_language_query: str = Field(..., description="Natural language description of the query")
    alert_request: str = Field(..., description="Natural language description of the alert requirements")
    sample_data: Optional[Dict[str, Any]] = Field(None, description="Sample data for the alert")
    
    def to_alert_combination(self) -> AlertCombination:
        """Convert to AlertCombination model"""
        return AlertCombination(
            sql_query=self.sql,
            natural_language_query=self.natural_language_query,
            alert_request=self.alert_request
        )


class SQLQueryPairRequest(BaseModel):
    """Request model for SQL query pair with alert creation"""
    sql_query_pair: SQLQueryPair = Field(..., description="SQL query pair containing alert information")
    project_id: str = Field(..., description="Project identifier")
    data_description: Optional[str] = Field(None, description="Description of the data")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Configuration overrides")
    session_id: Optional[str] = Field(None, description="Session identifier")


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
    request: SQLQueryPairRequest
):
    """Create a single alert using the compatibility service with SQL query pair."""
    try:
        compatibility_service = get_alert_compatibility_service()
        
        # Convert SQLQueryPair to AlertCombination and then to AlertCreate format
        alert_combination = request.sql_query_pair.to_alert_combination()
        
        # Create a combined input string from the alert combination
        combined_input = f"Alert Request: {alert_combination.alert_request}\n\nNatural Language Query: {alert_combination.natural_language_query}\n\nSQL Query: {alert_combination.sql_query}"
        
        alert_create = AlertCreate(
            input=combined_input,
            project_id=request.project_id,
            data_description=request.data_description,
            session_id=request.session_id,
            configuration=request.configuration,
            additional_context={
                "sql": request.sql_query_pair.sql,
                "natural_language_query": request.sql_query_pair.natural_language_query,
                "alert_request": request.sql_query_pair.alert_request,
                "sample_data": request.sql_query_pair.sample_data,
            },
        )
        
        result = await compatibility_service.process_alert_create(alert_create)
        return _wrap_compat_result(result, endpoint="create_single_alert", extra_metadata={"sql_query_pair_processed": True})
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating single alert: {str(e)}"
        )


@router.post("/service/create-single-direct", response_model=AlertCompatibilityResponse)
async def create_single_alert_direct(
    request: AlertCombination,
    project_id: str,
    data_description: Optional[str] = None,
    configuration: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
):
    """Create a single alert directly using AlertCombination model."""
    try:
        compatibility_service = get_alert_compatibility_service()
        
        # Convert AlertCombination to AlertCreate format
        combined_input = f"Alert Request: {request.alert_request}\n\nNatural Language Query: {request.natural_language_query}\n\nSQL Query: {request.sql_query}"
        
        alert_create = AlertCreate(
            input=combined_input,
            project_id=project_id,
            data_description=data_description,
            session_id=session_id,
            configuration=configuration,
            additional_context={
                "sql": request.sql_query,
                "natural_language_query": request.natural_language_query,
                "alert_request": request.alert_request,
            },
        )
        
        result = await compatibility_service.process_alert_create(alert_create)
        
        return _wrap_compat_result(
            result,
            endpoint="create_single_alert_direct",
            extra_metadata={"alert_combination_processed": True},
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating single alert directly: {str(e)}"
        )


@router.post("/service/create-multiple", response_model=List[AlertCompatibilityResponse])
async def create_multiple_alerts(
    request: BatchAlertCreateRequest
):
    """Create multiple alerts using the compatibility service."""
    try:
        # Ensure at least one project_id is provided
        has_project_id = request.project_id or any(alert.project_id for alert in request.alerts)
        if not has_project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required. Provide it in the batch request or in each individual alert."
            )
        
        compatibility_service = get_alert_compatibility_service()
        results = []
        
        for idx, alert in enumerate(request.alerts):
            # Use provided project_id or fall back to individual alert's project_id
            project_id = request.project_id or alert.project_id
            if not project_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Alert at index {request.alerts.index(alert)} is missing project_id"
                )
            
            normalized_alert = _normalize_alert_create(alert, project_id=project_id)
            result = await compatibility_service.process_alert_create(normalized_alert, project_id)
            results.append(
                _wrap_compat_result(
                    result,
                    endpoint="create_multiple_alerts",
                    extra_metadata={"alert_index": idx},
                )
            )
        
        return results
        
    except HTTPException:
        raise
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
        # Ensure project_id is provided
        if not request.project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required in feed creation request."
            )
        
        compatibility_service = get_alert_compatibility_service()
        results = []
        
        # Process each alert in the feed
        for idx, alert in enumerate(request.alerts):
            # Set the project_id from the feed request if not set in the alert
            if not alert.project_id:
                alert.project_id = request.project_id
            
            normalized_alert = _normalize_alert_create(alert, project_id=request.project_id)
            result = await compatibility_service.process_alert_create(normalized_alert, request.project_id)
            
            results.append(
                _wrap_compat_result(
                    result,
                    endpoint="create_feed",
                    extra_metadata={
                    "feed_id": request.feed_id,
                        "feed_name": request.feed_name,
                        "alert_index": idx,
                    },
                )
            )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating feed: {str(e)}"
        )


@router.post("/service/process-request", response_model=AlertCompatibilityResponse)
async def process_alert_request(
    request: AlertCreate,
    project_id: Optional[str] = None
):
    """Process a generic alert request using the compatibility service."""
    try:
        # Ensure project_id is provided
        if not request.project_id and not project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required. Provide it in the AlertCreate or as a parameter."
            )
        
        # Override with parameter if provided
        if project_id:
            request.project_id = project_id
        
        compatibility_service = get_alert_compatibility_service()
        normalized_request = _normalize_alert_create(request, project_id=request.project_id)
        result = await compatibility_service.process_alert_create(normalized_request)
        
        return _wrap_compat_result(result, endpoint="process_alert_request")
        
    except HTTPException:
        raise
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
        # Ensure project_id is provided
        if not alert_create.project_id and not project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required. Provide it in alert_create or as a parameter."
            )
        
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
        
    except HTTPException:
        raise
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
    alert: AlertCreate,
    project_id: Optional[str] = None
):
    """Main.py compatibility endpoint - exact API match."""
    try:
        # Ensure project_id is provided
        if not alert.project_id and not project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required. Provide it in alert or as a parameter."
            )
        
        # Override with parameter if provided
        if project_id:
            alert.project_id = project_id
        
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
        
    except HTTPException:
        raise
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
            "configs_present": alert.config is not None,
            "project_id_present": alert.project_id is not None,
            "warning": "project_id required for execution" if not alert.project_id else "project_id provided"
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
        # Ensure at least one project_id is provided
        has_project_id = request.project_id or any(alert.project_id for alert in request.alerts)
        if not has_project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required. Provide it in the batch request or in each individual alert."
            )
        
        compatibility_service = get_alert_compatibility_service()
        results = []
        
        for alert in request.alerts:
            # Use provided project_id or fall back to individual alert's project_id
            project_id = request.project_id or alert.project_id
            if not project_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Alert at index {request.alerts.index(alert)} is missing project_id"
                )
            
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
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error in batch alert creation: {str(e)}"
        )


# =============================================================================
# VALIDATION ENDPOINTS
# =============================================================================

class ConditionValidationRequest(BaseModel):
    """Request model for validating alert conditions"""
    sql_query: str = Field(..., description="SQL query to execute for validation")
    condition_type: AlertConditionType = Field(..., description="Type of condition to validate")
    operator: ThresholdOperator = Field(..., description="Threshold operator")
    threshold_value: float = Field(..., description="Threshold value to compare against")
    threshold_type: ThresholdType = Field(default=ThresholdType.DEFAULT, description="Type of threshold value interpretation")
    metric_column: Optional[str] = Field(default=None, description="Specific column to extract value from")
    use_cache: bool = Field(default=True, description="Whether to use caching for SQL execution")
    overall_condition_logic: str = Field(default="any_met", description="Logic for determining overall condition status")
    project_id: str = Field(..., description="Project identifier for data source access")

class ProposedAlertConditionValidationRequest(BaseModel):
    """Validate a condition by providing a proposed alert configuration (feed configuration)."""
    sql: str = Field(..., description="SQL query to execute for validation")
    proposed_alert: Dict[str, Any] = Field(..., description="Proposed alert/feed configuration to validate")
    project_id: str = Field(..., description="Project identifier for data source access")
    business_context: Optional[str] = Field(default=None, description="Optional business context for validation/explanation")
    condition_index: int = Field(default=0, description="Which condition in proposed_alert.conditions to validate")
    metric_column: Optional[str] = Field(default=None, description="Override for which result column to validate")
    use_cache: bool = Field(default=True, description="Whether to use caching for SQL execution")
    overall_condition_logic: str = Field(default="any_met", description="Logic for determining overall condition status")


def _map_threshold_type_from_feed(threshold_type: Optional[str]) -> str:
    """Map feed-style threshold_type values to validator ThresholdType values."""
    if not threshold_type:
        return ThresholdType.DEFAULT.value
    t = str(threshold_type).lower()
    if "percent" in t:
        return ThresholdType.PERCENTAGE.value
    if "ratio" in t:
        return ThresholdType.RATIO.value
    if "percentile" in t:
        return ThresholdType.PERCENTILE.value
    if "multiplier" in t:
        return ThresholdType.MULTIPLIER.value
    if "absolute" in t:
        return ThresholdType.ABSOLUTE.value
    # Common feed values like "based_on_value" / "based_on_change" map best to direct comparison
    return ThresholdType.DEFAULT.value


class ConditionValidationResponse(BaseModel):
    """Response model for condition validation"""
    is_valid: bool = Field(..., description="Whether the validation was successful")
    current_value: Optional[float] = Field(default=None, description="Current value from SQL query")
    threshold_value: Optional[float] = Field(default=None, description="Processed threshold value used for comparison")
    original_threshold_value: Optional[float] = Field(default=None, description="Original threshold value before processing")
    threshold_type: Optional[str] = Field(default=None, description="Type of threshold value interpretation")
    condition_met: Optional[bool] = Field(default=None, description="Whether the condition is currently met")
    error_message: Optional[str] = Field(default=None, description="Error message if validation failed")
    validation_timestamp: datetime = Field(..., description="Timestamp when validation was performed")
    execution_time_ms: Optional[float] = Field(default=None, description="Execution time in milliseconds")
    
    # Additional detailed results for multi-row validation
    validation_summary: Optional[Dict[str, Any]] = Field(default=None, description="Summary of validation results across all rows")
    condition_not_met_rows: Optional[List[Dict[str, Any]]] = Field(default=None, description="Rows where the condition was not met")
    condition_met_rows: Optional[List[Dict[str, Any]]] = Field(default=None, description="Rows where the condition was met")
    all_results: Optional[List[Dict[str, Any]]] = Field(default=None, description="All validation results for each row")
    debug_info: Optional[Dict[str, Any]] = Field(default=None, description="Debug information about data processing")


@router.post("/validate-condition", response_model=ConditionValidationResponse)
async def validate_alert_condition(request: Union[ConditionValidationRequest, ProposedAlertConditionValidationRequest]):
    """
    Validate an alert condition by executing SQL and checking threshold conditions
    
    This endpoint delegates to the AlertService for validation logic.
    """
    try:
        # Get the alert service
        alert_service = get_alert_service()
        
        # Backward compatible: support the original request shape
        if isinstance(request, ConditionValidationRequest):
            result = await alert_service.validate_alert_condition(
                sql_query=request.sql_query,
                condition_type=request.condition_type.value,  # Enum -> string
                operator=request.operator.value,  # Enum -> string
                threshold_value=request.threshold_value,
                threshold_type=request.threshold_type.value,  # Enum -> string
                metric_column=request.metric_column,
                use_cache=request.use_cache,
                overall_condition_logic=request.overall_condition_logic,
                project_id=request.project_id,
            )
        else:
            # New format: { sql, proposed_alert, project_id, ... }
            proposed = request.proposed_alert or {}
            metric = proposed.get("metric") or {}
            conditions = proposed.get("conditions") or []
            if not isinstance(conditions, list) or not conditions:
                raise HTTPException(status_code=400, detail="proposed_alert.conditions must be a non-empty list")

            idx = request.condition_index or 0
            if idx < 0 or idx >= len(conditions):
                raise HTTPException(status_code=400, detail=f"condition_index {idx} out of range for proposed_alert.conditions")

            cond = conditions[idx] or {}
            if not isinstance(cond, dict):
                raise HTTPException(status_code=400, detail="Each entry in proposed_alert.conditions must be an object")

            condition_type = str(cond.get("condition_type") or AlertConditionType.THRESHOLD_VALUE.value)
            operator = str(cond.get("operator") or ThresholdOperator.GREATER_THAN.value)
            threshold_value = cond.get("value")
            if threshold_value is None:
                raise HTTPException(status_code=400, detail="proposed_alert.conditions[condition_index].value is required")

            # Determine which result column to validate
            metric_column = request.metric_column or metric.get("measure") or None
            threshold_type = _map_threshold_type_from_feed(cond.get("threshold_type"))

            result = await alert_service.validate_alert_condition(
                sql_query=request.sql,
                condition_type=condition_type,
                operator=operator,
                threshold_value=float(threshold_value),
                threshold_type=threshold_type,
                metric_column=metric_column,
                use_cache=request.use_cache,
                overall_condition_logic=request.overall_condition_logic,
                project_id=request.project_id,
            )
        
        return ConditionValidationResponse(**result)
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error validating condition: {str(e)}"
        )


@router.post("/validate-threshold", response_model=ConditionValidationResponse)
async def validate_threshold_condition(
    sql_query: str,
    operator: ThresholdOperator,
    threshold_value: float,
    project_id: str,
    metric_column: Optional[str] = None,
    use_cache: bool = True
):
    """
    Validate a simple threshold condition
    
    This is a simplified endpoint for validating basic threshold conditions
    that delegates to the AlertService for validation logic.
    """
    try:
        # Get the alert service
        alert_service = get_alert_service()
        
        # Convert ThresholdOperator enum to string
        operator_str = operator.value if hasattr(operator, 'value') else str(operator)
        
        # Delegate to the service layer
        result = await alert_service.validate_threshold_condition(
            sql_query=sql_query,
            operator=operator_str,
            threshold_value=threshold_value,
            threshold_type="default", # Default threshold type for backward compatibility
            metric_column=metric_column,
            use_cache=use_cache,
            overall_condition_logic="any_met",
            project_id=project_id
        )
        
        return ConditionValidationResponse(**result)
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error validating threshold condition: {str(e)}"
        )


