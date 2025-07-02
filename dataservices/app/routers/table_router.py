from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.table_service import (
    create_table,
    get_table,
    update_table,
    delete_table,
)
from app.schemas.table_schemas import TableCreate, TableUpdate, TableRead

router = APIRouter()


@router.post("/tables/", response_model=TableRead, summary="Create a new table.")
async def create(data: TableCreate, db: Session = Depends(get_db)):
    """Create a new table within a dataset or project."""
    return create_table(db, data)


@router.get(
    "/tables/{table_id}",
    response_model=TableRead,
    summary="Retrieve a table by its ID.",
)
async def read(table_id: str, db: Session = Depends(get_db)):
    """Retrieve a table by its unique ID."""
    table = get_table(db, table_id)
    if not table:
        raise HTTPException(404, "Not found.")
    return table


@router.patch("/tables/{table_id}", response_model=TableRead, summary="Update a table.")
async def update(table_id: str, data: TableUpdate, db: Session = Depends(get_db)):
    """Partially update a table's details."""
    table = update_table(db, table_id, data)
    if not table:
        raise HTTPException(404, "Not found.")
    return table


@router.delete("/tables/{table_id}", summary="Delete a table.")
async def delete(table_id: str, db: Session = Depends(get_db)):
    """Remove a table from the database."""
    if not delete_table(db, table_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
