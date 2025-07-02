from typing import Optional
from pydantic import BaseModel


import uuid

class ColumnBase(BaseModel):
    table_id: uuid.UUID
    name: str
    data_type: str
    description: Optional[str] = None


class ColumnCreate(ColumnBase):
    pass


class ColumnUpdate(BaseModel):
    name: Optional[str] = None
    data_type: Optional[str] = None
    description: Optional[str] = None


class ColumnRead(ColumnBase):
    column_id: uuid.UUID

    class Config:
        from_attributes = True
