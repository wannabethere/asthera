from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.project_service import (
    create_project,
    get_project,
    update_project,
    delete_project,
)
from app.schemas.project_schemas import ProjectCreate, ProjectUpdate, ProjectRead
from uuid import UUID

router = APIRouter()

from sqlalchemy.exc import IntegrityError


@router.post("/projects/", response_model=ProjectRead, summary="Create a new project.")
async def create(data: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project in the database."""
    try:
        return create_project(db, data)
    except IntegrityError as e:
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(
                status_code=409, detail="A project with this project_id already exists."
            )
        raise


@router.get(
    "/projects/{project_id}",
    response_model=ProjectRead,
    summary="Retrieve a project by its ID.",
)
async def read(project_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a project by its unique ID."""
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(404, "Not found.")
    return project


@router.patch(
    "/projects/{project_id}", response_model=ProjectRead, summary="Update a project."
)
async def update(project_id: UUID, data: ProjectUpdate, db: Session = Depends(get_db)):
    """Partially update a project's details."""
    project = update_project(db, project_id, data)
    if not project:
        raise HTTPException(404, "Not found.")
    return project


@router.delete("/projects/{project_id}")
async def delete(project_id: UUID, db: Session = Depends(get_db)):
    """Remove a project from the database."""
    if not delete_project(db, project_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
