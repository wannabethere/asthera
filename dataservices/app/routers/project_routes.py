
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, Depends, BackgroundTasks, File, UploadFile,APIRouter
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from app.service.database import get_db
from app.config import ServiceConfig
from app.service.dbservice import ServiceFactory
from app.service.projectManagerService import ProjectManager
from app.service.models import CreateProjectRequest,ProjectResponse,DefinitionType,UserExample,ProjectContext
from app.service.database import get_db
import traceback
import logging as logger
from app.service.schema_manager_service import SchemaDocumentationService
import json
from app.service.dbmodels import Project, Table, Column, CalculatedColumn, SQLFunction, KnowledgeBase, ProjectVersionHistory, CalculatedColumn, Example
# ============================================================================
# API MODELS
# ============================================================================



class CreateDefinitionRequest(BaseModel):
    """Request model for creating definitions"""
    
    definition_type: str = Field(..., description="Type: metric, view, or calculated_column")
    name: str = Field(..., description="Technical name for the definition")
    description: str = Field(..., description="Business description")
    sql: str = Field(None, description="Optional SQL code")
    additional_context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    user_id: str = Field(default="api_user", description="User creating the definition")


class DefinitionResponse(BaseModel):
    """Response model for definition creation"""
    
    success: bool
    entity_id: str|None = None
    definition: Dict[str, Any]|None = None
    table_matches: str = None
    validation_errors: List[str] = []
    context_used: Dict[str, Any] = {}
    error: str = None


class BatchCreateRequest(BaseModel):
    """Request model for batch creation"""
    
    definitions: List[CreateDefinitionRequest]
    project_id: str


class ProjectSummaryResponse(BaseModel):
    """Response model for project summary"""
    
    project_id: str
    display_name: str
    current_version: str
    total_metrics: int
    total_views: int
    total_calculated_columns: int
    recent_changes: List[Dict[str, Any]]

class ProjectContextRequest(BaseModel):
    """Request model for project context"""
    
    business_domain: str = Field(..., description="Business domain (e.g., 'training_management', 'sales_analytics')")
    purpose: str = Field(..., description="Project purpose and business goals")
    target_users: List[str] = Field(..., description="Target user types (e.g., ['analysts', 'managers', 'executives'])")
    key_business_concepts: List[str] = Field(..., description="Key business concepts and terminology")
    data_sources: Optional[List[str]] = Field(None, description="Data source systems")
    compliance_requirements: Optional[List[str]] = Field(None, description="Compliance requirements")


class BatchDocumentRequest(BaseModel):
    """Request model for batch documentation"""
    
    project_context: ProjectContextRequest
    table_names: Optional[List[str]] = Field(None, description="Specific tables to document (all if not specified)")
    include_sample_data: bool = Field(False, description="Include sample data in analysis")
    update_database: bool = Field(True, description="Update database with generated documentation")


class DDLDocumentRequest(BaseModel):
    """Request model for DDL documentation"""
    
    ddl_statement: str = Field(..., description="CREATE TABLE DDL statement")
    project_context: ProjectContextRequest
    create_table: bool = Field(False, description="Create the table in the database")
    update_database: bool = Field(True, description="Update database with documentation")


class SchemaJSONDocumentRequest(BaseModel):
    """Request model for JSON schema documentation"""
    
    schema_definition: Dict[str, Any] = Field(..., description="JSON schema definition")
    project_context: ProjectContextRequest
    create_table: bool = Field(False, description="Create the table in the database")
    update_database: bool = Field(True, description="Update database with documentation")


class DocumentationSummaryResponse(BaseModel):
    """Response model for documentation summary"""
    
    project_id: str
    total_tables_documented: int
    total_columns_documented: int
    documentation_quality_score: float
    business_concepts_identified: List[str]
    privacy_classifications: Dict[str, int]
    usage_type_distribution: Dict[str, int]
    recommendations: List[str]

# ============================================================================
# API MODELS FOR SCHEMA DOCUMENTATION
# ============================================================================

class DocumentSchemaRequest(BaseModel):
    """Request model for schema documentation"""
    
    # Schema source (one of these)
    ddl_statement: Optional[str] = None
    table_name: Optional[str] = None
    schema_json: Optional[Dict[str, Any]] = None
    
    # Project context
    business_domain: str = Field(..., description="Business domain (e.g., 'training_management')")
    purpose: str = Field(..., description="Project purpose and goals")
    target_users: List[str] = Field(..., description="Target user types")
    key_business_concepts: List[str] = Field(..., description="Key business concepts")
    data_sources: Optional[List[str]] = None
    compliance_requirements: Optional[List[str]] = None
    
    # Options
    include_sample_data: bool = False
    update_database: bool = True


class DocumentedColumnResponse(BaseModel):
    """Response model for documented column"""
    
    column_name: str
    display_name: str
    description: str
    business_description: str
    usage_type: str
    data_type: str
    example_values: List[str]
    business_rules: List[str]
    data_quality_checks: List[str]
    related_concepts: List[str]
    privacy_classification: str
    aggregation_suggestions: List[str]
    filtering_suggestions: List[str]
    metadata: Dict[str, Any]


class DocumentedTableResponse(BaseModel):
    """Response model for documented table"""
    
    table_name: str
    display_name: str
    description: str
    business_purpose: str
    primary_use_cases: List[str]
    key_relationships: List[str]
    columns: List[DocumentedColumnResponse]
    data_lineage: Optional[str]
    update_frequency: str
    data_retention: Optional[str]
    access_patterns: List[str]
    performance_considerations: List[str]
    
# ============================================================================
# API ENDPOINTS
# ============================================================================

router = APIRouter()

@router.post("/projects/createProject", response_model=ProjectResponse)
async def create_projects(project: CreateProjectRequest, session: Session = Depends(get_db)):
    """Create a new project"""
    try:
        projService = ProjectManager(session)
        return projService.create_project(project)
    except Exception as e:
        # --- THIS IS THE CRITICAL DIAGNOSTIC CHANGE ---
        print("--- !!! AN EXCEPTION OCCURRED !!! ---")
        print(f"Python Exception Type: {type(e)}")
        print(f"Python Exception repr: {repr(e)}")
        print("--- FULL TRACEBACK ---")
        
        # This will print the complete error stack trace to your console
        traceback.print_exc() 
        
        print("--- END TRACEBACK ---")
        
        # We raise a generic error to the client, but the real error is in our logs.
        raise HTTPException(status_code=500, detail="An internal error occurred. Check server logs for full traceback.")


@router.post("/projects/{project_id}/definitions", response_model=DefinitionResponse)
async def create_definition(
    project_id: str,
    request: CreateDefinitionRequest,
    background_tasks: BackgroundTasks
):
    """Create a new definition using LLM"""
    try:
        # Get service
        config = ServiceConfig.from_env()
        service_factory = ServiceFactory(config)
        service = await service_factory.get_service(project_id)
        
        # Create user example
        definition_type = DefinitionType(request.definition_type.lower())
        user_example = UserExample(
            definition_type=definition_type,
            name=request.name,
            description=request.description,
            sql=request.sql,
            additional_context=request.additional_context,
            user_id=request.user_id
        )
        
        # Generate definition

        result = await service.create_definition_from_example(user_example)
        print("Results in create_definition : ", result)
        # Schedule cleanup
        background_tasks.add_task(service_factory.cleanup_service, project_id)
        
        return DefinitionResponse(**result)
        
    except Exception as e:
        # --- THIS IS THE CRITICAL DIAGNOSTIC CHANGE ---
        print("--- !!! AN EXCEPTION OCCURRED !!! ---")
        print(f"Python Exception Type: {type(e)}")
        print(f"Python Exception repr: {repr(e)}")
        print("--- FULL TRACEBACK ---")
        
        # This will print the complete error stack trace to your console
        traceback.print_exc() 
        
        print("--- END TRACEBACK ---")
        
        # We raise a generic error to the client, but the real error is in our logs.
        raise HTTPException(status_code=500, detail="An internal error occurred. Check server logs for full traceback.")


@router.post("/projects/{project_id}/definitions/batch")
async def batch_create_definitions(
    project_id: str,
    request: BatchCreateRequest,
    background_tasks: BackgroundTasks
):
    """Create multiple definitions in batch"""
    try:
        config = ServiceConfig.from_env()
        service_factory = ServiceFactory(config)
        service = await service_factory.get_service(project_id)
        
        # Convert requests to user examples
        examples = [
            UserExample(
                definition_type=DefinitionType(req.definition_type.lower()),
                name=req.name,
                description=req.description,
                sql=req.sql,
                additional_context=req.additional_context,
                user_id=req.user_id
            )
            for req in request.definitions
        ]
        
        # Process batch
        results = await service.batch_create_definitions(examples)
        
        background_tasks.add_task(service_factory.cleanup_service, project_id)
        
        return {
            "total": len(results),
            "successful": len([r for r in results if r["success"]]),
            "failed": len([r for r in results if not r["success"]]),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in batch creation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/summary", response_model=ProjectSummaryResponse)
async def get_project_summary(project_id: str, db: Session = Depends(get_db)):
    """Get project summary with definition counts"""
    try:
        project_manager = ProjectManager(db)
        summary = project_manager.get_project_summary(project_id)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get recent changes
        recent_changes = db.query(Project).filter(
            Project.project_id == project_id
        ).first().version_history[-5:]  # Last 5 changes
        
        return ProjectSummaryResponse(
            project_id=summary["project_id"],
            display_name=summary["display_name"],
            current_version=summary["current_version"],
            total_metrics=summary.get("total_metrics", 0),
            total_views=summary.get("total_views", 0),
            total_calculated_columns=summary.get("total_calculated_columns", 0),
            recent_changes=[
                {
                    "version": change.new_version,
                    "change_type": change.change_type,
                    "entity": change.triggered_by_entity,
                    "timestamp": change.created_at.isoformat()
                }
                for change in recent_changes
            ]
        )
        
    except Exception as e:
        logger.error(f"Error getting project summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/definitions/validate/{entity_id}")
async def validate_definition(project_id: str, entity_id: str):
    """Validate an existing definition"""
    try:
        config = ServiceConfig.from_env()
        service_factory = ServiceFactory(config)
        service = await service_factory.get_service(project_id)
        
        # This would fetch the definition and re-validate it
        # Implementation depends on your specific validation needs
        
        return {"status": "validated", "entity_id": entity_id}
        
    except Exception as e:
        logger.error(f"Error validating definition: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/lock")
async def lock_project_version(
    project_id: str, 
    locked: bool = True, 
    db: Session = Depends(get_db)
):
    """Lock or unlock project version"""
    try:
        project_manager = ProjectManager(db)
        success = project_manager.lock_project_version(
            project_id, locked, "api_user"
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {
            "project_id": project_id,
            "locked": locked,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error locking project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/schema/document-json", response_model=DocumentedTableResponse)
async def document_schema_from_json(
    project_id: str,
    request: SchemaJSONDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Document database schema from JSON definition"""
    try:
        config = ServiceConfig.from_env()
        service = SchemaDocumentationService(
            session=db,
            openai_api_key=config.openai_api_key,
            project_id=project_id
        )
        
        project_context = ProjectContext(
            project_id=project_id,
            project_name=f"Project {project_id}",
            business_domain=request.project_context.business_domain,
            purpose=request.project_context.purpose,
            target_users=request.project_context.target_users,
            key_business_concepts=request.project_context.key_business_concepts,
            data_sources=request.project_context.data_sources,
            compliance_requirements=request.project_context.compliance_requirements
        )
        
        documented_table = await service.document_schema_from_jsons(
            request.schema_definition, project_context
        )
        
        if request.create_table:
            background_tasks.add_task(
                _create_table_from_json, db, request.schema_definition, project_id
            )
        
        if request.update_database:
            background_tasks.add_task(
                service.update_database_with_documentation, documented_table
            )
        
        return _convert_documented_table_to_response(documented_table)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/schema/document-existing/{table_name}", response_model=DocumentedTableResponse)
async def document_existing_table(
    project_id: str,
    table_name: str,
    project_context: ProjectContextRequest,
    include_sample_data: bool = False,
    update_database: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Document existing table in database"""
    try:
        config = ServiceConfig.from_env()
        service = SchemaDocumentationService(
            session=db,
            openai_api_key=config.openai_api_key,
            project_id=project_id
        )
        
        context = ProjectContext(
            project_id=project_id,
            project_name=f"Project {project_id}",
            business_domain=project_context.business_domain,
            purpose=project_context.purpose,
            target_users=project_context.target_users,
            key_business_concepts=project_context.key_business_concepts,
            data_sources=project_context.data_sources,
            compliance_requirements=project_context.compliance_requirements
        )
        
        documented_table = await service.document_existing_table(
            table_name, context, include_sample_data
        )
        
        if update_database:
            background_tasks.add_task(
                service.update_database_with_documentation, documented_table
            )
        
        return _convert_documented_table_to_response(documented_table)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/schema/batch-document")
async def batch_document_tables(
    project_id: str,
    request: BatchDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Document multiple tables in batch"""
    try:
        config = ServiceConfig.from_env()
        service = SchemaDocumentationService(
            session=db,
            openai_api_key=config.openai_api_key,
            project_id=project_id
        )
        
        project_context = ProjectContext(
            project_id=project_id,
            project_name=f"Project {project_id}",
            business_domain=request.project_context.business_domain,
            purpose=request.project_context.purpose,
            target_users=request.project_context.target_users,
            key_business_concepts=request.project_context.key_business_concepts,
            data_sources=request.project_context.data_sources,
            compliance_requirements=request.project_context.compliance_requirements
        )
        
        documented_tables = await service.batch_document_project_tables(
            project_context, request.table_names
        )
        
        # Update database with all documentation
        if request.update_database:
            for documented_table in documented_tables:
                background_tasks.add_task(
                    service.update_database_with_documentation, documented_table
                )
        
        # Convert to response format
        response_tables = [
            _convert_documented_table_to_response(table) 
            for table in documented_tables
        ]
        
        # Generate summary
        summary = _generate_documentation_summary(project_id, documented_tables)
        
        return {
            "summary": summary,
            "documented_tables": response_tables,
            "total_tables": len(response_tables),
            "processing_time": "async"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/schema/upload-and-document")
async def upload_and_document_schema(
    project_id: str,
    file: UploadFile = File(...),
    business_domain: str = "general",
    purpose: str = "data_analysis",
    target_users: str = "analysts,managers",  # Comma-separated
    key_concepts: str = "data,analysis,reporting",  # Comma-separated
    db: Session = Depends(get_db)
):
    """Upload schema file (DDL or JSON) and generate documentation"""
    try:
        # Read uploaded file
        content = await file.read()
        
        # Parse content based on file type
        if file.filename.endswith(('.sql', '.ddl')):
            # DDL file
            ddl_statement = content.decode('utf-8')
            
            request = DDLDocumentRequest(
                ddl_statement=ddl_statement,
                project_context=ProjectContextRequest(
                    business_domain=business_domain,
                    purpose=purpose,
                    target_users=target_users.split(','),
                    key_business_concepts=key_concepts.split(',')
                )
            )
            
            return await document_schema_from_ddl(project_id, request, BackgroundTasks(), db)
            
        elif file.filename.endswith('.json'):
            # JSON schema file
            schema_json = json.loads(content.decode('utf-8'))
            
            request = SchemaJSONDocumentRequest(
                schema_definition=schema_json,
                project_context=ProjectContextRequest(
                    business_domain=business_domain,
                    purpose=purpose,
                    target_users=target_users.split(','),
                    key_business_concepts=key_concepts.split(',')
                )
            )
            
            return await document_schema_from_json(project_id, request, BackgroundTasks(), db)
            
        else:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Please upload .sql, .ddl, or .json files"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/schema/documentation-summary", response_model=DocumentationSummaryResponse)
async def get_documentation_summary(project_id: str, db: Session = Depends(get_db)):
    """Get summary of project documentation status"""
    try:
        # Get project tables and their documentation status
        tables = db.query(Table).filter(Table.project_id == project_id).all()
        
        if not tables:
            raise HTTPException(status_code=404, detail="Project not found or has no tables")
        
        total_tables = len(tables)
        total_columns = sum(len(table.columns) for table in tables)
        
        # Count documented vs undocumented
        documented_tables = sum(1 for table in tables if table.description)
        documented_columns = sum(
            1 for table in tables 
            for column in table.columns 
            if column.description
        )
        
        # Analyze usage types and privacy classifications
        usage_types = {}
        privacy_classifications = {}
        business_concepts = set()
        
        for table in tables:
            for column in table.columns:
                if column.usage_type:
                    usage_types[column.usage_type] = usage_types.get(column.usage_type, 0) + 1
                
                if column.metadata:
                    privacy = column.metadata.get('privacy_classification', 'unknown')
                    privacy_classifications[privacy] = privacy_classifications.get(privacy, 0) + 1
                    
                    concepts = column.metadata.get('related_concepts', [])
                    business_concepts.update(concepts)
        
        # Calculate quality score
        documentation_quality = (documented_columns / total_columns) * 100 if total_columns > 0 else 0
        
        # Generate recommendations
        recommendations = []
        if documentation_quality < 50:
            recommendations.append("Consider running batch documentation to improve coverage")
        if 'unknown' in privacy_classifications:
            recommendations.append("Review privacy classifications for data governance")
        if len(usage_types) < 3:
            recommendations.append("Define more specific usage types for better analysis")
        
        return DocumentationSummaryResponse(
            project_id=project_id,
            total_tables_documented=documented_tables,
            total_columns_documented=documented_columns,
            documentation_quality_score=round(documentation_quality, 2),
            business_concepts_identified=list(business_concepts),
            privacy_classifications=privacy_classifications,
            usage_type_distribution=usage_types,
            recommendations=recommendations
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/schema/examples")
async def get_schema_documentation_examples(project_id: str):
    """Get example schema documentation requests for the project domain"""
    try:
        # Get predefined examples
        project_context, ddl_statement, schema_json = (
            SchemaDocumentationExamples.cornerstone_training_example()
        )
        
        return {
            "examples": {
                "ddl_request": {
                    "description": "Document a table from DDL statement",
                    "example": {
                        "ddl_statement": ddl_statement,
                        "project_context": {
                            "business_domain": project_context.business_domain,
                            "purpose": project_context.purpose,
                            "target_users": project_context.target_users,
                            "key_business_concepts": project_context.key_business_concepts
                        }
                    }
                },
                "json_request": {
                    "description": "Document a table from JSON schema with sample data",
                    "example": {
                        "schema_definition": schema_json,
                        "project_context": {
                            "business_domain": project_context.business_domain,
                            "purpose": project_context.purpose,
                            "target_users": project_context.target_users,
                            "key_business_concepts": project_context.key_business_concepts
                        }
                    }
                },
                "batch_request": {
                    "description": "Document multiple tables in the project",
                    "example": {
                        "project_context": {
                            "business_domain": project_context.business_domain,
                            "purpose": project_context.purpose,
                            "target_users": project_context.target_users,
                            "key_business_concepts": project_context.key_business_concepts
                        },
                        "table_names": ["csod_training_records", "employee_data"],
                        "include_sample_data": True
                    }
                }
            },
            "common_domains": [
                "training_management", "sales_analytics", "financial_reporting",
                "customer_analytics", "operational_metrics", "compliance_tracking"
            ],
            "sample_target_users": [
                "Business Analysts", "Data Scientists", "Managers", "Executives",
                "Compliance Officers", "Training Coordinators", "Financial Analysts"
            ],
            "sample_business_concepts": [
                "performance_tracking", "compliance", "revenue_analysis", "customer_satisfaction",
                "operational_efficiency", "risk_management", "training_effectiveness"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))