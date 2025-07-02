from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.project_version_history_service import (
    create_project_version_history,
    get_project_version_history,
    update_project_version_history,
    delete_project_version_history,
)
from app.schemas.project_version_history_schemas import (
    ProjectVersionHistoryCreate,
    ProjectVersionHistoryUpdate,
    ProjectVersionHistoryRead,
)

router = APIRouter()


@router.post(
    "/project-versions/",
    response_model=ProjectVersionHistoryRead,
    summary="Create a new project version.",
)
async def create(data: ProjectVersionHistoryCreate, db: Session = Depends(get_db)):
    """Create a new project version history record."""
    return create_project_version_history(db, data)


@router.get(
    "/project-versions/{version_id}",
    response_model=ProjectVersionHistoryRead,
    summary="Retrieve a project version.",
)
async def read(version_id: str, db: Session = Depends(get_db)):
    """Retrieve a project version history by its unique ID."""
    version = get_project_version_history(db, version_id)
    if not version:
        raise HTTPException(404, "Not found.")
    return version


@router.patch(
    "/project-versions/{version_id}",
    response_model=ProjectVersionHistoryRead,
    summary="Update a project version.",
)
async def update(
    version_id: str, data: ProjectVersionHistoryUpdate, db: Session = Depends(get_db)
):
    """Partially update a project version's details."""
    version = update_project_version_history(db, version_id, data)
    if not version:
        raise HTTPException(404, "Not found.")
    return version


@router.delete("/project-versions/{version_id}", summary="Delete a project version.")
async def delete(version_id: str, db: Session = Depends(get_db)):
    """Remove a project version from the database."""
    if not delete_project_version_history(db, version_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
