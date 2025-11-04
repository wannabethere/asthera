from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
import asyncio
import uuid
import json
from datetime import datetime
import traceback
import httpx

# Import the SQL-to-Alert agent
from app.agents.nodes.writers.alerts_agent import SQLToAlertAgent, SQLAlertRequest, SQLAlertResult

# Enhanced request/response models
class SQLAlertAPIRequest(BaseModel):
    """API request model for SQL-to-Alert generation - matches SQLAlertRequest structure"""
    sql: str = Field(..., description="SQL query to analyze")
    query: str = Field(..., description="Natural language description of the query") 
    project_id: str = Field(..., description="Project identifier")
    data_description: Optional[str] = Field(None, description="Description of the data")
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional configuration")
    alert_request: str = Field(..., description="Natural language alert request")
    session_id: Optional[str] = Field(None, description="Session identifier for multi-turn conversations")
    sample_data: Optional[Dict[str, Any]] = Field(None, description="Sample data from SQL execution")
    
    # Advanced options
    enable_pattern_detection: bool = Field(True, description="Enable specialized pattern handlers")
    max_dimensions: int = Field(5, description="Maximum number of drilldown dimensions")
    preferred_resolution: Optional[str] = Field(None, description="Preferred time resolution (Daily/Weekly/Monthly)")
    notification_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SQLAlertAPIResponse(BaseModel):
    """API response model"""
    feed_configuration: Dict[str, Any]
    feed_api_payload: Dict[str, Any]
    sql_analysis: Dict[str, Any]
    confidence_score: float
    processing_time_ms: float
    session_id: str
    critique_notes: List[str]
    suggestions: List[str]
    pattern_matches: List[str] = []

class AlertValidationRequest(BaseModel):
    """Request for validating an alert configuration"""
    sql: str
    proposed_alert: Dict[str, Any]
    project_id: str = Field(..., description="Project identifier for data source access")
    business_context: Optional[str] = None

class AlertValidationResponse(BaseModel):
    """Response from alert validation"""
    is_valid: bool
    validation_score: float
    issues: List[str]
    suggestions: List[str]
    feed_compatibility: bool
    estimated_alert_frequency: str

class AlertPreviewRequest(BaseModel):
    """Request for alert preview/simulation"""
    sql: str
    alert_configuration: Dict[str, Any]
    project_id: str = Field(..., description="Project identifier for data source access")
    sample_data: Optional[List[Dict[str, Any]]] = None
    time_range_days: int = 30

class AlertPreviewResponse(BaseModel):
    """Alert preview response"""
    would_trigger: bool
    trigger_frequency: str
    sample_alerts: List[Dict[str, Any]]
    metric_trends: Dict[str, Any]
    recommendations: List[str]

class FeedIntegrationRequest(BaseModel):
    """Request for direct Feed integration"""
    feed_configuration: Dict[str, Any]
    feed_api_endpoint: str
    api_key: str
    auto_activate: bool = True

class BatchAlertRequest(BaseModel):
    """Request for batch alert generation"""
    alerts: List[SQLAlertAPIRequest]
    parallel_processing: bool = True
    max_concurrent: int = 5

# Create router instance
router = APIRouter(prefix="/api/sql-alerts", tags=["sql-alerts"])

# Global agent instance
agent: Optional[SQLToAlertAgent] = None

def get_agent() -> SQLToAlertAgent:
    """Dependency to get the agent instance"""
    global agent
    if agent is None:
        try:
            # Initialize the SQL-to-Alert agent
            agent = SQLToAlertAgent()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to initialize agent: {str(e)}")
    return agent

def initialize_agent() -> None:
    """Initialize the agent instance"""
    global agent
    if agent is None:
        try:
            agent = SQLToAlertAgent()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to initialize agent: {str(e)}")

# Main Endpoints

@router.post("/generate", response_model=SQLAlertAPIResponse)
async def generate_sql_alert(
    request: SQLAlertAPIRequest,
    background_tasks: BackgroundTasks,
    agent: SQLToAlertAgent = Depends(get_agent)
) -> SQLAlertAPIResponse:
    """
    Generate Feed alert configuration from SQL query and natural language request
    """
    start_time = datetime.now()
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Convert to agent request format
        agent_request = SQLAlertRequest(
            sql=request.sql,
            query=request.query,
            project_id=request.project_id,
            data_description=request.data_description,
            configuration=request.configuration,
            alert_request=request.alert_request,
            session_id=session_id
        )
        
        # Generate alert using Self-RAG pipeline
        result = await agent.generate_alert(agent_request)
        
        # Create Lexy API payload
        lexy_payload = agent.create_lexy_api_payload(result)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Detect patterns if enabled
        pattern_matches = []
        if request.enable_pattern_detection:
            pattern_matches = _detect_alert_patterns(request, result)
        
        return SQLAlertAPIResponse(
            feed_configuration=result.feed_configuration.dict(),
            feed_api_payload=lexy_payload,  # Using lexy_payload for backward compatibility
            sql_analysis=result.sql_analysis.dict(),
            confidence_score=result.confidence_score,
            processing_time_ms=processing_time,
            session_id=session_id,
            critique_notes=result.critique_notes,
            suggestions=result.suggestions,
            pattern_matches=pattern_matches
        )
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating SQL alert: {str(e)}"
        )

@router.post("/validate", response_model=AlertValidationResponse)
async def validate_alert_configuration(
    request: AlertValidationRequest,
    agent: SQLToAlertAgent = Depends(get_agent)
) -> AlertValidationResponse:
    """
    Validate an alert configuration against SQL analysis and business context
    """
    try:
        # Analyze SQL first
        sql_request = SQLAlertRequest(
            sql=request.sql,
            query="Validation query",
            project_id=request.project_id,
            alert_request="Validation request"
        )
        
        # Get SQL analysis
        inputs = {"request": sql_request}
        sql_analysis = await agent._analyze_sql(inputs)
        
        # Validate configuration
        validation_result = _validate_alert_config(
            request.proposed_alert,
            sql_analysis,
            request.business_context
        )
        
        return AlertValidationResponse(**validation_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")

@router.post("/preview", response_model=AlertPreviewResponse)
async def preview_alert_behavior(
    request: AlertPreviewRequest
) -> AlertPreviewResponse:
    """
    Preview how an alert configuration would behave with historical data
    """
    try:
        # Simulate alert behavior
        preview_result = _simulate_alert_behavior(request)
        
        return AlertPreviewResponse(**preview_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")

@router.post("/feed-integration")
async def integrate_with_feed(
    request: FeedIntegrationRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Directly integrate with Feed API to create Feed
    """
    try:
        # Add background task for Feed integration
        background_tasks.add_task(
            _create_feed,
            request.feed_configuration,
            request.feed_api_endpoint,
            request.api_key,
            request.auto_activate
        )
        
        return {
            "status": "integration_started",
            "message": " Feed creation initiated in background",
            "estimated_completion": "30-60 seconds"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")

@router.post("/batch", response_model=Dict[str, Any])
async def generate_batch_alerts(
    request: BatchAlertRequest,
    agent: SQLToAlertAgent = Depends(get_agent)
) -> Dict[str, Any]:
    """
    Generate multiple alerts in batch with optional parallel processing
    """
    try:
        start_time = datetime.now()
        
        if request.parallel_processing:
            # Process alerts in parallel
            semaphore = asyncio.Semaphore(request.max_concurrent)
            
            async def process_single_alert(alert_req):
                async with semaphore:
                    agent_request = SQLAlertRequest(
                        sql=alert_req.sql,
                        query=alert_req.query,
                        project_id=alert_req.project_id,
                        data_description=alert_req.data_description,
                        configuration=alert_req.configuration,
                        alert_request=alert_req.alert_request,
                        session_id=alert_req.session_id
                    )
                    return await agent.generate_alert(agent_request)
            
            tasks = [process_single_alert(req) for req in request.alerts]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Process alerts sequentially
            results = []
            for alert_req in request.alerts:
                try:
                    agent_request = SQLAlertRequest(
                        sql=alert_req.sql,
                        query=alert_req.query,
                        project_id=alert_req.project_id,
                        data_description=alert_req.data_description,
                        configuration=alert_req.configuration,
                        alert_request=alert_req.alert_request,
                        session_id=alert_req.session_id
                    )
                    result = await agent.generate_alert(agent_request)
                    results.append(result)
                except Exception as e:
                    results.append(e)
        
        # Process results
        successful_alerts = []
        failed_alerts = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_alerts.append({
                    "index": i,
                    "error": str(result),
                    "request": request.alerts[i].dict()
                })
            else:
                successful_alerts.append({
                    "index": i,
                    "configuration": result.feed_configuration.dict(),
                    "confidence": result.confidence_score
                })
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "total_requests": len(request.alerts),
            "successful": len(successful_alerts),
            "failed": len(failed_alerts),
            "processing_time_ms": processing_time,
            "successful_alerts": successful_alerts,
            "failed_alerts": failed_alerts,
            "parallel_processing": request.parallel_processing
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(e)}")

# Specialized endpoints for common patterns

@router.post("/training-completion")
async def generate_training_completion_alert(
    sql: str,
    project_id: str,
    completion_threshold: float = 90.0,
    expiry_threshold: float = 10.0,
    agent: SQLToAlertAgent = Depends(get_agent)
) -> SQLAlertAPIResponse:
    """
    Specialized endpoint for training completion alerts
    """
    request = SQLAlertAPIRequest(
        sql=sql,
        query="Training completion and status tracking",
        project_id=project_id,
        data_description="Training completion tracking data",
        alert_request=f"Alert when completion rate is below {completion_threshold}% or expiry rate exceeds {expiry_threshold}%"
    )
    
    return await generate_sql_alert(request, BackgroundTasks(), agent)

@router.post("/percentage-anomaly")
async def generate_percentage_anomaly_alert(
    sql: str,
    metric_name: str,
    project_id: str,
    agent: SQLToAlertAgent = Depends(get_agent)
) -> SQLAlertAPIResponse:
    """
    Specialized endpoint for percentage-based anomaly detection
    """
    request = SQLAlertAPIRequest(
        sql=sql,
        query=f"Monitor {metric_name} for anomalies",
        project_id=project_id,
        data_description=f"Percentage tracking for {metric_name}",
        alert_request=f"Use ARIMA-based anomaly detection to alert on unusual patterns in {metric_name}"
    )
    
    return await generate_sql_alert(request, BackgroundTasks(), agent)

# Utility endpoints

@router.get("/patterns")
async def get_supported_patterns() -> Dict[str, Any]:
    """
    Get list of supported alert patterns and their configurations
    """
    return {
        "training_completion": {
            "description": "Alerts for training completion rates, assignment backlogs, and expiry tracking",
            "typical_metrics": ["completion_percentage", "assigned_count", "expired_percentage"],
            "recommended_conditions": ["threshold_value", "threshold_percent_change"],
            "common_thresholds": {"completion": 90.0, "expiry": 10.0}
        },
        "percentage_anomaly": {
            "description": "Anomaly detection for percentage-based metrics",
            "typical_metrics": ["conversion_rate", "completion_rate", "satisfaction_score"],
            "recommended_conditions": ["intelligent_arima"],
            "considerations": ["seasonal_patterns", "historical_variance"]
        },
        "operational_threshold": {
            "description": "Simple threshold alerts for operational metrics",
            "typical_metrics": ["count", "sum", "average"],
            "recommended_conditions": ["threshold_value", "threshold_change"],
            "schedule_preference": "with_data_refresh"
        },
        "trend_analysis": {
            "description": "Trend-based alerts for strategic metrics",
            "typical_metrics": ["revenue", "user_growth", "performance_score"],
            "recommended_conditions": ["threshold_percent_change", "intelligent_arima"],
            "schedule_preference": "custom_schedule"
        }
    }

@router.get("/feed-conditions")
async def get_feed_condition_types() -> Dict[str, Any]:
    """
    Get available Feed condition types and their use cases
    """
    return {
        "intelligent_arima": {
            "description": "Automatic time-series anomaly detection using ARIMA models",
            "use_cases": ["seasonal_data", "trend_detection", "pattern_anomalies"],
            "pros": ["no_threshold_needed", "adaptive", "pattern_aware"],
            "cons": ["needs_historical_data", "less_predictable"]
        },
        "threshold_value": {
            "description": "Simple value-based threshold alerts",
            "use_cases": ["sla_monitoring", "capacity_limits", "business_rules"],
            "parameters": ["operator", "threshold_value"],
            "example": "Alert when Revenue > $10000"
        },
        "threshold_change": {
            "description": "Absolute change from previous period",
            "use_cases": ["growth_tracking", "decline_detection"],
            "parameters": ["operator", "change_amount"],
            "example": "Alert when Sales change by more than 1000 units"
        },
        "threshold_percent_change": {
            "description": "Percentage change from previous period",
            "use_cases": ["relative_performance", "percentage_tracking"],
            "parameters": ["operator", "percent_threshold"],
            "example": "Alert when Conversion Rate drops by more than 5%"
        }
    }

@router.delete("/sessions/{session_id}")
async def clear_session(
    session_id: str,
    agent: SQLToAlertAgent = Depends(get_agent)
) -> Dict[str, str]:
    """Clear a specific session"""
    if session_id in agent.sessions:
        del agent.sessions[session_id]
        return {"message": f"Session {session_id} cleared successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "SQL-to-Alert Generation Service",
        "version": "1.0.0",
        "agent_initialized": agent is not None,
        "timestamp": datetime.now().isoformat(),
        "supported_features": [
            "sql_analysis",
            "self_rag_pipeline", 
            "feed_integration",
            "batch_processing",
            "pattern_detection",
            "alert_validation"
        ]
    }

# Helper functions

def _detect_alert_patterns(request: SQLAlertAPIRequest, result: SQLAlertResult) -> List[str]:
    """Detect which alert patterns match the current request"""
    patterns = []
    
    # Check for training completion pattern
    training_keywords = ["training", "completion", "assigned", "expired"]
    if any(keyword in request.alert_request.lower() or 
           keyword in request.sql.lower() 
           for keyword in training_keywords):
        patterns.append("training_completion")
    
    # Check for percentage anomaly pattern  
    if ("percentage" in request.sql.lower() or 
        "%" in request.sql or
        "anomaly" in request.alert_request.lower()):
        patterns.append("percentage_anomaly")
    
    # Check for threshold pattern
    threshold_keywords = ["greater than", "less than", "above", "below", "exceeds"]
    if any(keyword in request.alert_request.lower() for keyword in threshold_keywords):
        patterns.append("operational_threshold")
    
    return patterns

def _validate_alert_config(
    proposed_alert: Dict[str, Any], 
    sql_analysis, 
    business_context: Optional[str]
) -> Dict[str, Any]:
    """Validate alert configuration against SQL analysis"""
    
    issues = []
    suggestions = []
    
    # Check metric availability
    if "metric" in proposed_alert:
        proposed_measure = proposed_alert["metric"].get("measure", "")
        available_metrics = sql_analysis.metrics
        
        if proposed_measure not in available_metrics and available_metrics:
            issues.append(f"Proposed measure '{proposed_measure}' not found in SQL analysis")
            suggestions.append(f"Consider using one of: {', '.join(available_metrics[:3])}")
    
    # Check dimension availability
    if "metric" in proposed_alert and "drilldown_dimensions" in proposed_alert["metric"]:
        proposed_dimensions = proposed_alert["metric"]["drilldown_dimensions"]
        available_dimensions = sql_analysis.dimensions
        
        invalid_dimensions = [d for d in proposed_dimensions if d not in available_dimensions]
        if invalid_dimensions and available_dimensions:
            issues.append(f"Invalid dimensions: {', '.join(invalid_dimensions)}")
            suggestions.append(f"Available dimensions: {', '.join(available_dimensions)}")
    
    # Validate condition appropriateness
    if "condition" in proposed_alert:
        condition_type = proposed_alert["condition"].get("condition_type", "")
        if condition_type == "intelligent_arima" and len(sql_analysis.metrics) == 0:
            issues.append("ARIMA requires time-series metrics but none detected")
            suggestions.append("Consider threshold-based conditions instead")
    
    validation_score = max(0, 1.0 - (len(issues) * 0.2))
    
    return {
        "is_valid": len(issues) == 0,
        "validation_score": validation_score,
        "issues": issues,
        "suggestions": suggestions,
        "feed_compatibility": True,  # Assume compatible for now
        "estimated_alert_frequency": "Medium"  # Would calculate based on conditions
    }

def _simulate_alert_behavior(request: AlertPreviewRequest) -> Dict[str, Any]:
    """Simulate how an alert would behave with sample data"""
    
    # Mock simulation - in real implementation, would analyze sample data
    return {
        "would_trigger": True,
        "trigger_frequency": "2-3 times per week",
        "sample_alerts": [
            {
                "timestamp": "2024-01-15T09:00:00Z",
                "metric_value": 87.5,
                "threshold": 90.0,
                "triggered": True,
                "message": "Training completion rate below threshold"
            }
        ],
        "metric_trends": {
            "average_value": 88.2,
            "trend_direction": "declining",
            "volatility": "moderate"
        },
        "recommendations": [
            "Consider adjusting threshold to 85% to reduce false positives",
            "Add weekly summary instead of immediate alerts"
        ]
    }

async def _create_feed(
    feed_config: Dict[str, Any],
    api_endpoint: str,
    api_key: str,
    auto_activate: bool
):
    """Background task to create Feed via API"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = await client.post(
                f"{api_endpoint}/feed/create",
                json=feed_config,
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"Successfully created Feed: {response.json()}")
            else:
                print(f"Failed to create Feed: {response.status_code} - {response.text}")
                
    except Exception as e:
        print(f"Error creating   Feed: {e}")

# Export the router for use in main application
__all__ = ["router", "initialize_agent"]
