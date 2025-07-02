from sqlalchemy.orm import Session
from app.service.dbmodel import Table
from app.schemas.table_schemas import TableCreate, TableUpdate, TableRead


def create_table(db: Session, data: TableCreate) -> Table:
    """Create a new Table."""
    table = Table(**data.model_dump())
    db.add(table)
    db.commit()
    db.refresh(table)
    return TableRead.model_validate(table)


def get_table(db: Session, table_id: str) -> Table:
    """Retrieve a Table by its ID."""
    return db.query(Table).filter_by(table_id=table_id).first()


def update_table(db: Session, table_id: str, data: TableUpdate) -> Table:
    """Partially update a Table's attributes."""
    table = get_table(db, table_id)
    if not table:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(table, field, value)

    db.commit()
    db.refresh(table)
    return table


def delete_table(db: Session, table_id: str) -> bool:
    """Remove a Table from the database."""
    table = get_table(db, table_id)
    if table:
        db.delete(table)
        db.commit()
        return True
    return False
