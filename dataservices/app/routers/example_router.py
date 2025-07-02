from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.example_service import (
    create_example,
    get_example,
    update_example,
    delete_example,
)
from app.schemas.example_schemas import ExampleCreate, ExampleUpdate, ExampleRead

router = APIRouter()


@router.post("/examples/", response_model=ExampleRead, summary="Create a new example.")
async def create(data: ExampleCreate, db: Session = Depends(get_db)):
    """Create a new example within a project."""
    return create_example(db, data)


@router.get(
    "/examples/{example_id}", response_model=ExampleRead, summary="Retrieve an example."
)
async def read(example_id: str, db: Session = Depends(get_db)):
    """Retrieve an example by its unique ID."""
    example = get_example(db, example_id)
    if not example:
        raise HTTPException(404, "Not found.")
    return example


@router.patch(
    "/examples/{example_id}", response_model=ExampleRead, summary="Update an example."
)
async def update(example_id: str, data: ExampleUpdate, db: Session = Depends(get_db)):
    """Partially update an example's details."""
    example = update_example(db, example_id, data)
    if not example:
        raise HTTPException(404, "Not found.")
    return example


@router.delete("/examples/{example_id}", summary="Delete an example.")
async def delete(example_id: str, db: Session = Depends(get_db)):
    """Remove an example from the database."""
    if not delete_example(db, example_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
