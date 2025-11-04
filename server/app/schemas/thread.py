from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field,validator
from enum import Enum
from datetime import datetime

class ThreadBase(BaseModel):
    title: str
    description: str = "No description provided"

class ThreadCreate(ThreadBase):
    project_id: UUID
    dataset_id:str
    dataset_name:str
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
    user_id: Optional[UUID]

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

class WorkflowType(str, Enum):
    DASHBOARD = "dashboard"
    REPORT = "report"
    ALERTS = "alerts"

class RequestType(str, Enum):
    DASHBOARD = "dashboard"
    ALERTS = "alerts"
    REPORTS = "reports"
 
# Request models
class AddWorkflowRequest(BaseModel):
    workflow_id: str
    workflow_type: WorkflowType

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
        from_attributes=True

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

class TraceCreate(BaseModel):
    auditid: str
    sequence: int = Field(..., ge=1, description="Step sequence (1, 2, or 3)")
    component: str
    status: str = Field(default="pending", description="Status: pending, running, completed, failed")
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    time_taken: Optional[float] = Field(None, ge=0, description="Time taken in seconds")
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['pending', 'running', 'completed', 'failed']
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v

class TraceUpdate(BaseModel):
    component: Optional[str] = None
    status: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    time_taken: Optional[float] = Field(None, ge=0)
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            allowed_statuses = ['pending', 'running', 'completed', 'failed']
            if v not in allowed_statuses:
                raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v

class TraceResponse(BaseModel):
    trace_id: str
    auditid: str
    sequence: int
    timestamp: datetime
    component: str
    status: str
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    time_taken: Optional[float]
    
    class Config:
        from_attributes = True

class AuditCreate(BaseModel):
    user_id: str 
    message_id: str 
    auditName: Optional[str] = None 
    steps: Optional[int] = Field(default=3, ge=1, le=10)
    
class AuditUpdate(BaseModel):
    auditName: Optional[str] = None
    steps: Optional[int] = Field(None, ge=1, le=10)

class AuditWithTracesCreate(BaseModel):
    user_id: str
    message_id: str
    auditName: Optional[str] = None
    components: List[str] = Field(..., min_items=3, max_items=3, description="Exactly 3 component names")







class AuditFilters(BaseModel):
    """All filter options in one place"""
    user_id: str
    thread_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    cursor: Optional[str] = None  # ISO timestamp
    limit: int = Field(default=20, ge=1, le=100)
    def get_cursor_datetime(self) -> Optional[datetime]:
        if not self.cursor:
            return None
        try:
            return datetime.fromisoformat(self.cursor.replace('Z', '+00:00'))
        except ValueError:
            return None
 
class AuditResponse(BaseModel):
    auditid: str
    auditName: str
    messageid: UUID
    timestamp: datetime
    total_time: Optional[float] 
    threadid: Optional[UUID] = None
    threadName: Optional[str] = None
    steps: int
    user_id: UUID
    traces: List[Dict[str, Any]] = []
    class Config:
        from_attributes = True
 
class PaginatedAuditResponse(BaseModel):
    audits: List[AuditResponse]
    next_cursor: Optional[str] = None
    has_more: bool = False
    count: int