from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.database import get_db
from app.service.sql_functions_service import (
    create_sql_function,
    get_sql_function,
    update_sql_function,
    delete_sql_function,
)
from app.schemas.sql_functions_schemas import (
    SQLFunctionCreate,
    SQLFunctionUpdate,
    SQLFunctionRead,
)

router = APIRouter()

@router.post(
    "/sql-functions/",
    response_model=SQLFunctionRead,
    summary="Create a new SQL function.",
)
async def create(data: SQLFunctionCreate, db: Session = Depends(get_db)):
    """Create a new SQL function."""
    return create_sql_function(db, data)

@router.get(
    "/sql-functions/{function_id}",
    response_model=SQLFunctionRead,
    summary="Retrieve a SQL function by its ID.",
)
async def read(function_id: str, db: Session = Depends(get_db)):
    """Retrieve a SQL function by its unique ID."""
    sql_function = get_sql_function(db, function_id)
    if not sql_function:
        raise HTTPException(404, "Not found.")
    return sql_function

@router.patch(
    "/sql-functions/{function_id}",
    response_model=SQLFunctionRead,
    summary="Update a SQL function.",
)
async def update(
    function_id: str,
    data: SQLFunctionUpdate,
    db: Session = Depends(get_db),
):
    """Partially update a SQL function's details."""
    sql_function = update_sql_function(db, function_id, data)
    if not sql_function:
        raise HTTPException(404, "Not found.")
    return sql_function

@router.delete(
    "/sql-functions/{function_id}", summary="Delete a SQL function."
)
async def delete(function_id: str, db: Session = Depends(get_db)):
    """Remove a SQL function from the database."""
    if not delete_sql_function(db, function_id):
        raise HTTPException(404, "Not found.")
    return {"message": "Deleted"}
