from uuid import UUID
from typing import Optional
from pydantic import BaseModel


import uuid

class DatasetBase(BaseModel):
    project_id: uuid.UUID
    name: str
    description: Optional[str] = None


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DatasetRead(DatasetBase):
    dataset_id: UUID

    class Config:
        from_attributes = True
