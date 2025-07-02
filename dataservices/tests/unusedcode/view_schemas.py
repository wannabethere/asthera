from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class ViewBase(BaseModel):
    table_id: UUID
    name: str
    display_name: str
    description: Optional[str]
    view_sql: str
    view_type: str


class ViewCreate(ViewBase):
    pass


class ViewUpdate(BaseModel):
    name: Optional[str] = None      
    display_name: Optional[str] = None
    description: Optional[str] = None


from datetime import datetime

class ViewRead(ViewBase):
    view_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
