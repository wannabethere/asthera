"""
MDL Semantic Layer Service
Service that orchestrates MDL agents and retrievers for semantic understanding.
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI

from app.agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent
from app.agents.mdl_edge_pruning_agent import MDLEdgePruningAgent
from app.agents.data.mdl_semantic_retriever import MDLSemanticRetriever
from app.services.contextual_graph_storage import ContextualGraphStorage, ContextualEdge
from app.storage.query.collection_factory import CollectionFactory

logger = logging.getLogger(__name__)


class MDLSemanticLayerService:
    """
    Service that orchestrates MDL agents and retrievers.
    
    This is a SERVICE (orchestrates) that:
    - Uses MDLContextBreakdownAgent (LLM) to break down questions
    - Uses MDLSemanticRetriever (data fetching) to retrieve edges and entities
    - Uses MDLEdgePruningAgent (LLM) to prune edges
    - Coordinates the workflow
    - Does NOT use LLM directly - delegates to agents
    - Does NOT fetch data directly - delegates to retrievers
    """
    
    def __init__(
        self,
        contextual_graph_storage: ContextualGraphStorage,
        collection_factory: CollectionFactory,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the MDL semantic layer service.
        
        Args:
            contextual_graph_storage: ContextualGraphStorage instance
            collection_factory: CollectionFactory instance
            llm: Optional LLM instance (passed to agents)
            model_name: Model name if llm not provided
        """
        self.contextual_graph_storage = contextual_graph_storage
        self.collection_factory = collection_factory
        
        # Initialize agents (use LLM)
        self.context_breakdown_agent = MDLContextBreakdownAgent(
            llm=llm,
            model_name=model_name
        )
        self.edge_pruning_agent = MDLEdgePruningAgent(
            llm=llm,
            model_name=model_name
        )
        
        # Initialize retriever (fetches data)
        self.retriever = MDLSemanticRetriever(
            contextual_graph_storage=contextual_graph_storage,
            collection_factory=collection_factory
        )
        
        logger.info("Initialized MDL Semantic Layer Service")
    
    async def discover_mdl_semantic_edges(
        self,
        user_question: str,
        product_name: Optional[str] = None,
        context_id: Optional[str] = None,
        top_k: int = 10,
        use_schema_categories: bool = True
    ) -> Dict[str, Any]:
        """
        Discover MDL semantic edges using agents and retrievers.
        
        Workflow:
        1. Agent: Break down question (LLM)
        2. Retriever: Discover edges (data fetching)
        3. Agent: Prune edges (LLM)
        4. Retriever: Enrich with schema categories (data fetching)
        
        Args:
            user_question: User's question about MDL schema
            product_name: Optional product name (Snyk, Cornerstone, etc.)
            context_id: Optional context ID to filter edges
            top_k: Number of edges to return after pruning
            use_schema_categories: Whether to use schema categories for discovery
            
        Returns:
            Dictionary with pruned edges, context breakdown, and MDL metadata
        """
        try:
            # Step 1: Agent - Break down question using LLM
            logger.info(f"Breaking down MDL question: {user_question[:100]}...")
            context_breakdown = await self.context_breakdown_agent.breakdown_mdl_question(
                user_question=user_question,
                product_name=product_name
            )
            
            # Step 2: Retriever - Discover edges using data fetching
            discovered_edges = []
            
            # Use search questions from breakdown if available
            if hasattr(context_breakdown, 'search_questions') and context_breakdown.search_questions:
                logger.info(f"Using {len(context_breakdown.search_questions)} search questions from breakdown")
                
                for search_question in context_breakdown.search_questions:
                    entity = search_question.get("entity", "")
                    query = search_question.get("question", "")
                    filters = search_question.get("metadata_filters", {})
                    
                    if context_id:
                        filters["context_id"] = context_id
                    
                    # Retriever - Fetch edges for this entity query
                    if entity == "contextual_edges":
                        edges = await self.retriever.retrieve_edges(
                            query=query,
                            filters=filters,
                            top_k=top_k * 2  # Get more edges per entity
                        )
                        discovered_edges.extend(edges)
                    else:
                        # For other entities, retrieve and convert to edges if applicable
                        results = await self.retriever.retrieve_by_entity(
                            entity=entity,
                            query=query,
                            filters=filters,
                            top_k=top_k * 2
                        )
                        # Convert results to edges if they look like edges
                        for result in results:
                            metadata = result.get("metadata", {})
                            if "edge_type" in metadata or "source_entity_id" in metadata:
                                try:
                                    edge = ContextualEdge.from_metadata(
                                        document=result.get("content", ""),
                                        metadata=metadata
                                    )
                                    discovered_edges.append(edge)
                                except Exception as e:
                                    logger.debug(f"Could not convert result to edge: {e}")
            else:
                # Fallback: Retriever - Generic edge discovery
                search_query = context_breakdown.to_search_query()
                metadata_filters = context_breakdown.to_metadata_filters()
                if context_id:
                    metadata_filters["context_id"] = context_id
                
                discovered_edges = await self.retriever.retrieve_edges(
                    query=search_query,
                    filters=metadata_filters if metadata_filters else None,
                    top_k=top_k * 3
                )
            
            # Deduplicate edges by edge_id
            seen_edge_ids = set()
            unique_edges = []
            for edge in discovered_edges:
                if edge.edge_id not in seen_edge_ids:
                    seen_edge_ids.add(edge.edge_id)
                    unique_edges.append(edge)
            discovered_edges = unique_edges
            
            logger.info(f"Discovered {len(discovered_edges)} unique edges from {len(discovered_edges)} total edges")
            if discovered_edges:
                logger.debug(f"Sample edge IDs: {[e.edge_id for e in discovered_edges[:5]]}")
            else:
                logger.warning(f"No edges discovered for query. Search questions used: {len(getattr(context_breakdown, 'search_questions', []))}")
            
            # Step 3: Agent - Prune edges using LLM
            if len(discovered_edges) > top_k:
                logger.info(f"Pruning {len(discovered_edges)} edges to {top_k}")
                pruned_edges = await self.edge_pruning_agent.prune_edges(
                    user_question=user_question,
                    discovered_edges=discovered_edges,
                    max_edges=top_k,
                    context_breakdown=context_breakdown.__dict__ if hasattr(context_breakdown, '__dict__') else None
                )
            else:
                pruned_edges = discovered_edges
            
            # Step 4: Retriever - Enrich with schema category context if available
            if use_schema_categories and product_name:
                pruned_edges = await self._enrich_edges_with_schema_categories(
                    edges=pruned_edges,
                    product_name=product_name
                )
            
            return {
                "edges": pruned_edges,
                "context_breakdown": context_breakdown,
                "discovered_count": len(discovered_edges),
                "pruned_count": len(pruned_edges),
                "mdl_metadata": {
                    "product_name": product_name,
                    "mdl_detection": getattr(context_breakdown, 'mdl_detection', {}),
                    "identified_entities": context_breakdown.identified_entities,
                    "search_questions_count": len(getattr(context_breakdown, 'search_questions', []))
                }
            }
            
        except Exception as e:
            logger.error(f"Error discovering MDL semantic edges: {str(e)}", exc_info=True)
            return {
                "edges": [],
                "context_breakdown": None,
                "discovered_count": 0,
                "pruned_count": 0,
                "error": str(e)
            }
    
    async def _enrich_edges_with_schema_categories(
        self,
        edges: List[ContextualEdge],
        product_name: str
    ) -> List[ContextualEdge]:
        """
        Enrich edges with schema category information using retriever.
        
        Note: Schema descriptions are now handled by project_reader.py via table_description component.
        This method now only extracts table info from entity IDs without querying schema_descriptions.
        
        Args:
            edges: List of edges to enrich
            product_name: Product name
            
        Returns:
            List of enriched edges
        """
        try:
            # Note: Schema descriptions are now handled by project_reader.py
            # We only extract table info from entity IDs here
            # For schema categories, use table_descriptions collection instead
            
            # For each edge, extract table info from entity IDs
            for edge in edges:
                # Extract table info from entity IDs
                source_table_info = self._extract_table_info(edge.source_entity_id)
                target_table_info = self._extract_table_info(edge.target_entity_id)
                
                # Add metadata if we have table info
                if source_table_info.get("table_name"):
                    if not hasattr(edge, 'mdl_metadata'):
                        edge.mdl_metadata = {}
                    edge.mdl_metadata["source_table"] = source_table_info
                
                if target_table_info.get("table_name"):
                    if not hasattr(edge, 'mdl_metadata'):
                        edge.mdl_metadata = {}
                    edge.mdl_metadata["target_table"] = target_table_info
            
            return edges
            
        except Exception as e:
            logger.warning(f"Error enriching edges with schema categories: {str(e)}")
            return edges
    
    def _extract_table_info(self, entity_id: str) -> Dict[str, str]:
        """
        Extract product and table name from entity ID.
        
        Args:
            entity_id: Entity ID (format: entity_{product}_{table})
            
        Returns:
            Dictionary with product_name and table_name
        """
        if not entity_id or not entity_id.startswith("entity_"):
            return {"product_name": None, "table_name": None}
        
        parts = entity_id.replace("entity_", "").split("_", 1)
        if len(parts) >= 2:
            return {
                "product_name": parts[0],
                "table_name": "_".join(parts[1:])
            }
        return {"product_name": None, "table_name": None}
    
    async def get_entities_from_mdl_edges(
        self,
        edges: List[ContextualEdge],
        user_question: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Get entities from MDL edges using retriever.
        
        Args:
            edges: List of pruned MDL edges
            user_question: Original user question
            top_k: Number of entities to return
            
        Returns:
            Dictionary with entities and metadata
        """
        try:
            entities = []
            entity_ids = set()
            
            for edge in edges:
                # Get source entity
                if edge.source_entity_id and edge.source_entity_id not in entity_ids:
                    entity_ids.add(edge.source_entity_id)
                    entities.append({
                        "entity_id": edge.source_entity_id,
                        "entity_type": edge.source_entity_type,
                        "context_id": edge.context_id,
                        "edge_type": edge.edge_type,
                        "role": "source"
                    })
                
                # Get target entity
                if edge.target_entity_id and edge.target_entity_id not in entity_ids:
                    entity_ids.add(edge.target_entity_id)
                    entities.append({
                        "entity_id": edge.target_entity_id,
                        "entity_type": edge.target_entity_type,
                        "context_id": edge.context_id,
                        "edge_type": edge.edge_type,
                        "role": "target"
                    })
            
            # Retriever - Fetch entity definitions from context_definitions
            context_definitions = []
            for entity in entities[:top_k]:
                if entity["entity_type"] == "entity" and entity["entity_id"].startswith("entity_"):
                    # Retriever - Fetch context definition
                    results = await self.retriever.retrieve_context_definitions(
                        query=f"Context for {entity['entity_id']}",
                        filters={"context_id": entity["entity_id"]},
                        top_k=1
                    )
                    if results:
                        entity["context_definition"] = results[0]
                    context_definitions.append(entity)
            
            return {
                "entities": context_definitions,
                "total_entities": len(entities),
                "returned_count": len(context_definitions)
            }
            
        except Exception as e:
            logger.error(f"Error getting entities from MDL edges: {str(e)}", exc_info=True)
            return {
                "entities": [],
                "total_entities": 0,
                "returned_count": 0,
                "error": str(e)
            }
