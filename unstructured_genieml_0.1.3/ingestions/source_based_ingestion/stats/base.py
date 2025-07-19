"""
Base stats generator interface for stats generators.
"""
from abc import ABC, abstractmethod
from typing import List, TypeVar, Generic

# Type variables for document and stats types
T = TypeVar('T')  # Generic type for documents
S = TypeVar('S')  # Generic type for stats

class IStatsGenerator(Generic[T, S], ABC):
    """Interface for stats generators that extract statistics from documents."""
    
    @abstractmethod
    def generate_stats(self, documents: List[T]) -> List[S]:
        """
        Generate statistics from documents.
        
        Args:
            documents: List of documents to analyze
            
        Returns:
            List of statistics records
        """
        pass 