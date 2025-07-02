from sqlalchemy.orm import Session
from app.service.dbmodel import View
from app.schemas.view_schemas import ViewCreate, ViewUpdate, ViewRead


def create_view(db: Session, data: ViewCreate) -> View:
    """Create a new View."""
    view = View(**data.model_dump())
    db.add(view)
    db.commit()
    db.refresh(view)
    return ViewRead.model_validate(view)


def get_view(db: Session, view_id: str) -> View:
    """Retrieve a View by its ID."""
    return db.query(View).filter_by(view_id=view_id).first()


def update_view(db: Session, view_id: str, data: ViewUpdate) -> View:
    """Partially update a View's attributes."""
    view = get_view(db, view_id)
    if not view:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(view, field, value)

    db.commit()
    db.refresh(view)
    return ViewRead.model_validate(view)


def delete_view(db: Session, view_id: str) -> bool:
    """Remove a View from the database."""
    view = get_view(db, view_id)
    if view:
        db.delete(view)
        db.commit()
        return True
    return False
