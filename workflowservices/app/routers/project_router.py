from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from uuid import UUID
import traceback

from app.core.dependencies import get_async_db_session
from app.services.project_service import ProjectService
from app.models.schema import (
    ProjectCreate, ProjectUpdate, ProjectArtifactCreate,
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["projects"],
)


# ==================== Project CRUD ====================

@router.post("/")
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Create a new project."""
    service = ProjectService(db)
    try:
        result = await service.create_project(
            user_id=UUID(user_id),
            name=project.name,
            description=project.description,
            workspace_id=project.workspace_id,
            goals=project.goals,
            data_sources=project.data_sources,
            thread_id=project.thread_id,
            metadata=project.metadata,
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
async def list_projects(
    workspace_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """List all projects for the current user."""
    service = ProjectService(db)
    try:
        projects = await service.list_projects(
            user_id=UUID(user_id),
            workspace_id=workspace_id,
            status=status,
            limit=limit,
        )
        return {"projects": projects, "count": len(projects)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Get a single project by ID."""
    service = ProjectService(db)
    try:
        result = await service.get_project(project_id)
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/artifacts")
async def get_project_with_artifacts(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Get a project with all its linked dashboards, reports, and alerts."""
    service = ProjectService(db)
    try:
        result = await service.get_project_with_artifacts(project_id)
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{project_id}")
async def update_project(
    project_id: UUID,
    project: ProjectUpdate,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Update a project."""
    service = ProjectService(db)
    try:
        update_data = project.model_dump(exclude_unset=True)
        # Rename 'metadata' key to 'project_metadata' for the model field
        if "metadata" in update_data:
            update_data["project_metadata"] = update_data.pop("metadata")
        result = await service.update_project(project_id, **update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Archive a project (soft delete)."""
    service = ProjectService(db)
    try:
        success = await service.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "archived", "project_id": str(project_id)}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Artifact Linking ====================

@router.post("/{project_id}/artifacts")
async def add_artifact_to_project(
    project_id: UUID,
    artifact: ProjectArtifactCreate,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Link a dashboard, report, or alert to a project."""
    if artifact.artifact_type not in ("dashboard", "report", "alert"):
        raise HTTPException(status_code=400, detail="artifact_type must be dashboard, report, or alert")

    service = ProjectService(db)
    try:
        result = await service.add_artifact(
            project_id=project_id,
            artifact_type=artifact.artifact_type,
            artifact_id=artifact.artifact_id,
            parent_artifact_id=artifact.parent_artifact_id,
            sequence_order=artifact.sequence_order or 0,
            metadata=artifact.metadata,
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}/artifacts/{artifact_id}")
async def remove_artifact_from_project(
    project_id: UUID,
    artifact_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
):
    """Remove an artifact link from a project."""
    service = ProjectService(db)
    try:
        success = await service.remove_artifact(project_id, artifact_id)
        if not success:
            raise HTTPException(status_code=404, detail="Artifact link not found")
        return {"status": "removed", "project_id": str(project_id), "artifact_id": str(artifact_id)}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
