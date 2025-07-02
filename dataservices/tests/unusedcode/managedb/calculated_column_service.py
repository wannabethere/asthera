from sqlalchemy.orm import Session
from app.service.dbmodel import CalculatedColumn
from app.schemas.calculated_column_schemas import (
    CalculatedColumnCreate,
    CalculatedColumnUpdate,
    CalculatedColumnRead,
)


def create_calculated_column(
    db: Session, data: CalculatedColumnCreate
) -> CalculatedColumn:
    """Create a new Calculated Column."""
    column = CalculatedColumn(**data.model_dump())
    db.add(column)
    db.commit()
    db.refresh(column)
    return CalculatedColumnRead.model_validate(column)


def get_calculated_column(db: Session, column_id: str) -> CalculatedColumn:
    """Retrieve a Calculated Column by its ID."""
    return db.query(CalculatedColumn).filter_by(calculated_column_id=column_id).first()


def update_calculated_column(
    db: Session, column_id: str, data: CalculatedColumnUpdate
) -> CalculatedColumn:
    """Partially update a Calculated Column's attributes."""
    column = get_calculated_column(db, column_id)
    if not column:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(column, field, value)

    db.commit()
    db.refresh(column)
    return column


def delete_calculated_column(db: Session, column_id: str) -> bool:
    """Remove a Calculated Column from the database."""
    column = get_calculated_column(db, column_id)
    if column:
        db.delete(column)
        db.commit()
        return True
    return False
