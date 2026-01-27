"""
MDL Semantic Retriever
Retriever that fetches MDL data from storage services using hybrid search.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from app.services.contextual_graph_storage import ContextualGraphStorage, ContextualEdge
from app.storage.query.collection_factory import CollectionFactory

logger = logging.getLogger(__name__)


class MDLSemanticRetriever:
    """
    Retriever that fetches MDL data from storage services.
    
    This is a RETRIEVER (fetches data) that:
    - Uses hybrid search to retrieve edges from contextual_edges collection
    - Retrieves context definitions from context_definitions collection
    - Retrieves table descriptions via retrieval_helper (full schemas with DDL)
    - Retrieves fields from fields collection
    - Does NOT use LLM - only data fetching
    - Returns complete data to be converted to markdown for LLM processing
    """
    
    def __init__(
        self,
        contextual_graph_storage: ContextualGraphStorage,
        collection_factory: CollectionFactory,
        retrieval_helper: Optional[Any] = None
    ):
        """
        Initialize the MDL semantic retriever.
        
        Args:
            contextual_graph_storage: ContextualGraphStorage instance for edge retrieval
            collection_factory: CollectionFactory instance for accessing collections
            retrieval_helper: Optional RetrievalHelper instance (preferred over direct collection access)
        """
        self.contextual_graph_storage = contextual_graph_storage
        self.collection_factory = collection_factory
        self.retrieval_helper = retrieval_helper
        
        logger.info("Initialized MDL Semantic Retriever" + (" (with retrieval_helper)" if retrieval_helper else ""))
    
    async def retrieve_edges(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20
    ) -> List[ContextualEdge]:
        """
        Retrieve edges using hybrid search.
        
        Args:
            query: Search query
            filters: Optional metadata filters
            top_k: Number of results
            
        Returns:
            List of retrieved edges
        """
        try:
            return await self.contextual_graph_storage.discover_edges_by_context(
                context_query=query,
                top_k=top_k,
                filters=filters if filters else None
            )
        except Exception as e:
            logger.error(f"Error retrieving edges: {str(e)}")
            return []
    
    async def retrieve_context_definitions(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context definitions using hybrid search.
        
        Args:
            query: Search query
            filters: Optional metadata filters
            top_k: Number of results
            
        Returns:
            List of context definition results
        """
        try:
            collection = self.collection_factory.get_collection_by_store_name("context_definitions")
            if not collection:
                logger.warning("context_definitions collection not found")
                return []
            
            if hasattr(collection, 'hybrid_search'):
                results = await collection.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters if filters else None
                )
                return results
            
            return []
        except Exception as e:
            logger.error(f"Error retrieving context definitions: {str(e)}")
            return []
    
    async def retrieve_table_descriptions(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve complete table descriptions with full DDL and metadata.
        
        Uses retrieval_helper.get_database_schemas() to get complete schema information.
        Returns full data that can be converted to markdown for LLM processing.
        
        Args:
            query: Search query
            filters: Optional metadata filters (e.g., product_name, table_name)
            top_k: Number of results (default: 10)
            project_id: Optional project ID for retrieval_helper
            
        Returns:
            List of complete table description results with DDL and metadata
        """
        try:
            # Prefer retrieval_helper.get_database_schemas if available
            if self.retrieval_helper and hasattr(self.retrieval_helper, 'get_database_schemas'):
                try:
                    project_id = project_id or filters.get("product_name") or filters.get("project_id") if filters else None
                    if not project_id:
                        logger.warning("MDLSemanticRetriever: project_id not provided, cannot use retrieval_helper")
                        # Fall through to collection_factory
                    else:
                        table_retrieval = {
                            "table_retrieval_size": top_k,
                            "table_column_retrieval_size": 100,
                            "allow_using_db_schemas_without_pruning": True  # Skip column pruning - return full DDL for markdown
                        }
                        
                        result = await self.retrieval_helper.get_database_schemas(
                            project_id=project_id,
                            table_retrieval=table_retrieval,
                            query=query,
                            histories=None,
                            tables=filters.get("table_name") if filters else None
                        )
                        
                        if result and "schemas" in result:
                            schemas = result.get("schemas", [])
                            
                            # Convert to expected format
                            results = []
                            for schema in schemas[:top_k]:
                                table_name = schema.get("table_name", "")
                                table_ddl = schema.get("table_ddl", "")
                                column_metadata = schema.get("column_metadata", [])
                                
                                results.append({
                                    "content": table_ddl if table_ddl else f"Table: {table_name}",
                                    "metadata": {
                                        "table_name": table_name,
                                        "product_name": project_id,
                                        "project_id": project_id,
                                        "relationships": schema.get("relationships", []),
                                        "column_metadata": column_metadata,
                                        "has_calculated_field": schema.get("has_calculated_field", False),
                                        "has_metric": schema.get("has_metric", False)
                                    }
                                })
                            
                            logger.info(f"MDLSemanticRetriever: Retrieved {len(results)} table descriptions via retrieval_helper (from db_schema + table_descriptions)")
                            return results
                except Exception as e:
                    logger.error(f"MDLSemanticRetriever: Error using retrieval_helper for table descriptions: {e}")
                    return []
            
            # retrieval_helper is required - no fallback to empty collections
            logger.error("MDLSemanticRetriever: retrieval_helper not available, cannot retrieve table descriptions")
            return []
        except Exception as e:
            logger.error(f"Error retrieving table descriptions: {str(e)}")
            return []
    
    async def retrieve_column_descriptions(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        project_id: Optional[str] = None,
        table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve column descriptions using retrieval_helper (preferred) or collection_factory.
        
        Uses retrieval_helper.get_database_schemas() which includes column_metadata,
        or directly queries column_metadata collection via retrieval_helper.
        
        Args:
            query: Search query
            filters: Optional metadata filters (e.g., product_name, table_name)
            top_k: Number of results
            project_id: Optional project ID for retrieval_helper
            table_name: Optional table name to filter columns
            
        Returns:
            List of column description results
        """
        try:
            # Prefer retrieval_helper if available
            if self.retrieval_helper:
                try:
                    project_id = project_id or filters.get("product_name") or filters.get("project_id") if filters else None
                    table_name = table_name or filters.get("table_name") if filters else None
                    
                    if project_id and table_name:
                        # Use retrieval_helper to get column metadata for specific table
                        if hasattr(self.retrieval_helper, '_get_column_metadata_for_table'):
                            column_metadata = await self.retrieval_helper._get_column_metadata_for_table(
                                table_name=table_name,
                                project_id=project_id
                            )
                            
                            # Convert to expected format
                            results = []
                            for col_meta in column_metadata[:top_k]:
                                results.append({
                                    "content": f"Column: {col_meta.get('column_name', '')} ({col_meta.get('type', '')}) - {col_meta.get('description', '')}",
                                    "metadata": {
                                        "column_name": col_meta.get("column_name", ""),
                                        "table_name": table_name,
                                        "product_name": project_id,
                                        "project_id": project_id,
                                        "type": col_meta.get("type", ""),
                                        "display_name": col_meta.get("display_name", ""),
                                        "description": col_meta.get("description", ""),
                                        "is_calculated": col_meta.get("is_calculated", False),
                                        "is_primary_key": col_meta.get("is_primary_key", False),
                                        "is_foreign_key": col_meta.get("is_foreign_key", False)
                                    }
                                })
                            
                            logger.info(f"MDLSemanticRetriever: Retrieved {len(results)} column descriptions via retrieval_helper")
                            return results
                    
                    # Fallback: get from database schemas
                    if project_id and hasattr(self.retrieval_helper, 'get_database_schemas'):
                        table_retrieval = {
                            "table_retrieval_size": top_k,
                            "table_column_retrieval_size": 100,
                            "allow_using_db_schemas_without_pruning": True  # Skip column pruning - return full DDL for markdown
                        }
                        
                        result = await self.retrieval_helper.get_database_schemas(
                            project_id=project_id,
                            table_retrieval=table_retrieval,
                            query=query,
                            histories=None,
                            tables=[table_name] if table_name else None
                        )
                        
                        if result and "schemas" in result:
                            # Extract column metadata from schemas
                            results = []
                            for schema in result.get("schemas", [])[:top_k]:
                                column_metadata = schema.get("column_metadata", [])
                                for col_meta in column_metadata:
                                    results.append({
                                        "content": f"Column: {col_meta.get('column_name', '')} ({col_meta.get('type', '')}) - {col_meta.get('description', '')}",
                                        "metadata": {
                                            **col_meta,
                                            "table_name": schema.get("table_name", ""),
                                            "product_name": project_id,
                                            "project_id": project_id
                                        }
                                    })
                                    if len(results) >= top_k:
                                        break
                                if len(results) >= top_k:
                                    break
                            
                            logger.info(f"MDLSemanticRetriever: Retrieved {len(results)} column descriptions via retrieval_helper (from schemas)")
                            return results[:top_k]
                except Exception as e:
                    logger.warning(f"MDLSemanticRetriever: Error using retrieval_helper for column descriptions, falling back to collection_factory: {e}")
            
            # Fallback to collection_factory if retrieval_helper not available or failed
            collection = self.collection_factory.get_collection_by_store_name("column_definitions")
            if not collection:
                logger.warning("column_definitions collection not found")
                return []
            
            if hasattr(collection, 'hybrid_search'):
                results = await collection.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters if filters else None
                )
                return results
            
            return []
        except Exception as e:
            logger.error(f"Error retrieving column descriptions: {str(e)}")
            return []
    
    async def retrieve_fields(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve fields using hybrid search.
        
        Args:
            query: Search query
            filters: Optional metadata filters (e.g., context_id, type='schema_field', product_name)
            top_k: Number of results
            
        Returns:
            List of field results
        """
        try:
            collection = self.collection_factory.get_collection_by_store_name("fields")
            if not collection:
                logger.warning("fields collection not found")
                return []
            
            if hasattr(collection, 'hybrid_search'):
                results = await collection.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters if filters else None
                )
                return results
            
            return []
        except Exception as e:
            logger.error(f"Error retrieving fields: {str(e)}")
            return []
    
    async def retrieve_by_entity(
        self,
        entity: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieve data for a specific entity type.
        
        Handles special entity mappings based on ingest_preview_files.py:
        - Policy documents route to general stores (domain_knowledge, entities, evidence, fields) with type="policy"
        - Risk controls route to domain_knowledge with type="risk" or controls with type="risk"
        - Other entities use direct collection lookup
        
        Args:
            entity: Entity name (e.g., "contextual_edges", "policy_documents", "risk_controls", "compliance_controls")
            query: Search query
            filters: Optional metadata filters
            top_k: Number of results
            
        Returns:
            List of retrieved results
        """
        try:
            # For contextual_edges, use contextual graph storage
            if entity == "contextual_edges":
                edges = await self.retrieve_edges(query, filters, top_k)
                # Convert edges to dict format
                return [
                    {
                        "content": edge.document,
                        "metadata": {
                            "edge_id": edge.edge_id,
                            "edge_type": edge.edge_type,
                            "source_entity_id": edge.source_entity_id,
                            "target_entity_id": edge.target_entity_id,
                            "source_entity_type": edge.source_entity_type,
                            "target_entity_type": edge.target_entity_type,
                            "context_id": edge.context_id,
                            "relevance_score": edge.relevance_score
                        }
                    }
                    for edge in edges
                ]
            
            # Handle special entity mappings based on ingest_preview_files.py
            # Policy documents route to domain_knowledge with type="policy" filter
            # The type filter already distinguishes policy content, so we only need to search domain_knowledge
            if entity == "policy_documents":
                policy_filters = (filters.copy() if filters else {})
                policy_filters["type"] = "policy"
                collection = self.collection_factory.get_collection_by_store_name("domain_knowledge")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=policy_filters)
                return []
            
            # Policy entities route to entities with type="policy"
            elif entity == "policy_entities":
                policy_filters = (filters.copy() if filters else {})
                policy_filters["type"] = "policy"
                collection = self.collection_factory.get_collection_by_store_name("entities")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=policy_filters)
                return []
            
            # Policy evidence routes to evidence with type="policy"
            elif entity == "policy_evidence":
                policy_filters = (filters.copy() if filters else {})
                policy_filters["type"] = "policy"
                collection = self.collection_factory.get_collection_by_store_name("evidence")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=policy_filters)
                return []
            
            # Policy fields route to fields with type="policy"
            elif entity == "policy_fields":
                policy_filters = (filters.copy() if filters else {})
                policy_filters["type"] = "policy"
                collection = self.collection_factory.get_collection_by_store_name("fields")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=policy_filters)
                return []
            
            # Risk controls route to domain_knowledge with type="risk" OR controls with type="risk"
            elif entity == "risk_controls":
                risk_filters = (filters.copy() if filters else {})
                risk_filters["type"] = "risk"
                
                async def search_risk_collection(store_name: str) -> List[Dict[str, Any]]:
                    """Helper function to search a single collection for risk controls"""
                    try:
                        collection = self.collection_factory.get_collection_by_store_name(store_name)
                        if collection and hasattr(collection, 'hybrid_search'):
                            return await collection.hybrid_search(
                                query=query,
                                top_k=top_k,
                                where=risk_filters
                            )
                    except Exception as e:
                        logger.warning(f"Error searching {store_name} for risk_controls: {e}")
                    return []
                
                # Search both collections in parallel
                store_names = ["domain_knowledge", "controls"]
                search_tasks = [search_risk_collection(store_name) for store_name in store_names]
                all_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                
                # Combine results from all collections
                results = []
                for i, result in enumerate(all_results):
                    if isinstance(result, Exception):
                        logger.warning(f"Error in parallel search for {store_names[i]}: {result}")
                    elif isinstance(result, list):
                        results.extend(result)
                
                logger.debug(f"Risk controls search: found {len(results)} results across {len(store_names)} collections")
                return results
            
            # Risk entities route to entities with type="risk_entities"
            elif entity == "risk_entities":
                risk_filters = (filters.copy() if filters else {})
                risk_filters["type"] = "risk_entities"
                collection = self.collection_factory.get_collection_by_store_name("entities")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=risk_filters)
                return []
            
            # Risk evidence routes to evidence with type="risk_evidence"
            elif entity == "risk_evidence":
                risk_filters = (filters.copy() if filters else {})
                risk_filters["type"] = "risk_evidence"
                collection = self.collection_factory.get_collection_by_store_name("evidence")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=risk_filters)
                return []
            
            # Risk fields route to fields with type="risk_fields"
            elif entity == "risk_fields":
                risk_filters = (filters.copy() if filters else {})
                risk_filters["type"] = "risk_fields"
                collection = self.collection_factory.get_collection_by_store_name("fields")
                if collection and hasattr(collection, 'hybrid_search'):
                    return await collection.hybrid_search(query=query, top_k=top_k, where=risk_filters)
                return []
            
            # For other entities (compliance_controls, table_definitions, etc.), use collection factory
            collection = self.collection_factory.get_collection_by_store_name(entity)
            if not collection:
                logger.warning(f"Collection not found for entity: {entity}")
                return []
            
            # Use hybrid search
            if hasattr(collection, 'hybrid_search'):
                results = await collection.hybrid_search(
                    query=query,
                    top_k=top_k,
                    where=filters if filters else None
                )
                return results
            
            return []
            
        except Exception as e:
            logger.error(f"Error retrieving by entity {entity}: {str(e)}")
            return []

