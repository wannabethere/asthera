from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.project_history_service import (
    create_project_history,
    get_project_history,
    update_project_history,
    delete_project_history,
)
from app.schemas.project_history_schemas import (
    ProjectHistoryCreate,
    ProjectHistoryUpdate,
    ProjectHistoryRead,
)

router = APIRouter()


@router.post(
    "/project-histories/",
    response_model=ProjectHistoryRead,
    summary="Create a new project history.",
)
async def create(data: ProjectHistoryCreate, db: Session = Depends(get_db)):
    """Create a new project history record."""
    return create_project_history(db, data)


@router.get(
    "/project-histories/{history_id}",
    response_model=ProjectHistoryRead,
    summary="Retrieve a project history.",
)
async def read(history_id: str, db: Session = Depends(get_db)):
    """Retrieve a project history by its unique ID."""
    history = get_project_history(db, history_id)
    if not history:
        raise HTTPException(404, "Not found.")
    return history


@router.patch(
    "/project-histories/{history_id}",
    response_model=ProjectHistoryRead,
    summary="Update a project history.",
)
async def update(
    history_id: str, data: ProjectHistoryUpdate, db: Session = Depends(get_db)
):
    """Partially update a project history's details."""
    history = update_project_history(db, history_id, data)
    if not history:
        raise HTTPException(404, "Not found.")
    return history


@router.delete("/project-histories/{history_id}", summary="Delete a project history.")
async def delete(history_id: str, db: Session = Depends(get_db)):
    """Remove a project history from the database."""
    if not delete_project_history(db, history_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
