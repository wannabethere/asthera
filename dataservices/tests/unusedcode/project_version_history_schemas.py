from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field           
from datetime import datetime


class ProjectVersionHistoryBase(BaseModel):
    project_id: UUID
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    change_type: str
    triggered_by_entity: str
    triggered_by_entity_id: Optional[UUID] = None
    triggered_by_user: Optional[str] = None
    change_description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectVersionHistoryCreate(ProjectVersionHistoryBase):
    pass


class ProjectVersionHistoryUpdate(BaseModel):
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    change_type: Optional[str] = None
    triggered_by_entity: Optional[str] = None
    triggered_by_entity_id: Optional[UUID] = None
    triggered_by_user: Optional[str] = None
    change_description: Optional[str] = None


class ProjectVersionHistoryRead(ProjectVersionHistoryBase):
    version_history_id: UUID = Field(..., alias="version_history_id")

    class Config:
        from_attributes = True
        populate_by_name = True
