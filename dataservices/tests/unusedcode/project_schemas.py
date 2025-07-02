from cgitb import text
from typing import Optional
import uuid
from pydantic import BaseModel


class ProjectBase(BaseModel):
    project_id: uuid.UUID
    display_name: str
    description: Optional[str] = None
    created_by: Optional[str] = None
    status: Optional[str] = "active"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None


class ProjectRead(BaseModel):
    project_id: uuid.UUID
    display_name: str
    description: Optional[str] = None
    created_by: Optional[str] = None
    status: Optional[str] = "active"

    class Config:
        from_attributes = True
