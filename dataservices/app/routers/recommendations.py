"""
Comprehensive Recommendations API Router
Provides endpoints for generating comprehensive recommendations including semantic descriptions,
relationship recommendations, optimization suggestions, and data quality recommendations
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["recommendations"])

class TableColumnRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    is_primary_key: bool = False
    is_nullable: bool = True
    is_foreign_key: bool = False
    usage_type: Optional[str] = None

class ComprehensiveRecommendationRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    columns: List[TableColumnRequest]
    project_id: Optional[str] = None
    business_domain: Optional[str] = "General"
    project_name: Optional[str] = None
    recommendation_types: Optional[List[str]] = None

class ComprehensiveRecommendationResponse(BaseModel):
    table_name: str
    project_id: str
    generated_at: str
    recommendation_types: List[str]
    results: Dict[str, Any]
    summary: Dict[str, Any]
    error: Optional[str] = None
    status: Optional[str] = None

@router.post("/comprehensive", response_model=ComprehensiveRecommendationResponse)
async def get_comprehensive_recommendations(request: ComprehensiveRecommendationRequest):
    """
    Generate comprehensive recommendations for a table structure
    
    This endpoint analyzes the table structure and generates multiple types of recommendations:
    - Semantic descriptions
    - Relationship recommendations
    - Optimization suggestions
    - Data quality recommendations
    
    The recommendation_types parameter allows you to specify which types to generate.
    Defaults to ["semantic", "relationships", "optimization"].
    """
    try:
        # Create project context for the request
        project_context = ProjectContext(
            project_id=request.project_id or "default_project",
            project_name=request.project_name or f"Project for {request.name}",
            business_domain=request.business_domain,
            purpose=f"Generate comprehensive recommendations for {request.name}",
            target_users=["Data Analysts", "Business Users", "Developers"],
            key_business_concepts=["Data Analysis", "Business Intelligence", "Data Quality"],
            data_sources=["User Input"],
            compliance_requirements=[]
        )
        
        # Convert columns to the format expected by SchemaInput
        columns = []
        for col in request.columns:
            column_data = {
                "name": col.name,
                "display_name": col.display_name or col.name,
                "description": col.description,
                "data_type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "is_nullable": col.is_nullable,
                "is_foreign_key": col.is_foreign_key,
                "usage_type": col.usage_type
            }
            columns.append(column_data)
        
        # Create schema input
        schema_input = SchemaInput(
            table_name=request.name,
            table_description=request.description,
            columns=columns
        )
        
        # Create add table request
        add_table_request = AddTableRequest(
            dataset_id="api_dataset",
            schema=schema_input
        )
        
        # Create workflow service instance
        workflow_service = ProjectWorkflowService(
            user_id="api_user",
            session_id=f"recommendations_{request.project_id or 'default'}"
        )
        
        # Generate comprehensive recommendations using workflow service
        recommendations = await workflow_service.get_recommendations(
            add_table_request, 
            project_context,
            recommendation_types=request.recommendation_types
        )
        
        return ComprehensiveRecommendationResponse(**recommendations)
        
    except Exception as e:
        logger.error(f"Error in get_comprehensive_recommendations endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate comprehensive recommendations: {str(e)}"
        )

@router.post("/semantic", response_model=Dict[str, Any])
async def get_semantic_recommendations(request: ComprehensiveRecommendationRequest):
    """
    Generate semantic description recommendations for a table structure
    """
    try:
        # Create project context for the request
        project_context = ProjectContext(
            project_id=request.project_id or "default_project",
            project_name=request.project_name or f"Project for {request.name}",
            business_domain=request.business_domain,
            purpose=f"Generate semantic descriptions for {request.name}",
            target_users=["Data Analysts", "Business Users"],
            key_business_concepts=["Data Analysis", "Business Intelligence"],
            data_sources=["User Input"],
            compliance_requirements=[]
        )
        
        # Convert columns to the format expected by SchemaInput
        columns = []
        for col in request.columns:
            column_data = {
                "name": col.name,
                "display_name": col.display_name or col.name,
                "description": col.description,
                "data_type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "is_nullable": col.is_nullable,
                "is_foreign_key": col.is_foreign_key,
                "usage_type": col.usage_type
            }
            columns.append(column_data)
        
        # Create schema input
        schema_input = SchemaInput(
            table_name=request.name,
            table_description=request.description,
            columns=columns
        )
        
        # Create add table request
        add_table_request = AddTableRequest(
            dataset_id="api_dataset",
            schema=schema_input
        )
        
        # Create workflow service instance
        workflow_service = ProjectWorkflowService(
            user_id="api_user",
            session_id=f"semantic_{request.project_id or 'default'}"
        )
        
        # Generate semantic recommendations using workflow service
        recommendations = await workflow_service.get_recommendations(
            add_table_request, 
            project_context,
            recommendation_types=["semantic"]
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error in get_semantic_recommendations endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate semantic recommendations: {str(e)}"
        )

@router.post("/relationships", response_model=Dict[str, Any])
async def get_relationship_recommendations(request: ComprehensiveRecommendationRequest):
    """
    Generate relationship recommendations for a table structure
    """
    try:
        # Create project context for the request
        project_context = ProjectContext(
            project_id=request.project_id or "default_project",
            project_name=request.project_name or f"Project for {request.name}",
            business_domain=request.business_domain,
            purpose=f"Generate relationship recommendations for {request.name}",
            target_users=["Data Analysts", "Business Users"],
            key_business_concepts=["Data Analysis", "Business Intelligence"],
            data_sources=["User Input"],
            compliance_requirements=[]
        )
        
        # Convert columns to the format expected by SchemaInput
        columns = []
        for col in request.columns:
            column_data = {
                "name": col.name,
                "display_name": col.display_name or col.name,
                "description": col.description,
                "data_type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "is_nullable": col.is_nullable,
                "is_foreign_key": col.is_foreign_key,
                "usage_type": col.usage_type
            }
            columns.append(column_data)
        
        # Create schema input
        schema_input = SchemaInput(
            table_name=request.name,
            table_description=request.description,
            columns=columns
        )
        
        # Create add table request
        add_table_request = AddTableRequest(
            dataset_id="api_dataset",
            schema=schema_input
        )
        
        # Create workflow service instance
        workflow_service = ProjectWorkflowService(
            user_id="api_user",
            session_id=f"relationships_{request.project_id or 'default'}"
        )
        
        # Generate relationship recommendations using workflow service
        recommendations = await workflow_service.get_recommendations(
            add_table_request, 
            project_context,
            recommendation_types=["relationships"]
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error in get_relationship_recommendations endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate relationship recommendations: {str(e)}"
        )

@router.post("/optimization", response_model=Dict[str, Any])
async def get_optimization_recommendations(request: ComprehensiveRecommendationRequest):
    """
    Generate optimization recommendations for a table structure
    """
    try:
        # Create project context for the request
        project_context = ProjectContext(
            project_id=request.project_id or "default_project",
            project_name=request.project_name or f"Project for {request.name}",
            business_domain=request.business_domain,
            purpose=f"Generate optimization recommendations for {request.name}",
            target_users=["Data Analysts", "Developers"],
            key_business_concepts=["Performance", "Optimization"],
            data_sources=["User Input"],
            compliance_requirements=[]
        )
        
        # Convert columns to the format expected by SchemaInput
        columns = []
        for col in request.columns:
            column_data = {
                "name": col.name,
                "display_name": col.display_name or col.name,
                "description": col.description,
                "data_type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "is_nullable": col.is_nullable,
                "is_foreign_key": col.is_foreign_key,
                "usage_type": col.usage_type
            }
            columns.append(column_data)
        
        # Create schema input
        schema_input = SchemaInput(
            table_name=request.name,
            table_description=request.description,
            columns=columns
        )
        
        # Create add table request
        add_table_request = AddTableRequest(
            dataset_id="api_dataset",
            schema=schema_input
        )
        
        # Create workflow service instance
        workflow_service = ProjectWorkflowService(
            user_id="api_user",
            session_id=f"optimization_{request.project_id or 'default'}"
        )
        
        # Generate optimization recommendations using workflow service
        recommendations = await workflow_service.get_recommendations(
            add_table_request, 
            project_context,
            recommendation_types=["optimization"]
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error in get_optimization_recommendations endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate optimization recommendations: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for comprehensive recommendations service"""
    return {"status": "healthy", "service": "comprehensive_recommendations"} 