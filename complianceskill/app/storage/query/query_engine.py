"""
Contextual Graph Query Engine

Implements all search patterns from hybrid_search.md:
1. Context matching with hybrid search
2. Context-aware control retrieval
3. Multi-hop contextual reasoning
4. Multi-store queries using CollectionFactory
"""
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import asyncpg
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json

from app.services.contextual_graph_storage import ContextualGraphStorage
from app.services.storage.measurement_service import MeasurementStorageService
from app.storage.query.collection_factory import CollectionFactory

if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)


class ContextualGraphQueryEngine:
    """
    Query engine that combines PostgreSQL and ChromaDB for contextual graph queries.
    
    Implements all search patterns from hybrid_search.md:
    - Pattern 1: Context matching with hybrid search
    - Pattern 2: Context-aware control retrieval
    - Pattern 3: Multi-hop contextual reasoning
    """
    
    def __init__(
        self,
        vector_store_client: "VectorStoreClient",
        db_pool: asyncpg.Pool,
        embeddings_model=None,
        llm: Optional[ChatOpenAI] = None,
        collection_prefix: str = "comprehensive_index"
    ):
        """
        Initialize query engine.
        
        Args:
            vector_store_client: VectorStoreClient instance (supports ChromaDB, Qdrant, etc.)
            db_pool: PostgreSQL connection pool
            embeddings_model: Optional embeddings model (will use vector_store_client's if None)
            llm: Optional LLM for synthesis
            collection_prefix: Prefix for collection names
        """
        self.vector_store_client = vector_store_client
        self.db_pool = db_pool
        self.llm = llm or ChatOpenAI(model="gpt-4o", temperature=0.2)
        
        # Initialize vector storage with collection prefix
        self.vector_storage = ContextualGraphStorage(
            vector_store_client=vector_store_client,
            embeddings_model=embeddings_model,
            collection_prefix=collection_prefix
        )
        
        # Initialize collection factory for multi-store queries
        self.collection_factory = CollectionFactory(
            vector_store_client=vector_store_client,
            embeddings_model=embeddings_model,
            collection_prefix=collection_prefix
        )
        
        # Initialize PostgreSQL service
        self.measurement_service = MeasurementStorageService(db_pool)
        
        logger.info("Initialized ContextualGraphQueryEngine with CollectionFactory")
    
    # ============================================================================
    # Pattern 1: Context Matching with Hybrid Search
    # ============================================================================
    
    async def find_relevant_contexts(
        self,
        user_context_description: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find contexts most relevant to user's situation using hybrid search.
        
        Combines:
        1. Dense vector similarity (semantic understanding)
        2. BM25 sparse retrieval (keyword matching)
        3. Metadata filtering (structured constraints)
        
        Args:
            user_context_description: Natural language description of user's context
            top_k: Number of results to return
            
        Returns:
            List of context results with combined scores
        """
        results = await self.vector_storage.find_relevant_contexts(
            description=user_context_description,
            top_k=top_k
        )
        
        # Format results - ContextDefinition objects to dicts
        formatted_results = []
        for result in results:
            # Convert ContextDefinition to dict format
            metadata = {
                "industry": result.industry,
                "organization_size": result.organization_size,
                "maturity_level": result.maturity_level,
                "regulatory_frameworks": result.regulatory_frameworks,
                "context_type": result.context_type,
                "active_status": result.active_status
            }
            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            formatted_results.append({
                "context_id": result.context_id,
                "document": result.document,
                "metadata": metadata,
                "dense_score": 0.0,  # Scores not available from ContextDefinition
                "bm25_score": 0.0,
                "combined_score": 0.0
            })
        
        return formatted_results
    
    # ============================================================================
    # Pattern 2: Context-Aware Control Retrieval
    # ============================================================================
    
    async def get_priority_controls_for_context(
        self,
        context_id: str,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve controls prioritized for specific context using hybrid search.
        
        Args:
            context_id: The active context
            query: Natural language query (optional)
            filters: Metadata filters (optional)
            top_k: Number of results
            
        Returns:
            List of enriched control results with both vector store context and PostgreSQL reality
        """
        # Build metadata filter
        where_clause = {"context_id": context_id}
        if filters:
            where_clause.update(filters)
        
        # Get profiles from vector store
        if query:
            # Hybrid search with query
            profiles = await self.vector_storage.search_control_profiles(
                query=query,
                context_id=context_id,
                filters=filters,
                top_k=top_k
            )
        else:
            # Metadata filtering only
            profiles = await self.vector_storage.get_control_profiles_for_context(
                context_id=context_id,
                top_k=top_k
            )
        
        # Get control IDs
        control_ids = [p.control_id for p in profiles]
        
        if not control_ids:
            return []
        
        # Get current compliance status from PostgreSQL
        analytics = await self.measurement_service.get_risk_analytics_batch(control_ids)
        
        # Combine vector store context + PostgreSQL reality
        enriched_results = []
        for profile in profiles:
            analytic = analytics.get(profile.control_id, {})
            
            enriched_results.append({
                "control_id": profile.control_id,
                "context_profile": {
                    "risk_level": profile.risk_level,
                    "estimated_effort_hours": profile.estimated_effort_hours,
                    "estimated_cost": profile.estimated_cost,
                    "timeline_weeks": profile.timeline_weeks,
                    "implementation_feasibility": profile.implementation_feasibility,
                    "implementation_complexity": profile.implementation_complexity
                },
                "current_compliance": {
                    "avg_compliance_score": analytic.avg_compliance_score if analytic else None,
                    "trend": analytic.trend if analytic else None,
                    "failure_count_30d": analytic.failure_count_30d if analytic else 0,
                    "risk_level": analytic.risk_level if analytic else None
                },
                "reasoning": profile.document
            })
        
        return enriched_results
    
    # ============================================================================
    # Pattern 3: Multi-Hop Contextual Reasoning
    # ============================================================================
    
    async def multi_hop_contextual_search(
        self,
        initial_query: str,
        context_id: str,
        max_hops: int = 3
    ) -> Dict[str, Any]:
        """
        Multi-hop reasoning through contextual graph using vector search.
        
        Example flow:
        1. Query: "What evidence do I need for access controls?"
        2. Hop 1: Find relevant controls in context
        3. Hop 2: Find requirements for those controls
        4. Hop 3: Find evidence types for those requirements
        
        Args:
            initial_query: Starting query
            context_id: Context to search within
            max_hops: Maximum number of hops
            
        Returns:
            Dictionary with reasoning_path and final_answer
        """
        reasoning_path = []
        current_entities = []
        
        # Hop 1: Find relevant controls
        logger.info(f"Hop 1: Finding controls for: '{initial_query}'")
        control_profiles = await self.vector_storage.search_control_profiles(
            query=initial_query,
            context_id=context_id,
            top_k=3
        )
        
        control_ids = [p.control_id for p in control_profiles]
        reasoning_path.append({
            "hop": 1,
            "query": initial_query,
            "entity_type": "controls",
            "entities_found": control_ids,
            "reasoning": control_profiles[0].document[:300] if control_profiles else ""
        })
        
        if not control_ids:
            return {
                "reasoning_path": reasoning_path,
                "final_answer": "No relevant controls found for the query."
            }
        
        # Hop 2: Find contextual requirements for these controls
        logger.info(f"Hop 2: Finding requirements for controls: {control_ids}")
        requirement_query = f"Requirements for controls {', '.join(control_ids)} in this context"
        
        requirement_edges = await self.vector_storage.search_edges(
            query=requirement_query,
            context_id=context_id,
            filters={
                "source_entity_id": {"$in": control_ids},
                "target_entity_type": "requirement"
            },
            top_k=5
        )
        
        requirement_ids = [e.target_entity_id for e in requirement_edges]
        reasoning_path.append({
            "hop": 2,
            "entity_type": "requirements",
            "entities_found": requirement_ids,
            "reasoning": requirement_edges[0].document[:300] if requirement_edges else ""
        })
        
        # Hop 3: Find evidence types for these requirements
        if max_hops >= 3 and requirement_ids:
            logger.info(f"Hop 3: Finding evidence for requirements: {requirement_ids}")
            evidence_query = f"Evidence that proves requirements {', '.join(requirement_ids)}"
            
            evidence_edges = await self.vector_storage.search_edges(
                query=evidence_query,
                context_id=context_id,
                filters={
                    "source_entity_id": {"$in": requirement_ids},
                    "target_entity_type": "evidence"
                },
                top_k=5
            )
            
            evidence_ids = [e.target_entity_id for e in evidence_edges]
            reasoning_path.append({
                "hop": 3,
                "entity_type": "evidence",
                "entities_found": evidence_ids,
                "reasoning": evidence_edges[0].document[:300] if evidence_edges else ""
            })
        
        # Synthesize with LLM
        synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at synthesizing compliance information.

Given a multi-hop reasoning path through a contextual graph, synthesize a complete,
actionable answer that explains:
1. Which controls are relevant in this context
2. What requirements they have
3. What evidence is needed
4. How to collect that evidence given the organizational context

Make it practical and specific to the context."""),
            ("human", """User Question: {initial_query}
Context: {context_id}

Multi-hop reasoning path:
{reasoning_path}

Synthesize a complete answer.""")
        ])
        
        chain = synthesis_prompt | self.llm
        
        try:
            result = await chain.ainvoke({
                "initial_query": initial_query,
                "context_id": context_id,
                "reasoning_path": json.dumps(reasoning_path, indent=2)
            })
            
            final_answer = result.content if hasattr(result, 'content') else str(result)
            
        except Exception as e:
            logger.error(f"Error synthesizing answer: {str(e)}", exc_info=True)
            final_answer = "Error generating synthesized answer."
        
        return {
            "reasoning_path": reasoning_path,
            "final_answer": final_answer
        }
    
    # ============================================================================
    # Pattern 4: Multi-Store Queries with Collection Factory
    # ============================================================================
    
    async def query_all_stores(
        self,
        query: str,
        context_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        include_schemas: bool = True
    ) -> Dict[str, Any]:
        """
        Query across all stores using collection factory.
        
        Hierarchy: Connector -> Domain -> Compliance -> Risks -> Additionals
        Schemas are separate.
        
        Args:
            query: Search query
            context_id: Optional context ID for filtering
            top_k: Number of results per collection
            filters: Optional metadata filters
            include_schemas: Whether to include schema collections
            
        Returns:
            Dictionary with results from all stores organized by entity type
        """
        # Add context_id to filters if provided
        search_filters = filters or {}
        if context_id:
            search_filters["context_id"] = context_id
        
        # Search all collections
        all_results = await self.collection_factory.search_all(
            query=query,
            top_k=top_k,
            filters=search_filters if search_filters else None,
            include_schemas=include_schemas
        )
        
        return {
            "query": query,
            "context_id": context_id,
            "results": all_results,
            "summary": {
                "connectors_count": len(all_results.get("connectors", [])),
                "domains_count": len(all_results.get("domains", [])),
                "compliance_count": len(all_results.get("compliance", [])),
                "risks_count": len(all_results.get("risks", [])),
                "additionals_count": len(all_results.get("additionals", [])),
                "schemas_count": len(all_results.get("schemas", [])) if include_schemas else 0,
            }
        }
    
    async def query_hierarchical(
        self,
        query: str,
        context_id: Optional[str] = None,
        start_level: str = "connector",
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query following the hierarchy: connector -> domain -> compliance -> risks -> additionals.
        
        Args:
            query: Search query
            context_id: Optional context ID
            start_level: Starting level in hierarchy (connector, domain, compliance, risks, additionals)
            top_k: Number of results per level
            filters: Optional metadata filters
            
        Returns:
            Dictionary with hierarchical results
        """
        hierarchy = ["connector", "domain", "compliance", "risks", "additionals"]
        
        if start_level not in hierarchy:
            raise ValueError(f"start_level must be one of {hierarchy}")
        
        start_idx = hierarchy.index(start_level)
        results = {}
        
        # Add context_id to filters if provided
        search_filters = filters or {}
        if context_id:
            search_filters["context_id"] = context_id
        
        # Query each level in hierarchy
        for level in hierarchy[start_idx:]:
            if level == "connector":
                results["connectors"] = await self.collection_factory.search_connectors(
                    query, top_k, search_filters
                )
            elif level == "domain":
                results["domains"] = await self.collection_factory.search_domains(
                    query, top_k, search_filters
                )
            elif level == "compliance":
                results["compliance"] = await self.collection_factory.search_compliance(
                    query, top_k, search_filters
                )
            elif level == "risks":
                results["risks"] = await self.collection_factory.search_risks(
                    query, top_k, search_filters
                )
            elif level == "additionals":
                results["additionals"] = await self.collection_factory.search_additionals(
                    query, top_k, search_filters
                )
        
        return {
            "query": query,
            "context_id": context_id,
            "start_level": start_level,
            "hierarchical_results": results
        }

