from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

class ThreadBase(BaseModel):
    title: str
    description: str = "No description provided"

class ThreadCreate(ThreadBase):
    project_id: UUID
    created_by: Optional[UUID] = None

class ThreadMessageBase(BaseModel):
    content: Dict[str, Any]

class ThreadMessageCreate(ThreadMessageBase):
    user_id: UUID

class WorkflowStep(BaseModel):
    step_type: str
    description: str
    data: Dict[str, Any] = Field(default_factory=dict)

class WorkflowBase(BaseModel):
    title: str
    description: Optional[str] = None
    steps: List[WorkflowStep] = Field(default_factory=list)
    status: str = "draft"

class WorkflowCreate(WorkflowBase):
    user_id: UUID

class NoteBase(BaseModel):
    title: str
    content: str

class NoteCreate(NoteBase):
    user_id: UUID

class TimelineEvent(BaseModel):
    event_type: str
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)

class TimelineBase(BaseModel):
    title: str
    description: Optional[str] = None
    events: List[TimelineEvent] = Field(default_factory=list)

class TimelineCreate(TimelineBase):
    user_id: UUID

# Response models
class ThreadMessage(ThreadMessageBase):
    id: UUID
    thread_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class Workflow(WorkflowBase):
    id: UUID
    thread_id: UUID
    user_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class Note(NoteBase):
    id: UUID
    thread_id: UUID
    user_id: UUID
    title: str
    content: str
    sortorder: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class Timeline(TimelineBase):
    id: UUID
    thread_id: UUID
    user_id: UUID
    title: str
    description: Optional[str] = None
    events: List[TimelineEvent] = Field(default_factory=list)
    sortorder: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class Thread(ThreadBase):
    id: UUID
    project_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool
    messages: List[ThreadMessage] = []
    workflows: List[Workflow] = []
    notes: List[Note] = []
    timelines: List[Timeline] = []
    workspace_id: Optional[UUID] = None
    workspace_name: Optional[str] = None
    project_name: Optional[str] = None

    class Config:
        orm_mode = True

class ThreadCollaboratorBase(BaseModel):
    role: str = "collaborator"
    message: Optional[str] = None
    data_connection: Optional[Dict[str, Any]] = None

class ThreadCollaboratorCreate(ThreadCollaboratorBase):
    user_id: UUID
    

class ThreadCollaboratorUpdate(ThreadCollaboratorBase):
    status: Optional[str] = None

class ThreadCollaborator(ThreadCollaboratorBase):
    id: UUID
    user_id: UUID
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ThreadConfigurationBase(BaseModel):
    name: str
    config: Dict[str, Any]
    is_default: bool = False

class ThreadConfigurationCreate(ThreadConfigurationBase):
    thread_id: UUID

class ThreadConfigurationUpdate(ThreadConfigurationBase):
    pass

class ThreadConfiguration(ThreadConfigurationBase):
    id: UUID
    thread_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 