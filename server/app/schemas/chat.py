from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, List,Dict
 
class MessageCreate(BaseModel):
    message: str
    thread_id: UUID
 
class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    user_id: UUID
    content: Dict
    created_at: datetime
    updated_at: Optional[datetime]
    response:Dict
    status : str
 
    class Config:
        from_attributes = True
 
class ChatHistoryResponse(BaseModel):
    thread_id: UUID
    messages: List[MessageResponse]

class ExpandQuery(BaseModel):
    query: str
    sql:str
    original_query:str
    original_reasoning:str
    project_id:str
    configuration:Optional[Dict] = {}
    schema_context:Optional[Dict] = {}