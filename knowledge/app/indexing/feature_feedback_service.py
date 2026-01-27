"""
Feature Feedback Service
Service for adding and managing feature feedback entries.
"""
import logging
from typing import Dict, Any, Optional

from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from app.indexing.storage.feature_storage import FeatureStorageService
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class FeatureFeedbackService:
    """Service for adding and managing feature feedback."""
    
    def __init__(
        self,
        vector_store_type: str = "chroma",
        persistent_client=None,
        qdrant_client=None,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        collection_prefix: str = "feature_store"
    ):
        """
        Initialize the feature feedback service.
        
        Args:
            vector_store_type: "chroma" or "qdrant"
            persistent_client: ChromaDB persistent client (for chroma)
            qdrant_client: Qdrant client (for qdrant)
            embeddings_model: Embeddings model instance
            collection_prefix: Prefix for collection names
        """
        self.storage_service = FeatureStorageService(
            vector_store_type=vector_store_type,
            persistent_client=persistent_client,
            qdrant_client=qdrant_client,
            embeddings_model=embeddings_model,
            collection_prefix=collection_prefix
        )
        
        logger.info("FeatureFeedbackService initialized")
    
    def add_feature(
        self,
        question: str,
        feature_type: str,
        compliance: str,
        control: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new feature feedback entry.
        
        Args:
            question: Natural language question for the feature
            feature_type: Type of feature (control, risk, impact, likelihood, evidence, effectiveness)
            compliance: Compliance framework (SOC2, HIPAA, etc.)
            control: Optional control identifier
            description: Optional description of the feature
            metadata: Additional metadata
        
        Returns:
            Dictionary with result information
        """
        return self.storage_service.add_feature_feedback(
            question=question,
            feature_type=feature_type,
            compliance=compliance,
            control=control,
            description=description,
            metadata=metadata
        )
    
    def search_features(
        self,
        query: str,
        feature_type: Optional[str] = None,
        compliance: Optional[str] = None,
        control: Optional[str] = None,
        k: int = 10,
        search_type: str = "semantic"
    ) -> Dict[str, Any]:
        """
        Search for features.
        
        Args:
            query: Search query
            feature_type: Filter by feature type
            compliance: Filter by compliance framework
            control: Filter by control
            k: Number of results
            search_type: "semantic", "bm25", "tfidf", "tfidf_only"
        
        Returns:
            Dictionary with search results
        """
        return self.storage_service.search_features(
            query=query,
            feature_type=feature_type,
            compliance=compliance,
            control=control,
            k=k,
            search_type=search_type
        )
    
    def get_feature_by_id(self, feature_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a feature by its ID.
        
        Args:
            feature_id: Feature ID
        
        Returns:
            Feature data or None if not found
        """
        return self.storage_service.get_feature_by_id(feature_id)

