"""
Dependency injection for persistence services
"""

from typing import AsyncGenerator
import os
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.session_manager import SessionManager
from app.storage.documents import DocumentChromaStore
from app.core.provider import DocumentStoreProvider
from app.core.settings import get_settings

settings = get_settings()


def get_session_manager() -> SessionManager:
    """Get the singleton session manager instance"""
    return SessionManager.get_instance()


def get_llm(temperature: float = 0.0, model: str = "gpt-4o-mini"):
    """Get LLM instance for AI operations"""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key
    )

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores."""
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    #client = chromadb.HttpClient(host='ec2-54-161-71-105.compute-1.amazonaws.com', port=8888)
    # Create document stores for SQL-related collections
    stores = {
        "usage_examples": DocumentChromaStore(persistent_client=client,collection_name="tools_examples_collection"),
        "function_spec": DocumentChromaStore(persistent_client=client,collection_name="tools_spec_collection"),
        "insights_store": DocumentChromaStore(persistent_client=client,collection_name="tools_insights_collection")
    }
    
    # Create and return the document store provider
    return DocumentStoreProvider(
        stores=stores,
        default_store="function_spec"
    )


async def get_async_db_session():
    """Get async database session using session manager"""
    session_manager = get_session_manager()
    async with session_manager.get_async_db_session() as session:
        yield session




def get_chromadb_client():
    """Get ChromaDB persistent client"""
    chroma_store_path = os.getenv("CHROMA_STORE_PATH", "./chroma_db")
    return chromadb.PersistentClient(path=chroma_store_path)


def get_embeddings():
    """Get OpenAI embeddings instance"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=api_key
    )


