"""
Base vectorizer interface for vectorizers.
"""
from abc import ABC, abstractmethod
from typing import List, TypeVar, Generic

# Type variables for document and vector types
T = TypeVar('T')  # Generic type for documents
V = TypeVar('V')  # Generic type for vector chunks

class IVectorizer(Generic[T, V], ABC):
    """Interface for vectorizers that convert documents into vector chunks."""
    
    @abstractmethod
    def vectorize(self, documents: List[T]) -> List[V]:
        """
        Convert documents into vector chunks suitable for vector database storage.
        
        Args:
            documents: List of documents to vectorize
            
        Returns:
            List of vector chunks
        """
        pass 