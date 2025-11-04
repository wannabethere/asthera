from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

class CollaborationRequestCreate(BaseModel):
    user_id: Optional[UUID] = None  # For existing users
    email: Optional[str] = None     # For inviting by email
    message: Optional[str] = None

class CollaborationRequestResponse(BaseModel):
    id: UUID
    thread_id: Optional[UUID]
    requester_id: Optional[UUID]
    status: str
    message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class CollaborationRequestRespond(BaseModel):
    accept: bool 