"""
Indexing2 - Unified ChromaDB Storage Mechanism

This module provides a unified storage mechanism that consolidates:
- TABLE_SCHEMA documents with descriptions, business context, and metadata
- Individual documents for TABLE_COLUMNS, RELATIONSHIPS, METRICS, VIEWS
- TF-IDF generation for quick reference lookups
- Enhanced search capabilities with embeddings

This eliminates duplication while maintaining backward compatibility.
"""

from .unified_storage import UnifiedStorage
from .tfidf_generator import TFIDFGenerator
from .document_builder import DocumentBuilder
from .storage_manager import StorageManager
from .ddl_chunker import DDLChunker
from .natural_language_search import NaturalLanguageSearch
from .query_builder import QueryBuilder
from .llm_field_classifier import LLMFieldClassifier
from .llm_query_optimizer import LLMQueryOptimizer
from .retrieval_helper2 import RetrievalHelper2
from .retrieval2 import TableRetrieval2
from .project_reader2 import ProjectReader2

__all__ = [
    "UnifiedStorage",
    "TFIDFGenerator", 
    "DocumentBuilder",
    "StorageManager",
    "DDLChunker",
    "NaturalLanguageSearch",
    "QueryBuilder",
    "LLMFieldClassifier",
    "LLMQueryOptimizer",
    "RetrievalHelper2",
    "TableRetrieval2",
    "ProjectReader2"
]
