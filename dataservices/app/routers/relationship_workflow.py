"""
Relationship Workflow Management Router
Provides endpoints for managing relationships in the domain workflow step

This router handles the relationship management workflow step that occurs after table creation,
allowing users to get LLM-generated relationship recommendations and add custom relationships
for creating the MDL schema.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
from uuid import UUID

from app.service.project_workflow_service import DomainWorkflowService
from app.service.models import DomainContext
from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow/relationships", tags=["relationship_workflow"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RelationshipWorkflowRequest(BaseModel):
    """Request for relationship workflow operations"""
    session_id: Optional[str] = None
    domain_id: str = Field(..., description="Domain ID for the workflow")
    domain_name: Optional[str] = None
    business_domain: Optional[str] = "General"

class CustomRelationshipRequest(BaseModel):
    """Request for adding a custom relationship"""
    from_table: str = Field(..., description="Source table name")
    to_table: str = Field(..., description="Target table name")
    relationship_type: str = Field(..., description="Type of relationship (one_to_one, one_to_many, many_to_one, many_to_many)")
    from_column: Optional[str] = Field(None, description="Source column name")
    to_column: Optional[str] = Field(None, description="Target column name")
    name: Optional[str] = Field(None, description="Custom name for the relationship")
    description: Optional[str] = Field(None, description="Description of the relationship")
    confidence_score: Optional[float] = Field(1.0, description="Confidence score (0.0-1.0)")
    reasoning: Optional[str] = Field(None, description="Reasoning for the relationship")
    user_notes: Optional[str] = Field(None, description="User notes about the relationship")
    business_justification: Optional[str] = Field(None, description="Business justification for the relationship")
    implementation_notes: Optional[str] = Field(None, description="Implementation notes")

class RelationshipUpdateRequest(BaseModel):
    """Request for updating an existing relationship"""
    relationship_id: str = Field(..., description="ID of the relationship to update")
    updates: Dict[str, Any] = Field(..., description="Fields to update")

class RelationshipWorkflowResponse(BaseModel):
    """Response for relationship workflow operations"""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ============================================================================
# WORKFLOW ENDPOINTS
# ============================================================================

@router.post("/recommendations", response_model=RelationshipWorkflowResponse)
async def generate_relationship_recommendations(
    request: RelationshipWorkflowRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Generate comprehensive relationship recommendations for all tables in the workflow
    
    This endpoint uses the existing RelationshipRecommendation service to analyze all tables
    in the workflow and generate relationship recommendations between them.
    
    This is the main workflow step that should be called after all tables have been added.
    """
    try:
        # Create domain context
        domain_context = DomainContext(
            domain_id=request.domain_id,
            domain_name=request.domain_name or f"Domain {request.domain_id}",
            business_domain=request.business_domain,
            purpose="Generate relationship recommendations for workflow tables",
            target_users=["Data Analysts", "Business Users", "Data Engineers"],
            key_business_concepts=["Data Modeling", "Business Intelligence", "Data Relationships"],
            data_sources=["Workflow Tables"],
            compliance_requirements=[]
        )
        
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=request.session_id
        )
        
        # Generate comprehensive relationship recommendations using existing service
        recommendations = await workflow_service.get_comprehensive_relationship_recommendations(domain_context)
        
        if recommendations.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=recommendations.get("error", "Failed to generate recommendations")
            )
        
        return RelationshipWorkflowResponse(
            status="success",
            message="Successfully generated relationship recommendations using existing service",
            data=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error generating relationship recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate relationship recommendations: {str(e)}"
        )

@router.post("/custom", response_model=RelationshipWorkflowResponse)
async def add_custom_relationship(
    request: CustomRelationshipRequest,
    workflow_request: RelationshipWorkflowRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Add a custom relationship to the workflow
    
    This allows users to manually define relationships that may not have been
    automatically detected by the LLM analysis.
    """
    try:
        # Create domain context
        domain_context = DomainContext(
            domain_id=workflow_request.domain_id,
            domain_name=workflow_request.domain_name or f"Domain {workflow_request.domain_id}",
            business_domain=workflow_request.business_domain,
            purpose="Add custom relationship to workflow",
            target_users=["Data Analysts", "Business Users", "Data Engineers"],
            key_business_concepts=["Data Modeling", "Business Intelligence", "Data Relationships"],
            data_sources=["User Input"],
            compliance_requirements=[]
        )
        
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=workflow_request.session_id
        )
        
        # Convert request to relationship data
        relationship_data = {
            "from_table": request.from_table,
            "to_table": request.to_table,
            "relationship_type": request.relationship_type,
            "from_column": request.from_column,
            "to_column": request.to_column,
            "name": request.name,
            "description": request.description,
            "confidence_score": request.confidence_score,
            "reasoning": request.reasoning,
            "user_notes": request.user_notes,
            "business_justification": request.business_justification,
            "implementation_notes": request.implementation_notes
        }
        
        # Add custom relationship
        result = await workflow_service.add_custom_relationship(relationship_data, domain_context)
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to add custom relationship")
            )
        
        return RelationshipWorkflowResponse(
            status="success",
            message=result.get("message", "Successfully added custom relationship"),
            data=result.get("relationship")
        )
        
    except Exception as e:
        logger.error(f"Error adding custom relationship: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add custom relationship: {str(e)}"
        )

@router.get("/workflow", response_model=RelationshipWorkflowResponse)
async def get_workflow_relationships(
    domain_id: str,
    session_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """
    Get all relationships currently defined in the workflow
    
    This provides a comprehensive view of the current relationship state
    in the workflow, including both LLM recommendations and custom relationships.
    """
    try:
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=session_id
        )
        
        # Get workflow relationships
        result = await workflow_service.get_workflow_relationships()
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get workflow relationships")
            )
        
        return RelationshipWorkflowResponse(
            status="success",
            message="Successfully retrieved workflow relationships",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error getting workflow relationships: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow relationships: {str(e)}"
        )

@router.put("/update", response_model=RelationshipWorkflowResponse)
async def update_relationship(
    request: RelationshipUpdateRequest,
    workflow_request: RelationshipWorkflowRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Update an existing relationship in the workflow
    
    This allows users to modify relationship details such as description,
    confidence score, or other metadata.
    """
    try:
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=workflow_request.session_id
        )
        
        # Update relationship
        result = await workflow_service.update_relationship(
            request.relationship_id,
            request.updates
        )
        
        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Relationship {request.relationship_id} not found"
            )
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update relationship")
            )
        
        return RelationshipWorkflowResponse(
            status="success",
            message=result.get("message", "Successfully updated relationship"),
            data=result.get("relationship")
        )
        
    except Exception as e:
        logger.error(f"Error updating relationship: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update relationship: {str(e)}"
        )

@router.delete("/{relationship_id}", response_model=RelationshipWorkflowResponse)
async def remove_relationship(
    relationship_id: str,
    domain_id: str,
    session_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """
    Remove a relationship from the workflow
    
    This allows users to delete relationships that are no longer needed
    or were added by mistake.
    """
    try:
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=session_id
        )
        
        # Remove relationship
        result = await workflow_service.remove_relationship(relationship_id)
        
        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Relationship {relationship_id} not found"
            )
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to remove relationship")
            )
        
        return RelationshipWorkflowResponse(
            status="success",
            message=result.get("message", "Successfully removed relationship")
        )
        
    except Exception as e:
        logger.error(f"Error removing relationship: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove relationship: {str(e)}"
        )

@router.get("/status/{domain_id}", response_model=RelationshipWorkflowResponse)
async def get_relationship_workflow_status(
    domain_id: str,
    session_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """
    Get the current status of the relationship workflow step
    
    This provides information about the progress of the relationship
    workflow step, including counts of tables, relationships, and
    whether recommendations have been generated.
    """
    try:
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=session_id
        )
        
        # Get workflow state
        state = workflow_service.get_workflow_state()
        
        # Extract relevant information
        tables = state.get("tables", [])
        relationships = state.get("relationships", [])
        recommendations = state.get("relationship_recommendations", {})
        
        status_data = {
            "domain_id": domain_id,
            "workflow_progress": {
                "tables_added": len(tables),
                "relationships_defined": len(relationships),
                "recommendations_generated": bool(recommendations),
                "workflow_step": "relationship_management"
            },
            "summary": {
                "total_tables": len(tables),
                "total_relationships": len(relationships),
                "recommendations_available": bool(recommendations)
            },
            "next_steps": []
        }
        
        # Determine next steps based on current state
        if not tables:
            status_data["next_steps"].append("Add tables to the workflow first")
        elif not recommendations:
            status_data["next_steps"].append("Generate relationship recommendations")
        elif not relationships:
            status_data["next_steps"].append("Review and add relationships based on recommendations")
        else:
            status_data["next_steps"].append("Review relationships and proceed to next workflow step")
            status_data["next_steps"].append("Consider committing workflow to database")
        
        return RelationshipWorkflowResponse(
            status="success",
            message="Successfully retrieved workflow status",
            data=status_data
        )
        
    except Exception as e:
        logger.error(f"Error getting workflow status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow status: {str(e)}"
        )

@router.post("/validate/{domain_id}", response_model=RelationshipWorkflowResponse)
async def validate_relationship_workflow(
    domain_id: str,
    session_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """
    Validate the relationship workflow step
    
    This performs validation checks on the relationships defined in the workflow,
    ensuring they are properly configured for MDL schema generation.
    """
    try:
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=session_id
        )
        
        # Get workflow state
        state = workflow_service.get_workflow_state()
        tables = state.get("tables", [])
        relationships = state.get("relationships", [])
        recommendations = state.get("relationship_recommendations", {})
        
        # Perform validation checks
        validation_results = {
            "domain_id": domain_id,
            "validation_passed": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        # Check if tables exist
        if not tables:
            validation_results["validation_passed"] = False
            validation_results["errors"].append("No tables defined in workflow")
        
        # Check if recommendations were generated
        if not recommendations:
            validation_results["warnings"].append("No relationship recommendations generated")
            validation_results["recommendations"].append("Generate relationship recommendations first")
        
        # Check relationship validity
        if relationships:
            table_names = [t.name if hasattr(t, 'name') else t.get('name', '') for t in tables]
            
            for rel in relationships:
                from_table = rel.get("from_table", "")
                to_table = rel.get("to_table", "")
                
                # Check if referenced tables exist
                if from_table not in table_names:
                    validation_results["errors"].append(f"Relationship references non-existent table: {from_table}")
                    validation_results["validation_passed"] = False
                
                if to_table not in table_names:
                    validation_results["errors"].append(f"Relationship references non-existent table: {to_table}")
                    validation_results["validation_passed"] = False
                
                # Check relationship type validity
                rel_type = rel.get("relationship_type", "")
                valid_types = ["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
                if rel_type not in valid_types:
                    validation_results["errors"].append(f"Invalid relationship type: {rel_type}")
                    validation_results["validation_passed"] = False
        
        # Generate summary
        if validation_results["validation_passed"]:
            validation_results["summary"] = f"Relationship workflow validation passed with {len(relationships)} relationships defined"
        else:
            validation_results["summary"] = f"Relationship workflow validation failed with {len(validation_results['errors'])} errors"
        
        return RelationshipWorkflowResponse(
            status="success",
            message="Validation completed",
            data=validation_results
        )
        
    except Exception as e:
        logger.error(f"Error validating workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate workflow: {str(e)}"
        )

@router.post("/manage", response_model=RelationshipWorkflowResponse)
async def manage_relationships_workflow(
    request: RelationshipWorkflowRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Complete relationship workflow management endpoint
    
    This endpoint provides a comprehensive workflow for managing relationships:
    1. Generates LLM recommendations if not already available
    2. Returns current relationships and recommendations
    3. Allows for relationship management operations
    
    This is the main endpoint users should call to manage the relationship workflow step.
    """
    try:
        # Create domain context
        domain_context = DomainContext(
            domain_id=request.domain_id,
            domain_name=request.domain_name or f"Domain {request.domain_id}",
            business_domain=request.business_domain,
            purpose="Manage relationships in workflow",
            target_users=["Data Analysts", "Business Users", "Data Engineers"],
            key_business_concepts=["Data Modeling", "Business Intelligence", "Data Relationships"],
            data_sources=["Workflow Tables"],
            compliance_requirements=[]
        )
        
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=request.session_id
        )
        
        # Get current workflow state
        current_state = await workflow_service.get_workflow_relationships()
        
        # If no recommendations exist, generate them
        if not current_state.get("data", {}).get("recommendations"):
            logger.info("No relationship recommendations found, generating new ones...")
            recommendations = await workflow_service.get_comprehensive_relationship_recommendations(domain_context)
            
            if recommendations.get("status") == "error":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=recommendations.get("error", "Failed to generate recommendations")
                )
            
            # Update current state with new recommendations
            current_state["data"]["recommendations"] = recommendations
        
        # Get updated workflow state
        updated_state = await workflow_service.get_workflow_relationships()
        
        # Prepare comprehensive response
        workflow_data = {
            "domain_id": request.domain_id,
            "workflow_status": "ready_for_management",
            "current_state": updated_state.get("data", {}),
            "available_actions": [
                "generate_recommendations",
                "add_custom_relationship", 
                "update_relationship",
                "remove_relationship",
                "validate_workflow",
                "commit_workflow"
            ],
            "next_steps": [
                "Review LLM-generated recommendations",
                "Add custom relationships if needed",
                "Update relationship details",
                "Validate all relationships",
                "Commit workflow when ready"
            ]
        }
        
        return RelationshipWorkflowResponse(
            status="success",
            message="Relationship workflow ready for management",
            data=workflow_data
        )
        
    except Exception as e:
        logger.error(f"Error managing relationships workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to manage relationships workflow: {str(e)}"
        )

@router.post("/batch-operations", response_model=RelationshipWorkflowResponse)
async def batch_relationship_operations(
    operations: List[Dict[str, Any]],
    workflow_request: RelationshipWorkflowRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Perform multiple relationship operations in a single request
    
    This allows users to perform multiple relationship operations (add, update, delete)
    in a single API call for better efficiency.
    
    Operations format:
    [
        {"action": "add", "data": {...}},
        {"action": "update", "relationship_id": "...", "data": {...}},
        {"action": "delete", "relationship_id": "..."}
    ]
    """
    try:
        # Create domain context
        domain_context = DomainContext(
            domain_id=workflow_request.domain_id,
            domain_name=workflow_request.domain_name or f"Domain {workflow_request.domain_id}",
            business_domain=workflow_request.business_domain,
            purpose="Batch relationship operations",
            target_users=["Data Analysts", "Business Users", "Data Engineers"],
            key_business_concepts=["Data Modeling", "Business Intelligence", "Data Relationships"],
            data_sources=["User Input"],
            compliance_requirements=[]
        )
        
        # Create workflow service instance
        workflow_service = DomainWorkflowService(
            user_id=current_user,
            session_id=workflow_request.session_id
        )
        
        results = []
        errors = []
        
        # Process each operation
        for i, operation in enumerate(operations):
            try:
                action = operation.get("action", "").lower()
                
                if action == "add":
                    # Add new relationship
                    result = await workflow_service.add_custom_relationship(
                        operation.get("data", {}), domain_context
                    )
                    results.append({"operation": i, "action": "add", "result": result})
                    
                elif action == "update":
                    # Update existing relationship
                    relationship_id = operation.get("relationship_id")
                    updates = operation.get("data", {})
                    
                    if not relationship_id:
                        errors.append({"operation": i, "error": "Missing relationship_id for update"})
                        continue
                    
                    result = await workflow_service.update_relationship(relationship_id, updates)
                    results.append({"operation": i, "action": "update", "result": result})
                    
                elif action == "delete":
                    # Delete relationship
                    relationship_id = operation.get("relationship_id")
                    
                    if not relationship_id:
                        errors.append({"operation": i, "error": "Missing relationship_id for delete"})
                        continue
                    
                    result = await workflow_service.remove_relationship(relationship_id)
                    results.append({"operation": i, "action": "delete", "result": result})
                    
                else:
                    errors.append({"operation": i, "error": f"Unknown action: {action}"})
                    
            except Exception as e:
                errors.append({"operation": i, "error": str(e)})
        
        # Get final workflow state
        final_state = await workflow_service.get_workflow_relationships()
        
        batch_result = {
            "operations_processed": len(operations),
            "successful_operations": len(results),
            "failed_operations": len(errors),
            "results": results,
            "errors": errors,
            "final_workflow_state": final_state.get("data", {}),
            "summary": {
                "total_relationships": final_state.get("data", {}).get("summary", {}).get("total_relationships", 0),
                "recommendations_available": bool(final_state.get("data", {}).get("recommendations"))
            }
        }
        
        if errors:
            return RelationshipWorkflowResponse(
                status="partial_success",
                message=f"Batch operations completed with {len(errors)} errors",
                data=batch_result
            )
        else:
            return RelationshipWorkflowResponse(
                status="success",
                message="All batch operations completed successfully",
                data=batch_result
            )
        
    except Exception as e:
        logger.error(f"Error in batch operations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch operations: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for relationship workflow service"""
    return {"status": "healthy", "service": "relationship_workflow"}
