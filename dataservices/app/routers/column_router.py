from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.column_service import (
    create_column,
    get_column,
    update_column,
    delete_column,
)
from app.schemas.column_schemas import ColumnCreate, ColumnUpdate, ColumnRead

router = APIRouter()


@router.post("/columns/", response_model=ColumnRead, summary="Create a new column.")
async def create(data: ColumnCreate, db: Session = Depends(get_db)):
    """Create a new column within a table."""
    return create_column(db, data)


@router.get(
    "/columns/{column_id}",
    response_model=ColumnRead,
    summary="Retrieve a column by its ID.",
)
async def read(column_id: str, db: Session = Depends(get_db)):
    """Retrieve a column by its unique ID."""
    column = get_column(db, column_id)
    if not column:
        raise HTTPException(404, "Not found.")
    return column


@router.patch(
    "/columns/{column_id}", response_model=ColumnRead, summary="Update a column."
)
async def update(column_id: str, data: ColumnUpdate, db: Session = Depends(get_db)):
    """Partially update a column's details."""
    column = update_column(db, column_id, data)
    if not column:
        raise HTTPException(404, "Not found.")
    return column


@router.delete("/columns/{column_id}", summary="Delete a column.")
async def delete(column_id: str, db: Session = Depends(get_db)):
    """Remove a column from the database."""
    if not delete_column(db, column_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
