"""
Base extractor interface for connectors.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, TypeVar, Generic

# Type variable for document type
T = TypeVar('T')  # Generic type for documents

class IExtractor(Generic[T], ABC):
    """Interface for extractors that pull data from various sources."""
    
    @abstractmethod
    def extract(self, config: Dict[str, Any]) -> List[T]:
        """
        Extract documents from a source based on the provided configuration.
        
        Args:
            config: Configuration parameters for extraction
            
        Returns:
            List of extracted documents
        """
        pass 