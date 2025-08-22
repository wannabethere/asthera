"""
Report Writing API Router

This router provides endpoints for:
1. Generating reports using AI agents
2. Managing report generation status
3. Regenerating reports with feedback
4. Exporting reports in different formats
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.report_writing_service import (
    ReportWritingService,
    get_report_writing_service
)
from app.agents.report_writing_agent import WriterActorType, BusinessGoal
from app.core.dependencies import get_current_user
from app.models.dbmodels import User

router = APIRouter(prefix="/report-writing", tags=["Report Writing"])


# Request/Response Models
class BusinessGoalCreate(BaseModel):
    """Request model for creating business goals"""
    primary_objective: str = Field(..., description="Primary business objective")
    target_audience: List[str] = Field(..., description="Target audience for the report")
    decision_context: str = Field(..., description="Context for decision making")
    success_metrics: List[str] = Field(..., description="Success metrics to track")
    timeframe: str = Field(..., description="Timeframe for the report")
    risk_factors: List[str] = Field(default_factory=list, description="Key risk factors")


class ReportGenerationRequest(BaseModel):
    """Request model for report generation"""
    workflow_id: UUID = Field(..., description="Report workflow ID")
    writer_actor: WriterActorType = Field(..., description="Writer actor type")
    business_goal: BusinessGoalCreate = Field(..., description="Business goal configuration")


class ReportFeedbackRequest(BaseModel):
    """Request model for report feedback and regeneration"""
    business_objective: Optional[str] = Field(None, description="Updated business objective")
    target_audience: Optional[List[str]] = Field(None, description="Updated target audience")
    decision_context: Optional[str] = Field(None, description="Updated decision context")
    additional_requirements: Optional[str] = Field(None, description="Additional requirements")
    style_preferences: Optional[Dict[str, Any]] = Field(None, description="Style preferences")


class ReportGenerationResponse(BaseModel):
    """Response model for report generation"""
    success: bool
    workflow_id: str
    report_data: Dict[str, Any]
    generated_at: str
    quality_score: Optional[float] = None
    iterations: Optional[int] = None


class ReportStatusResponse(BaseModel):
    """Response model for report generation status"""
    workflow_id: str
    has_generated_report: bool
    last_generation: Optional[str] = None
    writer_actor: Optional[str] = None
    quality_score: Optional[float] = None
    iterations: Optional[int] = None
    business_goal: Optional[Dict[str, Any]] = None


class WriterActorResponse(BaseModel):
    """Response model for writer actor information"""
    value: str
    label: str
    description: str


class QualityMetricsResponse(BaseModel):
    """Response model for quality metrics"""
    workflow_id: str
    quality_score: float
    iterations: int
    writer_actor: str
    business_goal_alignment: Dict[str, Any]
    generation_timestamp: str
    is_regeneration: bool


@router.post("/generate", response_model=ReportGenerationResponse)
async def generate_report(
    request: ReportGenerationRequest,
    current_user: User = Depends(get_current_user),
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> Dict[str, Any]:
    """
    Generate a report using AI agent with self-correcting RAG
    
    This endpoint:
    1. Takes thread component questions selected for report generation
    2. Uses a self-correcting RAG architecture with LangChain agents
    3. Evaluates content quality and relevance
    4. Incorporates writer actor types and business goals
    5. Generates comprehensive, well-structured reports
    """
    
    try:
        # Convert request to BusinessGoal model
        business_goal = BusinessGoal(**request.business_goal.dict())
        
        # Generate report
        result = report_service.generate_report_with_agent(
            workflow_id=request.workflow_id,
            writer_actor=request.writer_actor,
            business_goal=business_goal,
            user_id=current_user.id
        )
        
        # Extract quality metrics
        quality_score = None
        iterations = None
        if result.get("report_data", {}).get("quality_assessment"):
            quality_score = result["report_data"]["quality_assessment"].get("average_quality_score")
            iterations = result["report_data"]["generation_metadata"].get("iterations")
        
        return ReportGenerationResponse(
            success=result["success"],
            workflow_id=result["workflow_id"],
            report_data=result["report_data"],
            generated_at=result["generated_at"],
            quality_score=quality_score,
            iterations=iterations
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )


@router.get("/status/{workflow_id}", response_model=ReportStatusResponse)
async def get_report_status(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> Dict[str, Any]:
    """Get the status of report generation for a workflow"""
    
    try:
        status_info = report_service.get_report_generation_status(
            workflow_id=workflow_id,
            user_id=current_user.id
        )
        
        return ReportStatusResponse(**status_info)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get report status: {str(e)}"
        )


@router.post("/regenerate/{workflow_id}", response_model=ReportGenerationResponse)
async def regenerate_report(
    workflow_id: UUID,
    feedback: ReportFeedbackRequest,
    current_user: User = Depends(get_current_user),
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> Dict[str, Any]:
    """Regenerate report based on user feedback"""
    
    try:
        # Convert feedback to dictionary format
        feedback_dict = feedback.dict(exclude_none=True)
        
        # Regenerate report
        result = report_service.regenerate_report_with_feedback(
            workflow_id=workflow_id,
            user_id=current_user.id,
            feedback=feedback_dict
        )
        
        # Extract quality metrics
        quality_score = None
        iterations = None
        if result.get("report_data", {}).get("quality_assessment"):
            quality_score = result["report_data"]["quality_assessment"].get("average_quality_score")
            iterations = result["report_data"]["generation_metadata"].get("iterations")
        
        return ReportGenerationResponse(
            success=result["success"],
            workflow_id=result["workflow_id"],
            report_data=result["report_data"],
            generated_at=result["regenerated_at"],
            quality_score=quality_score,
            iterations=iterations
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate report: {str(e)}"
        )


@router.get("/writer-actors", response_model=List[WriterActorResponse])
async def get_writer_actors(
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> List[Dict[str, str]]:
    """Get available writer actor types with descriptions"""
    
    try:
        actors = report_service.get_available_writer_actors()
        return [WriterActorResponse(**actor) for actor in actors]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get writer actors: {str(e)}"
        )


@router.get("/quality-metrics/{workflow_id}", response_model=QualityMetricsResponse)
async def get_quality_metrics(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> Dict[str, Any]:
    """Get detailed quality metrics for the generated report"""
    
    try:
        metrics = report_service.get_report_quality_metrics(
            workflow_id=workflow_id,
            user_id=current_user.id
        )
        
        return QualityMetricsResponse(**metrics)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quality metrics: {str(e)}"
        )


@router.get("/export/{workflow_id}")
async def export_report(
    workflow_id: UUID,
    format_type: str = "json",
    current_user: User = Depends(get_current_user),
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> Dict[str, Any]:
    """Export the generated report to a specific format"""
    
    try:
        export_data = report_service.export_report_to_format(
            workflow_id=workflow_id,
            user_id=current_user.id,
            format_type=format_type
        )
        
        return export_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for report writing service"""
    return {"status": "healthy", "service": "report-writing"}


# Additional utility endpoints
@router.get("/workflow/{workflow_id}/components")
async def get_workflow_components(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    report_service: ReportWritingService = Depends(get_report_writing_service)
) -> Dict[str, Any]:
    """Get thread components for a workflow (for debugging/inspection)"""
    
    try:
        # This would need to be added to the service
        # For now, return a placeholder
        return {
            "workflow_id": str(workflow_id),
            "message": "Component retrieval not yet implemented",
            "status": "placeholder"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow components: {str(e)}"
        )


@router.post("/validate-business-goal")
async def validate_business_goal(
    business_goal: BusinessGoalCreate
) -> Dict[str, Any]:
    """Validate a business goal configuration"""
    
    try:
        # Basic validation
        if not business_goal.primary_objective.strip():
            raise ValueError("Primary objective cannot be empty")
        
        if not business_goal.target_audience:
            raise ValueError("Target audience must be specified")
        
        if not business_goal.decision_context.strip():
            raise ValueError("Decision context cannot be empty")
        
        return {
            "valid": True,
            "message": "Business goal configuration is valid",
            "business_goal": business_goal.dict()
        }
        
    except Exception as e:
        return {
            "valid": False,
            "message": f"Business goal validation failed: {str(e)}",
            "errors": [str(e)]
        }
