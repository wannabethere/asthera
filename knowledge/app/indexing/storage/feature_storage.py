"""
Feature Storage Service
Handles storage and retrieval of feature feedback and indexed features.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.storage.documents import DocumentChromaStore, DocumentQdrantStore, sanitize_collection_name
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class FeatureStorageService:
    """Service for storing and managing feature feedback and indexed features."""
    
    def __init__(
        self,
        vector_store_type: str = "chroma",
        persistent_client=None,
        qdrant_client=None,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        collection_prefix: str = "feature_store"
    ):
        """
        Initialize the feature storage service.
        
        Args:
            vector_store_type: "chroma" or "qdrant"
            persistent_client: ChromaDB persistent client (for chroma)
            qdrant_client: Qdrant client (for qdrant)
            embeddings_model: Embeddings model instance
            collection_prefix: Prefix for collection names (default: "feature_store")
        """
        self.vector_store_type = vector_store_type.lower()
        self.collection_prefix = collection_prefix
        settings = get_settings()
        
        # Initialize embeddings
        self.embeddings_model = embeddings_model or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize stores
        self._init_stores(persistent_client, qdrant_client)
        
        logger.info(f"FeatureStorageService initialized with {vector_store_type}")
    
    def _init_stores(self, persistent_client, qdrant_client):
        """Initialize document stores based on vector store type."""
        self.stores = {}
        
        if self.vector_store_type == "chroma":
            if persistent_client is None:
                from app.core.dependencies import get_chromadb_client
                persistent_client = get_chromadb_client()
            self.persistent_client = persistent_client
            
            # Create store for feature feedback
            collection_name = f"{self.collection_prefix}_features" if self.collection_prefix else "feature_store_features"
            collection_name = sanitize_collection_name(collection_name)
            
            self.stores["features"] = DocumentChromaStore(
                persistent_client=self.persistent_client,
                collection_name=collection_name,
                embeddings_model=self.embeddings_model,
                tf_idf=True
            )
            logger.info(f"Initialized ChromaDB store: {collection_name}")
        
        elif self.vector_store_type == "qdrant":
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError("Qdrant dependencies not installed. Install with: pip install qdrant-client langchain-qdrant")
            
            if qdrant_client is None:
                qdrant_config = get_settings().get_vector_store_config()
                qdrant_client = QdrantClient(
                    host=qdrant_config.get("host", "localhost"),
                    port=qdrant_config.get("port", 6333)
                )
            self.qdrant_client = qdrant_client
            
            collection_name = f"{self.collection_prefix}_features" if self.collection_prefix else "feature_store_features"
            collection_name = sanitize_collection_name(collection_name)
            
            self.stores["features"] = DocumentQdrantStore(
                qdrant_client=self.qdrant_client,
                collection_name=collection_name,
                embeddings_model=self.embeddings_model,
                tf_idf=False
            )
            logger.info(f"Initialized Qdrant store: {collection_name}")
        
        else:
            raise ValueError(f"Unsupported vector_store_type: {self.vector_store_type}")
    
    def add_feature_feedback(
        self,
        question: str,
        feature_type: str,
        compliance: str,
        control: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a feature feedback entry to the store.
        
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
        # Validate feature type
        valid_types = ["control", "risk", "impact", "likelihood", "evidence", "effectiveness"]
        if feature_type not in valid_types:
            raise ValueError(f"Invalid feature_type: {feature_type}. Must be one of {valid_types}")
        
        # Create document content
        content = {
            "question": question,
            "feature_type": feature_type,
            "compliance": compliance,
            "control": control,
            "description": description or question
        }
        
        # Create document metadata
        doc_metadata = {
            "feature_type": feature_type,
            "compliance": compliance,
            "control": control or "none",
            "source": "feedback",
            "created_at": datetime.utcnow().isoformat(),
            "feature_id": str(uuid4()),
            **(metadata or {})
        }
        
        # Create document
        doc = Document(
            page_content=json.dumps(content, indent=2),
            metadata=doc_metadata
        )
        
        # Store document
        try:
            store = self.stores["features"]
            result = store.add_documents([doc])
            logger.info(f"Added feature feedback: {question[:50]}... (type: {feature_type}, compliance: {compliance})")
            
            return {
                "success": True,
                "feature_id": doc_metadata["feature_id"],
                "question": question,
                "feature_type": feature_type,
                "compliance": compliance,
                "control": control,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding feature feedback: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
        Search for features in the store.
        
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
        store = self.stores["features"]
        
        # Build where clause for filtering
        where_clause = {}
        if feature_type:
            where_clause["feature_type"] = feature_type
        if compliance:
            where_clause["compliance"] = compliance
        if control:
            where_clause["control"] = control
        
        try:
            if search_type == "semantic":
                results = store.semantic_search(query, k=k, where=where_clause if where_clause else None)
            elif search_type == "bm25":
                results = store.semantic_search_with_bm25(query, k=k, where=where_clause if where_clause else None)
            elif search_type == "tfidf":
                results = store.semantic_search_with_tfidf(query, k=k, where=where_clause if where_clause else None)
            elif search_type == "tfidf_only":
                results = store.tfidf_search(query, k=k, where=where_clause if where_clause else None)
            else:
                results = store.semantic_search(query, k=k, where=where_clause if where_clause else None)
            
            # Parse results
            parsed_results = []
            for result in results:
                try:
                    content = json.loads(result.get("page_content", "{}"))
                    parsed_results.append({
                        "question": content.get("question", ""),
                        "feature_type": content.get("feature_type", ""),
                        "compliance": content.get("compliance", ""),
                        "control": content.get("control"),
                        "description": content.get("description", ""),
                        "score": result.get("score", 0),
                        "metadata": result.get("metadata", {})
                    })
                except json.JSONDecodeError:
                    # Fallback if content is not JSON
                    parsed_results.append({
                        "question": result.get("page_content", ""),
                        "feature_type": result.get("metadata", {}).get("feature_type", ""),
                        "compliance": result.get("metadata", {}).get("compliance", ""),
                        "control": result.get("metadata", {}).get("control"),
                        "score": result.get("score", 0),
                        "metadata": result.get("metadata", {})
                    })
            
            return {
                "success": True,
                "results": parsed_results,
                "count": len(parsed_results),
                "query": query
            }
        except Exception as e:
            logger.error(f"Error searching features: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "count": 0
            }
    
    def get_feature_by_id(self, feature_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a feature by its ID.
        
        Args:
            feature_id: Feature ID
        
        Returns:
            Feature data or None if not found
        """
        # Search for the feature by ID in metadata
        results = self.search_features(
            query="",
            k=1,
            search_type="semantic"
        )
        
        # Filter by feature_id in metadata
        for result in results.get("results", []):
            if result.get("metadata", {}).get("feature_id") == feature_id:
                return result
        
        return None

