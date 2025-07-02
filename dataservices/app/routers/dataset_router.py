from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.dataset_service import (
    create_dataset,
    get_dataset,
    update_dataset,
    delete_dataset,
)
from app.schemas.dataset_schemas import DatasetCreate, DatasetUpdate, DatasetRead

router = APIRouter()


@router.post("/datasets/", response_model=DatasetRead, summary="Create a new dataset.")
async def create(data: DatasetCreate, db: Session = Depends(get_db)):
    """Create a new dataset within a project."""
    return create_dataset(db, data)


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetRead,
    summary="Retrieve a dataset by its ID.",
)
async def read(dataset_id: str, db: Session = Depends(get_db)):
    """Retrieve a dataset by its unique ID."""
    dataset = get_dataset(db, dataset_id)
    if not dataset:
        raise HTTPException(404, "Not found.")
    return dataset


@router.patch(
    "/datasets/{dataset_id}", response_model=DatasetRead, summary="Update a dataset."
)
async def update(dataset_id: str, data: DatasetUpdate, db: Session = Depends(get_db)):
    """Partially update a dataset's details."""
    dataset = update_dataset(db, dataset_id, data)
    if not dataset:
        raise HTTPException(404, "Not found.")
    return dataset


@router.delete("/datasets/{dataset_id}", summary="Delete a dataset.")
async def delete(dataset_id: str, db: Session = Depends(get_db)):
    """Remove a dataset from the database."""
    if not delete_dataset(db, dataset_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
