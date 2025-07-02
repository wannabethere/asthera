import uuid
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.dbmodel import Project
from app.schemas.project_schemas import ProjectCreate, ProjectUpdate, ProjectRead


def create_project(db: Session, project_data: ProjectCreate):
    project = Project(**project_data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project)


def get_project(db: Session, project_id: uuid.UUID):
    return db.query(Project).filter_by(project_id=project_id).first()


def update_project(db: Session, project_id: uuid.UUID, data: ProjectUpdate):
    project = get_project(db, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project)


def delete_project(db: Session, project_id: uuid.UUID):
    project = get_project(db, project_id)
    if project:
        db.delete(project)
        db.commit()
        return True
    return False
