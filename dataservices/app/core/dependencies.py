"""
Dependency injection for persistence services
"""

from typing import AsyncGenerator
import os
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.session_manager import SessionManager
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import DomainManager
from app.storage.documents import DocumentChromaStore
from app.agents.indexing.sql_pairs import SqlPairs
from app.agents.indexing.instructions import Instructions


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


async def get_persistence_factory() -> AsyncGenerator[PersistenceServiceFactory, None]:
    """Get persistence service factory with session manager"""
    session_manager = get_session_manager()
    
    # Create a project manager instance
    # Note: ProjectManager might need to be updated to work with async sessions
    project_manager = DomainManager(None)  # We'll pass None for now since we're using async sessions
    
    # Get the processors
    sql_pairs_processor = get_sql_pairs_processor()
    instructions_processor = get_instructions_processor()
    
    factory = PersistenceServiceFactory(
        session_manager, 
        project_manager, 
        sql_pairs_processor, 
        instructions_processor
    )
    yield factory


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


def get_sql_pairs_processor() -> SqlPairs:
    """Get SQL pairs processor instance"""
    chroma_client = get_chromadb_client()
    embeddings = get_embeddings()
    
    doc_store = DocumentChromaStore(
        persistent_client=chroma_client,
        collection_name="sql_pairs"
    )
    
    return SqlPairs(
        document_store=doc_store,
        embedder=embeddings
    )


def get_instructions_processor() -> Instructions:
    """Get instructions processor instance"""
    chroma_client = get_chromadb_client()
    embeddings = get_embeddings()
    
    doc_store = DocumentChromaStore(
        persistent_client=chroma_client,
        collection_name="instructions"
    )
    
    return Instructions(
        document_store=doc_store,
        embedder=embeddings
    )