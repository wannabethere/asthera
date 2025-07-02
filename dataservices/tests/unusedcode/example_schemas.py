from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ExampleBase(BaseModel):
    project_id: UUID
    question: str
    sql_query: str
    context: Optional[str]
    document_reference: Optional[str]
    instructions: Optional[str]
    categories: Optional[list]
    samples: Optional[list]
    example_metadata: Optional[dict]


class ExampleCreate(ExampleBase):
    pass


class ExampleUpdate(BaseModel):
    question: Optional[str]
    sql_query: Optional[str]
    context: Optional[str]
    document_reference: Optional[str]
    instructions: Optional[str]
    categories: Optional[list]
    samples: Optional[list]
    example_metadata: Optional[dict]


class ExampleRead(ExampleBase):
    example_id: UUID

    class Config:
        from_attributes = True
