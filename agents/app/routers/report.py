from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from uuid import UUID

from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/report", tags=["report"])

# Request/Response Models
class ReportQuery(BaseModel):
    """Model for report query data"""
    sql: str
    query: str
    data_description: Optional[str] = None

class ReportContext(BaseModel):
    """Model for report context"""
    title: str
    description: str
    sections: Optional[List[str]] = Field(default_factory=lambda: ["overview", "analysis", "conclusions"])
    available_columns: Optional[List[str]] = Field(default_factory=list)
    data_types: Optional[Dict[str, str]] = Field(default_factory=dict)

class ReportRequest(BaseModel):
    """Request model for comprehensive report generation"""
    report_queries: List[ReportQuery]
    project_id: str
    natural_language_query: Optional[str] = None
    report_context: Optional[ReportContext] = None
    report_template: Optional[str] = None
    custom_components: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    writer_actor: Optional[str] = None
    business_goal: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    workflow_data: Optional[Union[Dict[str, Any], str]] = None
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)

class WorkflowReportComponent(BaseModel):
    """Model for workflow report component data"""
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

class ReportWorkflowMetadata(BaseModel):
    """Model for report workflow metadata"""
    dashboard_template: Optional[str] = None
    dashboard_layout: Optional[str] = None
    refresh_rate: Optional[int] = None
    report_title: Optional[str] = None
    report_description: Optional[str] = None
    report_sections: Optional[List[str]] = None
    writer_actor: Optional[str] = None
    business_goal: Optional[Dict[str, Any]] = None
    custom_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ReportWorkflowRequest(BaseModel):
    """Request model for report generation from workflow data"""
    workflow_id: UUID
    project_id: str
    state: str
    current_step: int
    workflow_metadata: ReportWorkflowMetadata
    thread_components: List[WorkflowReportComponent]
    natural_language_query: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    render_options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    report_template: Optional[str] = None
    writer_actor: Optional[str] = None
    business_goal: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

class SimpleReportRequest(BaseModel):
    """Request model for simple report generation"""
    report_queries: List[ReportQuery]
    project_id: str
    report_context: ReportContext
    natural_language_query: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ConditionalFormattingRequest(BaseModel):
    """Request model for conditional formatting only"""
    natural_language_query: str
    report_context: ReportContext
    project_id: str
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    time_filters: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ReportValidationRequest(BaseModel):
    """Request model for report validation"""
    report_queries: List[ReportQuery]
    report_context: ReportContext
    natural_language_query: Optional[str] = None

class ReportResponse(BaseModel):
    """Response model for report operations"""
    success: bool
    report_data: Optional[Dict[str, Any]] = None
    conditional_formatting: Optional[Dict[str, Any]] = None
    orchestration_metadata: Optional[Dict[str, Any]] = None
    report_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    workflow_metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ReportTemplate(BaseModel):
    """Model for report template"""
    name: str
    description: str
    components: List[str]
    writer_actor: str
    business_goal: str

class ServiceStatusResponse(BaseModel):
    """Response model for service status"""
    report_orchestrator: Dict[str, Any]
    report_writing_agent: Dict[str, Any]
    conditional_formatting: Dict[str, Any]
    simple_report: Dict[str, Any]
    pipeline_container: Dict[str, Any]
    report_templates: Dict[str, Any]
    execution_history: Dict[str, Any]

def get_report_service():
    """Get the ReportService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("report_service")

@router.post("/generate", response_model=ReportResponse)
async def generate_comprehensive_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks
) -> ReportResponse:
    """
    Generate a comprehensive report with conditional formatting and workflow support.
    
    This endpoint processes report queries with optional natural language formatting
    and workflow-driven configuration to create enhanced reports.
    """
    try:
        service = get_report_service()
        
        # Create report context if not provided
        report_context = request.report_context
        if not report_context:
            report_context = ReportContext(
                title=f"Report for Project {request.project_id}",
                description="Auto-generated report context",
                sections=["overview", "analysis", "conclusions"]
            )
        
        # Convert to dict for service
        context_dict = report_context.dict()
        
        # Convert queries to dict format
        queries_dict = [query.dict() for query in request.report_queries]
        
        # Generate comprehensive report
        result = await service.generate_comprehensive_report(
            report_queries=queries_dict,
            project_id=request.project_id,
            report_context=context_dict,
            natural_language_query=request.natural_language_query,
            report_template=request.report_template,
            custom_components=request.custom_components,
            writer_actor=request.writer_actor,
            business_goal=request.business_goal,
            additional_context=request.additional_context,
            time_filters=request.time_filters,
            configuration=request.configuration
        )
        
        return ReportResponse(
            success=result.get("post_process", {}).get("success", False),
            report_data=result.get("post_process"),
            orchestration_metadata=result.get("post_process", {}).get("orchestration_metadata"),
            metadata={
                "project_id": request.project_id,
                "total_queries": len(request.report_queries),
                "report_template": request.report_template,
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating comprehensive report: {str(e)}"
        )

@router.post("/generate-from-workflow", response_model=ReportResponse)
async def generate_report_from_workflow(
    request: ReportRequest,
    background_tasks: BackgroundTasks
) -> ReportResponse:
    """
    Generate report using workflow data from API or JSON file.
    
    This endpoint processes report queries using workflow-driven configuration
    to create enhanced reports with predefined templates and components.
    """
    try:
        service = get_report_service()
        
        # Convert to dict format
        queries_dict = [query.dict() for query in request.report_queries]
        context_dict = request.report_context.dict() if request.report_context else {}
        
        # Generate report from workflow
        result = await service.generate_report_from_workflow(
            workflow_data=request.workflow_data,
            report_queries=queries_dict,
            project_id=request.project_id,
            natural_language_query=request.natural_language_query,
            additional_context=request.additional_context,
            time_filters=request.time_filters,
            configuration=request.configuration
        )
        
        return ReportResponse(
            success=result.get("post_process", {}).get("success", False),
            report_data=result.get("post_process"),
            orchestration_metadata=result.get("post_process", {}).get("orchestration_metadata"),
            workflow_metadata=result.get("workflow_metadata"),
            metadata={
                "project_id": request.project_id,
                "total_queries": len(request.report_queries),
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report from workflow: {str(e)}"
        )

@router.post("/render-from-workflow", response_model=ReportResponse)
async def render_report_from_workflow(
    request: ReportWorkflowRequest,
    background_tasks: BackgroundTasks
) -> ReportResponse:
    """
    Render report from workflow data.
    
    This endpoint processes workflow data passed in the request and renders
    the report using the agents based on the workflow configuration.
    """
    try:
        service = get_report_service()
        
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
        
        # Process report from workflow data
        result = await service.render_report_from_workflow_data(
            workflow_data=workflow_data,
            project_id=request.project_id,
            natural_language_query=request.natural_language_query,
            additional_context=request.additional_context,
            time_filters=request.time_filters,
            render_options=request.render_options,
            report_template=request.report_template,
            writer_actor=request.writer_actor,
            business_goal=request.business_goal
        )
        
        return ReportResponse(
            success=result.get("post_process", {}).get("success", False),
            report_data=result.get("post_process"),
            orchestration_metadata=result.get("post_process", {}).get("orchestration_metadata"),
            workflow_metadata=result.get("workflow_metadata"),
            metadata={
                "project_id": request.project_id,
                "workflow_id": str(request.workflow_id),
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error rendering report from workflow: {str(e)}"
        )

@router.post("/generate-simple", response_model=ReportResponse)
async def generate_simple_report(
    request: SimpleReportRequest
) -> ReportResponse:
    """
    Generate a simple report without comprehensive components.
    
    This endpoint creates basic reports with minimal formatting
    and structure for quick insights.
    """
    try:
        service = get_report_service()
        
        # Convert to dict format
        queries_dict = [query.dict() for query in request.report_queries]
        context_dict = request.report_context.dict()
        
        # Generate simple report
        result = await service.generate_simple_report(
            report_queries=queries_dict,
            project_id=request.project_id,
            report_context=context_dict,
            natural_language_query=request.natural_language_query,
            additional_context=request.additional_context,
            time_filters=request.time_filters
        )
        
        return ReportResponse(
            success=result.get("post_process", {}).get("success", False),
            report_data=result.get("post_process"),
            metadata={
                "project_id": request.project_id,
                "total_queries": len(request.report_queries),
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating simple report: {str(e)}"
        )

@router.post("/conditional-formatting", response_model=ReportResponse)
async def generate_conditional_formatting_only(
    request: ConditionalFormattingRequest
) -> ReportResponse:
    """
    Generate only conditional formatting without executing report queries.
    
    This endpoint processes natural language queries to create
    conditional formatting configurations for report data.
    """
    try:
        service = get_report_service()
        
        # Convert to dict format
        context_dict = request.report_context.dict()
        
        # Process conditional formatting only
        result = await service.generate_conditional_formatting_only(
            natural_language_query=request.natural_language_query,
            report_context=context_dict,
            project_id=request.project_id,
            additional_context=request.additional_context,
            time_filters=request.time_filters
        )
        
        return ReportResponse(
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
async def validate_report_configuration(
    request: ReportValidationRequest
) -> Dict[str, Any]:
    """
    Validate report configuration and queries.
    
    This endpoint validates the structure and syntax of report
    queries and configuration before execution.
    """
    try:
        service = get_report_service()
        
        # Convert to dict format
        queries_dict = [query.dict() for query in request.report_queries]
        context_dict = request.report_context.dict()
        
        # Validate configuration
        validation_result = service.validate_report_configuration(
            report_queries=queries_dict,
            report_context=context_dict,
            natural_language_query=request.natural_language_query
        )
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validating report configuration: {str(e)}"
        )

@router.get("/templates")
async def get_report_templates() -> Dict[str, ReportTemplate]:
    """
    Get available report templates.
    
    Returns a list of predefined report templates that can be used
    for quick report generation.
    """
    try:
        service = get_report_service()
        templates = service.get_available_templates()
        
        # Convert to response format
        response_templates = {}
        for key, template in templates.items():
            response_templates[key] = ReportTemplate(**template)
        
        return response_templates
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving report templates: {str(e)}"
        )

@router.post("/templates/add")
async def add_custom_template(
    template_name: str,
    template_config: Dict[str, Any]
) -> Dict[str, str]:
    """
    Add a custom report template.
    
    Allows users to create and store custom report templates
    for future use.
    """
    try:
        service = get_report_service()
        success = service.add_custom_template(template_name, template_config)
        
        if success:
            return {"message": f"Custom template '{template_name}' added successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to add custom template '{template_name}'"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding custom template: {str(e)}"
        )

@router.delete("/templates/{template_name}")
async def remove_template(template_name: str) -> Dict[str, str]:
    """
    Remove a report template.
    
    Removes a custom template from the available templates.
    """
    try:
        service = get_report_service()
        success = service.remove_template(template_name)
        
        if success:
            return {"message": f"Template '{template_name}' removed successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{template_name}' not found"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error removing template: {str(e)}"
        )

@router.get("/execution-history")
async def get_execution_history(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent report execution history.
    
    Returns the most recent report generations with their results
    and metadata for analytics purposes.
    """
    try:
        service = get_report_service()
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
    Get status of all report services.
    
    Returns the availability and status of all report-related
    services and pipelines.
    """
    try:
        service = get_report_service()
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
    Clear report service cache.
    
    Clears all cached configurations and execution history
    to free up memory and ensure fresh data.
    """
    try:
        service = get_report_service()
        service.clear_cache()
        return {"message": "Report service cache cleared successfully"}
        
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
    a workflow that can be used for report rendering.
    """
    try:
        service = get_report_service()
        
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
        service = get_report_service()
        
        # Get workflow status
        status = await service.get_workflow_status(workflow_id)
        
        return status
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving workflow status: {str(e)}"
        )

@router.post("/workflow/{workflow_id}/preview")
async def preview_workflow_report(
    workflow_id: UUID,
    preview_options: Optional[Dict[str, Any]] = None
) -> ReportResponse:
    """
    Preview report from workflow without full rendering.
    
    This endpoint provides a quick preview of how the report
    would look based on the workflow configuration.
    """
    try:
        service = get_report_service()
        
        # Preview report from workflow
        result = await service.preview_report_from_workflow(
            workflow_id=workflow_id,
            preview_options=preview_options or {}
        )
        
        return ReportResponse(
            success=result.get("post_process", {}).get("success", False),
            report_data=result.get("post_process"),
            orchestration_metadata=result.get("post_process", {}).get("orchestration_metadata"),
            workflow_metadata=result.get("workflow_metadata"),
            metadata={
                "workflow_id": str(workflow_id),
                "preview_mode": True,
                "timestamp": result.get("metadata", {}).get("timestamp")
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error previewing workflow report: {str(e)}"
        )

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check for report service.
    
    Simple endpoint to verify that the report service
    is running and accessible.
    """
    return {"status": "healthy", "service": "report"}
