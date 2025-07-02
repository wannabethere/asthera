from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class InstructionBase(BaseModel):
    project_id: UUID
    question: str

    instructions: Optional[str]
    sql_query: Optional[str]
    chain_of_thought: Optional[str]


class InstructionCreate(InstructionBase):
    pass


class InstructionUpdate(BaseModel):
    question: Optional[str]

    instructions: Optional[str]
    sql_query: Optional[str]
    chain_of_thought: Optional[str]


class InstructionRead(InstructionBase):
    instruction_id: UUID
    question: Optional[str]
    instructions: Optional[str]
    sql_query: Optional[str]
    chain_of_thought: Optional[str]
    class Config:
        from_attributes = True
