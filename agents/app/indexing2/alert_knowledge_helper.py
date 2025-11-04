"""
Alert Knowledge Helper

This module provides a helper class to access the alert knowledge base
stored in ChromaDB through the ProjectReader.
"""

import logging
from typing import List, Dict, Optional
from app.indexing.project_reader import ProjectReader
from app.storage.documents import DocumentChromaStore
from app.core.dependencies import get_doc_store_provider, get_chromadb_client

logger = logging.getLogger(__name__)

class AlertKnowledgeHelper:
    """Helper class to access alert knowledge base from ChromaDB."""
    
    def __init__(self, project_reader: Optional[ProjectReader] = None):
        """Initialize the alert knowledge helper.
        
        Args:
            project_reader: Optional ProjectReader instance. If not provided,
                          a new one will be created.
        """
        self.project_reader = project_reader
        self.alert_knowledge_store = None
        self._initialize_knowledge_store()
    
    def _initialize_knowledge_store(self):
        """Initialize the alert knowledge store."""
        try:
            if self.project_reader:
                # Use existing project reader's knowledge store
                self.alert_knowledge_store = self.project_reader.get_alert_knowledge_store()
            else:
                # Use the document store provider to get the alert knowledge store
                logger.info("Getting alert knowledge store from document store provider")
                doc_store_provider = get_doc_store_provider()
                self.alert_knowledge_store = doc_store_provider.get_store("alert_knowledge_base")
                
            if self.alert_knowledge_store is None:
                logger.warning("Alert knowledge store is not available")
            else:
                logger.info("Alert knowledge store initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize alert knowledge store: {str(e)}")
            # Set to None as fallback
            self.alert_knowledge_store = None
            logger.warning("Alert knowledge store set to None due to initialization failure")
    
    def search_knowledge(self, query: str, k: int = 5, search_type: str = "semantic") -> List[str]:
        """Search the alert knowledge base and return content strings.
        
        Args:
            query: Search query string
            k: Number of results to return
            search_type: Type of search ("semantic", "bm25", "tfidf", "tfidf_only")
            
        Returns:
            List of knowledge content strings
        """
        try:
            if not self.alert_knowledge_store:
                logger.warning("Alert knowledge store not initialized")
                return []
            
            # Perform search based on type
            if search_type == "semantic":
                results = self.alert_knowledge_store.semantic_search(query, k=k)
            elif search_type == "bm25":
                results = self.alert_knowledge_store.semantic_search_with_bm25(query, k=k)
            elif search_type == "tfidf":
                results = self.alert_knowledge_store.semantic_search_with_tfidf(query, k=k)
            elif search_type == "tfidf_only":
                results = self.alert_knowledge_store.tfidf_search(query, k=k)
            else:
                logger.warning(f"Unknown search type: {search_type}, falling back to semantic search")
                results = self.alert_knowledge_store.semantic_search(query, k=k)
            
            # Extract content from results
            knowledge_content = [result["content"] for result in results]
            
            logger.info(f"Found {len(knowledge_content)} knowledge base results for query: {query}")
            return knowledge_content
            
        except Exception as e:
            logger.error(f"Error searching alert knowledge base: {str(e)}")
            return []
    
    def search_knowledge_with_metadata(self, query: str, k: int = 5, search_type: str = "semantic") -> List[Dict]:
        """Search the alert knowledge base and return full results with metadata.
        
        Args:
            query: Search query string
            k: Number of results to return
            search_type: Type of search ("semantic", "bm25", "tfidf", "tfidf_only")
            
        Returns:
            List of search results with content and metadata
        """
        try:
            if not self.alert_knowledge_store:
                logger.warning("Alert knowledge store not initialized")
                return []
            
            # Perform search based on type
            if search_type == "semantic":
                results = self.alert_knowledge_store.semantic_search(query, k=k)
            elif search_type == "bm25":
                results = self.alert_knowledge_store.semantic_search_with_bm25(query, k=k)
            elif search_type == "tfidf":
                results = self.alert_knowledge_store.semantic_search_with_tfidf(query, k=k)
            elif search_type == "tfidf_only":
                results = self.alert_knowledge_store.tfidf_search(query, k=k)
            else:
                logger.warning(f"Unknown search type: {search_type}, falling back to semantic search")
                results = self.alert_knowledge_store.semantic_search(query, k=k)
            
            logger.info(f"Found {len(results)} knowledge base results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching alert knowledge base: {str(e)}")
            return []
    
    def search_by_category(self, category: str, query: str = "", k: int = 5) -> List[str]:
        """Search knowledge base by category with optional query filter.
        
        Args:
            category: Knowledge category to filter by
            query: Optional additional query string
            k: Number of results to return
            
        Returns:
            List of knowledge content strings
        """
        try:
            if not self.alert_knowledge_store:
                logger.warning("Alert knowledge store not initialized")
                return []
            
            # Search with category filter
            where_filter = {"category": category}
            results = self.alert_knowledge_store.semantic_search(
                query=query or "knowledge", 
                k=k, 
                where=where_filter
            )
            
            # Extract content from results
            knowledge_content = [result["content"] for result in results]
            
            logger.info(f"Found {len(knowledge_content)} {category} knowledge results")
            return knowledge_content
            
        except Exception as e:
            logger.error(f"Error searching knowledge by category {category}: {str(e)}")
            return []
    
    def get_knowledge_store(self) -> Optional[DocumentChromaStore]:
        """Get the underlying knowledge store.
        
        Returns:
            DocumentChromaStore instance or None if not initialized
        """
        return self.alert_knowledge_store

# Global instance for easy access
_alert_knowledge_helper = None

def get_alert_knowledge_helper() -> AlertKnowledgeHelper:
    """Get the global alert knowledge helper instance.
    
    Returns:
        AlertKnowledgeHelper instance
    """
    global _alert_knowledge_helper
    if _alert_knowledge_helper is None:
        _alert_knowledge_helper = AlertKnowledgeHelper()
    return _alert_knowledge_helper

def initialize_alert_knowledge_helper(project_reader: ProjectReader) -> AlertKnowledgeHelper:
    """Initialize the global alert knowledge helper with a project reader.
    
    Args:
        project_reader: ProjectReader instance with initialized knowledge base
        
    Returns:
        AlertKnowledgeHelper instance
    """
    global _alert_knowledge_helper
    _alert_knowledge_helper = AlertKnowledgeHelper(project_reader)
    return _alert_knowledge_helper
