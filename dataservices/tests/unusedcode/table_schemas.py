import uuid
from typing import Optional
from pydantic import BaseModel

class TableBase(BaseModel):
    project_id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    description: Optional[str] = None


class TableCreate(TableBase):
    pass


class TableUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TableRead(TableBase):
    table_id: uuid.UUID

    class Config:
        from_attributes = True
