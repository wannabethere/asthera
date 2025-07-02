from sqlalchemy.orm import Session
from app.service.dbmodel import ProjectVersionHistory
from app.schemas.project_version_history_schemas import (
    ProjectVersionHistoryCreate,
    ProjectVersionHistoryUpdate,
    ProjectVersionHistoryRead,
)


def create_project_version_history(
    db: Session, data: ProjectVersionHistoryCreate
) -> ProjectVersionHistory:
    """Create a new Project Version History."""
    version = ProjectVersionHistory(**data.model_dump())
    db.add(version)
    db.commit()
    db.refresh(version)
    return ProjectVersionHistoryRead.model_validate(version)


def get_project_version_history(db: Session, version_id: str) -> ProjectVersionHistory:
    """Retrieve a Project Version History by its ID."""
    return db.query(ProjectVersionHistory).filter_by(version_history_id=version_id).first()


def update_project_version_history(
    db: Session, version_id: str, data: ProjectVersionHistoryUpdate
) -> ProjectVersionHistory:
    """Partially update a Project Version History's attributes."""
    version = get_project_version_history(db, version_id)
    if not version:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(version, field, value)

    db.commit()
    db.refresh(version)
    return ProjectVersionHistoryRead.model_validate(version)


def delete_project_version_history(db: Session, version_id: str) -> bool:
    """Remove a Project Version History from the database."""
    version = get_project_version_history(db, version_id)
    if version:
        db.delete(version)
        db.commit()
        return True
    return False
