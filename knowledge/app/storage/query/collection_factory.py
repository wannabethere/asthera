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
    
    This factory matches the stores defined in ingest_preview_files.py CONTENT_TYPE_TO_STORE.
    
    Hierarchy:
    - Connector -> Domain -> Compliance -> Risks -> Additionals
    - Schemas (tables, columns) are separate
    - Features (feature knowledge base) are separate
    - Contextual Graph (relationship edges between entities/tables) - accessed via ContextualGraphService
    
    Collections (aligned with ingest_preview_files.py STORE_NAME_TO_EXTRACTION_TYPE):
    1. Connectors: (empty - product/connector content routes to general stores with type="product")
    2. Domains: domain_knowledge (policies, risks, products use metadata.type to distinguish)
    3. Compliance: compliance_controls, entities, evidence, fields, controls
        - General collections (entities, evidence, fields, controls) use metadata.type for filtering
        - Policies route to general stores with type="policy" in metadata
        - Risks route to general stores with type="risk" in metadata
        - Products route to general stores (entities, domain_knowledge) with type="product" in metadata
    4. Risks: (stored in domain_knowledge with type="risk" in metadata, or in general stores)
    5. Policies: (routed to general stores with type="policy" in metadata)
        - policy_documents routes to general stores (entities, evidence, fields, domain_knowledge)
    6. Schemas: table_definitions, table_descriptions, column_definitions, schema_descriptions
        - IMPORTANT: Schema collections are ALWAYS UNPREFIXED (even if collection_prefix is set)
        - This matches index_mdl.py and retrieval.py which use unprefixed collection names
        - These collections are shared between comprehensive indexing and project-based systems
    7. Features: features (feature knowledge base for similar feature discovery)
    8. Contextual Graph Edges: contextual_edges (relationship edges between tables/entities)
        - Stored in contextual_edges collection via ContextualGraphStorage
        - Relationship types: BELONGS_TO_TABLE, HAS_MANY_TABLES, REFERENCES_TABLE, MANY_TO_MANY_TABLE, etc.
        - Access via ContextualGraphService.get_related_tables() or ContextualGraphReasoningAgent.get_related_tables()
        - Used to discover related tables based on MDL relationship definitions
    
    Note: 
    - General collections (entities, evidence, fields, controls, domain_knowledge) use metadata.type for filtering
    - Policy content routes to general stores, not separate policy_* collections
    - Risk content routes to domain_knowledge or general stores with type="risk"
    - Product content routes to connector/domain stores with type="product"
    - Features collection stores feature knowledge base entries indexed from feature JSON files
    - Table relationships are stored as contextual edges and can be accessed via ContextualGraphService
    - Use get_related_tables() method in ContextualGraphReasoningAgent to find related tables via relationship edges
    - Schema collections (table_definitions, table_descriptions, column_definitions, schema_descriptions) are 
      always unprefixed to match index_mdl.py and retrieval.py which write/read from unprefixed collections
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
        
        Schema collections (table_definitions, table_descriptions, column_definitions, 
        schema_descriptions) are always unprefixed to match project_reader.py and 
        index_mdl.py which write to unprefixed collections.
        
        Args:
            base_name: Base collection name (e.g., "policy_context")
            
        Returns:
            Sanitized collection name with prefix (except for schema collections)
        """
        # Schema collections are always unprefixed to match index_mdl.py and retrieval.py
        # These collections are shared between comprehensive indexing and project-based systems
        unprefixed_schema_collections = {
            "table_definitions",
            "table_descriptions", 
            "column_definitions",
            "schema_descriptions",
            "db_schema",  # Also unprefixed
            "column_metadata"  # Also unprefixed (column_definitions maps to this)
        }
        
        if base_name in unprefixed_schema_collections:
            # Schema collections are always unprefixed
            return sanitize_collection_name(base_name)
        
        if self.collection_prefix:
            full_name = f"{self.collection_prefix}_{base_name}"
        else:
            # If prefix is empty, use base_name directly (but sanitize it)
            full_name = base_name
        return sanitize_collection_name(full_name)
    
    def _init_collections(self):
        """Initialize all collection services"""
        
        # ========================================================================
        # 1. CONNECTOR COLLECTIONS (Product/Connector stores)
        # ========================================================================
        # Note: Product/connector content types (product_purpose, product_docs, extendable_entities, etc.)
        # are routed to general stores (entities, domain_knowledge) with type="product" in metadata.
        # They don't exist as separate collections - use search_compliance() or search_domains() 
        # with filters={"type": "product"} to find product content.
        self.connector_collections = {
            # Empty - product/connector content routes to general stores
        }
        
        # ========================================================================
        # 2. DOMAIN COLLECTIONS
        # ========================================================================
        # domain_knowledge stores policies, risks, products (distinguished by metadata.type)
        # Policy context, risk context, and product docs all route to domain_knowledge
        self.domain_collections = {
            "domain_knowledge": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("domain_knowledge"),
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 3. COMPLIANCE COLLECTIONS
        # ========================================================================
        # General collections use metadata.type for filtering (policy, risk, compliance, etc.)
        # Policy content routes to general stores with type="policy" in metadata
        # Risk content routes to general stores with type="risk" in metadata
        self.compliance_collections = {
            "compliance_controls": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("compliance_controls"),
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
        # Risks are stored in domain_knowledge with type="risk" in metadata
        # Risk controls route to general "controls" store with type="risk"
        # Risk entities, evidence, fields route to general stores with type="risk"
        # This section is kept for backward compatibility but risks are primarily in domain_knowledge
        self.risk_collections = {
            # Note: risk_controls collection doesn't exist - risks route to domain_knowledge or general stores
            # Keeping empty for now, but can add if a dedicated risk collection is created
        }
        
        # ========================================================================
        # 5. ADDITIONAL COLLECTIONS
        # ========================================================================
        # Policy documents route to general stores (entities, evidence, fields, domain_knowledge)
        # with type="policy" in metadata. The policy_documents collection name exists but
        # content is routed to general stores during ingestion.
        self.additional_collections = {
            "policy_documents": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("policy_documents"),
                embeddings_model=self.embeddings_model
            ),
            # Note: policy_evidence, policy_fields, policy_entities don't exist as separate collections
            # They route to general stores (evidence, fields, entities) with type="policy" in metadata
        }
        
        # ========================================================================
        # 6. SCHEMA COLLECTIONS (Separate from hierarchy)
        # ========================================================================
        # NOTE: Schema collections are always unprefixed (even if collection_prefix is set)
        # This matches index_mdl.py and retrieval.py which use unprefixed collection names
        # These collections are shared between comprehensive indexing and project-based systems
        self.schema_collections = {
            "table_definitions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("table_definitions"),  # Will be unprefixed
                embeddings_model=self.embeddings_model
            ),
            "table_descriptions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("table_descriptions"),  # Will be unprefixed
                embeddings_model=self.embeddings_model
            ),
            "column_definitions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("column_definitions"),  # Will be unprefixed
                embeddings_model=self.embeddings_model
            ),
            "schema_descriptions": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name("schema_descriptions"),  # Will be unprefixed
                embeddings_model=self.embeddings_model
            ),
        }
        
        # ========================================================================
        # 7. FEATURE COLLECTIONS (for feature knowledge base)
        # ========================================================================
        # Features can be stored with different collection names:
        # - "features" (direct name)
        # - "feature_store_features" (with feature_store prefix)
        # - "{collection_prefix}_features" (with custom prefix)
        # We'll try to use the collection_prefix if available, otherwise use "features"
        feature_base_name = "features"
        # If collection_prefix is set and not empty, use it
        if self.collection_prefix:
            # Try with prefix first
            feature_base_name = f"{self.collection_prefix}_features"
        # Also try "feature_store_features" as fallback
        # But for now, just use the standard naming convention
        
        self.feature_collections = {
            "features": HybridSearchService(
                vector_store_client=self.vector_store_client,
                collection_name=self._get_collection_name(feature_base_name),
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
            **self.feature_collections,
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
        Search for connector/product content.
        
        Note: Product/connector content is stored in general collections (entities, domain_knowledge)
        with type="product" in metadata. This method searches those collections with the product filter.
        
        Args:
            query: Search query
            top_k: Number of results per collection
            filters: Optional metadata filters (will add type="product" if not present)
            
        Returns:
            List of results from entities and domain_knowledge collections with type="product"
        """
        # Product content is stored in entities and domain_knowledge with type="product"
        import asyncio
        
        # Add type="product" to filters
        product_filters = filters.copy() if filters else {}
        product_filters["type"] = "product"
        
        # Build parallel search tasks
        tasks = []
        
        # Search entities collection for product entities
        if "entities" in self.compliance_collections:
            async def search_entities():
                try:
                    entity_results = await self.compliance_collections["entities"].hybrid_search(
                        query=query,
                        top_k=top_k,
                        where=product_filters
                    )
                    for result in entity_results:
                        result["collection_name"] = "entities"
                        result["entity_type"] = "connector"
                    return entity_results
                except Exception as e:
                    logger.warning(f"Error searching entities for products: {str(e)}")
                    return []
            tasks.append(search_entities())
        
        # Search domain_knowledge collection for product docs
        if "domain_knowledge" in self.domain_collections:
            async def search_domain():
                try:
                    domain_results = await self.domain_collections["domain_knowledge"].hybrid_search(
                        query=query,
                        top_k=top_k,
                        where=product_filters
                    )
                    for result in domain_results:
                        result["collection_name"] = "domain_knowledge"
                        result["entity_type"] = "connector"
                    return domain_results
                except Exception as e:
                    logger.warning(f"Error searching domain_knowledge for products: {str(e)}")
                    return []
            tasks.append(search_domain())
        
        # Execute searches in parallel and flatten results
        if tasks:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            for result_group in results_list:
                if not isinstance(result_group, Exception):
                    results.extend(result_group)
            return results
        
        return []
    
    async def search_domains(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all domain collections in parallel"""
        import asyncio
        
        async def search_collection(name: str, service: HybridSearchService) -> List[Dict[str, Any]]:
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "domain"
                return collection_results
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
                return []
        
        # Execute all collection searches in parallel
        tasks = [search_collection(name, service) for name, service in self.domain_collections.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for result_group in results_list:
            if not isinstance(result_group, Exception):
                results.extend(result_group)
        
        return results
    
    async def search_compliance(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all compliance collections in parallel"""
        import asyncio
        
        async def search_collection(name: str, service: HybridSearchService) -> List[Dict[str, Any]]:
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "compliance"
                return collection_results
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
                return []
        
        # Execute all collection searches in parallel
        tasks = [search_collection(name, service) for name, service in self.compliance_collections.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for result_group in results_list:
            if not isinstance(result_group, Exception):
                results.extend(result_group)
        
        return results
    
    async def search_risks(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across all risk collections in parallel.
        
        Note: Risks are primarily stored in domain_knowledge with type="risk" in metadata.
        Risk controls route to general "controls" store with type="risk".
        Use search_domains() with filters={"type": "risk"} to find risk content.
        """
        import asyncio
        
        async def search_collection(name: str, service: HybridSearchService) -> List[Dict[str, Any]]:
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "risk"
                return collection_results
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
                return []
        
        # Execute all collection searches in parallel
        tasks = [search_collection(name, service) for name, service in self.risk_collections.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for result_group in results_list:
            if not isinstance(result_group, Exception):
                results.extend(result_group)
        
        return results
    
    async def search_schemas(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all schema collections (tables, columns, schemas) in parallel"""
        import asyncio
        
        async def search_collection(name: str, service: HybridSearchService) -> List[Dict[str, Any]]:
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "schema"
                return collection_results
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
                return []
        
        # Execute all collection searches in parallel
        tasks = [search_collection(name, service) for name, service in self.schema_collections.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for result_group in results_list:
            if not isinstance(result_group, Exception):
                results.extend(result_group)
        
        return results
    
    async def search_features(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all feature collections in parallel"""
        import asyncio
        
        async def search_collection(name: str, service: HybridSearchService) -> List[Dict[str, Any]]:
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "feature"
                return collection_results
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
                return []
        
        # Execute all collection searches in parallel
        tasks = [search_collection(name, service) for name, service in self.feature_collections.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for result_group in results_list:
            if not isinstance(result_group, Exception):
                results.extend(result_group)
        
        return results
    
    async def search_all(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        include_schemas: bool = True,
        include_features: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across all collections organized by hierarchy.
        Uses parallel execution with asyncio.gather() for better performance.
        
        Args:
            query: Search query
            top_k: Number of results per collection
            filters: Optional metadata filters
            include_schemas: Whether to include schema collections
            include_features: Whether to include feature collections
            
        Returns:
            Dictionary with results organized by entity type
        """
        import asyncio
        
        # Execute all searches in parallel for significant speedup
        tasks = [
            self.search_connectors(query, top_k, filters),
            self.search_domains(query, top_k, filters),
            self.search_compliance(query, top_k, filters),
            self.search_risks(query, top_k, filters),
            self.search_additionals(query, top_k, filters),
            self.search_schemas(query, top_k, filters) if include_schemas else self._empty_result(),
            self.search_features(query, top_k, filters) if include_features else self._empty_result(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions and build result dictionary
        result = {}
        keys = ["connectors", "domains", "compliance", "risks", "additionals", "schemas", "features"]
        
        for i, key in enumerate(keys):
            # Skip schemas/features if not included
            if (key == "schemas" and not include_schemas) or (key == "features" and not include_features):
                continue
                
            if isinstance(results[i], Exception):
                logger.warning(f"Error searching {key}: {str(results[i])}")
                result[key] = []
            else:
                result[key] = results[i]
        
        return result
    
    async def _empty_result(self) -> List[Dict[str, Any]]:
        """Return empty result list for conditional searches"""
        return []
    
    async def search_additionals(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all additional collections in parallel"""
        import asyncio
        
        async def search_collection(name: str, service: HybridSearchService) -> List[Dict[str, Any]]:
            try:
                collection_results = await service.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters
                )
                for result in collection_results:
                    result["collection_name"] = name
                    result["entity_type"] = "additional"
                return collection_results
            except Exception as e:
                logger.warning(f"Error searching {name}: {str(e)}")
                return []
        
        # Execute all collection searches in parallel
        tasks = [search_collection(name, service) for name, service in self.additional_collections.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for result_group in results_list:
            if not isinstance(result_group, Exception):
                results.extend(result_group)
        
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

