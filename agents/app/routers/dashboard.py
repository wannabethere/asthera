from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from uuid import UUID

from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Request/Response Models
class DashboardQuery(BaseModel):
    """Model for dashboard query data"""
    chart_schema: Dict[str, Any]
    sql: str
    query: str
    data_description: Optional[str] = None

class DashboardContext(BaseModel):
    """Model for dashboard context"""
    title: str
    description: str
    template: Optional[str] = "operational_dashboard"
    layout: Optional[str] = "grid_2x2"
    refresh_rate: Optional[int] = 300
    auto_refresh: Optional[bool] = True
    responsive: Optional[bool] = True
    theme: Optional[str] = "default"
    custom_styling: Optional[Dict[str, Any]] = Field(default_factory=dict)
    interactive_features: Optional[List[str]] = Field(default_factory=list)
    export_options: Optional[List[str]] = Field(default_factory=lambda: ["pdf", "png", "csv"])
    sharing_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    alert_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    performance_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    charts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    available_columns: Optional[List[str]] = Field(default_factory=list)
    data_types: Optional[Dict[str, str]] = Field(default_factory=dict)

class DashboardRequest(BaseModel):
    """Request model for dashboard generation"""
    dashboard_queries: List[DashboardQuery]
    project_id: str
    natural_language_query: Optional[str] = None
    dashboard_context: Optional[DashboardContext] = None
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    workflow_data: Optional[Union[Dict[str, Any], str]] = None

class WorkflowComponentData(BaseModel):
    """Model for workflow component data"""
    id: UUID
    component_type: str
    sequence_order: int
    question: Optional[str] = None
    description: Optional[str] = None
    overview: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    table_config: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    thread_metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None
    alert_config: Optional[Dict[str, Any]] = None
    alert_status: Optional[str] = None
    last_triggered: Optional[str] = None
    trigger_count: Optional[int] = None
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_configured: Optional[bool] = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class WorkflowMetadata(BaseModel):
    """Model for workflow metadata"""
    dashboard_template: Optional[str] = None
    dashboard_layout: Optional[str] = None
    refresh_rate: Optional[int] = None
    report_title: Optional[str] = None
    report_description: Optional[str] = None
    report_sections: Optional[List[str]] = None
    writer_actor: Optional[str] = None
    business_goal: Optional[Dict[str, Any]] = None
    custom_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class DashboardWorkflowRequest(BaseModel):
    """Request model for dashboard generation from workflow data"""
    workflow_id: UUID
    project_id: str
    state: str
    current_step: int
    workflow_metadata: WorkflowMetadata
    thread_components: List[WorkflowComponentData]
    natural_language_query: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    render_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

class WorkflowComponentQuery(BaseModel):
    """Model for workflow component query data"""
    component_id: UUID
    chart_schema: Dict[str, Any]
    sql: str
    query: str
    data_description: Optional[str] = None
    component_type: str
    sequence_order: int
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)
    chart_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    table_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    alert_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class DashboardOnlyRequest(BaseModel):
    """Request model for dashboard execution without conditional formatting"""
    dashboard_queries: List[DashboardQuery]
    project_id: str

class ConditionalFormattingRequest(BaseModel):
    """Request model for conditional formatting only"""
    natural_language_query: str
    dashboard_context: DashboardContext
    project_id: str
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)

class DashboardValidationRequest(BaseModel):
    """Request model for dashboard validation"""
    dashboard_queries: List[DashboardQuery]
    dashboard_context: DashboardContext
    natural_language_query: Optional[str] = None

class DashboardResponse(BaseModel):
    """Response model for dashboard operations"""
    success: bool
    dashboard_data: Optional[Dict[str, Any]] = None
    conditional_formatting: Optional[Dict[str, Any]] = None
    chart_configurations: Optional[Dict[str, Any]] = None
    dashboard_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    workflow_metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DashboardTemplate(BaseModel):
    """Model for dashboard template"""
    name: str
    description: str
    components: List[str]
    layout: str
    refresh_rate: int
    auto_refresh: bool
    responsive: bool
    theme: str
    custom_styling: Dict[str, Any]
    interactive_features: List[str]
    export_options: List[str]

class ServiceStatusResponse(BaseModel):
    """Response model for service status"""
    dashboard_streaming: Dict[str, Any]
    conditional_formatting: Dict[str, Any]
    enhanced_dashboard: Dict[str, Any]
    pipeline_container: Dict[str, Any]
    execution_history: Dict[str, Any]

def get_dashboard_service():
    """Get the DashboardService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("dashboard_service")

@router.post("/generate", response_model=DashboardResponse)
async def generate_dashboard(
    request: DashboardRequest,
    background_tasks: BackgroundTasks
) -> DashboardResponse:
    """
    Generate a comprehensive dashboard with conditional formatting and workflow support.
    
    This endpoint processes dashboard queries with optional natural language formatting
    and workflow-driven configuration to create enhanced dashboards.
    """
    try:
        service = get_dashboard_service()
        
        # Create dashboard context if not provided
        dashboard_context = request.dashboard_context
        if not dashboard_context:
            dashboard_context = DashboardContext(
                title=f"Dashboard for Project {request.project_id}",
                description="Auto-generated dashboard context",
                template="operational_dashboard"
            )
        
        # Convert to dict for service
        context_dict = dashboard_context.dict()
        
        # Convert queries to dict format
        queries_dict = [query.dict() for query in request.dashboard_queries]
        
        # Process dashboard with conditional formatting
        result = await service.process_dashboard_with_conditional_formatting(
            natural_language_query=request.natural_language_query,
            dashboard_queries=queries_dict,
            project_id=request.project_id,
            dashboard_context=context_dict,
            additional_context=request.additional_context,
            time_filters=request.time_filters
        )
        
        return DashboardResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating dashboard: {str(e)}"
        )

@router.post("/generate-from-workflow", response_model=DashboardResponse)
async def generate_dashboard_from_workflow(
    request: DashboardRequest,
    background_tasks: BackgroundTasks
) -> DashboardResponse:
    """
    Generate dashboard using workflow data from API or JSON file.
    
    This endpoint processes dashboard queries using workflow-driven configuration
    to create enhanced dashboards with predefined templates and components.
    """
    try:
        service = get_dashboard_service()
        
        # Convert to dict format
        queries_dict = [query.dict() for query in request.dashboard_queries]
        context_dict = request.dashboard_context.dict() if request.dashboard_context else {}
        
        # Process dashboard from workflow
        result = await service.process_dashboard_from_workflow(
            workflow_data=request.workflow_data,
            dashboard_queries=queries_dict,
            project_id=request.project_id,
            natural_language_query=request.natural_language_query,
            additional_context=request.additional_context,
            time_filters=request.time_filters
        )
        
        return DashboardResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating dashboard from workflow: {str(e)}"
        )

@router.post("/render-from-workflow", response_model=DashboardResponse)
async def render_dashboard_from_workflow(
    request: DashboardWorkflowRequest,
    background_tasks: BackgroundTasks
) -> DashboardResponse:
    """
    Render dashboard from workflow data.
    
    This endpoint processes workflow data passed in the request and renders
    the dashboard using the agents based on the workflow configuration.
    """
    try:
        service = get_dashboard_service()
        
        # Convert request to workflow data format
        workflow_data = {
            "workflow_id": str(request.workflow_id),
            "state": request.state,
            "current_step": request.current_step,
            "workflow_metadata": request.workflow_metadata.dict() if request.workflow_metadata else {},
            "thread_components": [comp.dict() for comp in request.thread_components],
            "error_message": request.error_message,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
            "completed_at": request.completed_at
        }
        
        # Process dashboard from workflow data
        result = await service.render_dashboard_from_workflow_data(
            workflow_data=workflow_data,
            project_id=request.project_id,
            natural_language_query=request.natural_language_query,
            additional_context=request.additional_context,
            time_filters=request.time_filters,
            render_options=request.render_options
        )
        
        return DashboardResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error rendering dashboard from workflow: {str(e)}"
        )

@router.post("/execute-only", response_model=DashboardResponse)
async def execute_dashboard_only(
    request: DashboardOnlyRequest
) -> DashboardResponse:
    """
    Execute dashboard without conditional formatting.
    
    This endpoint runs dashboard queries directly without applying
    conditional formatting or workflow configuration.
    """
    try:
        service = get_dashboard_service()
        
        # Convert to dict format
        queries_dict = [query.dict() for query in request.dashboard_queries]
        
        # Execute dashboard only
        result = await service.execute_dashboard_only(
            dashboard_queries=queries_dict,
            project_id=request.project_id
        )
        
        return DashboardResponse(
            success=result.get("post_process", {}).get("success", False),
            dashboard_data=result.get("post_process"),
            metadata={
                "project_id": request.project_id,
                "total_queries": len(request.dashboard_queries),
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing dashboard: {str(e)}"
        )

@router.post("/conditional-formatting", response_model=DashboardResponse)
async def generate_conditional_formatting_only(
    request: ConditionalFormattingRequest
) -> DashboardResponse:
    """
    Generate only conditional formatting without executing dashboard.
    
    This endpoint processes natural language queries to create
    conditional formatting configurations for dashboard charts.
    """
    try:
        service = get_dashboard_service()
        
        # Convert to dict format
        context_dict = request.dashboard_context.dict()
        
        # Process conditional formatting only
        result = await service.process_conditional_formatting_only(
            natural_language_query=request.natural_language_query,
            dashboard_context=context_dict,
            project_id=request.project_id,
            additional_context=request.additional_context,
            time_filters=request.time_filters
        )
        
        return DashboardResponse(
            success=result.get("post_process", {}).get("success", False),
            conditional_formatting=result.get("post_process"),
            metadata={
                "project_id": request.project_id,
                "natural_language_query": request.natural_language_query,
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating conditional formatting: {str(e)}"
        )

@router.post("/validate")
async def validate_dashboard_configuration(
    request: DashboardValidationRequest
) -> Dict[str, Any]:
    """
    Validate dashboard configuration and queries.
    
    This endpoint validates the structure and syntax of dashboard
    queries and configuration before execution.
    """
    try:
        service = get_dashboard_service()
        
        # Convert to dict format
        queries_dict = [query.dict() for query in request.dashboard_queries]
        context_dict = request.dashboard_context.dict()
        
        # Validate configuration
        validation_result = service.validate_dashboard_configuration(
            dashboard_queries=queries_dict,
            dashboard_context=context_dict,
            natural_language_query=request.natural_language_query
        )
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validating dashboard configuration: {str(e)}"
        )

@router.get("/templates")
async def get_dashboard_templates() -> Dict[str, DashboardTemplate]:
    """
    Get available dashboard templates.
    
    Returns a list of predefined dashboard templates that can be used
    for quick dashboard generation.
    """
    try:
        service = get_dashboard_service()
        templates = service.get_available_templates()
        
        # Convert to response format
        response_templates = {}
        for key, template in templates.items():
            response_templates[key] = DashboardTemplate(**template)
        
        return response_templates
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving dashboard templates: {str(e)}"
        )

@router.get("/execution-history")
async def get_execution_history(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent dashboard execution history.
    
    Returns the most recent dashboard executions with their results
    and metadata for analytics purposes.
    """
    try:
        service = get_dashboard_service()
        history = service.get_execution_history(limit=limit)
        return history
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving execution history: {str(e)}"
        )

@router.get("/service-status", response_model=ServiceStatusResponse)
async def get_service_status() -> ServiceStatusResponse:
    """
    Get status of all dashboard services.
    
    Returns the availability and status of all dashboard-related
    services and pipelines.
    """
    try:
        service = get_dashboard_service()
        status = service.get_service_status()
        return ServiceStatusResponse(**status)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving service status: {str(e)}"
        )

@router.post("/clear-cache")
async def clear_cache() -> Dict[str, str]:
    """
    Clear dashboard service cache.
    
    Clears all cached configurations and execution history
    to free up memory and ensure fresh data.
    """
    try:
        service = get_dashboard_service()
        service.clear_cache()
        return {"message": "Dashboard service cache cleared successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing cache: {str(e)}"
        )

@router.get("/workflow/{workflow_id}/components")
async def get_workflow_components(workflow_id: UUID) -> Dict[str, Any]:
    """
    Get workflow components for a specific workflow.
    
    This endpoint retrieves all thread components associated with
    a workflow that can be used for dashboard rendering.
    """
    try:
        service = get_dashboard_service()
        
        # Get workflow components
        components = await service.get_workflow_components(workflow_id)
        
        return {
            "workflow_id": str(workflow_id),
            "components": components,
            "total_components": len(components)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving workflow components: {str(e)}"
        )

@router.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: UUID) -> Dict[str, Any]:
    """
    Get workflow status and metadata.
    
    This endpoint retrieves the current status and metadata
    for a specific workflow.
    """
    try:
        service = get_dashboard_service()
        
        # Get workflow status
        status = await service.get_workflow_status(workflow_id)
        
        return status
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving workflow status: {str(e)}"
        )

@router.post("/workflow/{workflow_id}/preview")
async def preview_workflow_dashboard(
    workflow_id: UUID,
    preview_options: Optional[Dict[str, Any]] = None
) -> DashboardResponse:
    """
    Preview dashboard from workflow without full rendering.
    
    This endpoint provides a quick preview of how the dashboard
    would look based on the workflow configuration.
    """
    try:
        service = get_dashboard_service()
        
        # Preview dashboard from workflow
        result = await service.preview_dashboard_from_workflow(
            workflow_id=workflow_id,
            preview_options=preview_options or {}
        )
        
        return DashboardResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error previewing workflow dashboard: {str(e)}"
        )

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check for dashboard service.
    
    Simple endpoint to verify that the dashboard service
    is running and accessible.
    """
    return {"status": "healthy", "service": "dashboard"}
