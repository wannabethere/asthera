"""
Dependency injection for persistence services
"""

from typing import AsyncGenerator, Union
import os
import chromadb
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.session_manager import SessionManager
from app.storage.documents import DocumentChromaStore
from app.storage.qdrant_store import DocumentQdrantStore, QDRANT_AVAILABLE
from app.core.settings import get_settings, VectorStoreType


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


DocumentVectorStore = Union[DocumentChromaStore, DocumentQdrantStore]


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
        persistent_client=client,
        collection_name=collection_name,
        embeddings_model=embeddings,
        tf_idf=tf_idf,
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


