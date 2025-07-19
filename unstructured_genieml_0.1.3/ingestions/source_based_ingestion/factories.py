"""
Abstract Factory pattern implementation for ingestion pipelines.

This module provides the abstract factory interfaces and concrete implementations
for creating ingestion pipeline components (extractors, vectorizers, stats generators, storage).
"""
from abc import ABC, abstractmethod
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from .connectors.base import IExtractor
from .vectorizers.base import IVectorizer
from .stats.base import IStatsGenerator
from .storage.base import IStorage

# Load environment variables from .env file
load_dotenv()

class IngestFactory(ABC):
    """Abstract Factory for creating components of an ingestion pipeline."""
    
    @abstractmethod
    def create_extractor(self) -> IExtractor:
        """Create an extractor instance."""
        pass
    
    @abstractmethod
    def create_vectorizer(self) -> IVectorizer:
        """Create a vectorizer instance."""
        pass
    
    @abstractmethod
    def create_stats_generator(self) -> Optional[IStatsGenerator]:
        """Create a stats generator instance, or None if not applicable."""
        pass
    
    @abstractmethod
    def create_storage(self, storage_type: str = "default") -> IStorage:
        """
        Create a storage instance.
        
        Args:
            storage_type: Type of storage to create ("chroma", "postgres", etc.)
            
        Returns:
            Storage instance
        """
        pass

class GongIngestFactory(IngestFactory):
    """Concrete factory for Gong ingestion components."""
    
    def create_extractor(self) -> IExtractor:
        from .connectors.gong import GongExtractor
        return GongExtractor()
    
    def create_vectorizer(self) -> IVectorizer:
        from .vectorizers.gong import GongVectorizer
        # Get OpenAI API key from environment variables
        openai_api_key = os.getenv("OPENAI_API_KEY")
        return GongVectorizer(openai_api_key=openai_api_key)
    
    def create_stats_generator(self) -> Optional[IStatsGenerator]:
        from .stats.gong import GongStatsGenerator
        return GongStatsGenerator()
    
    def create_storage(self, storage_type: str = "chroma") -> IStorage:
        if storage_type.lower() == "postgres":
            from .storage.postgres import PostgresStorage
            return PostgresStorage()
        else:
            from .storage.chroma import ChromaDBStorage
            return ChromaDBStorage()

class GDriveIngestFactory(IngestFactory):
    """Concrete factory for Google Drive document ingestion components."""
    
    def create_extractor(self) -> IExtractor:
        from .connectors.gdrive import GDriveExtractor
        return GDriveExtractor()
    
    def create_vectorizer(self) -> IVectorizer:
        from .vectorizers.document import DocumentVectorizer
        # Get OpenAI API key from environment variables
        openai_api_key = os.getenv("OPENAI_API_KEY")
        return DocumentVectorizer(openai_api_key=openai_api_key)
    
    def create_stats_generator(self) -> Optional[IStatsGenerator]:
        # No stats generator needed for documents
        return None
    
    def create_storage(self, storage_type: str = "chroma") -> IStorage:
        if storage_type.lower() == "postgres":
            from .storage.postgres import PostgresStorage
            return PostgresStorage()
        else:
            from .storage.chroma import ChromaDBStorage
            return ChromaDBStorage()

# Registry of source → factory
_FACTORY_REGISTRY = {
    "gong": GongIngestFactory(),
    "gdrive": GDriveIngestFactory(),
    "pdf": GDriveIngestFactory(),  # Use same factory for PDF ingestion
    # Other factories will be added here as they are implemented
}

def get_factory(source_type: str) -> IngestFactory:
    """
    Get the appropriate factory for a given source type.
    
    Args:
        source_type: Type of source ("gong", "pdf", "gdrive", "sfdc")
        
    Returns:
        Factory instance for the specified source
        
    Raises:
        ValueError: If the source type is not supported
    """
    try:
        return _FACTORY_REGISTRY[source_type.lower()]
    except KeyError:
        raise ValueError(f"Unknown source type {source_type}") 