"""
Dependency injection and caching for Knowledge App
Similar to genieml/agents/app/core/dependencies.py
"""
from typing import Dict, Any, Optional
import logging
from functools import lru_cache
import ssl
import chromadb
import asyncpg
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic

from app.core.provider import get_llm as _provider_get_llm, get_llm_for_type as _provider_get_llm_for_type, LLMProvider

from app.core.settings import get_settings, clear_settings_cache
from app.storage.database import get_database_client as _get_database_client, DatabaseClient
# Lazy import to avoid circular dependency
# from app.storage.vector_store import get_vector_store_client as _get_vector_store_client, VectorStoreClient
from app.storage.cache import get_cache_client as _get_cache_client, CacheClient

# Type hint for VectorStoreClient (imported lazily to avoid circular dependency)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)

# Global cache for clients and providers
_chromadb_client_cache: Optional[chromadb.Client] = None
_database_pool_cache: Optional[asyncpg.Pool] = None
_embeddings_cache: Optional[OpenAIEmbeddings] = None
_vector_store_client_cache: Optional[Any] = None  # VectorStoreClient (lazy import)
_cache_client_cache: Optional[CacheClient] = None
_doc_store_provider_cache: Optional[Any] = None

# Cache for security intelligence database pools (keyed by source)
_security_intel_db_pools: Dict[str, asyncpg.Pool] = {}


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
        # Ensure path is absolute (resolve relative to BASE_DIR if needed)
        import os
        from pathlib import Path
        
        store_path = settings.CHROMA_STORE_PATH
        if not os.path.isabs(store_path):
            # Resolve relative path from BASE_DIR
            store_path = str(settings.BASE_DIR / store_path)
        
        # Create directory if it doesn't exist
        Path(store_path).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating local PersistentClient with path: {store_path}")
        try:
            _chromadb_client_cache = chromadb.PersistentClient(path=store_path)
            logger.info("✓ ChromaDB PersistentClient created successfully")
        except Exception as e:
            logger.error(f"Failed to create ChromaDB PersistentClient: {e}")
            logger.error(f"Path attempted: {store_path}")
            raise
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
            logger.info("✓ ChromaDB HttpClient created successfully")
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
            # Configure SSL for Azure PostgreSQL
            # Azure PostgreSQL requires SSL but may have self-signed certificates
            ssl_config = None
            if settings.POSTGRES_SSL_MODE == "require":
                # Create SSL context that doesn't verify certificates (for Azure PostgreSQL)
                # In production, you should use proper certificate verification
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                ssl_config = ssl_context
            elif settings.POSTGRES_SSL_MODE in ["prefer", "allow"]:
                # Prefer SSL but don't require it
                ssl_config = "prefer"
            elif settings.POSTGRES_SSL_MODE == "disable":
                ssl_config = False
            
            _database_pool_cache = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                min_size=settings.POSTGRES_POOL_MIN_SIZE,
                max_size=settings.POSTGRES_POOL_MAX_SIZE,
                ssl=ssl_config
            )
            logger.info("PostgreSQL connection pool created and cached")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise
    else:
        raise ValueError(f"Unsupported database type: {settings.DATABASE_TYPE}")
    
    return _database_pool_cache


async def get_security_intel_database_pool(source: str) -> asyncpg.Pool:
    """
    Get database connection pool for a specific security intelligence source.
    
    Supports separate database connections for different security intelligence sources:
    - "cve_attack": CVE → ATT&CK mappings, ATT&CK → Control mappings
    - "cpe": CPE dictionary and CVE-CPE relationships
    - "exploit": Exploit-DB, Metasploit, Nuclei templates
    - "compliance": CIS benchmarks, Sigma rules
    
    If source-specific configuration is not provided, falls back to default database.
    
    Args:
        source: Security intelligence source identifier
                One of: "cve_attack", "cpe", "exploit", "compliance"
    
    Returns:
        asyncpg.Pool: Database connection pool for the specified source
    """
    global _security_intel_db_pools
    
    # Check cache first
    if source in _security_intel_db_pools:
        logger.debug(f"Returning cached database pool for source: {source}")
        return _security_intel_db_pools[source]
    
    # Clear settings cache to ensure we get the latest settings
    clear_settings_cache()
    settings = get_settings()
    
    # Get source-specific database config
    db_config = settings.get_security_intel_db_config(source)
    
    # If using default database, return the default pool
    if db_config.get("host") == (settings.POSTGRES_HOST or "localhost") and \
       db_config.get("database") == settings.POSTGRES_DB:
        logger.info(f"Source '{source}' using default database connection")
        return await get_database_pool()
    
    # Create source-specific pool
    try:
        # Configure SSL (use same logic as default pool)
        ssl_config = None
        ssl_mode = db_config.get("ssl_mode", settings.POSTGRES_SSL_MODE)
        if ssl_mode == "require":
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            ssl_config = ssl_context
        elif ssl_mode in ["prefer", "allow"]:
            ssl_config = "prefer"
        elif ssl_mode == "disable":
            ssl_config = False
        
        pool = await asyncpg.create_pool(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            database=db_config.get("database", ""),
            user=db_config.get("user", ""),
            password=db_config.get("password", ""),
            min_size=db_config.get("pool_min_size", settings.POSTGRES_POOL_MIN_SIZE),
            max_size=db_config.get("pool_max_size", settings.POSTGRES_POOL_MAX_SIZE),
            ssl=ssl_config
        )
        
        # Cache the pool
        _security_intel_db_pools[source] = pool
        logger.info(
            f"Created source-specific database pool for '{source}': "
            f"{db_config.get('host')}:{db_config.get('port')}/{db_config.get('database')}"
        )
        
        return pool
    except Exception as e:
        logger.error(f"Failed to create database pool for source '{source}': {e}")
        # Fall back to default pool on error
        logger.warning(f"Falling back to default database pool for source '{source}'")
        return await get_database_pool()




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
    """Get LLM with specified temperature and model. Uses externalized config (.env); defaults when config missing."""
    return _provider_get_llm(temperature=temperature, model=model, provider=provider)


def get_llm_for_type(
    llm_type: str,
    temperature: float = 0.2,
    model_override: Optional[str] = None,
) -> Any:
    """Get LLM for type (REASONING, EXECUTOR, CRITIQUE, PLAN, WRITER). Uses type-specific model from config or defaults to get_llm."""
    return _provider_get_llm_for_type(llm_type, temperature=temperature, model_override=model_override)


def get_llm_provider(config: Optional[Dict[str, Any]] = None) -> LLMProvider:
    """Get LLM provider; when config is missing uses get_llm / get_llm_for_type from settings."""
    return LLMProvider(config=config)


def get_anthropic_llm(temperature: float = 0.2, model: str = "claude-sonnet-4-20250514"):
    """Get Anthropic LLM with specified temperature and model."""
    return _provider_get_llm(temperature=temperature, model=model, provider="anthropic")


async def get_vector_store_client(
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    config: Optional[Dict[str, Any]] = None
):
    """Get vector store client with caching."""
    # Lazy import to avoid circular dependency
    from app.storage.vector_store import get_vector_store_client as _get_vector_store_client, VectorStoreClient
    
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


def get_doc_store_provider():
    """Get the document store provider for Compliance Skill collections with caching.
    
    This function initializes ALL document stores that are actively used in the compliance skill:
    - Framework KB Collections (framework_controls, framework_requirements, framework_risks, 
      framework_test_cases, framework_scenarios, user_policies)
    - MDL Collections (leen_db_schema, leen_table_description, leen_project_meta, leen_metrics_registry)
    - XSOAR Collection (xsoar_enriched)
    - LLM Safety Collection (llm_safety)
    
    Framework KB collections are used by RetrievalService for semantic search across controls,
    requirements, risks, test cases, and scenarios.
    
    This function initializes document stores based on VECTOR_STORE_TYPE configuration.
    Supports both ChromaDB and Qdrant vector stores.
    """
    global _doc_store_provider_cache
    
    if _doc_store_provider_cache is not None:
        logger.info("Returning cached document store provider (no re-initialization needed)")
        return _doc_store_provider_cache
    
    logger.info("Creating new document store provider (first time initialization)")
    
    try:
        # Try to import from app.storage.documents and app.core.provider
        from app.storage.documents import DocumentChromaStore, DocumentQdrantStore
        from app.core.provider import DocumentStoreProvider
        from app.storage.collections import (
            MDLCollections, XSOARCollections, LLMSafetyCollections, FrameworkCollections
        )
        from app.storage.qdrant_framework_store import Collections as FrameworkStoreCollections
    except ImportError as e:
        logger.error(f"Failed to import document store classes or DocumentStoreProvider: {e}")
        logger.error("These modules are required for retrieval services.")
        raise ImportError(
            "Document store classes and DocumentStoreProvider are required but not found. "
            "These should be available in app.storage.documents and app.core.provider"
        ) from e
    
    # Get settings to determine vector store type
    settings = get_settings()
    vector_store_type = settings.VECTOR_STORE_TYPE
    
    # Create embeddings model for document stores
    from langchain_openai import OpenAIEmbeddings
    embeddings_model = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    # Create document stores - ONLY for collections actively used in compliance skill
    doc_stores = {}
    
    if vector_store_type.value == "chroma":
        # Initialize ChromaDB client
        client = get_chromadb_client()
        
        # Framework KB Collections (used by RetrievalService)
        # Note: Framework collections are typically Qdrant-only, but we initialize them here
        # for consistency. If using ChromaDB, these may need to be migrated or handled differently.
        doc_stores["framework_controls"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=FrameworkStoreCollections.CONTROLS,
            embeddings_model=embeddings_model
        )
        doc_stores["framework_requirements"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=FrameworkStoreCollections.REQUIREMENTS,
            embeddings_model=embeddings_model
        )
        doc_stores["framework_risks"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=FrameworkStoreCollections.RISKS,
            embeddings_model=embeddings_model
        )
        doc_stores["framework_test_cases"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=FrameworkStoreCollections.TEST_CASES,
            embeddings_model=embeddings_model
        )
        doc_stores["framework_scenarios"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=FrameworkStoreCollections.SCENARIOS,
            embeddings_model=embeddings_model
        )
        doc_stores["user_policies"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=FrameworkStoreCollections.USER_POLICIES,
            embeddings_model=embeddings_model
        )
        
        # MDL Collections (used by MDLRetrievalService)
        # LEEN/DT workflow collections
        doc_stores["leen_db_schema"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.DB_SCHEMA,
            embeddings_model=embeddings_model
        )
        doc_stores["leen_table_description"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.TABLE_DESCRIPTION,
            embeddings_model=embeddings_model
        )
        doc_stores["leen_project_meta"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.PROJECT_META,
            embeddings_model=embeddings_model
        )
        doc_stores["leen_metrics_registry"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.METRICS_REGISTRY,
            embeddings_model=embeddings_model
        )
        # CSOD workflow collections
        doc_stores["csod_db_schema"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.CSOD_DB_SCHEMA,
            embeddings_model=embeddings_model
        )
        doc_stores["csod_table_descriptions"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.CSOD_TABLE_DESCRIPTION,
            embeddings_model=embeddings_model
        )
        doc_stores["csod_metrics_registry"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.CSOD_METRICS_REGISTRY,
            embeddings_model=embeddings_model
        )
        # Shared collections
        doc_stores["mdl_dashboards"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.DASHBOARDS,
            embeddings_model=embeddings_model
        )
        doc_stores["dashboard_templates"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.DASHBOARD_TEMPLATES,
            embeddings_model=embeddings_model
        )
        # Dashboard Decision Tree collections (used by DashboardDecisionTreeService)
        doc_stores["layout_templates"] = DocumentChromaStore(
            persistent_client=client,
            collection_name="layout_templates",
            embeddings_model=embeddings_model
        )
        doc_stores["metric_catalog"] = DocumentChromaStore(
            persistent_client=client,
            collection_name="metric_catalog",
            embeddings_model=embeddings_model
        )
        doc_stores["decision_tree_options"] = DocumentChromaStore(
            persistent_client=client,
            collection_name="decision_tree_options",
            embeddings_model=embeddings_model
        )
        doc_stores["past_layout_specs"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=MDLCollections.PAST_LAYOUT_SPECS,
            embeddings_model=embeddings_model
        )
        
        # XSOAR Collection (used by XSOARRetrievalService)
        doc_stores["xsoar_enriched"] = DocumentChromaStore(
            persistent_client=client,
            collection_name=XSOARCollections.ENRICHED,
            embeddings_model=embeddings_model
        )
        
        # LLM Safety Collection (used by LLMSafetyRetrievalService)
        doc_stores[LLMSafetyCollections.SAFETY] = DocumentChromaStore(
            persistent_client=client,
            collection_name=LLMSafetyCollections.SAFETY,
            embeddings_model=embeddings_model
        )
        
        logger.info(f"Initialized {len(doc_stores)} ChromaDB document stores for compliance skill")
        
    elif vector_store_type.value == "qdrant":
        # Initialize Qdrant document stores (embedding required for dense retrieval)
        qdrant_config = settings.get_vector_store_config()
        
        # Framework KB Collections (used by RetrievalService)
        doc_stores["framework_controls"] = DocumentQdrantStore(
            collection_name=FrameworkStoreCollections.CONTROLS,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["framework_requirements"] = DocumentQdrantStore(
            collection_name=FrameworkStoreCollections.REQUIREMENTS,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["framework_risks"] = DocumentQdrantStore(
            collection_name=FrameworkStoreCollections.RISKS,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["framework_test_cases"] = DocumentQdrantStore(
            collection_name=FrameworkStoreCollections.TEST_CASES,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["framework_scenarios"] = DocumentQdrantStore(
            collection_name=FrameworkStoreCollections.SCENARIOS,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["user_policies"] = DocumentQdrantStore(
            collection_name=FrameworkStoreCollections.USER_POLICIES,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        
        # MDL Collections (used by MDLRetrievalService)
        # LEEN/DT workflow collections
        doc_stores["leen_db_schema"] = DocumentQdrantStore(
            collection_name=MDLCollections.DB_SCHEMA,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["leen_table_description"] = DocumentQdrantStore(
            collection_name=MDLCollections.TABLE_DESCRIPTION,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["leen_project_meta"] = DocumentQdrantStore(
            collection_name=MDLCollections.PROJECT_META,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["leen_metrics_registry"] = DocumentQdrantStore(
            collection_name=MDLCollections.METRICS_REGISTRY,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        # CSOD workflow collections
        doc_stores["csod_db_schema"] = DocumentQdrantStore(
            collection_name=MDLCollections.CSOD_DB_SCHEMA,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["csod_table_descriptions"] = DocumentQdrantStore(
            collection_name=MDLCollections.CSOD_TABLE_DESCRIPTION,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["csod_metrics_registry"] = DocumentQdrantStore(
            collection_name=MDLCollections.CSOD_METRICS_REGISTRY,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        # Shared collections
        doc_stores["mdl_dashboards"] = DocumentQdrantStore(
            collection_name=MDLCollections.DASHBOARDS,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["dashboard_templates"] = DocumentQdrantStore(
            collection_name=MDLCollections.DASHBOARD_TEMPLATES,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        # Dashboard Decision Tree collections (used by DashboardDecisionTreeService)
        doc_stores["layout_templates"] = DocumentQdrantStore(
            collection_name="layout_templates",
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["metric_catalog"] = DocumentQdrantStore(
            collection_name="metric_catalog",
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["decision_tree_options"] = DocumentQdrantStore(
            collection_name="decision_tree_options",
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        doc_stores["past_layout_specs"] = DocumentQdrantStore(
            collection_name=MDLCollections.PAST_LAYOUT_SPECS,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        
        # XSOAR Collection (used by XSOARRetrievalService)
        doc_stores["xsoar_enriched"] = DocumentQdrantStore(
            collection_name=XSOARCollections.ENRICHED,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        
        # LLM Safety Collection (used by LLMSafetyRetrievalService)
        doc_stores[LLMSafetyCollections.SAFETY] = DocumentQdrantStore(
            collection_name=LLMSafetyCollections.SAFETY,
            host=qdrant_config.get("host", "localhost"),
            port=qdrant_config.get("port", 6333),
            embeddings_model=embeddings_model
        )
        
        logger.info(f"Initialized {len(doc_stores)} Qdrant document stores for compliance skill")
    else:
        raise ValueError(f"Unsupported vector store type: {vector_store_type}. Supported types: chroma, qdrant")
    
    # Create and return the document store provider
    # Use first MDL collection as default store
    _doc_store_provider_cache = DocumentStoreProvider(
        stores=doc_stores,
        default_store="leen_db_schema"
    )
    
    logger.info(
        f"Document store provider initialized with {len(doc_stores)} stores using {vector_store_type.value}. "
        f"Collections: {list(doc_stores.keys())}"
    )
    return _doc_store_provider_cache


def get_gateway_config() -> Dict[str, Any]:
    """
    Get gateway-related config for agent server mode.
    Used when complianceskill receives requests from the Agent Gateway.
    """
    settings = get_settings()
    return {
        "gateway_jwt_secret": getattr(settings, "GATEWAY_JWT_SECRET", None),
        "gateway_ctx_secret": getattr(settings, "GATEWAY_CTX_SECRET", None),
    }


def clear_chromadb_cache():
    """Clear the ChromaDB client and document store provider cache."""
    global _chromadb_client_cache, _doc_store_provider_cache
    _chromadb_client_cache = None
    _doc_store_provider_cache = None
    logger.info("Cleared ChromaDB client and document store provider cache")


def clear_all_caches():
    """Clear all cached clients and providers."""
    global _chromadb_client_cache, _database_pool_cache, _embeddings_cache, _vector_store_client_cache, _cache_client_cache, _doc_store_provider_cache
    
    _chromadb_client_cache = None
    _database_pool_cache = None
    _embeddings_cache = None
    _vector_store_client_cache = None
    _cache_client_cache = None
    _doc_store_provider_cache = None
    
    # Clear settings cache
    clear_settings_cache()
    
    logger.info("Cleared all cached clients and providers")


async def get_contextual_graph_query_engine(
    vector_store_client: Optional[Any] = None,
    db_pool: Optional[asyncpg.Pool] = None,
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    llm: Optional[Any] = None,
    collection_prefix: str = "comprehensive_index"
):
    """
    Get or create a ContextualGraphQueryEngine instance.
    
    Args:
        vector_store_client: Optional VectorStoreClient (will be created if None)
        db_pool: Optional database pool (will be created if None)
        embeddings_model: Optional embeddings model (will use default if None)
        llm: Optional LLM instance (will use default if None)
        collection_prefix: Prefix for collection names
        
    Returns:
        ContextualGraphQueryEngine instance
    
    Raises:
        ImportError: If app.storage.query.query_engine is not available
    """
    try:
        from app.storage.query.query_engine import ContextualGraphQueryEngine
    except ImportError as e:
        logger.error(f"Could not import ContextualGraphQueryEngine: {e}")
        raise
    
    if vector_store_client is None:
        vector_store_client = await get_vector_store_client(embeddings_model=embeddings_model)
    
    if db_pool is None:
        db_pool = await get_database_pool()
    
    if embeddings_model is None:
        embeddings_model = get_embeddings_model()
    
    if llm is None:
        settings = get_settings()
        llm = get_llm(
            temperature=settings.LLM_TEMPERATURE,
            model=settings.LLM_MODEL
        )
    
    return ContextualGraphQueryEngine(
        vector_store_client=vector_store_client,
        db_pool=db_pool,
        embeddings_model=embeddings_model,
        llm=llm,
        collection_prefix=collection_prefix
    )


async def get_contextual_graph_service(
    vector_store_client: Optional[Any] = None,
    db_pool: Optional[asyncpg.Pool] = None,
    embeddings_model: Optional[OpenAIEmbeddings] = None,
    llm: Optional[Any] = None,
    collection_prefix: Optional[str] = None,
    **kwargs
):
    """
    Get or create a ContextualGraphService instance.
    
    Args:
        vector_store_client: Optional VectorStoreClient (will be created if None)
        db_pool: Optional database pool (will be created if None)
        embeddings_model: Optional embeddings model (will use default if None)
        llm: Optional LLM instance (will use default if None)
        collection_prefix: Optional prefix for collection names (defaults to "comprehensive_index" from settings)
        **kwargs: Additional arguments for ContextualGraphService
    
    Returns:
        ContextualGraphService instance
    
    Raises:
        ImportError: If app.services.contextual_graph_service is not available
    """
    try:
        from app.services.contextual_graph_service import ContextualGraphService
    except ImportError as e:
        logger.error(f"Could not import ContextualGraphService: {e}")
        raise
    
    if vector_store_client is None:
        vector_store_client = await get_vector_store_client(embeddings_model=embeddings_model)
    
    if db_pool is None:
        db_pool = await get_database_pool()
    
    if embeddings_model is None:
        embeddings_model = get_embeddings_model()
    
    if llm is None:
        settings = get_settings()
        llm = get_llm(
            temperature=settings.LLM_TEMPERATURE,
            model=settings.LLM_MODEL
        )
    
    # Get collection prefix from settings if not provided
    if collection_prefix is None:
        settings = get_settings()
        # Try to get from settings, default to "comprehensive_index" to match indexing services
        collection_prefix = getattr(settings, 'COLLECTION_PREFIX', 'comprehensive_index')
    
    return ContextualGraphService(
        db_pool=db_pool,
        vector_store_client=vector_store_client,
        embeddings_model=embeddings_model,
        llm=llm,
        collection_prefix=collection_prefix,
        **kwargs
    )


async def get_dependencies():
    """Get all dependencies for the Knowledge App.
    
    Returns:
        Dictionary containing:
        - db_pool: Database connection pool
        - embeddings: Embeddings model
        - llm: LLM instance
        - vector_store_client: Vector store client (supports ChromaDB and Qdrant)
        - cache_client: Cache client
        - vector_store_type: The configured vector store type
        - contextual_graph_service: ContextualGraphService instance
        - query_engine: ContextualGraphQueryEngine instance
        - settings: Settings instance
        - chroma_client: ChromaDB client (if using ChromaDB)
    """
    settings = get_settings()
    
    # Initialize ChromaDB client early if using ChromaDB (needed for indexing services)
    chroma_client = None
    if settings.VECTOR_STORE_TYPE.value == "chroma":
        try:
            chroma_client = get_chromadb_client()
            logger.info("✓ ChromaDB client initialized in get_dependencies")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            # Continue anyway - vector_store_client will handle its own ChromaDB client
    
    # Get vector store client (supports both ChromaDB and Qdrant)
    vector_store_client = await get_vector_store_client(embeddings_model=get_embeddings_model())
    
    # Get database pool
    db_pool = await get_database_pool()
    
    # Get embeddings model
    embeddings = get_embeddings_model()
    
    # Get LLM
    llm = get_llm(
        temperature=settings.LLM_TEMPERATURE,
        model=settings.LLM_MODEL
    )
    
    # Get cache client
    cache_client = get_cache_client()
    
    # Get contextual graph service (optional - may not be available in all deployments)
    contextual_graph_service = None
    query_engine = None
    
    try:
        contextual_graph_service = await get_contextual_graph_service(
            vector_store_client=vector_store_client,
            db_pool=db_pool,
            embeddings_model=embeddings,
            llm=llm
        )
        logger.info("ContextualGraphService initialized successfully")
        
        # Get query engine
        query_engine = await get_contextual_graph_query_engine(
            vector_store_client=vector_store_client,
            db_pool=db_pool,
            embeddings_model=embeddings,
            llm=llm
        )
        logger.info("ContextualGraphQueryEngine initialized successfully")
    except ImportError as e:
        logger.warning(f"ContextualGraphService not available: {e}")
        logger.warning("Continuing without contextual graph service and query engine")
    except Exception as e:
        logger.warning(f"Failed to initialize contextual graph service: {e}")
        logger.warning("Continuing without contextual graph service and query engine")
    
    return {
        "db_pool": db_pool,
        "embeddings": embeddings,
        "llm": llm,
        "vector_store_client": vector_store_client,
        "cache_client": cache_client,
        "vector_store_type": settings.VECTOR_STORE_TYPE.value,
        "contextual_graph_service": contextual_graph_service,
        "query_engine": query_engine,
        "settings": settings,
        "chroma_client": chroma_client  # Add ChromaDB client for direct access
    }

