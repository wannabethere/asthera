"""
Dependency injection for persistence services
"""

from typing import AsyncGenerator
import os
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.session_manager import SessionManager
from app.storage.documents import DocumentChromaStore
from app.core.settings import get_settings


def get_session_manager() -> SessionManager:
    """Get the singleton session manager instance"""
    return SessionManager.get_instance()


def get_llm(temperature: float = 0.0, model: str = "gpt-4o-mini"):
    """Get LLM instance for AI operations"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key
    )


async def get_async_db_session():
    """Get async database session using session manager"""
    session_manager = get_session_manager()
    async with session_manager.get_async_db_session() as session:
        yield session


def get_chromadb_client():
    """Get ChromaDB client based on configuration settings."""
    settings = get_settings()
    
    if settings.CHROMA_USE_LOCAL:
        # Use local persistent client
        return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)
    else:
        # Use HTTP client (default)
        return chromadb.HttpClient(
            host=settings.CHROMA_HOST, 
            port=settings.CHROMA_PORT
        )


def get_embeddings():
    """Get OpenAI embeddings instance"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key
    )


