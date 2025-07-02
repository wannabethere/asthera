from typing import Optional, Any
from pydantic import BaseModel
import uuid

class SQLFunctionBase(BaseModel):
    project_id: uuid.UUID
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    function_sql: str
    return_type: Optional[str] = None
    parameters: Optional[Any] = None

class SQLFunctionCreate(SQLFunctionBase):
    pass

class SQLFunctionUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    function_sql: Optional[str] = None
    return_type: Optional[str] = None
    parameters: Optional[Any] = None

class SQLFunctionRead(SQLFunctionBase):
    function_id: uuid.UUID

    class Config:
        from_attributes = True
