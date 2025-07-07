"""
Relationship Recommendation API Router
Provides endpoints for generating relationship recommendations between tables
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/relationships", tags=["relationships"])

class TableColumnRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    is_primary_key: bool = False
    is_nullable: bool = True
    is_foreign_key: bool = False
    usage_type: Optional[str] = None

class RelationshipRecommendationRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    columns: List[TableColumnRequest]
    project_id: Optional[str] = None
    business_domain: Optional[str] = "General"
    project_name: Optional[str] = None

class RelationshipRecommendationResponse(BaseModel):
    id: str
    status: str
    response: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

@router.post("/recommend", response_model=RelationshipRecommendationResponse)
async def recommend_relationships(request: RelationshipRecommendationRequest):
    """
    Generate relationship recommendations for a table structure
    
    This endpoint analyzes the table structure and suggests potential relationships
    with other tables that could enhance data analysis capabilities.
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
        relationship_recommendations = await workflow_service.get_relationship_recommendation_for_table(
            add_table_request, project_context
        )
        
        # Convert result to response format
        response = RelationshipRecommendationResponse(
            id=f"table_{request.name}_{request.project_id or 'default'}",
            status="finished",
            response=relationship_recommendations,
            error=None
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in recommend_relationships endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate relationship recommendations: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for relationship recommendation service"""
    return {"status": "healthy", "service": "relationship_recommendation"} 