from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, List

class MessageCreate(BaseModel):
    message: str
    thread_id: UUID

class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ChatHistoryResponse(BaseModel):
    thread_id: UUID
    messages: List[MessageResponse] 