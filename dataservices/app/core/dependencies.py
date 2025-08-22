"""
Dependency injection for persistence services
"""

from typing import AsyncGenerator, Generator
import os
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Header
from app.core.session_manager import SessionManager
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import DomainManager
from app.storage.documents import DocumentChromaStore
from app.agents.indexing.sql_pairs import SqlPairs
from app.agents.indexing.instructions import Instructions
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


def get_db_session() -> Generator[Session, None, None]:
    """Get synchronous database session using session manager"""
    session_manager = get_session_manager()
    
    # For now, we'll create a sync session from the async engine
    # This is a temporary solution - you might want to add a sync engine to SessionManager
    try:
        # Create a sync session from the async engine
        # Note: This is not ideal for production - consider adding a sync engine
        from sqlalchemy.ext.asyncio import AsyncEngine
        from sqlalchemy import create_engine
        
        # Get the async engine and create a sync engine from it
        async_engine = session_manager.engine
        sync_engine = create_engine(
            str(async_engine.url),
            echo=async_engine.echo,
            pool_pre_ping=async_engine.pool._pre_ping,
            pool_recycle=async_engine.pool._recycle
        )
        
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
        
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {str(e)}"
        )


def get_current_user(authorization: str = Header(None)) -> str:
    """
    Get current user from authorization header
    
    This is a simplified implementation. In production, you should:
    1. Validate the JWT token
    2. Extract user information from the token
    3. Verify user permissions
    """
    if not authorization:
        # For development/testing, return a default user
        # In production, this should raise an authentication error
        return "default_user"
    
    # Simple token extraction (you should implement proper JWT validation)
    if authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        # Here you would validate the JWT token and extract user info
        # For now, we'll just return a placeholder
        return "user_from_token"
    
    # If no Bearer token, return default user for development
    return "default_user"


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