# unstructured/genieml/dataservices/app/routers/project_workflow.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, func
from app.core.dependencies import get_async_db_session, get_session_manager
from app.service.models import (
    CreateProjectRequest, ProjectContext, AddTableRequest, 
    ProjectResponse, TableResponse
)
from app.schemas.dbmodels import Project, Dataset, Table, SQLColumn
from app.service.project_workflow_service import ProjectWorkflowService
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


@router.post("/project", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def api_create_project(
    project_data: CreateProjectRequest, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create a new project in draft status"""
    try:
        # Check if project already exists
        result = await db.execute(
            select(Project).where(Project.project_id == project_data.project_id)
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID {project_data.project_id} already exists"
            )
        
        # Create project in draft status
        project = Project(
            project_id=project_data.project_id,
            display_name=project_data.display_name,
            description=project_data.description,
            created_by=project_data.created_by,
            status='draft',  # Start as draft
            version_locked=True  # Lock version during draft phase
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        # Initialize workflow service for this project
        workflow_service = ProjectWorkflowService(user_id, session_id)
        await workflow_service.create_project({
            "project_id": project.project_id,
            "display_name": project.display_name,
            "description": project.description,
            "created_by": project.created_by,
            "context": project_data.context.dict() if project_data.context else None
        })
        
        return ProjectResponse(
            project_id=project.project_id,
            display_name=project.display_name,
            description=project.description,
            created_by=project.created_by,
            status=project.status,
            version_string=project.version_string,
            created_at=project.created_at,
            is_draft=True if project.status =='draft' else False,
            updated_at=project.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )

@router.post("/dataset", status_code=status.HTTP_201_CREATED)
async def api_add_dataset(
    dataset_data: dict, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Add a dataset to a project"""
    try:
        project_id = dataset_data.get("project_id")
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id is required"
            )
        
        # Check if project exists and is in draft
        project = await db.execute(
            select(Project).where(Project.project_id == project_id)
        )
        project = project.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        if project.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add datasets to draft projects"
            )
        
        # Create dataset
        dataset = Dataset(
            project_id=project_id,
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
        workflow_service = ProjectWorkflowService(user_id, session_id)
        await workflow_service.add_dataset({
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "display_name": dataset.display_name,
            "description": dataset.description,
            "project_id": project_id
        })
        
        return {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "display_name": dataset.display_name,
            "description": dataset.description,
            "project_id": project_id
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
    project_context: ProjectContext,
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
        
        # Check if project is in draft
        project = await db.execute(
            select(Project).where(Project.project_id == dataset.project_id)
        )
        project = project.scalar_one_or_none()
        
        if not project or project.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only add tables to draft projects"
            )
        
        # Check table limit (3-4 tables max per project)
        table_count = await db.execute(
            select(func.count(Table.table_id)).where(Table.project_id == dataset.project_id)
        )
        table_count = table_count.scalar()
        
        if table_count >= 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project can have maximum 4 tables"
            )
        
        # Check for duplicate table name in the project
        existing_table = await db.execute(
            select(Table).where(
                Table.project_id == dataset.project_id,
                Table.name == add_table_request.schema.table_name
            )
        )
        if existing_table.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table '{add_table_request.schema.table_name}' already exists in project"
            )
        
        # Use workflow service to add table with enhanced features
        workflow_service = ProjectWorkflowService(user_id, session_id)
        documented_table = await workflow_service.add_table(add_table_request, project_context)
        
        # Create table in database
        table = Table(
            project_id=dataset.project_id,
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
    """Commit the workflow and transition project to draft_ready status"""
    try:
        workflow_service = ProjectWorkflowService(user_id, session_id)
        state = await workflow_service.commit_workflow(db)
        
        # Get the project from state
        project_data = state.get("project")
        if not project_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No project found in workflow state"
            )
        
        # Update project status to draft_ready
        project = await db.execute(
            select(Project).where(Project.project_id == project_data.get("project_id"))
        )
        project = project.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        if project.status != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project must be in draft status to commit"
            )
        
        # Transition to draft_ready
        await db.execute(
            update(Project)
            .where(Project.project_id == project.project_id)
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
                post_commit_service.execute_post_commit_workflows(project.project_id, db)
            )
            
            logger.info(f"Post-commit workflows initiated for project {project.project_id}")
            
        except Exception as e:
            logger.error(f"Error initiating post-commit workflows: {str(e)}")
            # Don't fail the commit if post-commit workflows fail
        
        return {
            "message": "Workflow committed successfully",
            "project_id": project.project_id,
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

@router.get("/project/{project_id}/status")
async def get_project_status(
    project_id: str,
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get project workflow status"""
    try:
        project = await db.execute(
            select(Project)
            .options(selectinload(Project.datasets).selectinload(Dataset.tables).selectinload(Table.columns),
            selectinload(Project.tables))
            .where(Project.project_id == project_id)
        )
        project = project.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        # Get workflow status
        workflow_status = project.get_workflow_status()
        
        # Add dataset and table information
        datasets_info = []
        for dataset in project.datasets:
            
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
            "project_id": project.project_id,
            "display_name": project.display_name,
            "workflow_status": workflow_status,
            "datasets": datasets_info,
            "total_datasets": len(datasets_info),
            "total_tables": sum(len(dataset["tables"]) for dataset in datasets_info)
        }
        
    except Exception as e:
        logger.error(f"Error getting project status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project status: {str(e)}"
        )

@router.get("/project/{project_id}/post-commit-status")
async def get_post_commit_status(
    project_id: str,
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get post-commit workflow status for a project"""
    try:
        project = await db.execute(
            select(Project).where(Project.project_id == project_id)
        )
        project = project.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        # Extract post-commit information from project metadata
        metadata = project.json_metadata or {}
        post_commit_info = metadata.get("post_commit", {})
        
        return {
            "project_id": project_id,
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

@router.post("/project/{project_id}/trigger-post-commit")
async def trigger_post_commit_workflows(
    project_id: str,
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Manually trigger post-commit workflows for a project"""
    try:
        project = await db.execute(
            select(Project).where(Project.project_id == project_id)
        )
        project = project.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found"
            )
        
        if project.status not in ['draft_ready', 'active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post-commit workflows can only be triggered for draft_ready or active projects"
            )
        
        # Execute post-commit workflows
        from app.service.post_commit_service import PostCommitService
        post_commit_service = PostCommitService(user_id, session_id)
        
        # Execute in background
        asyncio.create_task(
            post_commit_service.execute_post_commit_workflows(project_id, db)
        )
        
        return {
            "message": "Post-commit workflows triggered successfully",
            "project_id": project_id,
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