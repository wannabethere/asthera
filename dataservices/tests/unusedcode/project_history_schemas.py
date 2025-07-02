from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel,Field



class ProjectHistoryBase(BaseModel):
    project_id: UUID
    table_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    action: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    new_entity_version: Optional[int] = None
    changed_by: Optional[str] = None
    change_description: Optional[str] = None
    project_version_before: Optional[str] = None
    project_version_after: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectHistoryCreate(ProjectHistoryBase):
    pass


class ProjectHistoryUpdate(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    action: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    new_entity_version: Optional[int] = None
    changed_by: Optional[str] = None
    change_description: Optional[str] = None

class ProjectHistoryRead(ProjectHistoryBase):
    project_history_id: UUID = Field(..., alias="history_id")

    class Config:
        from_attributes = True
        populate_by_name = True
