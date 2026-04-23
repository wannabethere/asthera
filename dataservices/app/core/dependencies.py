"""
Dependency injection for persistence services
"""

from typing import AsyncGenerator, Generator, Union
import os
import logging
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Header
from app.core.session_manager import SessionManager
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import DomainManager
from app.storage.documents import DocumentChromaStore
from app.storage.qdrant_store import DocumentQdrantStore, QDRANT_AVAILABLE
from app.agents.indexing.sql_pairs import SqlPairs
from app.agents.indexing.instructions import Instructions
from app.core.settings import get_settings, VectorStoreType


logger = logging.getLogger(__name__)

DocumentVectorStore = Union[DocumentChromaStore, DocumentQdrantStore]


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
        persist = settings.CHROMA_PERSIST_DIRECTORY or settings.CHROMA_STORE_PATH
        return chromadb.PersistentClient(path=persist)
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST or "localhost",
        port=settings.CHROMA_PORT,
    )


_qdrant_client_cache = None


def get_qdrant_client():
    """Singleton Qdrant client from settings (QDRANT_URL or host/port; optional QDRANT_API_KEY for Qdrant Cloud)."""
    global _qdrant_client_cache
    if _qdrant_client_cache is not None:
        return _qdrant_client_cache
    if not QDRANT_AVAILABLE:
        raise ImportError("qdrant-client / langchain-qdrant are required when VECTOR_STORE_TYPE=qdrant")
    from qdrant_client import QdrantClient

    settings = get_settings()
    if settings.QDRANT_URL:
        kwargs = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _qdrant_client_cache = QdrantClient(**kwargs)
    else:
        kwargs = {
            "host": settings.QDRANT_HOST or "localhost",
            "port": settings.QDRANT_PORT,
        }
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _qdrant_client_cache = QdrantClient(**kwargs)
    return _qdrant_client_cache


def build_document_store(
    collection_name: str,
    *,
    tf_idf: bool = False,
    chroma_client=None,
) -> DocumentVectorStore:
    """Create a document vector store for ``collection_name`` using VECTOR_STORE_TYPE."""
    settings = get_settings()
    embeddings = get_embeddings()
    if settings.VECTOR_STORE_TYPE == VectorStoreType.QDRANT:
        return DocumentQdrantStore(
            qdrant_client=get_qdrant_client(),
            collection_name=collection_name,
            embeddings_model=embeddings,
            tf_idf=tf_idf,
        )
    client = chroma_client if chroma_client is not None else get_chromadb_client()
    return DocumentChromaStore(
        client=client,
        collection_name=collection_name,
        tf_idf=tf_idf,
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
    embeddings = get_embeddings()
    doc_store = build_document_store("sql_pairs")
    return SqlPairs(document_store=doc_store, embedder=embeddings)


def get_instructions_processor() -> Instructions:
    """Get instructions processor instance"""
    embeddings = get_embeddings()
    doc_store = build_document_store("instructions")
    return Instructions(document_store=doc_store, embedder=embeddings)


# Global cache for document store provider
_doc_store_provider_cache = None

def get_doc_store_provider():
    """Get the document store provider with all SQL-related stores with caching."""
    global _doc_store_provider_cache
    
    if _doc_store_provider_cache is not None:
        return _doc_store_provider_cache
    
    from app.core.provider import DocumentStoreProvider

    sql_stores = {
        "db_schema": build_document_store("db_schema"),
        "sql_pairs": build_document_store("sql_pairs"),
        "instructions": build_document_store("instructions"),
        "historical_question": build_document_store("historical_question"),
        "table_description": build_document_store("table_descriptions"),
        "project_meta": build_document_store("project_meta"),
        "document_insights": build_document_store("document_insights"),
        "document_planning": build_document_store("document_planning"),
        "alert_knowledge_base": build_document_store("alert_knowledge_base"),
        "column_metadata": build_document_store("column_metadata"),
        "silver_table_descriptions": build_document_store("silver_table_descriptions"),
        "silver_db_schema": build_document_store("silver_db_schema"),
    }
    
    _doc_store_provider_cache = DocumentStoreProvider(
        stores=sql_stores,
        default_store="table_description"
    )
    
    return _doc_store_provider_cache