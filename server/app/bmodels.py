from pydantic import BaseModel, Field,EmailStr
from enum import Enum
from typing import Optional, Literal
from datetime import datetime

class ModelName(str, Enum):
    CLAUDE_3_5_SONNET_20240620 = "claude-3-5-sonnet-20240620"
    GPT_4_TURBO_2024_04_09 = "gpt-4-turbo-2024-04-09"
    GPT_3_5_TURBO_2025_31_03 = "gpt-3.5-turbo"
    GPT_4="gpt-4o-mini"

class ChatRequest(BaseModel):
    user_input: str
    model_name: ModelName = Field(default=ModelName.GPT_4)
    temperature: float = Field(default=0.0)
    recursion_limit: int = Field(default=25)

class ChatResponse(BaseModel):
    response: str
    session_id: str
    question_id: Optional[str] = None
    plot_url: Optional[str] = None

class addChat(BaseModel):
    questionId:str
    questionName:str
    sessionId:str
    addedDate:Optional[str] = datetime.now()
    response:dict

    

class UserIn(BaseModel):
    email: str
    password: str
    name: str

class SignUpRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str


class CollaboratorRequest(BaseModel):
    session_id: str
    collaborator_email: EmailStr
    role: Literal["read", "read-write"]