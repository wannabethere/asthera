from typing import Dict, List, Any, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas.document_schemas import DocumentType
from app.agentic.orchestration.parallel_workflow import ParallelWorkflow
from app.routers.semantic_router import SemanticRouter, AgentType
from langchain_openai import ChatOpenAI

router = APIRouter(
    prefix="/agentic",
    tags=["agentic"],
)

class MessageType(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"
    TOOL = "tool"

class Message(BaseModel):
    message_type: MessageType
    message_content: str
    message_id: str
    message_extra: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    question: str
    source_type: str = DocumentType.GENERIC.value

class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]]

@router.post("/chat", response_model=ChatResponse)
async def process_chat(request: ChatRequest):
    """
    Process a chat request through the appropriate agent
    """
    try:
        # Initialize models
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Initialize router
        router = SemanticRouter(llm=llm)
        
        # Decide which agent to use
        routing_decision = await router.route_question(
            question=request.question,
            chat_history=request.messages
        )
        
        # For now, let's use ParallelWorkflow for all requests
        if routing_decision.primary_agent == AgentType.SELF_RAG:
            # Initialize the ParallelWorkflow agent with the OpenAI LLM
            parallel_workflow = ParallelWorkflow(llm=llm)
            
            # Run the agent
            response = await parallel_workflow.run_workflow(
                messages=request.messages,
                question=request.question
            )
            
            return response
        else:
            # For now, default to ParallelWorkflow if any other agent is chosen
            parallel_workflow = ParallelWorkflow(llm=llm)
            
            # Run the agent
            response = await parallel_workflow.run_workflow(
                messages=request.messages,
                question=request.question
            )
            
            return response
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing chat request: {str(e)}"
        ) 