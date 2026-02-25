"""
Collection Factory for Framework Ingestion

Provides unified access to framework-related collections in Qdrant:
- Controls (framework controls)
- Requirements (framework requirements)
- Risks (framework risks)
- Test Cases (framework test cases)
- Scenarios (framework scenarios)
- User Policies (user-uploaded document chunks)

This factory is designed for use by other systems that need to query
framework data from Qdrant.
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.storage.qdrant_framework_store import (
    get_qdrant_client,
    Collections,
    search_collection,
)

logger = logging.getLogger(__name__)


class FrameworkArtifactType(str, Enum):
    """Types of framework artifacts stored in collections."""
    CONTROL = "control"
    REQUIREMENT = "requirement"
    RISK = "risk"
    TEST_CASE = "test_case"
    SCENARIO = "scenario"
    USER_POLICY = "user_policy"


class FrameworkCollectionFactory:
    """
    Factory for accessing framework-related collections in Qdrant.
    
    Provides methods to:
    - Get collection names for different artifact types
    - Search collections with filters
    - Query by framework, domain, artifact type, etc.
    """
    
    def __init__(self, qdrant_client: Optional[QdrantClient] = None):
        """
        Initialize the framework collection factory.
        
        Args:
            qdrant_client: Optional QdrantClient instance. If None, uses singleton from qdrant_framework_store.
        """
        self._client = qdrant_client or get_qdrant_client()
        logger.info("FrameworkCollectionFactory initialized")
    
    # ---------------------------------------------------------------------------
    # Collection name getters
    # ---------------------------------------------------------------------------
    
    @staticmethod
    def get_collection_for_artifact(artifact_type: FrameworkArtifactType) -> str:
        """
        Get the Qdrant collection name for a given artifact type.
        
        Args:
            artifact_type: Type of framework artifact
            
        Returns:
            Collection name string
        """
        mapping = {
            FrameworkArtifactType.CONTROL: Collections.CONTROLS,
            FrameworkArtifactType.REQUIREMENT: Collections.REQUIREMENTS,
            FrameworkArtifactType.RISK: Collections.RISKS,
            FrameworkArtifactType.TEST_CASE: Collections.TEST_CASES,
            FrameworkArtifactType.SCENARIO: Collections.SCENARIOS,
            FrameworkArtifactType.USER_POLICY: Collections.USER_POLICIES,
        }
        return mapping[artifact_type]
    
    @staticmethod
    def get_all_collections() -> List[str]:
        """Get all framework collection names."""
        return Collections.ALL
    
    @staticmethod
    def get_framework_collections() -> List[str]:
        """Get all framework-specific collection names (excludes user_policies)."""
        return Collections.ALL_FRAMEWORK
    
    # ---------------------------------------------------------------------------
    # Search methods
    # ---------------------------------------------------------------------------
    
    def search_controls(
        self,
        query_vector: List[float],
        framework_id: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> List[qmodels.ScoredPoint]:
        """
        Search for controls matching the query vector.
        
        Args:
            query_vector: Embedding vector for semantic search
            framework_id: Optional framework ID filter
            domain: Optional domain filter
            limit: Maximum number of results
            
        Returns:
            List of ScoredPoint results
        """
        filters = self._build_framework_filter(framework_id, domain)
        return search_collection(
            collection=Collections.CONTROLS,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
        )
    
    def search_requirements(
        self,
        query_vector: List[float],
        framework_id: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> List[qmodels.ScoredPoint]:
        """Search for requirements matching the query vector."""
        filters = self._build_framework_filter(framework_id, domain)
        return search_collection(
            collection=Collections.REQUIREMENTS,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
        )
    
    def search_risks(
        self,
        query_vector: List[float],
        framework_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[qmodels.ScoredPoint]:
        """Search for risks matching the query vector."""
        filters = self._build_framework_filter(framework_id)
        return search_collection(
            collection=Collections.RISKS,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
        )
    
    def search_scenarios(
        self,
        query_vector: List[float],
        framework_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[qmodels.ScoredPoint]:
        """Search for scenarios matching the query vector."""
        filters = self._build_framework_filter(framework_id)
        return search_collection(
            collection=Collections.SCENARIOS,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
        )
    
    def search_test_cases(
        self,
        query_vector: List[float],
        framework_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[qmodels.ScoredPoint]:
        """Search for test cases matching the query vector."""
        filters = self._build_framework_filter(framework_id)
        return search_collection(
            collection=Collections.TEST_CASES,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
        )
    
    def search_user_policies(
        self,
        query_vector: List[float],
        session_id: Optional[str] = None,
        framework_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[qmodels.ScoredPoint]:
        """Search for user-uploaded policy documents."""
        conditions = []
        if framework_id:
            conditions.append(
                qmodels.FieldCondition(
                    key="framework_id",
                    match=qmodels.MatchValue(value=framework_id)
                )
            )
        if session_id:
            conditions.append(
                qmodels.FieldCondition(
                    key="session_id",
                    match=qmodels.MatchValue(value=session_id)
                )
            )
        
        filters = qmodels.Filter(must=conditions) if conditions else None
        return search_collection(
            collection=Collections.USER_POLICIES,
            query_vector=query_vector,
            limit=limit,
            filters=filters,
        )
    
    # ---------------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------------
    
    @staticmethod
    def _build_framework_filter(
        framework_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Optional[qmodels.Filter]:
        """Build a Qdrant filter for framework and domain."""
        conditions = []
        if framework_id:
            conditions.append(
                qmodels.FieldCondition(
                    key="framework_id",
                    match=qmodels.MatchValue(value=framework_id)
                )
            )
        if domain:
            conditions.append(
                qmodels.FieldCondition(
                    key="domain",
                    match=qmodels.MatchValue(value=domain)
                )
            )
        return qmodels.Filter(must=conditions) if conditions else None
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary with collection information
        """
        try:
            collection_info = self._client.get_collection(collection_name)
            return {
                "name": collection_name,
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "config": {
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance,
                }
            }
        except Exception as exc:
            logger.error(f"Failed to get collection info for {collection_name}: {exc}")
            return {"name": collection_name, "error": str(exc)}


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def get_framework_collection_factory(
    qdrant_client: Optional[QdrantClient] = None
) -> FrameworkCollectionFactory:
    """
    Get a FrameworkCollectionFactory instance.
    
    Args:
        qdrant_client: Optional QdrantClient instance
        
    Returns:
        FrameworkCollectionFactory instance
    """
    return FrameworkCollectionFactory(qdrant_client=qdrant_client)
