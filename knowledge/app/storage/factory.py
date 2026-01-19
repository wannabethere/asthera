"""
Factory functions for creating storage clients
Uses unified storage architecture from documents.py
"""
import logging
from typing import Optional
from langchain_openai import OpenAIEmbeddings

from app.core.settings import get_settings
from app.storage.database import get_database_client
from app.storage.vector_store import get_vector_store_client
from app.storage.cache import get_cache_client
from app.storage.documents import DocumentChromaStore, DocumentVectorstore

logger = logging.getLogger(__name__)


async def initialize_storage_clients(
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    db_config: Optional[dict] = None,
    vector_store_config: Optional[dict] = None,
    cache_config: Optional[dict] = None
):
    """
    Initialize all storage clients based on settings.
    
    Args:
        embeddings_model: Optional embeddings model
        db_config: Optional database configuration override
        vector_store_config: Optional vector store configuration override
        cache_config: Optional cache configuration override
        
    Returns:
        Tuple of (database_client, vector_store_client, cache_client)
    """
    settings = get_settings()
    
    # Initialize database client
    db_client = get_database_client(db_config)
    await db_client.connect()
    logger.info(f"Database client initialized: {settings.DATABASE_TYPE}")
    
    # Initialize vector store client
    vector_store_client = get_vector_store_client(
        embeddings_model=embeddings_model,
        config=vector_store_config
    )
    await vector_store_client.initialize()
    logger.info(f"Vector store client initialized: {settings.VECTOR_STORE_TYPE}")
    
    # Initialize cache client
    cache_client = get_cache_client(cache_config)
    logger.info(f"Cache client initialized: {settings.CACHE_TYPE}")
    
    return db_client, vector_store_client, cache_client


async def cleanup_storage_clients(
    db_client,
    vector_store_client,
    cache_client
):
    """Cleanup all storage clients"""
    if db_client:
        await db_client.disconnect()
        logger.info("Database client disconnected")
    
    if hasattr(cache_client, 'close'):
        await cache_client.close()
        logger.info("Cache client closed")

