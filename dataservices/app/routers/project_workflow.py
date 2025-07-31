# unstructured/genieml/dataservices/app/routers/domain_workflow.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, func
from app.core.dependencies import get_async_db_session, get_session_manager
from app.service.models import (
    CreateDomainRequest, DomainContext, AddTableRequest, 
    DomainResponse, TableResponse
)
from app.schemas.dbmodels import Domain, Dataset, Table, SQLColumn
from app.service.project_workflow_service import DomainWorkflowService
from fastapi.responses import StreamingResponse
import asyncio
import json
from app.utils.sse import add_subscriber, remove_subscriber
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["workflow"])

def get_session_id(request: Request):
    return request.headers.get("X-Session-Id") or "demo-session"

def get_user_id(request: Request):
    return request.headers.get("X-User-Id") or "demo-user"

from sqlalchemy import text


@router.post("/domain", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def api_create_domain(
    domain_data: CreateDomainRequest, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create a new domain in draft status"""
    try:
        # Check if domain already exists
        result = await db.execute(
            select(Domain).where(Domain.domain_id == domain_data.domain_id)
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Domain with ID {domain_data.domain_id} already exists"
            )
        
        # Create domain in draft status
        domain = Domain(
            domain_id=domain_data.domain_id,
            display_name=domain_data.display_name,
            description=domain_data.description,
            created_by=domain_data.created_by,
            status='draft',  # Start as draft
            version_locked=True  # Lock version during draft phase
        )
        db.add(domain)
        await db.commit()
        await db.refresh(domain)
        # Initialize workflow service for this domain
        workflow_service = DomainWorkflowService(user_id, session_id)
        await workflow_service.create_domain({
            "domain_id": domain.domain_id,
            "display_name": domain.display_name,
            "description": domain.description,
            "created_by": domain.created_by,
            "context": domain_data.context.dict() if domain_data.context else None
        })
        
        return DomainResponse(
            domain_id=domain.domain_id,
            display_name=domain.display_name,
            description=domain.description,
            created_by=domain.created_by,
            status=domain.status,
            version_string=domain.version_string,
            created_at=domain.created_at,
            is_draft=True if domain.status =='draft' else False,
            updated_at=domain.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error creating domain: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create domain: {str(e)}"
        )

@router.post("/dataset", status_code=status.HTTP_201_CREATED)
async def api_add_dataset(
    dataset_data: dict, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a dataset to a domain"""
    try:
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
            json_metadata=dataset_data.get("metadata", {})
        )
        
        
        db.add(dataset)
        try:
            await db.commit()
            await db.refresh(dataset)
        except Exception as e:
            import traceback
            traceback.print_exc()
        

        
        # Update workflow service
        workflow_service = DomainWorkflowService(user_id, session_id)
        await workflow_service.add_dataset({
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "display_name": dataset.display_name,
            "description": dataset.description,
            "domain_id": domain_id
        })
        
        return {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
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

@router.post("/table", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def api_add_table(
    add_table_request: AddTableRequest,
    domain_context: DomainContext,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a table to a dataset with enhanced documentation"""
    try:
        # Check if dataset exists
        dataset = await db.execute(
            select(Dataset).where(Dataset.dataset_id == add_table_request.dataset_id)
        )
        dataset = dataset.scalar_one_or_none()
        
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset {add_table_request.dataset_id} not found"
            )
        
        # Check if domain is in draft
        domain = await db.execute(
            select(Domain).where(Domain.domain_id == dataset.domain_id)
        )
        domain = domain.scalar_one_or_none()
        
        if not domain or domain.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add tables to draft domains"
            )
        
        # Check table limit (3-4 tables max per domain)
        table_count = await db.execute(
            select(func.count(Table.table_id)).where(Table.domain_id == dataset.domain_id)
        )
        table_count = table_count.scalar()
        
        if table_count >= 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain can have maximum 4 tables"
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
        workflow_service = DomainWorkflowService(user_id, session_id)
        documented_table = await workflow_service.add_table(add_table_request, domain_context)
        
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
        
        # Add columns to the table
        for i, col_data in enumerate(add_table_request.schema.columns):
            column = SQLColumn(
                table_id=table.table_id,
                name=col_data.get("name", "unknown"),
                display_name=col_data.get("display_name") or col_data.get("name", "unknown"),
                description=col_data.get("description"),
                data_type=col_data.get("data_type"),
                is_nullable=col_data.get("is_nullable", True),
                is_primary_key=col_data.get("is_primary_key", False),
                is_foreign_key=col_data.get("is_foreign_key", False),
                usage_type=col_data.get("usage_type"),
                ordinal_position=i + 1,
                json_metadata=col_data.get("metadata", {})
            )
            db.add(column)
        
        await db.commit()
        
        # Get column count
        column_count = await db.execute(
            select(func.count(SQLColumn.column_id)).where(SQLColumn.table_id == table.table_id)
        )
        column_count = column_count.scalar()
        
        return TableResponse(
            table_id=table.table_id,
            name=table.name,
            display_name=table.display_name,
            description=table.description,
            table_type=table.table_type,
            semantic_description=documented_table.description,
            column_count=column_count
        )
        
    except Exception as e:
        logger.error(f"Error adding table: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add table: {str(e)}"
        )

@router.post("/commit")
async def api_commit_workflow(
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Commit the workflow and transition domain to draft_ready status"""
    try:
        workflow_service = DomainWorkflowService(user_id, session_id)
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
            post_commit_service = PostCommitService(user_id, session_id)
            
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