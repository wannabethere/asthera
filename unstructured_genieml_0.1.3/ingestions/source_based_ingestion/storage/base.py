"""
Base storage interface for storage backends.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class IStorage(ABC):
    """Interface for storage backends that persist documents, vectors, and stats."""
    
    @abstractmethod
    def store_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a document in the storage backend.
        
        Args:
            document: The document to store
            
        Returns:
            Result dictionary with status and document ID
        """
        pass