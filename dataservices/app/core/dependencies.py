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
    from app.core.settings import get_settings
    import os
    import logging
    
    logger = logging.getLogger(__name__)
    
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY
    
    if not api_key:
        # Try to get from environment variable as fallback
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        error_msg = (
            "OPENAI_API_KEY is not configured in settings or environment variables. "
            "Please set OPENAI_API_KEY in your settings or environment variables."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate API key format (basic check - should start with 'sk-')
    if not api_key.startswith('sk-'):
        logger.warning(f"API key does not start with 'sk-' - may be invalid. Key starts with: {api_key[:5]}...")
    
    # Set as environment variable for LangChain to pick up
    # This ensures compatibility with all LangChain components
    os.environ["OPENAI_API_KEY"] = api_key
    
    try:
        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key
        )
        # Log API key info (first 10 chars only for security)
        api_key_preview = api_key[:10] + "..." if len(api_key) > 10 else api_key
        logger.info(f"LLM initialized with model: {model}, temperature: {temperature}, API key: {api_key_preview}")
        return llm
    except Exception as e:
        error_msg = (
            f"Failed to initialize LLM: {str(e)}\n"
            "This may be due to:\n"
            "1. Invalid or expired API key\n"
            "2. API key does not have access to the required organization\n"
            "3. Network connectivity issues\n"
            f"Please verify your OPENAI_API_KEY in settings. Key starts with: {api_key[:10]}..."
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e


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
    from app.core.settings import get_settings
    
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured in settings")
    
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=api_key
    )


def get_sql_pairs_processor() -> SqlPairs:
    """Get SQL pairs processor instance"""
    chroma_client = get_chromadb_client()
    embeddings = get_embeddings()
    
    doc_store = DocumentChromaStore(
        client=chroma_client,
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
        client=chroma_client,
        collection_name="instructions"
        )
    
    return Instructions(
        document_store=doc_store,
        embedder=embeddings
    )


# Global cache for document store provider
_doc_store_provider_cache = None

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores with caching."""
    global _doc_store_provider_cache
    
    if _doc_store_provider_cache is not None:
        return _doc_store_provider_cache
    
    from app.core.provider import DocumentStoreProvider
    
    chroma_client = get_chromadb_client()
    
    # Create document stores for SQL-related collections
    sql_stores = {
        "db_schema": DocumentChromaStore(
            client=chroma_client,
            collection_name="db_schema"
        ),
        "sql_pairs": DocumentChromaStore(
            client=chroma_client,
            collection_name="sql_pairs"
        ),
        "instructions": DocumentChromaStore(
            client=chroma_client,
            collection_name="instructions"
        ),
        "historical_question": DocumentChromaStore(
            client=chroma_client,
            collection_name="historical_question"
        ),
        "table_description": DocumentChromaStore(
            client=chroma_client,
            collection_name="table_descriptions"
        ),
        "project_meta": DocumentChromaStore(
            client=chroma_client,
            collection_name="project_meta"
        ),
        "document_insights": DocumentChromaStore(
            client=chroma_client,
            collection_name="document_insights"
        ),
        "document_planning": DocumentChromaStore(
            client=chroma_client,   
            collection_name="document_planning"
        ),
        "alert_knowledge_base": DocumentChromaStore(
            client=chroma_client,
            collection_name="alert_knowledge_base"
        ),
        "column_metadata": DocumentChromaStore(
            client=chroma_client,
            collection_name="column_metadata"
        ),
        # Silver table stores for data mart planning
        "silver_table_descriptions": DocumentChromaStore(
            client=chroma_client,
            collection_name="silver_table_descriptions"
        ),
        "silver_db_schema": DocumentChromaStore(
            client=chroma_client,
            collection_name="silver_db_schema"
        )
    }
    
    _doc_store_provider_cache = DocumentStoreProvider(
        stores=sql_stores,
        default_store="table_description"
    )
    
    return _doc_store_provider_cache