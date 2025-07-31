"""
Semantics Description API Router
Provides endpoints for generating semantic descriptions of table structures
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

from app.service.project_workflow_service import DomainWorkflowService
from app.service.models import AddTableRequest, SchemaInput, DomainContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/semantics", tags=["semantics"])

class TableColumnRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    is_primary_key: bool = False
    is_nullable: bool = True
    usage_type: Optional[str] = None

class TableDescriptionRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    columns: List[TableColumnRequest]
    domain_id: Optional[str] = None
    business_domain: Optional[str] = "General"
    domain_name: Optional[str] = None

class TableDescriptionResponse(BaseModel):
    id: str
    status: str
    response: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

@router.post("/describe-table", response_model=TableDescriptionResponse)
async def describe_table(request: TableDescriptionRequest):
    """
    Generate semantic description for a table structure
    
    This endpoint analyzes the table structure and generates a comprehensive
    semantic description including business context, key columns, and suggested relationships.
    """
    try:
        # Create domain context for the request
        domain_context = DomainContext(
            domain_id=request.domain_id or "default_domain",
            domain_name=request.domain_name or f"Domain for {request.name}",
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
        workflow_service = DomainWorkflowService(
            user_id="api_user",
            session_id=f"semantics_{request.domain_id or 'default'}"
        )
        
        # Generate semantic description using workflow service
        semantic_description = await workflow_service.get_semantic_description_for_table(
            add_table_request, domain_context
        )
        
        # Convert result to response format
        response = TableDescriptionResponse(
            id=f"table_{request.name}_{request.domain_id or 'default'}",
            status="finished",
            response=semantic_description,
            error=None
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in describe_table endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate semantic description: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for semantics service"""
    return {"status": "healthy", "service": "semantics_description"} 