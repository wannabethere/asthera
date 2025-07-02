from sqlalchemy.orm import Session
from app.service.dbmodel import SQLFunction
from app.schemas.sql_functions_schemas import (
    SQLFunctionCreate,
    SQLFunctionUpdate,
    SQLFunctionRead,
)

def create_sql_function(db: Session, data: SQLFunctionCreate) -> SQLFunctionRead:
    """Create a new SQL function."""
    sql_function = SQLFunction(**data.model_dump())
    db.add(sql_function)
    db.commit()
    db.refresh(sql_function)
    return SQLFunctionRead.model_validate(sql_function)

def get_sql_function(db: Session, function_id: str) -> SQLFunction:
    """Retrieve a SQL function by its ID."""
    return db.query(SQLFunction).filter_by(function_id=function_id).first()

def update_sql_function(db: Session, function_id: str, data: SQLFunctionUpdate) -> SQLFunction:
    """Partially update a SQL function's attributes."""
    sql_function = get_sql_function(db, function_id)
    if not sql_function:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sql_function, field, value)
    db.commit()
    db.refresh(sql_function)
    return sql_function

def delete_sql_function(db: Session, function_id: str) -> bool:
    """Remove a SQL function from the database."""
    sql_function = get_sql_function(db, function_id)
    if sql_function:
        db.delete(sql_function)
        db.commit()
        return True
    return False
