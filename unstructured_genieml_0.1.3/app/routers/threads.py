from typing import Any, List

from fastapi import APIRouter
from pydantic import BaseModel

from app.handlers import thread_handler

router = APIRouter(
    prefix="/threads",
    tags=["threads"],
)


class ChatRequest(BaseModel):
    prompt: str
    thread_id: str | None = None
    return_new_messages_only: bool = True
    document_ids: List[str] | None = None


class Message(BaseModel):
    id: str | None = None
    role: str
    content: Any | None = None


class ChatResponse(BaseModel):
    messages: List[Message]
    thread_id: str


class Thread(BaseModel):
    id: str
    name: str
    user_id: int | None = None


class ThreadWithMessages(Thread):
    messages: List[Message] | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_documents(request: ChatRequest):
    """
    Chat with documents - ask questions about processed documents
    """
    return await thread_handler.chat_with_documents(
        request.prompt, request.thread_id, request.return_new_messages_only, request.document_ids
    )


@router.get("/all", response_model=List[Thread])
async def get_threads(limit: int = -1):
    """
    Get all chat threads
    """
    return thread_handler.get_all_threads(limit=limit)


@router.get("/{thread_id}", response_model=ThreadWithMessages)
async def get_thread(thread_id: str):
    """
    Get a chat thread by ID
    """
    return thread_handler.get_thread(thread_id)
