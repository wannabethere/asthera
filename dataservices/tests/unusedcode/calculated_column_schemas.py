from typing import Optional
from pydantic import BaseModel


import uuid

class CalculatedColumnBase(BaseModel):
    column_id: uuid.UUID
    calculation_sql: str


class CalculatedColumnCreate(CalculatedColumnBase):
    pass


class CalculatedColumnUpdate(BaseModel):
    calculation_sql: Optional[str] = None


class CalculatedColumnRead(CalculatedColumnBase):
    calculated_column_id: uuid.UUID

    class Config:
        from_attributes = True
