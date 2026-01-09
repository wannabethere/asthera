"""
Dependency injection and caching for Knowledge App
Similar to genieml/agents/app/core/dependencies.py
"""
from typing import Dict, Any, Optional
import logging
from functools import lru_cache
import chromadb
import asyncpg
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic

from app.core.settings import get_settings, clear_settings_cache
from app.storage.database import get_database_client as _get_database_client, DatabaseClient
from app.storage.vector_store import get_vector_store_client as _get_vector_store_client, VectorStoreClient
from app.storage.cache import get_cache_client as _get_cache_client, CacheClient

logger = logging.getLogger(__name__)

# Global cache for clients and providers
_chromadb_client_cache: Optional[chromadb.Client] = None
_database_pool_cache: Optional[asyncpg.Pool] = None
_embeddings_cache: Optional[OpenAIEmbeddings] = None
_vector_store_client_cache: Optional[VectorStoreClient] = None
_cache_client_cache: Optional[CacheClient] = None


def get_chromadb_client():
    """Get ChromaDB client based on configuration settings with caching."""
    global _chromadb_client_cache
    
    if _chromadb_client_cache is not None:
        logger.info("Returning cached ChromaDB client (no re-initialization needed)")
        return _chromadb_client_cache
    
    # Clear settings cache to ensure we get the latest settings
    clear_settings_cache()
    
    settings = get_settings()
    
    logger.info(
        f"ChromaDB configuration: CHROMA_USE_LOCAL={settings.CHROMA_USE_LOCAL}, "
        f"CHROMA_STORE_PATH={settings.CHROMA_STORE_PATH}"
    )
    
    if settings.CHROMA_USE_LOCAL:
        # Use local persistent client
        logger.info(f"Creating local PersistentClient with path: {settings.CHROMA_STORE_PATH}")
        _chromadb_client_cache = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    else:
        # Use HTTP client (default)
        logger.info(f"Creating HTTP client with host: {settings.CHROMA_HOST}, port: {settings.CHROMA_PORT}")
        try:
            _chromadb_client_cache = chromadb.HttpClient(
                host=settings.CHROMA_HOST or "localhost",
                port=settings.CHROMA_PORT,
                settings=chromadb.Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception as e:
            logger.error(f"Failed to create HTTP client: {e}")
            raise
    
    return _chromadb_client_cache


async def get_database_pool():
    """Get database connection pool with caching."""
    global _database_pool_cache
    
    if _database_pool_cache is not None:
        logger.info("Returning cached database pool (no re-initialization needed)")
        return _database_pool_cache
    
    # Clear settings cache to ensure we get the latest settings
    clear_settings_cache()
    
    settings = get_settings()
    
    logger.info(
        f"Database configuration: DATABASE_TYPE={settings.DATABASE_TYPE}, "
        f"POSTGRES_HOST={settings.POSTGRES_HOST}, POSTGRES_PORT={settings.POSTGRES_PORT}"
    )
    
    if settings.DATABASE_TYPE.value == "postgres":
        try:
            _database_pool_cache = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                min_size=settings.POSTGRES_POOL_MIN_SIZE,
                max_size=settings.POSTGRES_POOL_MAX_SIZE,
                ssl=settings.POSTGRES_SSL_MODE == "require"
            )
            logger.info("PostgreSQL connection pool created and cached")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise
    else:
        raise ValueError(f"Unsupported database type: {settings.DATABASE_TYPE}")
    
    return _database_pool_cache


def get_embeddings_model(
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> OpenAIEmbeddings:
    """Get embeddings model with caching."""
    global _embeddings_cache
    
    settings = get_settings()
    model = model or settings.EMBEDDING_MODEL
    api_key = api_key or settings.OPENAI_API_KEY
    
    # Check if we need to recreate the embeddings model
    if _embeddings_cache is None or (
        hasattr(_embeddings_cache, 'model') and _embeddings_cache.model != model
    ):
        logger.info(f"Creating new embeddings model: {model}")
        _embeddings_cache = OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key
        )
    else:
        logger.info("Returning cached embeddings model")
    
    return _embeddings_cache


def get_llm(
    temperature: float = 0.2,
    model: Optional[str] = None,
    provider: str = "openai"
) -> Any:
    """Get LLM with specified temperature and model.
    
    Args:
        temperature: Temperature for the model (default: 0.2)
        model: Model name (defaults to settings)
        provider: LLM provider - "openai" or "anthropic" (default: "openai")
        
    Returns:
        ChatOpenAI or ChatAnthropic instance configured with settings
    """
    settings = get_settings()
    model = model or settings.LLM_MODEL
    
    if provider.lower() == "anthropic":
        return get_anthropic_llm(temperature=temperature, model=model)
    else:
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            openai_api_key=settings.OPENAI_API_KEY
        )


def get_anthropic_llm(temperature: float = 0.2, model: str = "claude-sonnet-4-20250514"):
    """Get Anthropic LLM with specified temperature and model.
    
    Args:
        temperature: Temperature for the model (default: 0.2)
        model: Model name (default: claude-sonnet-4-20250514)
        
    Returns:
        ChatAnthropic instance configured with settings
    """
    settings = get_settings()
    # Check for ANTHROPIC_API_KEY in settings or environment
    anthropic_api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
    if not anthropic_api_key:
        import os
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not anthropic_api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not found in settings or environment. "
            "ChatAnthropic will try to use default."
        )
        # ChatAnthropic can work without explicit API key if set in environment
        return ChatAnthropic(
            model=model,
            temperature=temperature
        )
    
    return ChatAnthropic(
        model=model,
        temperature=temperature,
        anthropic_api_key=anthropic_api_key
    )


async def get_vector_store_client(
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    config: Optional[Dict[str, Any]] = None
) -> VectorStoreClient:
    """Get vector store client with caching."""
    global _vector_store_client_cache
    
    if _vector_store_client_cache is not None:
        logger.info("Returning cached vector store client (no re-initialization needed)")
        return _vector_store_client_cache
    
    # Clear settings cache to ensure we get the latest settings
    clear_settings_cache()
    
    settings = get_settings()
    
    # Use provided config or get from settings
    if config is None:
        config = settings.get_vector_store_config()
    
    # Use provided embeddings or get default
    if embeddings_model is None:
        embeddings_model = get_embeddings_model()
    
    logger.info(f"Creating vector store client: {config.get('type')}")
    _vector_store_client_cache = _get_vector_store_client(
        embeddings_model=embeddings_model,
        config=config
    )
    
    await _vector_store_client_cache.initialize()
    
    return _vector_store_client_cache


def get_cache_client(config: Optional[Dict[str, Any]] = None) -> CacheClient:
    """Get cache client with caching."""
    global _cache_client_cache
    
    if _cache_client_cache is not None:
        logger.info("Returning cached cache client (no re-initialization needed)")
        return _cache_client_cache
    
    # Clear settings cache to ensure we get the latest settings
    clear_settings_cache()
    
    settings = get_settings()
    
    # Use provided config or get from settings
    if config is None:
        config = settings.get_cache_config()
    
    logger.info(f"Creating cache client: {config.get('type')}")
    _cache_client_cache = _get_cache_client(config)
    
    return _cache_client_cache


async def get_database_client(config: Optional[Dict[str, Any]] = None) -> DatabaseClient:
    """Get database client (wrapper around database pool for compatibility)."""
    # For now, return a client that uses the pool
    # This maintains compatibility with existing code
    pool = await get_database_pool()
    
    # Create a database client wrapper
    from app.storage.database import PostgresDatabaseClient
    
    settings = get_settings()
    if config is None:
        config = settings.get_database_config()
    
    client = PostgresDatabaseClient(config)
    client._pool = pool  # Use the cached pool
    
    return client


def clear_all_caches():
    """Clear all cached clients and providers."""
    global _chromadb_client_cache, _database_pool_cache, _embeddings_cache, _vector_store_client_cache, _cache_client_cache
    
    _chromadb_client_cache = None
    _database_pool_cache = None
    _embeddings_cache = None
    _vector_store_client_cache = None
    _cache_client_cache = None
    
    # Clear settings cache
    clear_settings_cache()
    
    logger.info("Cleared all cached clients and providers")


async def get_dependencies():
    """Get all dependencies for the Knowledge App.
    
    Returns:
        Dictionary containing:
        - chroma_client: ChromaDB client
        - db_pool: Database connection pool
        - embeddings: Embeddings model
        - llm: LLM instance
        - vector_store_client: Vector store client
        - cache_client: Cache client
    """
    settings = get_settings()
    
    # Get ChromaDB client
    chroma_client = get_chromadb_client()
    
    # Get database pool
    db_pool = await get_database_pool()
    
    # Get embeddings model
    embeddings = get_embeddings_model()
    
    # Get LLM
    llm = get_llm(
        temperature=settings.LLM_TEMPERATURE,
        model=settings.LLM_MODEL
    )
    
    # Get vector store client
    vector_store_client = await get_vector_store_client(embeddings_model=embeddings)
    
    # Get cache client
    cache_client = get_cache_client()
    
    return {
        "chroma_client": chroma_client,
        "db_pool": db_pool,
        "embeddings": embeddings,
        "llm": llm,
        "vector_store_client": vector_store_client,
        "cache_client": cache_client,
        "settings": settings
    }

