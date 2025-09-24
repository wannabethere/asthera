# unstructured/genieml/dataservices/app/routers/domain_workflow.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.utils.sse import publish_update
from sqlalchemy import select, update, func
from app.core.dependencies import get_async_db_session, get_session_manager
from app.service.models import (
    CreateDomainRequest, DomainContext, AddTableRequest, 
    DomainResponse, TableResponse, MetricCreate, ViewCreate, CalculatedColumnCreate, EnhancedTableResponse, datasetRead, tableRead
)
from app.service.share_permissions import SharePermissions
from app.service.datasource_service import DataRetriever
import traceback
from app.schemas.dbmodels import Domain, Dataset, Table, SQLColumn, Metric, View, CalculatedColumn
from app.service.project_workflow_service import DomainWorkflowService, MetricsService
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.utils.sse import add_subscriber, remove_subscriber
from typing import List, Optional
import logging
from datetime import datetime
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow", tags=["workflow"])
security = HTTPBearer()

def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    return token

def get_session_id(request: Request):
    return request.headers.get("X-Session-Id") or "demo-session"

def get_user_id(request: Request):
    return request.headers.get("X-User-Id") or "demo-user"

from sqlalchemy import text


@router.post("/domain", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def api_create_domain(
    domain_data: CreateDomainRequest, 
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create a new domain in draft status"""
    try:
        # Initialize workflow service first to generate domain ID if needed
        user = await SharePermissions()._validate_user(token)
        workflow_service = DomainWorkflowService(user['id'], session_id)
        
        # Prepare domain data for workflow service
        workflow_domain_data = {
            "display_name": domain_data.display_name,
            "description": domain_data.description,
            "created_by": user['id'],
            "context": domain_data.context.model_dump() if domain_data.context else None
        }
        
        # If domain_id is provided, use it; otherwise let workflow service generate one
        if domain_data.domain_id:
            workflow_domain_data["domain_id"] = domain_data.domain_id
        
        # Create domain in workflow state (this will generate domain_id if not provided)
        workflow_domain = await workflow_service.create_domain(workflow_domain_data)
        
        # Now check if the generated domain_id already exists in database
        domain_id = workflow_domain["domain_id"]
        result = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Domain with ID {domain_data.domain_id} already exists"
            )
        
        # Create domain in draft status
        domain = Domain(
            domain_id=domain_id,
            display_name=domain_data.display_name,
            description=domain_data.description,
            created_by=user['id'],
            status='draft',  # Start as draft
            version_locked=True,  # Lock version during draft phase
            json_metadata=domain_data.context.model_dump(),
            updated_by=user['id']
        )
        db.add(domain)
        await db.commit()
        await db.refresh(domain)
        logger.info(f"Successfully created domain: {domain.domain_id} - {domain.display_name}")
        
        return DomainResponse(
            domain_id=domain.domain_id,
            display_name=domain.display_name,
            description=domain.description,
            created_by=domain.created_by,
            status=domain.status,
            version_string=domain.version_string,
            created_at=domain.created_at,
            is_draft=True if domain.status =='draft' else False,
            updated_at=domain.updated_at,
            context=domain.json_metadata,
            updated_by=domain.updated_by
        )
        
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error creating domain: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create domain: {str(e)}"
        )


@router.get("/summary")
async def get_workflow_summary(
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token)
):
    """Get a summary of the current workflow state"""
    try:
        user = await SharePermissions()._validate_user(token)
        workflow_service = DomainWorkflowService(user['id'], session_id)
        summary = workflow_service.get_workflow_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting workflow summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow summary: {str(e)}"
        )

@router.delete("/clear")
async def clear_workflow(
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token)
):
    """Clear the current workflow state"""
    try:
        user = await SharePermissions()._validate_user(token)
        workflow_service = DomainWorkflowService(user['id'], session_id)
        cleared_state = workflow_service.clear_workflow()
        return {
            "message": "Workflow cleared successfully",
            "cleared_state": cleared_state
        }
    except Exception as e:
        logger.error(f"Error clearing workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear workflow: {str(e)}"
        )



@router.get("/dataset/domain/all")
async def api_get_dataset_domain(
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get a domain by ID"""
    try:
        user = await SharePermissions()._validate_user(token)
        domains = await db.execute(
            select(Domain)
            .where(Domain.created_by == user["id"])
            .where(~Domain.datasets.any())  # NOT having any datasets
        )
        domains = domains.scalars().all()
        return [{"domain_id": domain.domain_id, "display_name": domain.display_name, "description": domain.description, "created_by": domain.created_by, "status": domain.status, "version_string": domain.version_string, "created_at": str(domain.created_at), "is_draft": domain.is_draft, "updated_at": str(domain.updated_at)} for domain in domains]
    except Exception as e:
        logger.error(f"Error getting ")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get domain: {str(e)}"
        )

@router.get("/global/domain/all")
async def api_get_global_domain(
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get a domain by ID"""
    try:
        user = await SharePermissions()._validate_user(token)
        domains = await db.execute(
            select(Domain)
            .where(Domain.created_by == user["id"])
        )
        domains = domains.scalars().all()
        return [{"domain_id": domain.domain_id, "display_name": domain.display_name, "description": domain.description, "created_by": domain.created_by, "status": domain.status, "version_string": domain.version_string, "created_at": str(domain.created_at), "is_draft": domain.is_draft, "updated_at": str(domain.updated_at)} for domain in domains]
    except Exception as e:
        logger.error(f"Error getting ")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get domain: {str(e)}"
        )

@router.post("/dataset", status_code=status.HTTP_201_CREATED)
async def api_add_dataset(
    dataset_data: dict, 
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a dataset to a domain"""
    try:
        user = await SharePermissions()._validate_user(token)
        domain_id = dataset_data.get("domain_id")
        if not domain_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="domain_id is required"
            )
        
        # Check if domain exists and is in draft
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        if domain.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add datasets to draft domains"
            )
        
        # Create dataset
        dataset = Dataset(
            domain_id=domain_id,
            name=dataset_data.get("name"),
            display_name=dataset_data.get("display_name") or dataset_data.get("name"),
            description=dataset_data.get("description"),
            json_metadata=dataset_data.get("metadata", {}),
            connection_id=dataset_data.get("connection_id"),
            created_by=user['id'],
            modified_by=user['id']
        )
        
        db.add(dataset)
        try:
            await db.commit()
            await db.refresh(dataset)
        except Exception as e:
            import traceback
            traceback.print_exc()
        
        print("dataset created")
        # Update workflow service
        workflow_service = DomainWorkflowService(user['id'], session_id)
        await workflow_service.add_dataset({
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "connection_id": dataset.connection_id,
            "display_name": dataset.display_name,
            "description": dataset.description,
            "domain_id": domain_id,
            "created_by": user['id'],
            "modified_by": user['id']
        })
        print("workflow_service")
        
        # Fetch and store sharing permissions after dataset creation
        try:
            await workflow_service.fetch_and_store_sharing_permissions(dataset_data['permissions'],domain_id,token)
            logger.info(f"Sharing permissions fetched and stored for domain {domain_id}")
        except Exception as e:
            logger.warning(f"Failed to fetch sharing permissions: {str(e)}")
            # Continue with dataset creation even if permissions fail
        
        return {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "connection_id": dataset.connection_id,
            "display_name": dataset.display_name,
            "description": dataset.description,
            "domain_id": domain_id
        }
        
    except Exception as e:
        logger.error(f"Error adding dataset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add dataset: {str(e)}"
        )

@router.get("/dataset/all")
async def api_get_all_datasets(
    token: str = Depends(get_token)
):
    """Get all datasets"""
    try:
        result = await SharePermissions().get_user_domains(token)
        return result
        
    except Exception as e:
        logger.error(f"Error getting all datasets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get all datasets: {str(e)}"
        )


@router.get("/dataset/samples/getTablesData")
async def get_sample_data_for_dataset(
   dataset_id: str,
   db: AsyncSession = Depends(get_async_db_session),
   token: str = Depends(get_token)
):
   try:
       user= await SharePermissions()._validate_user(token)
       # Use async query with selectinload for async session
       result = await db.execute(
           select(Dataset).options(selectinload(Dataset.tables)).filter(Dataset.dataset_id == dataset_id)
       )
       dataset = result.scalar_one_or_none()
       
       print(f"dataset {dataset}")
       if not dataset:
           raise ValueError("Dataset Not found")
       
       tables = []
       dataset = datasetRead.model_validate(dataset)
       for table in dataset.tables:
           tables.append(tableRead.model_validate(table).name)
       print("Tables", tables)

       # Await the async DataRetriever method
       tabledata = await DataRetriever(db).get_data_from_connection(
           str(dataset.connection_id), tables
       )
       return tabledata
   except Exception as e:
       print("====Error =====")
       traceback.print_exc()
       print("====Error Ended here ====")
       # Consider returning a proper error response
       raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset/{dataset_id}")
async def api_get_dataset_details(
   dataset_id: str,
   db: AsyncSession = Depends(get_async_db_session),
   token: str = Depends(get_token)
):
   """Get details for a specific dataset, including its domain and tables."""
   try:
       user = await SharePermissions()._validate_user(token)
       # Create a query to select the dataset and pre-load related entities
       stmt = (
           select(Dataset)
           .options(
               selectinload(Dataset.domain),  # Eagerly load the parent domain
               selectinload(Dataset.tables).selectinload(Table.columns).selectinload(SQLColumn.calculated_column),  # Eagerly load tables, columns, and calculated columns
               selectinload(Dataset.tables).selectinload(Table.metrics),  # Eagerly load metrics
               selectinload(Dataset.tables).selectinload(Table.views)  # Eagerly load views
           )
           .where(Dataset.dataset_id == dataset_id)
       )
 
       result = await db.execute(stmt)
       dataset = result.scalar_one_or_none()
 
       if not dataset:
           raise HTTPException(
               status_code=status.HTTP_404_NOT_FOUND,
               detail=f"Dataset with ID {dataset_id} not found"
           )
 
       domain_id = dataset.domain_id
 
       checkPermission = await SharePermissions().check_user_permission(token, domain_id)
       
       if not checkPermission['has_permission']:
           raise HTTPException(
               status_code=status.HTTP_403_FORBIDDEN,
               detail="User does not have permission to access this dataset"
           )
       
       tables_details = []
       for table in dataset.tables:
           
           # --- Detailed Metrics List ---
           metrics_details = [
               {
                   "metric_id": metric.metric_id,
                   "name": metric.name,
                   "display_name": metric.display_name,
                   "description": metric.description,
                   "metric_sql": metric.metric_sql,
                   "metric_type": metric.metric_type,
                   "aggregation_type": metric.aggregation_type,
                   "format_string": metric.format_string,
                   "created_at": metric.created_at.isoformat() if metric.created_at else None,
                   "updated_at": metric.updated_at.isoformat() if metric.updated_at else None
               }
               for metric in table.metrics
           ]
 
           # --- Detailed Views List ---
           views_details = [
               {
                   "view_id": view.view_id,
                   "name": view.name,
                   "display_name": view.display_name,
                   "description": view.description,
                   "view_sql": view.view_sql,
                   "view_type": view.view_type,
                   "created_at": view.created_at.isoformat() if view.created_at else None,
                   "updated_at": view.updated_at.isoformat() if view.updated_at else None
               }
               for view in table.views
           ]
           
           # --- Detailed Calculated Columns List ---
           calculated_columns_details = []
           physical_columns_details = []
           for col in table.columns:
               if col.column_type == 'calculated_column' and col.calculated_column:
                   calculated_columns_details.append({
                       "column_id": col.column_id,
                       "name": col.name,
                       "display_name": col.display_name,
                       "description": col.description,
                       "data_type": col.data_type,
                       "usage_type": col.usage_type,
                       "calculated_column_id": col.calculated_column.calculated_column_id,
                       "calculation_sql": col.calculated_column.calculation_sql,
                       "function_id": col.calculated_column.function_id,
                       "dependencies": col.calculated_column.dependencies,
                       "created_at": col.created_at.isoformat() if col.created_at else None,
                       "updated_at": col.updated_at.isoformat() if col.updated_at else None
                   })
               else:
                   # Also include physical columns for completeness
                   physical_columns_details.append({
                       "column_id": col.column_id,
                       "name": col.name,
                       "display_name": col.display_name,
                       "description": col.description,
                       "data_type": col.data_type
                   })
 
           # --- Assemble all details for this table ---
           tables_details.append({
               "table_id": table.table_id,
               "name": table.name,
               "display_name": table.display_name,
               "description": table.description,
               "relationships": table.json_metadata.get("key_relationships", []),
               
               # Physical Columns
               "columns": physical_columns_details,
               "total_columns": len(physical_columns_details),
 
               # Calculated Columns with Total
               "calculated_columns": calculated_columns_details,
               "total_calculated_columns": len(calculated_columns_details),
 
               # Metrics with Total
               "metrics": metrics_details,
               "total_metrics": len(metrics_details),
               
               # Views with Total
               "views": views_details,
               "total_views": len(views_details)
           })
           
       # --- Structure the final, complete response ---
       response = {
           "dataset_id": dataset.dataset_id,
           "name": dataset.name,
           "display_name": dataset.display_name,
           "description": dataset.description,
           "created_at": str(dataset.created_at),
           "domain": {
               "domain_id": dataset.domain.domain_id,
               "display_name": dataset.domain.display_name,
               "status": dataset.domain.status
           },
           "tables": tables_details,
           "table_count": len(dataset.tables)
       }
       
       return response
 
   except Exception as e:
       logger.error(f"Error getting dataset details for ID {dataset_id}: {str(e)}")
       raise HTTPException(
           status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
           detail=f"Failed to get dataset details: {str(e)}"
       )

@router.post("/table", response_model=EnhancedTableResponse, status_code=status.HTTP_201_CREATED)
async def api_add_table(
    add_table_request: AddTableRequest,
    domain_context: DomainContext,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a table to a dataset with enhanced documentation and column definitions"""
    try:
        user = await SharePermissions()._validate_user(token)
        # Check if dataset exists
        dataset = await db.execute(
            select(Dataset).where(Dataset.dataset_id == add_table_request.dataset_id, Dataset.created_by == user['id'])
        )
        dataset = dataset.scalar_one_or_none()
        
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {add_table_request.dataset_id} not found"
            )
        
        # Check if domain is in draft
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == dataset.domain_id, Domain.created_by == user['id'])
        )
        domain = domain.scalar_one_or_none()
        
        # Check table limit (3-4 tables max per domain)
        table_count = await db.execute(
            select(func.count(Table.table_id)).where(Table.domain_id == dataset.domain_id)
        )
        table_count = table_count.scalar()
        
        if table_count >= 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain can have maximum 10 tables"
            )
        
        # Check for duplicate table name in the domain
        existing_table = await db.execute(
            select(Table).where(
                Table.domain_id == dataset.domain_id,
                Table.name == add_table_request.schema.table_name
            )
        )
        if existing_table.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table '{add_table_request.schema.table_name}' already exists in domain"
            )
        
        # Use workflow service to add table with enhanced features
        workflow_service = DomainWorkflowService(user['id'], session_id)
        documented_table = await workflow_service.add_table(add_table_request, domain_context)
        
        # Create enhanced column definitions for metadata storage
        enhanced_columns_for_metadata = []
        for enhanced_col in documented_table.columns:
            enhanced_columns_for_metadata.append({
                "column_name": enhanced_col.column_name,
                "display_name": enhanced_col.display_name,
                "description": enhanced_col.description,
                "business_description": enhanced_col.business_description,
                "usage_type": enhanced_col.usage_type.value,
                "data_type": enhanced_col.data_type,
                "example_values": enhanced_col.example_values,
                "business_rules": enhanced_col.business_rules,
                "data_quality_checks": enhanced_col.data_quality_checks,
                "related_concepts": enhanced_col.related_concepts,
                "privacy_classification": enhanced_col.privacy_classification,
                "aggregation_suggestions": enhanced_col.aggregation_suggestions,
                "filtering_suggestions": enhanced_col.filtering_suggestions,
                "json_metadata": enhanced_col.json_metadata
            })
        
        # Create table in database
        table = Table(
            domain_id=dataset.domain_id,
            dataset_id=add_table_request.dataset_id,
            name=add_table_request.schema.table_name,
            display_name=add_table_request.schema.table_name,
            description=documented_table.description,
            table_type='table',
            json_metadata={
                "columns": add_table_request.schema.columns,
                "enhanced_columns": enhanced_columns_for_metadata,
                "semantic_description": documented_table.semantic_description,
                "relationship_recommendations": documented_table.relationship_recommendations,
                "business_purpose": documented_table.business_purpose,
                "primary_use_cases": documented_table.primary_use_cases,
                "key_relationships": documented_table.key_relationships,
                "data_lineage": documented_table.data_lineage,
                "update_frequency": documented_table.update_frequency,
                "data_retention": documented_table.data_retention,
                "access_patterns": documented_table.access_patterns,
                "performance_considerations": documented_table.performance_considerations
            }
        )
        
        db.add(table)
        await db.commit()
        await db.refresh(table)
        
        # Create enhanced columns using service method
        enhanced_columns = await workflow_service.create_enhanced_columns(documented_table, add_table_request.schema)
        
        # Add columns to the table
        for enhanced_col_data in enhanced_columns:
            enhanced_col_data["table_id"] = table.table_id
            column = SQLColumn(
                table_id=enhanced_col_data["table_id"],
                name=enhanced_col_data["name"],
                display_name=enhanced_col_data["display_name"],
                description=enhanced_col_data["description"],
                data_type=enhanced_col_data["data_type"],
                is_nullable=enhanced_col_data["is_nullable"],
                is_primary_key=enhanced_col_data["is_primary_key"],
                is_foreign_key=enhanced_col_data["is_foreign_key"],
                usage_type=enhanced_col_data["usage_type"],
                ordinal_position=enhanced_col_data["ordinal_position"],
                json_metadata=enhanced_col_data["json_metadata"]
            )
            db.add(column)
        await db.commit()
        
        # Get column count
        column_count = await db.execute(
            select(func.count(SQLColumn.column_id)).where(SQLColumn.table_id == table.table_id)
        )
        column_count = column_count.scalar()
        
        # Get enhanced table response using service method
        #response_data = await workflow_service.get_enhanced_table_response(table, documented_table, enhanced_columns, column_count)
        response_data = await workflow_service.get_enhanced_table_response(table, documented_table, enhanced_columns, column_count, db)
        
        return EnhancedTableResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error adding table: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add table: {str(e)}"
        )

@router.get("/table/{table_id}/enhanced-columns")
async def api_get_table_enhanced_columns(
    table_id: str,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get enhanced column definitions for an existing table"""
    try:
        # Use workflow service to get enhanced columns
        user = await SharePermissions()._validate_user(token)
        workflow_service = DomainWorkflowService(user['id'], session_id)
        result = await workflow_service.get_enhanced_columns_for_table(table_id, db)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Error getting enhanced columns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get enhanced columns: {str(e)}"
        )

@router.post("/commit")
async def api_commit_workflow(
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Commit the workflow and transition domain to draft_ready status"""
    try:
        user = await SharePermissions()._validate_user(token)
        workflow_service = DomainWorkflowService(user['id'], session_id)
        state = await workflow_service.commit_workflow(db)
        
        # Get the domain from state
        domain_data = state.get("domain")
        if not domain_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No domain found in workflow state"
            )
        
        # Update domain status to draft_ready
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_data.get("domain_id"))
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found"
            )
        
        if domain.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain must be in draft status to commit"
            )
        
        # Transition to draft_ready
        await db.execute(
            update(Domain)
            .where(Domain.domain_id == domain.domain_id)
            .values(
                status='draft_ready',
                updated_at=func.now()
            )
        )
        await db.commit()
        
        # Execute post-commit workflows asynchronously
        try:
            from app.service.post_commit_service import PostCommitService
            post_commit_service = PostCommitService(user['id'], session_id)
            
            # Execute post-commit workflows in background
            asyncio.create_task(
                post_commit_service.execute_post_commit_workflows(domain.domain_id, db)
            )
            
            logger.info(f"Post-commit workflows initiated for domain {domain.domain_id}")
            
        except Exception as e:
            logger.error(f"Error initiating post-commit workflows: {str(e)}")
            # Don't fail the commit if post-commit workflows fail
        
        return {
            "message": "Workflow committed successfully",
            "domain_id": domain.domain_id,
            "status": "draft_ready",
            "state": state,
            "post_commit_initiated": True
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error committing workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit workflow: {str(e)}"
        )

@router.get("/{domain_id}/sharing-permissions")
async def api_get_sharing_permissions(
    domain_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get sharing permissions for a domain"""
    try:
        workflow_service = DomainWorkflowService(user_id, session_id)
        
        # Check if domain exists
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Fetch fresh sharing permissions
        permissions = await SharePermissions().get_share_datamodel_info(token)
        
        return {
            "domain_id": domain_id,
            "permissions": permissions,
            "fetched_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting sharing permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sharing permissions: {str(e)}"
        )

@router.post("/{domain_id}/refresh-permissions")
async def api_refresh_sharing_permissions(
    domain_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Refresh sharing permissions for a domain by fetching from team API"""
    try:
        workflow_service = DomainWorkflowService(user_id, session_id)
        
        # Check if domain exists
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Fetch fresh sharing permissions
        permissions = await SharePermissions().get_share_datamodel_info(token)
        
        return {
            "status": "success",
            "message": "Sharing permissions refreshed successfully",
            "domain_id": domain_id,
            "permissions": permissions['permissions'],
            "refreshed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error refreshing sharing permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh sharing permissions: {str(e)}"
        )

@router.post("/{domain_id}/setup-sharing-permissions")
async def api_setup_sharing_permissions(
    domain_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Setup sharing permissions for a domain as part of the data setup workflow
    
    This endpoint is designed to be called explicitly during the data setup process
    to establish sharing permissions before proceeding with other workflow steps.
    """
    try:
        workflow_service = DomainWorkflowService(user_id, session_id)
        
        # Check if domain exists
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Check if domain is in appropriate status for setup
        if domain.status not in ['draft', 'draft_ready']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sharing permissions can only be set up for domains in draft or draft_ready status"
            )
        
        logger.info(f"Setting up sharing permissions for domain {domain_id} as part of data setup workflow")
        
        # Step 1: Generate initial sharing permissions
        initial_permissions = await workflow_service.fetch_and_store_sharing_permissions(domain_id)
        
        # Step 2: Store permissions in domain metadata
        domain_metadata = domain.json_metadata or {}
        domain_metadata["sharing_permissions"] = {
            "setup_completed_at": datetime.now().isoformat(),
            "setup_by": user_id,
            "initial_permissions": initial_permissions,
            "workflow_step": "data_setup"
        }
        
        # Update domain with permissions metadata
        await db.execute(
            update(Domain)
            .where(Domain.domain_id == domain_id)
            .values(
                json_metadata=domain_metadata,
                updated_at=func.now()
            )
        )
        
        await db.commit()
        
        # Step 3: Publish update for real-time workflow tracking
        publish_update(user_id, session_id, {
            "type": "sharing_permissions_setup_completed",
            "domain_id": domain_id,
            "data": {
                "setup_completed_at": datetime.now().isoformat(),
                "permissions_count": {
                    "users": len(initial_permissions.get("permissions", {}).get("users", [])),
                    "total_teams": len(initial_permissions.get("permissions", {}).get("teams", [])),
                    "total_workspaces": len(initial_permissions.get("permissions", {}).get("workspaces", [])),
                    "total_projects": len(initial_permissions.get("permissions", {}).get("projects", [])),
                    "total_organizations": len(initial_permissions.get("permissions", {}).get("organizations", []))
                }
            }
        })
        
        logger.info(f"Successfully completed sharing permissions setup for domain {domain_id}")
        
        return {
            "status": "success",
            "message": "Sharing permissions setup completed successfully",
            "domain_id": domain_id,
            "setup_completed_at": datetime.now().isoformat(),
            "setup_by": user_id,
            "permissions": initial_permissions,
            "workflow_step": "data_setup",
            "next_steps": [
                "Continue with dataset creation",
                "Add tables to datasets",
                "Configure relationships between tables",
                "Commit workflow when ready"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error setting up sharing permissions for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup sharing permissions: {str(e)}"
        )

@router.get("/{domain_id}/sharing-permissions-status")
async def api_get_sharing_permissions_status(
    domain_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get the current status of sharing permissions setup for a domain"""
    try:
        # Check if domain exists
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Check if sharing permissions are already set up
        domain_metadata = domain.json_metadata or {}
        sharing_permissions = domain_metadata.get("sharing_permissions", {})
        
        if sharing_permissions:
            # Permissions are already set up
            return {
                "domain_id": domain_id,
                "status": "setup_completed",
                "setup_completed_at": sharing_permissions.get("setup_completed_at"),
                "setup_by": sharing_permissions.get("setup_by"),
                "workflow_step": sharing_permissions.get("workflow_step"),
                "permissions_summary": {
                    "total_users": len(sharing_permissions.get("initial_permissions", {}).get("permissions", {}).get("users", [])),
                    "total_teams": len(sharing_permissions.get("initial_permissions", {}).get("permissions", {}).get("teams", [])),
                    "total_workspaces": len(sharing_permissions.get("initial_permissions", {}).get("permissions", {}).get("workspaces", [])),
                    "total_projects": len(sharing_permissions.get("initial_permissions", {}).get("permissions", {}).get("projects", [])),
                    "total_organizations": len(sharing_permissions.get("initial_permissions", {}).get("permissions", {}).get("organizations", []))
                },
                "can_proceed": True,
                "message": "Sharing permissions are already set up for this domain"
            }
        else:
            # Permissions not set up yet
            return {
                "domain_id": domain_id,
                "status": "not_setup",
                "setup_completed_at": None,
                "setup_by": None,
                "workflow_step": None,
                "permissions_summary": {
                    "total_users": 0,
                    "total_teams": 0,
                    "total_workspaces": 0,
                    "total_projects": 0,
                    "total_organizations": 0
                },
                "can_proceed": False,
                "message": "Sharing permissions need to be set up before proceeding",
                "next_action": "Call POST /{domain_id}/setup-sharing-permissions to set up permissions"
            }
        
    except Exception as e:
        logger.error(f"Error getting sharing permissions status for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sharing permissions status: {str(e)}"
        )

@router.post("/{domain_id}/data-setup-workflow")
async def api_execute_data_setup_workflow(
    domain_id: str,
    setup_steps: List[str] = None,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Execute the complete data setup workflow for a domain
    
    This endpoint orchestrates the entire data setup process including:
    1. Sharing permissions setup
    2. Domain validation
    3. Workflow state initialization
    4. Ready for dataset creation
    """
    try:
        workflow_service = DomainWorkflowService(user_id, session_id)
        
        # Check if domain exists
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Check if domain is in appropriate status
        if domain.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data setup workflow can only be executed for domains in draft status"
            )
        
        # Default setup steps if none provided
        if setup_steps is None:
            setup_steps = [
                "sharing_permissions",
                "domain_validation", 
                "workflow_initialization",
                "ready_for_datasets"
            ]
        
        logger.info(f"Starting data setup workflow for domain {domain_id} with steps: {setup_steps}")
        
        workflow_results = {
            "domain_id": domain_id,
            "workflow_started_at": datetime.now().isoformat(),
            "executed_by": user_id,
            "steps": {},
            "overall_status": "in_progress"
        }
        
        # Step 1: Sharing Permissions Setup
        if "sharing_permissions" in setup_steps:
            try:
                logger.info(f"Executing sharing permissions setup for domain {domain_id}")
                permissions_result = await workflow_service.fetch_and_store_sharing_permissions(domain_id)
                
                workflow_results["steps"]["sharing_permissions"] = {
                    "status": "completed",
                    "result": permissions_result,
                    "completed_at": datetime.now().isoformat()
                }
                
                logger.info(f"Sharing permissions setup completed for domain {domain_id}")
                
            except Exception as e:
                logger.error(f"Error in sharing permissions setup: {str(e)}")
                workflow_results["steps"]["sharing_permissions"] = {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                }
        
        # Step 2: Domain Validation
        if "domain_validation" in setup_steps:
            try:
                logger.info(f"Executing domain validation for domain {domain_id}")
                
                # Basic validation checks
                validation_checks = {
                    "domain_exists": True,
                    "status_valid": domain.status == 'draft',
                    "has_required_fields": bool(domain.domain_id and domain.display_name),
                    "can_proceed": True
                }
                
                workflow_results["steps"]["domain_validation"] = {
                    "status": "completed",
                    "result": validation_checks,
                    "completed_at": datetime.now().isoformat()
                }
                
                logger.info(f"Domain validation completed for domain {domain_id}")
                
            except Exception as e:
                logger.error(f"Error in domain validation: {str(e)}")
                workflow_results["steps"]["domain_validation"] = {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                }
        
        # Step 3: Workflow Initialization
        if "workflow_initialization" in setup_steps:
            try:
                logger.info(f"Executing workflow initialization for domain {domain_id}")
                
                # Initialize workflow state
                workflow_state = workflow_service.get_workflow_state()
                workflow_state["domain"] = {
                    "domain_id": domain.domain_id,
                    "display_name": domain.display_name,
                    "description": domain.description,
                    "created_by": domain.created_by,
                    "setup_completed_at": datetime.now().isoformat()
                }
                workflow_service.set_workflow_state(workflow_state)
                
                workflow_results["steps"]["workflow_initialization"] = {
                    "status": "completed",
                    "result": {"workflow_state_initialized": True},
                    "completed_at": datetime.now().isoformat()
                }
                
                logger.info(f"Workflow initialization completed for domain {domain_id}")
                
            except Exception as e:
                logger.error(f"Error in workflow initialization: {str(e)}")
                workflow_results["steps"]["workflow_initialization"] = {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                }
        
        # Step 4: Ready for Datasets
        if "ready_for_datasets" in setup_steps:
            try:
                logger.info(f"Marking domain {domain_id} as ready for datasets")
                
                # Update domain metadata to indicate setup completion
                domain_metadata = domain.json_metadata or {}
                domain_metadata["data_setup_workflow"] = {
                    "completed_at": datetime.now().isoformat(),
                    "completed_by": user_id,
                    "workflow_results": workflow_results,
                    "status": "ready_for_datasets"
                }
                
                await db.execute(
                    update(Domain)
                    .where(Domain.domain_id == domain_id)
                    .values(
                        json_metadata=domain_metadata,
                        updated_at=func.now()
                    )
                )
                
                workflow_results["steps"]["ready_for_datasets"] = {
                    "status": "completed",
                    "result": {"ready_for_datasets": True},
                    "completed_at": datetime.now().isoformat()
                }
                
                logger.info(f"Domain {domain_id} marked as ready for datasets")
                
            except Exception as e:
                logger.error(f"Error marking domain as ready for datasets: {str(e)}")
                workflow_results["steps"]["ready_for_datasets"] = {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                }
        
        # Determine overall workflow status
        failed_steps = [step for step, result in workflow_results["steps"].items() if result["status"] == "failed"]
        if failed_steps:
            workflow_results["overall_status"] = "failed"
            workflow_results["failed_steps"] = failed_steps
            workflow_results["message"] = f"Data setup workflow failed for steps: {', '.join(failed_steps)}"
        else:
            workflow_results["overall_status"] = "completed"
            workflow_results["message"] = "Data setup workflow completed successfully"
            workflow_results["completed_at"] = datetime.now().isoformat()
        
        await db.commit()
        
        # Publish workflow completion update
        publish_update(user_id, session_id, {
            "type": "data_setup_workflow_completed",
            "domain_id": domain_id,
            "data": workflow_results
        })
        
        logger.info(f"Data setup workflow completed for domain {domain_id} with status: {workflow_results['overall_status']}")
        
        return workflow_results
        
    except Exception as e:
        logger.error(f"Error executing data setup workflow for domain {domain_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute data setup workflow: {str(e)}"
        )

@router.get("/domain/{domain_id}/status")
async def get_domain_status(
    domain_id: str,
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get domain workflow status"""
    try:
        domain = await db.execute(
            select(Domain)
            .options(selectinload(Domain.datasets).selectinload(Dataset.tables).selectinload(Table.columns),
            selectinload(Domain.tables))
            .where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Get workflow status
        workflow_status = domain.get_workflow_status()
        
        # Add dataset and table information
        datasets_info = []
        for dataset in domain.datasets:
            
            try:
                dataset_info = {
                "dataset_id": dataset.dataset_id,
                "name": dataset.name,
                "display_name": dataset.display_name,
                "description": dataset.description,
                "table_count": len(dataset.tables),
                "tables": [
                    {
                        "table_id": table.table_id,
                        "name": table.name,
                        "display_name": table.display_name,
                        "description": table.description,
                        "column_count": len(table.columns) if hasattr(table, 'columns') else 0
                    }
                    for table in dataset.tables
                ]
            }
            except Exception as e:
                import traceback
                traceback.print_exc()
            
            
            datasets_info.append(dataset_info)
        
        return {
            "domain_id": domain.domain_id,
            "display_name": domain.display_name,
            "workflow_status": workflow_status,
            "datasets": datasets_info,
            "total_datasets": len(datasets_info),
            "total_tables": sum(len(dataset["tables"]) for dataset in datasets_info)
        }
        
    except Exception as e:
        logger.error(f"Error getting domain status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get domain status: {str(e)}"
        )

@router.get("/domain/{domain_id}/post-commit-status")
async def get_post_commit_status(
    domain_id: str,
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get post-commit workflow status for a domain"""
    try:
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        # Extract post-commit information from domain metadata
        metadata = domain.json_metadata or {}
        post_commit_info = metadata.get("post_commit", {})
        
        return {
            "domain_id": domain_id,
            "post_commit_status": post_commit_info.get("status", "not_started"),
            "workflows_completed": post_commit_info.get("workflows_completed", []),
            "last_updated": post_commit_info.get("last_updated"),
            "errors": post_commit_info.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error getting post-commit status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get post-commit status: {str(e)}"
        )

@router.post("/domain/{domain_id}/trigger-post-commit")
async def trigger_post_commit_workflows(
    domain_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Manually trigger post-commit workflows for a domain"""
    try:
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain {domain_id} not found"
            )
        
        if domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post-commit workflows can only be triggered for draft_ready or active domains"
            )
        
        # Execute post-commit workflows
        from app.service.post_commit_service import PostCommitService
        post_commit_service = PostCommitService(user_id, session_id)
        
        # Execute in background
        asyncio.create_task(
            post_commit_service.execute_post_commit_workflows(domain_id, db)
        )
        
        return {
            "message": "Post-commit workflows triggered successfully",
            "domain_id": domain_id,
            "status": "initiated"
        }
        
    except Exception as e:
        logger.error(f"Error triggering post-commit workflows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger post-commit workflows: {str(e)}"
        )

@router.post("/metric", status_code=status.HTTP_201_CREATED)
async def api_add_metric(
    table_id: str,
    metric_data: MetricCreate,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a new metric to a table"""
    try:
        user = await SharePermissions()._validate_user(token)
        # Check if table exists
        table = await db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        # Check if domain is in appropriate status for adding metrics
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add metrics to domains in draft_ready or active status"
            )
        
        # Check for duplicate metric name in the table
        existing_metric = await db.execute(
            select(Metric).where(
                Metric.table_id == table_id,
                Metric.name == metric_data.name
            )
        )
        if existing_metric.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Metric '{metric_data.name}' already exists in table"
            )
        
        # Use MetricsService to add metric with LLM enhancement
        metrics_service = MetricsService(db, domain.domain_id)
        enhanced_metric = await metrics_service.add_metric(table_id, metric_data, user['id'])
        
        return {
            "metric_id": enhanced_metric.metric_id,
            "name": enhanced_metric.name,
            "display_name": enhanced_metric.display_name,
            "description": enhanced_metric.description,
            "metric_sql": enhanced_metric.metric_sql,
            "metric_type": enhanced_metric.metric_type,
            "aggregation_type": enhanced_metric.aggregation_type,
            "table_id": table_id,
            "enhanced": True
        }
        
    except Exception as e:
        logger.error(f"Error adding metric: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add metric: {str(e)}"
        )

@router.put("/metric/{metric_id}")
async def api_update_metric(
    metric_id: str,
    metric_data: MetricCreate,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Update an existing metric"""
    try:
        # Check if metric exists
        user = await SharePermissions()._validate_user(token)
        metric = await db.execute(
            select(Metric).where(Metric.metric_id == metric_id)
        )
        metric = metric.scalar_one_or_none()
        
        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metric {metric_id} not found"
            )
        
        # Check if domain is in appropriate status for updating metrics
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == metric.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only update metrics in domains with draft_ready or active status"
            )
        
        # Check for duplicate metric name (excluding current metric)
        existing_metric = await db.execute(
            select(Metric).where(
                Metric.table_id == metric.table_id,
                Metric.name == metric_data.name,
                Metric.metric_id != metric_id
            )
        )
        if existing_metric.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Metric '{metric_data.name}' already exists in table"
            )
        
        # Update metric fields
        metric.name = metric_data.name
        metric.display_name = metric_data.display_name or metric_data.name
        metric.description = metric_data.description
        metric.metric_sql = metric_data.metric_sql
        metric.metric_type = metric_data.metric_type
        metric.aggregation_type = metric_data.aggregation_type
        metric.modified_by = user['id']
        metric.entity_version += 1
        
        await db.commit()
        await db.refresh(metric)
        
        return {
            "metric_id": metric.metric_id,
            "name": metric.name,
            "display_name": metric.display_name,
            "description": metric.description,
            "metric_sql": metric.metric_sql,
            "metric_type": metric.metric_type,
            "aggregation_type": metric.aggregation_type,
            "table_id": metric.table_id,
            "updated": True
        }
        
    except Exception as e:
        logger.error(f"Error updating metric: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update metric: {str(e)}"
        )

@router.post("/calculated-column", status_code=status.HTTP_201_CREATED)
async def api_add_calculated_column(
    table_id: str,
    column_data: CalculatedColumnCreate,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a new calculated column to a table"""
    try:
        user = await SharePermissions()._validate_user(token)
        # Check if table exists
        table = await db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        # Check if domain is in appropriate status for adding calculated columns
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add calculated columns to domains in draft_ready or active status"
            )
        
        # Check for duplicate column name in the table
        existing_column = await db.execute(
            select(SQLColumn).where(
                SQLColumn.table_id == table_id,
                SQLColumn.name == column_data.name
            )
        )
        if existing_column.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{column_data.name}' already exists in table"
            )
        
        # Use MetricsService to add calculated column with LLM enhancement
        metrics_service = MetricsService(db, domain.domain_id)
        enhanced_column = await metrics_service.add_calculated_column(table_id, column_data.dict(), user['id'])
        
        return {
            "column_id": enhanced_column.column_id,
            "name": enhanced_column.name,
            "display_name": enhanced_column.display_name,
            "description": enhanced_column.description,
            "data_type": enhanced_column.data_type,
            "usage_type": enhanced_column.usage_type,
            "table_id": table_id,
            "calculated_column_id": enhanced_column.calculated_column.calculated_column_id,
            "calculation_sql": enhanced_column.calculated_column.calculation_sql,
            "enhanced": True
        }
        
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error adding calculated column: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add calculated column: {str(e)}"
        )

@router.put("/calculated-column/{column_id}")
async def api_update_calculated_column(
    column_id: str,
    column_data: CalculatedColumnCreate,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Update an existing calculated column"""
    try:
        # Check if column exists and is a calculated column
        column = await db.execute(
            select(SQLColumn)
            .options(selectinload(SQLColumn.calculated_column))
            .where(SQLColumn.column_id == column_id)
        )
        column = column.scalar_one_or_none()
        
        if not column:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Column {column_id} not found"
            )
        
        if column.column_type != 'calculated_column':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column is not a calculated column"
            )
        
        # Check if domain is in appropriate status for updating calculated columns
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == column.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only update calculated columns in domains with draft_ready or active status"
            )
        
        # Check for duplicate column name (excluding current column)
        existing_column = await db.execute(
            select(SQLColumn).where(
                SQLColumn.table_id == column.table_id,
                SQLColumn.name == column_data.name,
                SQLColumn.column_id != column_id
            )
        )
        if existing_column.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{column_data.name}' already exists in table"
            )
        
        # Update column fields
        column.name = column_data.name
        column.display_name = column_data.display_name or column_data.name
        column.description = column_data.description
        column.data_type = column_data.data_type
        column.usage_type = column_data.usage_type
        column.is_nullable = column_data.is_nullable
        column.is_primary_key = column_data.is_primary_key
        column.is_foreign_key = column_data.is_foreign_key
        column.default_value = column_data.default_value
        column.ordinal_position = column_data.ordinal_position
        column.modified_by = user['id']
        column.entity_version += 1
        
        # Update calculated column fields
        if column.calculated_column:
            column.calculated_column.calculation_sql = column_data.calculation_sql
            column.calculated_column.function_id = column_data.function_id
            column.calculated_column.dependencies = column_data.dependencies
            column.calculated_column.modified_by = user['id']
            column.calculated_column.entity_version += 1
        
        await db.commit()
        await db.refresh(column)
        
        return {
            "column_id": column.column_id,
            "name": column.name,
            "display_name": column.display_name,
            "description": column.description,
            "data_type": column.data_type,
            "usage_type": column.usage_type,
            "table_id": column.table_id,
            "calculated_column_id": column.calculated_column.calculated_column_id,
            "calculation_sql": column.calculated_column.calculation_sql,
            "updated": True
        }
        
    except Exception as e:
        logger.error(f"Error updating calculated column: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update calculated column: {str(e)}"
        )

@router.post("/view", status_code=status.HTTP_201_CREATED)
async def api_add_view(
    table_id: str,
    view_data: ViewCreate,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a new view to a table"""
    try:
        # Check if table exists
        user = await SharePermissions()._validate_user(token)
        table = await db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        # Check if domain is in appropriate status for adding views
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add views to domains in draft_ready or active status"
            )
        
        # Check for duplicate view name in the table
        existing_view = await db.execute(
            select(View).where(
                View.table_id == table_id,
                View.name == view_data.name
            )
        )
        if existing_view.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"View '{view_data.name}' already exists in table"
            )
        
        # Use MetricsService to add view with LLM enhancement
        metrics_service = MetricsService(db, domain.domain_id)
        enhanced_view = await metrics_service.add_view(table_id, view_data, user['id'])
        
        return {
            "view_id": enhanced_view.view_id,
            "name": enhanced_view.name,
            "display_name": enhanced_view.display_name,
            "description": enhanced_view.description,
            "view_sql": enhanced_view.view_sql,
            "view_type": enhanced_view.view_type,
            "table_id": table_id,
            "enhanced": True
        }
        
    except Exception as e:
        logger.error(f"Error adding view: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add view: {str(e)}"
        )

@router.put("/view/{view_id}")
async def api_update_view(
    view_id: str,
    view_data: ViewCreate,
    session_id: str = Depends(get_session_id),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Update an existing view"""
    try:
        # Check if view exists
        user = await SharePermissions()._validate_user(token)
        view = await db.execute(
            select(View).where(View.view_id == view_id)
        )
        view = view.scalar_one_or_none()
        
        if not view:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View {view_id} not found"
            )
        
        # Check if domain is in appropriate status for updating views
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == view.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only update views in domains with draft_ready or active status"
            )
        
        # Check for duplicate view name (excluding current view)
        existing_view = await db.execute(
            select(View).where(
                View.table_id == view.table_id,
                View.name == view_data.name,
                View.view_id != view_id
            )
        )
        if existing_view.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"View '{view_data.name}' already exists in table"
            )
        
        # Update view fields
        view.name = view_data.name
        view.display_name = view_data.display_name or view_data.name
        view.description = view_data.description
        view.view_sql = view_data.view_sql
        view.view_type = view_data.view_type
        view.modified_by = user['id']
        view.entity_version += 1
        
        await db.commit()
        await db.refresh(view)
        
        return {
            "view_id": view.view_id,
            "name": view.name,
            "display_name": view.display_name,
            "description": view.description,
            "view_sql": view.view_sql,
            "view_type": view.view_type,
            "table_id": view.table_id,
            "updated": True
        }
        
    except Exception as e:
        logger.error(f"Error updating view: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update view: {str(e)}"
        )

@router.get("/table/{table_id}/metrics")
async def api_get_table_metrics(
    table_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get all metrics for a table"""
    try:
        user = await SharePermissions()._validate_user(token)
        # Check if table exists
        table = await db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        # Get metrics
        metrics = await db.execute(
            select(Metric).where(Metric.table_id == table_id)
        )
        metrics = metrics.scalars().all()
        
        return {
            "table_id": table_id,
            "table_name": table.name,
            "metrics": [
                {
                    "metric_id": metric.metric_id,
                    "name": metric.name,
                    "display_name": metric.display_name,
                    "description": metric.description,
                    "metric_sql": metric.metric_sql,
                    "metric_type": metric.metric_type,
                    "aggregation_type": metric.aggregation_type,
                    "format_string": metric.format_string,
                    "created_at": metric.created_at,
                    "updated_at": metric.updated_at
                }
                for metric in metrics
            ],
            "total_metrics": len(metrics)
        }
        
    except Exception as e:
        logger.error(f"Error getting table metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get table metrics: {str(e)}"
        )

@router.get("/table/{table_id}/calculated-columns")
async def api_get_table_calculated_columns(
    table_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get all calculated columns for a table"""
    try:
        user = await SharePermissions()._validate_user(token)
        # Check if table exists
        table = await db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        # Get calculated columns
        columns = await db.execute(
            select(SQLColumn)
            .options(selectinload(SQLColumn.calculated_column))
            .where(
                SQLColumn.table_id == table_id,
                SQLColumn.column_type == 'calculated_column'
            )
        )
        print("columns",columns)
        columns = columns.scalars().all()
        
        return {
            "table_id": table_id,
            "table_name": table.name,
            "calculated_columns": [
                {
                    "column_id": column.column_id,
                    "name": column.name,
                    "display_name": column.display_name,
                    "description": column.description,
                    "data_type": column.data_type,
                    "usage_type": column.usage_type,
                    "calculated_column_id": column.calculated_column.calculated_column_id,
                    "calculation_sql": column.calculated_column.calculation_sql,
                    "function_id": column.calculated_column.function_id,
                    "dependencies": column.calculated_column.dependencies,
                    "created_at": column.created_at,
                    "updated_at": column.updated_at
                }
                for column in columns
            ],
            "total_calculated_columns": len(columns)
        }
        
    except Exception as e:
        logger.error(f"Error getting table calculated columns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get table calculated columns: {str(e)}"
        )

@router.get("/table/{table_id}/views")
async def api_get_table_views(
    table_id: str,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get all views for a table"""
    try:
        user = await SharePermissions()._validate_user(token)
        # Check if table exists
        table = await db.execute(
            select(Table).where(Table.table_id == table_id)
        )
        table = table.scalar_one_or_none()
        
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {table_id} not found"
            )
        
        # Get views
        views = await db.execute(
            select(View).where(View.table_id == table_id)
        )
        views = views.scalars().all()
        
        return {
            "table_id": table_id,
            "table_name": table.name,
            "views": [
                {
                    "view_id": view.view_id,
                    "name": view.name,
                    "display_name": view.display_name,
                    "description": view.description,
                    "view_sql": view.view_sql,
                    "view_type": view.view_type,
                    "created_at": view.created_at,
                    "updated_at": view.updated_at
                }
                for view in views
            ],
            "total_views": len(views)
        }
        
    except Exception as e:
        logger.error(f"Error getting table views: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get table views: {str(e)}"
        )

@router.get("/metric/{metric_id}/enhance")
async def api_enhance_metric_definition(
    metric_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Enhance an existing metric definition using LLM"""
    try:
        # Check if metric exists
        metric = await db.execute(
            select(Metric).where(Metric.metric_id == metric_id)
        )
        metric = metric.scalar_one_or_none()
        
        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metric {metric_id} not found"
            )
        
        # Check if domain is in appropriate status for enhancing metrics
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == metric.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only enhance metrics in domains with draft_ready or active status"
            )
        
        # Use MetricsService to enhance the metric definition
        metrics_service = MetricsService(db, domain.domain_id)
        enhancement_result = await metrics_service.enhance_metric_definition(metric_id, user_id)
        
        return enhancement_result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error enhancing metric definition: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enhance metric definition: {str(e)}"
        )

@router.post("/metric/{metric_id}/apply-enhancement")
async def api_apply_metric_enhancement(
    metric_id: str,
    enhancement_data: dict,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Apply LLM enhancement to an existing metric"""
    try:
        # Check if metric exists
        metric = await db.execute(
            select(Metric).where(Metric.metric_id == metric_id)
        )
        metric = metric.scalar_one_or_none()
        
        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metric {metric_id} not found"
            )
        
        # Check if domain is in appropriate status for updating metrics
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == metric.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only apply enhancements to metrics in domains with draft_ready or active status"
            )
        
        # Use MetricsService to apply the enhancement
        metrics_service = MetricsService(db, domain.domain_id)
        updated_metric = await metrics_service.apply_metric_enhancement(metric_id, enhancement_data, user_id, session_id)
        
        return {
            "metric_id": updated_metric.metric_id,
            "name": updated_metric.name,
            "display_name": updated_metric.display_name,
            "description": updated_metric.description,
            "metric_sql": updated_metric.metric_sql,
            "metric_type": updated_metric.metric_type,
            "aggregation_type": updated_metric.aggregation_type,
            "format_string": updated_metric.format_string,
            "table_id": updated_metric.table_id,
            "enhancement_applied": True,
            "enhanced_at": updated_metric.json_metadata.get("enhanced_at") if updated_metric.json_metadata else None,
            "confidence_score": updated_metric.json_metadata.get("confidence_score") if updated_metric.json_metadata else None
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error applying metric enhancement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply metric enhancement: {str(e)}"
        )

@router.get("/view/{view_id}/enhance")
async def api_enhance_view_definition(
    view_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Enhance an existing view definition using LLM"""
    try:
        # Check if view exists
        view = await db.execute(
            select(View).where(View.view_id == view_id)
        )
        view = view.scalar_one_or_none()
        
        if not view:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View {view_id} not found"
            )
        
        # Check if domain is in appropriate status for enhancing views
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == view.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only enhance views in domains with draft_ready or active status"
            )
        
        # Use MetricsService to enhance the view definition
        metrics_service = MetricsService(db, domain.domain_id)
        enhancement_result = await metrics_service.enhance_view_definition(view_id, user_id)
        
        return enhancement_result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error enhancing view definition: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enhance view definition: {str(e)}"
        )

@router.post("/view/{view_id}/apply-enhancement")
async def api_apply_view_enhancement(
    view_id: str,
    enhancement_data: dict,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Apply LLM enhancement to an existing view"""
    try:
        # Check if view exists
        view = await db.execute(
            select(View).where(View.view_id == view_id)
        )
        view = view.scalar_one_or_none()
        
        if not view:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"View {view_id} not found"
            )
        
        # Check if domain is in appropriate status for updating views
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == view.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only apply enhancements to views in domains with draft_ready or active status"
            )
        
        # Use MetricsService to apply the enhancement
        metrics_service = MetricsService(db, domain.domain_id)
        updated_view = await metrics_service.apply_view_enhancement(view_id, enhancement_data, user_id, session_id)
        
        return {
            "view_id": updated_view.view_id,
            "name": updated_view.name,
            "display_name": updated_view.display_name,
            "description": updated_view.description,
            "view_sql": updated_view.view_sql,
            "view_type": updated_view.view_type,
            "table_id": updated_view.table_id,
            "enhancement_applied": True,
            "enhanced_at": updated_view.json_metadata.get("enhanced_at") if updated_view.json_metadata else None,
            "confidence_score": updated_view.json_metadata.get("confidence_score") if updated_view.json_metadata else None
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error applying view enhancement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply view enhancement: {str(e)}"
        )

@router.get("/calculated-column/{column_id}/enhance")
async def api_enhance_calculated_column_definition(
    column_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Enhance an existing calculated column definition using LLM"""
    try:
        # Check if calculated column exists
        column = await db.execute(
            select(SQLColumn)
            .options(selectinload(SQLColumn.calculated_column))
            .where(SQLColumn.column_id == column_id)
        )
        column = column.scalar_one_or_none()
        
        if not column:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Column {column_id} not found"
            )
        
        if column.column_type != 'calculated_column':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column is not a calculated column"
            )
        
        # Check if domain is in appropriate status for enhancing calculated columns
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == column.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only enhance calculated columns in domains with draft_ready or active status"
            )
        
        # Use MetricsService to enhance the calculated column definition
        metrics_service = MetricsService(db, domain.domain_id)
        enhancement_result = await metrics_service.enhance_calculated_column_definition(column_id, user_id)
        
        return enhancement_result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error enhancing calculated column definition: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enhance calculated column definition: {str(e)}"
        )

@router.post("/calculated-column/{column_id}/apply-enhancement")
async def api_apply_calculated_column_enhancement(
    column_id: str,
    enhancement_data: dict,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Apply LLM enhancement to an existing calculated column"""
    try:
        # Check if calculated column exists
        column = await db.execute(
            select(SQLColumn)
            .options(selectinload(SQLColumn.calculated_column))
            .where(SQLColumn.column_id == column_id)
        )
        column = column.scalar_one_or_none()
        
        if not column:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Column {column_id} not found"
            )
        
        if column.column_type != 'calculated_column':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column is not a calculated column"
            )
        
        # Check if domain is in appropriate status for updating calculated columns
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == column.table.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only apply enhancements to calculated columns in domains with draft_ready or active status"
            )
        
        # Use MetricsService to apply the enhancement
        metrics_service = MetricsService(db, domain.domain_id)
        updated_column = await metrics_service.apply_calculated_column_enhancement(column_id, enhancement_data, user_id, session_id)
        
        return {
            "column_id": updated_column.column_id,
            "name": updated_column.name,
            "display_name": updated_column.display_name,
            "description": updated_column.description,
            "data_type": updated_column.data_type,
            "usage_type": updated_column.usage_type,
            "table_id": updated_column.table_id,
            "calculated_column_id": updated_column.calculated_column.calculated_column_id,
            "calculation_sql": updated_column.calculated_column.calculation_sql,
            "dependencies": updated_column.calculated_column.dependencies,
            "enhancement_applied": True,
            "enhanced_at": updated_column.json_metadata.get("enhanced_at") if updated_column.json_metadata else None,
            "confidence_score": updated_column.json_metadata.get("confidence_score") if updated_column.json_metadata else None
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error applying calculated column enhancement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply calculated column enhancement: {str(e)}"
        )

@router.get("/stream/{user_id}")
async def workflow_stream(user_id: str, session_id: str = "default", request: Request = None):
    """Stream workflow updates via Server-Sent Events"""
    async def event_generator():
        queue = asyncio.Queue()
        add_subscriber(user_id, session_id, queue)
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    # Send a keep-alive comment every 15 seconds
                    yield ":\n\n"
                    continue
                yield f"data: {json.dumps(data)}\n\n"
                if await request.is_disconnected():
                    break
        finally:
            remove_subscriber(user_id, session_id, queue)
    return StreamingResponse(event_generator(), media_type='text/event-stream')