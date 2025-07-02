from sqlalchemy.orm import Session
from app.service.dbmodel import ProjectHistory
from app.schemas.project_history_schemas import (
    ProjectHistoryCreate,
    ProjectHistoryUpdate,
    ProjectHistoryRead,
)


def create_project_history(db: Session, data: ProjectHistoryCreate) -> ProjectHistory:
    """Create a new Project History."""
    history = ProjectHistory(**data.model_dump())
    db.add(history)
    db.commit()
    db.refresh(history)
    return ProjectHistoryRead.model_validate(history)


def get_project_history(db: Session, history_id: str) -> ProjectHistory:
    """Retrieve a ProjectHistory by its ID."""
    return db.query(ProjectHistory).filter_by(history_id=history_id).first()


def update_project_history(
    db: Session, history_id: str, data: ProjectHistoryUpdate
) -> ProjectHistory:
    """Partially update a Project History's attributes."""
    history = get_project_history(db, history_id)
    if not history:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(history, field, value)

    db.commit()
    db.refresh(history)
    return history


def delete_project_history(db: Session, history_id: str) -> bool:
    """Remove a Project History from the database."""
    history = get_project_history(db, history_id)
    if history:
        db.delete(history)
        db.commit()
        return True
    return False
