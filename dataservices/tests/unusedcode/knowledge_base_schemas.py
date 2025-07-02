from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class KnowledgeBaseBase(BaseModel):
    project_id: UUID
    name: str
    display_name: Optional[str] = None
    file_path: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    file_path: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseRead(BaseModel):
    knowledge_base_id: UUID = Field(..., alias="kb_id")
    project_id: UUID
    name: str
    display_name: Optional[str] = None
    file_path: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True
