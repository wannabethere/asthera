from sqlalchemy.orm import Session
from app.service.dbmodel import Columns
from app.schemas.column_schemas import ColumnCreate, ColumnUpdate, ColumnRead


from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

def create_column(db: Session, data: ColumnCreate) -> Columns:
    """Create a new Column."""
    column = Columns(**data.model_dump())
    db.add(column)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Check for unique constraint violation on (table_id, name)
        if 'uq_columns_table_name' in str(e.orig):
            raise HTTPException(status_code=409, detail="Column with this name already exists for this table.")
        raise
    db.refresh(column)
    return ColumnRead.model_validate(column)


def get_column(db: Session, column_id: str) -> Columns:
    """Retrieve a Column by its ID."""
    return db.query(Columns).filter_by(column_id=column_id).first()


def update_column(db: Session, column_id: str, data: ColumnUpdate) -> Columns:
    """Partially update a Column's attributes."""
    column = get_column(db, column_id)
    if not column:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(column, field, value)

    db.commit()
    db.refresh(column)
    return column


def delete_column(db: Session, column_id: str) -> bool:
    """Remove a Column from the database."""
    column = get_column(db, column_id)
    if column:
        db.delete(column)
        db.commit()
        return True
    return False
