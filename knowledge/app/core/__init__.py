"""
Core module for Knowledge App
Contains settings, abstractions, and shared utilities
"""
from app.core.settings import get_settings, Settings, clear_settings_cache
from app.core.dependencies import (
    get_chromadb_client,
    get_database_pool,
    get_embeddings_model,
    get_llm,
    get_anthropic_llm,
    get_vector_store_client,
    get_cache_client,
    get_database_client,
    get_dependencies,
    get_doc_store_provider,
    clear_chromadb_cache,
    clear_all_caches
)
from app.core.engine_provider import (
    EngineProvider,
    DatabaseEngine,
    EngineType
)
from app.core.cache_provider import (
    CacheProvider,
    get_cache_provider,
    clear_cache_provider,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    cached_function
)

__all__ = [
    # Settings
    "get_settings",
    "Settings",
    "clear_settings_cache",
    # Dependencies
    "get_chromadb_client",
    "get_database_pool",
    "get_embeddings_model",
    "get_llm",
    "get_anthropic_llm",
    "get_vector_store_client",
    "get_cache_client",
    "get_database_client",
    "get_dependencies",
    "get_doc_store_provider",
    "clear_chromadb_cache",
    "clear_all_caches",
    # Engine Provider
    "EngineProvider",
    "DatabaseEngine",
    "EngineType",
    # Cache Provider
    "CacheProvider",
    "get_cache_provider",
    "clear_cache_provider",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_clear",
    "cached_function",
]

