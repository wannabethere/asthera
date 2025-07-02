import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.service.dbmodel import Dataset, Project
from app.schemas.dataset_schemas import DatasetCreate, DatasetUpdate, DatasetRead


def create_dataset(db: Session, data: DatasetCreate) -> DatasetRead:
    """Create a new Dataset under an existing Project."""

    project = db.query(Project).filter_by(project_id=data.project_id).first()
    if not project:
        raise HTTPException(404, f"Project {data.project_id} not found.")

    existing = (
        db.query(Dataset).filter_by(project_id=data.project_id, name=data.name).first()
    )
    if existing:
        raise HTTPException(
            409, f"Dataset with name '{data.name}' already exists for this project."
        )

    dataset = Dataset(
        dataset_id=uuid.uuid4(), 
        project_id=data.project_id,
        name=data.name,
        description=data.description,
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return DatasetRead.model_validate(dataset)


def get_dataset(db: Session, dataset_id: str) -> Dataset:
    """Retrieve a Dataset by its ID."""
    return db.query(Dataset).filter_by(dataset_id=dataset_id).first()


def update_dataset(db: Session, dataset_id: str, data: DatasetUpdate) -> Dataset:
    """Partially update a Dataset's attributes."""
    dataset = get_dataset(db, dataset_id)
    if not dataset:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dataset, field, value)

    db.commit()
    db.refresh(dataset)
    return dataset


def delete_dataset(db: Session, dataset_id: str) -> bool:
    """Remove a Dataset from the database."""
    dataset = get_dataset(db, dataset_id)
    if dataset:
        db.delete(dataset)
        db.commit()
        return True
    return False
