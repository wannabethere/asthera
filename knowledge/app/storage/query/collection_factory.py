"""
Collection Factory for Contextual Graph Reasoning

Provides unified access to all collections needed for contextual reasoning:
- Connectors (data sources, APIs, integrations)
- Domains (business domains, data domains)
- Compliance (controls, requirements, policies)
- Risks (risk controls, risk assessments)
- Additionals (policies, evidence, etc.)
- Schemas (tables, columns, schema descriptions - separate from main hierarchy)
"""
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from langchain_openai import OpenAIEmbeddings

from app.services.hybrid_search_service import HybridSearchService
from app.storage.documents import sanitize_collection_name

if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)


class CollectionFactory:
    """
    Factory for accessing all collections used in contextual graph reasoning.
    
    Hierarchy:
    - Connector -> Domain -> Compliance -> Risks -> Additionals
    - Schemas (tables, columns) are separate
    
    Collections:
    1. Connectors: extendable_entities, product_purpose, product_docs, product_key_concepts
    2. Domains: domain_knowledge, policy_context
    3. Compliance: compliance_controls, policy_requirements, policy_entities, entities, evidence, fields, controls
    4. Risks: (stored in domain_knowledge with type="risk" in metadata)
    5. Additionals: policy_documents, policy_evidence, policy_fields
    6. Schemas: table_definitions, table_descriptions, column_definitions, schema_descriptions
    
    Note: General collections (entities, evidence, fields, controls) use metadata.type for filtering.
    Policy-specific collections (policy_entities, policy_evidence, policy_fields) are kept for backward compatibility.
    """
    
    def __init__(
        self,
        vector_store_client: "VectorStoreClient",
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        collection_prefix: str = "comprehensive_index"
    ):
        """
        Initialize collection factory.
        
        Args:
            vector_store_client: VectorStoreClient instance (supports ChromaDB, Qdrant, etc.)
            embeddings_model: Optional embeddings model (will use vector_store_client's if None)
            collection_prefix: Prefix for collection names
        """
        self.vector_store_client = vector_store_client
        self.embeddings_model = embeddings_model  # Will be set from vector_store_client if None
        self.collection_prefix = collection_prefix
        
        # Initialize all collection services
        self._init_collections()
        
        logger.info(f"Initialized CollectionFactory with prefix: {collection_prefix}")
    
    def _get_collection_name(self, base_name: str) -> str:
        """
        Get collection name with prefix, sanitized for ChromaDB compliance.
        
        Args:
            base_name: Base collection name (e.g., "policy_context")
            
        Returns:
            Sanitized collection name with prefix
        """
        if self.collection_prefix:
            full_name = f"{self.collection_prefix}_{base_name}"
        else:
            # If prefix is empty, use base_name directly (but sanitize it)
            full_name = base_name
        return sanitize_collection_name(full_name)
    
    def _init_collections(self):
        """Initialize all collection services"""
        
        # ========================================================================
        # 1. CONNECTOR COLLECTIONS
        # ========================================================================
        self.connector_collections = {
            "extendable_entities": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("extendable_entities"),
                embeddings_model=self.embeddings_model
            ),
            "product_purpose": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("product_purpose"),
                embeddings_model=self.embeddings_model
            ),
            "product_docs": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("product_docs"),
                embeddings_model=self.embeddings_model
            ),
            "product_key_concepts": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("product_key_concepts"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 2. DOMAIN COLLECTIONS
        # ========================================================================
        self.domain_collections = {
            "domain_knowledge": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("domain_knowledge"),
                embeddings_model=self.embeddings_model
            ),
            "policy_context": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_context"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 3. COMPLIANCE COLLECTIONS
        # ========================================================================
        self.compliance_collections = {
            "compliance_controls": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("compliance_controls"),
                embeddings_model=self.embeddings_model
            ),
            "policy_requirements": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_requirements"),
                embeddings_model=self.embeddings_model
            ),
            "policy_entities": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_entities"),
                embeddings_model=self.embeddings_model
            ),
            # General collections (use metadata.type for filtering)
            "entities": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("entities"),
                embeddings_model=self.embeddings_model
            ),
            "evidence": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("evidence"),
                embeddings_model=self.embeddings_model
            ),
            "fields": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("fields"),
                embeddings_model=self.embeddings_model
            ),
            "controls": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("controls"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 4. RISK COLLECTIONS
        # ========================================================================
        self.risk_collections = {
            "risk_controls": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("risk_controls"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 5. ADDITIONAL COLLECTIONS
        # ========================================================================
        self.additional_collections = {
            "policy_documents": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_documents"),
                embeddings_model=self.embeddings_model
            ),
            "policy_evidence": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_evidence"),
                embeddings_model=self.embeddings_model
            ),
            "policy_fields": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_fields"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 6. SCHEMA COLLECTIONS (Separate from hierarchy)
        # ========================================================================
        self.schema_collections = {
            "table_definitions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("table_definitions"),
                embeddings_model=self.embeddings_model
            ),
            "table_descriptions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("table_descriptions"),
                embeddings_model=self.embeddings_model
            ),
            "column_definitions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("column_definitions"),
                embeddings_model=self.embeddings_model
            ),
            "schema_descriptions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("schema_descriptions"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # All collections map for easy access
        self.all_collections = {
            **self.connector_collections,
            **self.domain_collections,
            **self.compliance_collections,
            **self.risk_collections,
            **self.additional_collections,
            **self.schema_collections,
        }
    
    def get_collection(self, collection_name: str) -> Optional[HybridSearchService]:
        """
        Get a collection service by name.
        
        Args:
            collection_name: Name of the collection (with or without prefix)
            
        Returns:
            HybridSearchService instance or None if not found
        """
        # Try with prefix first (sanitized)
        prefixed_name = self._get_collection_name(collection_name)
        if prefixed_name in self.all_collections:
            return self.all_collections[prefixed_name]
        
        # Try without prefix (but sanitize)
        sanitized_name = sanitize_collection_name(collection_name)
        if sanitized_name in self.all_collections:
            return self.all_collections[sanitized_name]
        
        logger.warning(f"Collection not found: {collection_name}")
        return None
    
    def get_collection_by_store_name(self, store_name: str) -> Optional[HybridSearchService]:
        """
        Get a collection service by store name (without prefix).
        
        This method looks up collections by their base store name across all collection types.
        Useful when you have fixed store names and want to get the corresponding collection.
        
        Args:
            store_name: Base store name (e.g., "policy_context", "table_definitions")
            
        Returns:
            HybridSearchService instance or None if not found
        """
        # Look in all_collections by store name (key is the store name, not the collection name)
        if store_name in self.all_collections:
            return self.all_collections[store_name]
        
        logger.warning(f"Store '{store_name}' not found in collection factory")
        return None
    
    async def search_connectors(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across all connector collections.
        
        Args:
            query: Search query
            top_k: Number of results per collection
            filters: Optional metadata filters
            
        Returns:
            List of results from all connector collections
        """
        results = []
        for name, service in self.connector_collections.items():
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "connector"
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
        
        return results
    
    async def search_domains(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all domain collections"""
        results = []
        for name, service in self.domain_collections.items():
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "domain"
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
        
        return results
    
    async def search_compliance(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all compliance collections"""
        results = []
        for name, service in self.compliance_collections.items():
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "compliance"
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
        
        return results
    
    async def search_risks(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all risk collections"""
        results = []
        for name, service in self.risk_collections.items():
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "risk"
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
        
        return results
    
    async def search_schemas(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all schema collections (tables, columns, schemas)"""
        results = []
        for name, service in self.schema_collections.items():
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "schema"
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
        
        return results
    
    async def search_all(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        include_schemas: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across all collections organized by hierarchy.
        
        Args:
            query: Search query
            top_k: Number of results per collection
            filters: Optional metadata filters
            include_schemas: Whether to include schema collections
            
        Returns:
            Dictionary with results organized by entity type
        """
        return {
            "connectors": await self.search_connectors(query, top_k, filters),
            "domains": await self.search_domains(query, top_k, filters),
            "compliance": await self.search_compliance(query, top_k, filters),
            "risks": await self.search_risks(query, top_k, filters),
            "additionals": await self.search_additionals(query, top_k, filters),
            **({"schemas": await self.search_schemas(query, top_k, filters)} if include_schemas else {})
        }
    
    async def search_additionals(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all additional collections"""
        results = []
        for name, service in self.additional_collections.items():
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "additional"
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
        
        return results
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics for all collections"""
        stats = {}
        for name, service in self.all_collections.items():
            try:
                # Get collection via vector store client
                collection = await self.vector_store_client.get_collection(
                    collection_name=service.collection_name,
                    create_if_not_exists=False
                )
                # Try to get count - this depends on the vector store implementation
                # For now, we'll just note that the collection exists
                stats[name] = {
                    "exists": True,
                    "collection_name": service.collection_name
                }
            except Exception as e:
                stats[name] = {
                    "exists": False,
                    "error": str(e),
                    "collection_name": service.collection_name
                }
        
        return stats

