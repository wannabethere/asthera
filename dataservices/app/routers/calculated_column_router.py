from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.calculated_column_service import (
    create_calculated_column,
    get_calculated_column,
    update_calculated_column,
    delete_calculated_column,
)
from app.schemas.calculated_column_schemas import (
    CalculatedColumnCreate,
    CalculatedColumnUpdate,
    CalculatedColumnRead,
)

router = APIRouter()


@router.post(
    "/calculated-columns/",
    response_model=CalculatedColumnRead,
    summary="Create a new calculated column.",
)
async def create(data: CalculatedColumnCreate, db: Session = Depends(get_db)):
    """Create a new calculated column within a table."""
    return create_calculated_column(db, data)


@router.get(
    "/calculated-columns/{calculated_column_id}",
    response_model=CalculatedColumnRead,
    summary="Retrieve a calculated column by its ID.",
)
async def read(calculated_column_id: str, db: Session = Depends(get_db)):
    """Retrieve a calculated column by its unique ID."""
    column = get_calculated_column(db, calculated_column_id)
    if not column:
        raise HTTPException(404, "Not found.")
    return column


@router.patch(
    "/calculated-columns/{calculated_column_id}",
    response_model=CalculatedColumnRead,
    summary="Update a calculated column.",
)
async def update(
    calculated_column_id: str,
    data: CalculatedColumnUpdate,
    db: Session = Depends(get_db),
):
    """Partially update a calculated column's details."""
    column = update_calculated_column(db, calculated_column_id, data)
    if not column:
        raise HTTPException(404, "Not found.")
    return column


@router.delete(
    "/calculated-columns/{calculated_column_id}", summary="Delete a calculated column."
)
async def delete(calculated_column_id: str, db: Session = Depends(get_db)):
    """Remove a calculated column from the database."""
    if not delete_calculated_column(db, calculated_column_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
