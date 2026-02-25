"""
Storage module for Knowledge App
Contains abstractions and implementations for vector store, cache, and database
Uses unified storage architecture from documents.py
"""
from app.storage.vector_store import VectorStoreClient, get_vector_store_client
from app.storage.cache import CacheClient, get_cache_client
from app.storage.database import DatabaseClient, get_database_client
from app.storage.factory import initialize_storage_clients, cleanup_storage_clients
from app.storage.documents import (
    DocumentChromaStore,
    DocumentQdrantStore,
    DocumentVectorstore,
    BM25Ranker,
    DuplicatePolicy,
    AsyncDocumentWriter,
    create_langchain_doc_util
)
# SQLAlchemy session management for ingestion (reuses existing database config)
from app.storage.sqlalchemy_session import (
    get_session,
    get_session_dependency,
    create_tables,
    drop_tables,
    check_connection as check_db_connection,
)
# Qdrant framework store for ingestion (reuses existing Qdrant config)
from app.storage.qdrant_framework_store import (
    Collections,
    get_qdrant_client,
    initialize_collections,
    upsert_points,
    search_collection,
    check_qdrant_connection,
)
# Framework collection factory for querying framework collections
from app.storage.framework_collection_factory import (
    FrameworkCollectionFactory,
    FrameworkArtifactType,
    get_framework_collection_factory,
)
# Consolidated collections registry
from app.storage.collections import (
    FrameworkCollections,
    MDLCollections,
    XSOARCollections,
    ComprehensiveIndexingCollections,
    ComplianceSkillCollections,
)

__all__ = [
    "VectorStoreClient",
    "get_vector_store_client",
    "CacheClient",
    "get_cache_client",
    "DatabaseClient",
    "get_database_client",
    "initialize_storage_clients",
    "cleanup_storage_clients",
    # Document storage classes
    "DocumentChromaStore",
    "DocumentQdrantStore",
    "DocumentVectorstore",
    "BM25Ranker",
    "DuplicatePolicy",
    "AsyncDocumentWriter",
    "create_langchain_doc_util",
    # SQLAlchemy session for ingestion
    "get_session",
    "get_session_dependency",
    "create_tables",
    "drop_tables",
    "check_db_connection",
    # Qdrant framework store for ingestion
    "Collections",  # Backward compatibility - use FrameworkCollections for new code
    "get_qdrant_client",
    "initialize_collections",
    "upsert_points",
    "search_collection",
    "check_qdrant_connection",
    # Framework collection factory
    "FrameworkCollectionFactory",
    "FrameworkArtifactType",
    "get_framework_collection_factory",
    # Consolidated collections registry
    "FrameworkCollections",
    "MDLCollections",
    "XSOARCollections",
    "ComprehensiveIndexingCollections",
    "ComplianceSkillCollections",
]
