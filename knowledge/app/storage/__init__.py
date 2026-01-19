"""
Storage module for Knowledge App
Contains abstractions and implementations for vector store, cache, and database
Uses unified storage architecture from documents.py
"""
from .vector_store import VectorStoreClient, get_vector_store_client
from .cache import CacheClient, get_cache_client
from .database import DatabaseClient, get_database_client
from .factory import initialize_storage_clients, cleanup_storage_clients
from .documents import (
    DocumentChromaStore,
    DocumentQdrantStore,
    DocumentVectorstore,
    BM25Ranker,
    DuplicatePolicy,
    AsyncDocumentWriter,
    create_langchain_doc_util
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
]
