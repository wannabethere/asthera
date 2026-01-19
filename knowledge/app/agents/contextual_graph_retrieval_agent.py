"""
Contextual Graph Retrieval Agent
Retrieves relevant contexts and creates reasoning plans based on user queries
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

logger = logging.getLogger(__name__)


class ContextualGraphRetrievalAgent:
    """
    Agent that retrieves relevant contexts from the contextual graph and creates reasoning plans.
    
    Performs:
    - Context search and matching
    - Reasoning plan generation
    - Context prioritization and filtering
    - Multi-context aggregation
    """
    
    def __init__(
        self,
        contextual_graph_service: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        collection_factory: Optional[Any] = None
    ):
        """
        Initialize the contextual graph retrieval agent
        
        Args:
            contextual_graph_service: ContextualGraphService instance
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            collection_factory: Optional CollectionFactory instance for multi-store queries
        """
        self.contextual_graph_service = contextual_graph_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        self.collection_factory = collection_factory
    
    async def retrieve_contexts(
        self,
        query: str,
        context_ids: Optional[List[str]] = None,
        include_all_contexts: bool = True,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve relevant contexts for a query
        
        Args:
            query: Natural language query or description
            context_ids: Optional list of specific context IDs to retrieve
            include_all_contexts: Whether to search all contexts if context_ids not provided
            top_k: Number of contexts to return
            filters: Optional metadata filters
            
        Returns:
            Dictionary with retrieved contexts and metadata
        """
        try:
            from app.services.models import ContextSearchRequest
            
            # If specific context IDs provided, retrieve them directly
            if context_ids:
                contexts = []
                for ctx_id in context_ids[:top_k]:
                    # Search for specific context
                    response = await self.contextual_graph_service.search_contexts(
                        ContextSearchRequest(
                            description=f"context_id: {ctx_id}",
                            top_k=1,
                            filters={"context_id": ctx_id} if filters else None,
                            request_id=f"retrieve_{ctx_id}"
                        )
                    )
                    if response.success and response.data:
                        contexts.extend(response.data.get("contexts", []))
            else:
                # Search all contexts
                response = await self.contextual_graph_service.search_contexts(
                    ContextSearchRequest(
                        description=query,
                        top_k=top_k,
                        filters=filters,
                        request_id="retrieve_contexts"
                    )
                )
                
                if not response.success:
                    logger.warning(f"Context search failed: {response.error}")
                    return {
                        "success": False,
                        "error": response.error,
                        "contexts": []
                    }
                
                contexts = response.data.get("contexts", []) if response.data else []
            
            # Enrich contexts with additional metadata
            enriched_contexts = await self._enrich_contexts(contexts)
            
            # If collection factory available, enrich with multi-store data
            if self.collection_factory:
                enriched_contexts = await self._enrich_contexts_with_stores(
                    contexts=enriched_contexts,
                    query=query
                )
            
            return {
                "success": True,
                "contexts": enriched_contexts,
                "count": len(enriched_contexts),
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Error retrieving contexts: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "contexts": []
            }
    
    async def create_reasoning_plan(
        self,
        user_action: str,
        retrieved_contexts: List[Dict[str, Any]],
        target_domain: Optional[str] = None,
        schema_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a reasoning plan based on user action and retrieved contexts
        
        Args:
            user_action: User's action or query
            retrieved_contexts: List of retrieved context dictionaries
            target_domain: Optional target domain for domain-specific planning
            schema_info: Optional schema information for data-related queries
            
        Returns:
            Dictionary with reasoning plan including steps, context information, and strategy
        """
        try:
            # Prepare context summaries for LLM
            context_summaries = []
            for ctx in retrieved_contexts:
                summary = {
                    "context_id": ctx.get("context_id"),
                    "context_type": ctx.get("metadata", {}).get("context_type", "unknown"),
                    "industry": ctx.get("metadata", {}).get("industry"),
                    "organization_size": ctx.get("metadata", {}).get("organization_size"),
                    "maturity_level": ctx.get("metadata", {}).get("maturity_level"),
                    "regulatory_frameworks": ctx.get("metadata", {}).get("regulatory_frameworks", []),
                    "relevance_score": ctx.get("combined_score", 0.0)
                }
                context_summaries.append(summary)
            
            # Build schema context for prompt
            schema_context = ""
            if schema_info:
                schema_names = schema_info.get("schema_names", [])
                schema_count = schema_info.get("schemas_count", 0)
                schema_summary = schema_info.get("schema_summary", "")
                
                schema_context = f"""

IMPORTANT: Database Schema Information Available
- Number of available schemas: {schema_count}
- Schema names: {', '.join(schema_names[:5])}
- Schema details: {schema_summary[:500]}...

When creating the reasoning plan, consider:
1. The available database tables and their structures
2. How the user's query relates to these schemas
3. What data analysis or queries might be needed
4. How to leverage schema information for better reasoning steps
"""
            
            # Add multi-store context if collection factory available
            store_context = ""
            if self.collection_factory:
                store_context = f"""

IMPORTANT: Multi-Store Knowledge Available
The system has access to multiple knowledge stores organized in hierarchy:
1. Connectors (data sources, APIs, integrations)
2. Domains (business domains, data domains)
3. Compliance (controls, requirements, policies)
4. Risks (risk controls, risk assessments)
5. Additionals (policies, evidence, etc.)
6. Schemas (tables, columns - separate from hierarchy)

When creating the reasoning plan, consider:
1. How to traverse the hierarchy: Connector -> Domain -> Compliance -> Risks -> Additionals
2. Which stores are most relevant for this query
3. How to connect entities across stores
4. How schemas relate to the entities in the hierarchy
"""
            
            # Generate reasoning plan using LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at creating reasoning plans for compliance and risk management tasks.

Given a user action and relevant organizational contexts, create a detailed reasoning plan that:
1. Identifies which contexts are most relevant
2. Determines the sequence of reasoning steps needed
3. Specifies which pipelines/extractors to use
4. Considers context-specific factors (industry, maturity, frameworks)
5. Provides a strategy for combining multi-context information
6. Traverses the knowledge hierarchy: Connector -> Domain -> Compliance -> Risks -> Additionals
7. Considers schema connections separately
{schema_context if schema_context else ""}
{store_context if store_context else ""}

Return a JSON object with:
- reasoning_steps: Array of step objects with fields: step_number, step_type, description, required_pipelines, context_ids, stores_to_query (connectors, domains, compliance, risks, schemas), consider_schemas (if applicable)
- context_priorities: Array of context priorities with fields: context_id, priority_score, reasoning
- strategy: Overall strategy description (include schema and store considerations)
- expected_outputs: What outputs to expect from each step
- multi_context_considerations: How to handle multiple contexts
- store_traversal: How to traverse the knowledge stores (connector -> domain -> compliance -> risks)
"""),
                ("human", """Create a reasoning plan for:

User Action: {user_action}
Target Domain: {target_domain}

Retrieved Contexts:
{contexts}
{schema_section}

Provide the reasoning plan as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            schema_section = ""
            if schema_info:
                schema_section = f"\n\nAvailable Database Schemas:\n{schema_info.get('schema_summary', '')[:1000]}"
            
            result = await chain.ainvoke({
                "user_action": user_action,
                "target_domain": target_domain or "general",
                "contexts": json.dumps(context_summaries, indent=2),
                "schema_section": schema_section
            })
            
            # Validate and structure the result
            reasoning_plan = {
                "user_action": user_action,
                "target_domain": target_domain,
                "reasoning_steps": result.get("reasoning_steps", []),
                "context_priorities": result.get("context_priorities", []),
                "strategy": result.get("strategy", ""),
                "expected_outputs": result.get("expected_outputs", []),
                "multi_context_considerations": result.get("multi_context_considerations", ""),
                "contexts_used": [ctx.get("context_id") for ctx in retrieved_contexts]
            }
            
            return {
                "success": True,
                "reasoning_plan": reasoning_plan
            }
            
        except Exception as e:
            logger.error(f"Error creating reasoning plan: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "reasoning_plan": {}
            }
    
    async def prioritize_contexts(
        self,
        contexts: List[Dict[str, Any]],
        query: str,
        action_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Prioritize contexts based on relevance to query and action type
        
        Args:
            contexts: List of context dictionaries
            query: User query or action
            action_type: Optional action type (e.g., 'metadata_generation', 'risk_assessment')
            
        Returns:
            List of prioritized contexts with priority scores
        """
        try:
            if not contexts:
                return []
            
            # Use LLM to score and prioritize contexts
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at prioritizing organizational contexts for compliance tasks.

Given a query and list of contexts, prioritize them based on:
1. Relevance to the query
2. Action type requirements
3. Context completeness
4. Temporal relevance (if applicable)

Return a JSON array of context priorities with:
- context_id: Context identifier
- priority_score: 0-1 priority score
- reasoning: Why this context is prioritized
"""),
                ("human", """Prioritize contexts:

Query: {query}
Action Type: {action_type}

Contexts:
{contexts}

Return prioritized contexts as JSON array.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            context_summaries = [
                {
                    "context_id": ctx.get("context_id"),
                    "metadata": ctx.get("metadata", {}),
                    "relevance_score": ctx.get("combined_score", 0.0)
                }
                for ctx in contexts
            ]
            
            result = await chain.ainvoke({
                "query": query,
                "action_type": action_type or "general",
                "contexts": json.dumps(context_summaries, indent=2)
            })
            
            # Merge priorities back into contexts
            priority_map = {
                item.get("context_id"): item
                for item in result if isinstance(result, list)
            }
            
            prioritized = []
            for ctx in contexts:
                ctx_id = ctx.get("context_id")
                priority_info = priority_map.get(ctx_id, {})
                ctx["priority_score"] = priority_info.get("priority_score", ctx.get("combined_score", 0.0))
                ctx["priority_reasoning"] = priority_info.get("reasoning", "")
                prioritized.append(ctx)
            
            # Sort by priority score
            prioritized.sort(key=lambda x: x.get("priority_score", 0.0), reverse=True)
            
            return prioritized
            
        except Exception as e:
            logger.error(f"Error prioritizing contexts: {str(e)}", exc_info=True)
            # Fallback: sort by existing relevance score
            return sorted(contexts, key=lambda x: x.get("combined_score", 0.0), reverse=True)
    
    async def _enrich_contexts(
        self,
        contexts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich context dictionaries with additional metadata and data store information
        
        Args:
            contexts: List of context dictionaries
            
        Returns:
            List of enriched context dictionaries
        """
        enriched = []
        for ctx in contexts:
            enriched_ctx = ctx.copy()
            context_id = ctx.get("context_id")
            
            # Add computed fields
            metadata = ctx.get("metadata", {})
            enriched_ctx["has_frameworks"] = bool(metadata.get("regulatory_frameworks"))
            enriched_ctx["has_systems"] = bool(metadata.get("systems"))
            enriched_ctx["context_completeness"] = self._calculate_completeness(metadata)
            
            # Enrich with data store information if context_id available
            if context_id:
                try:
                    # Get contextual edges count
                    edges = await self.contextual_graph_service.vector_storage.get_edges_for_context(
                        context_id=context_id,
                        top_k=100  # Get count
                    )
                    enriched_ctx["edges_count"] = len(edges)
                    
                    # Get control profiles count
                    profiles = await self.contextual_graph_service.vector_storage.get_control_profiles_for_context(
                        context_id=context_id,
                        top_k=100
                    )
                    enriched_ctx["controls_count"] = len(profiles)
                    
                    # Get entity types from edges
                    entity_types = set()
                    for edge in edges[:50]:  # Sample first 50
                        entity_types.add(edge.source_entity_type)
                        entity_types.add(edge.target_entity_type)
                    enriched_ctx["entity_types"] = list(entity_types)
                    
                except Exception as e:
                    logger.warning(f"Error enriching context {context_id}: {str(e)}")
                    enriched_ctx["edges_count"] = 0
                    enriched_ctx["controls_count"] = 0
                    enriched_ctx["entity_types"] = []
            
            enriched.append(enriched_ctx)
        
        return enriched
    
    def _calculate_completeness(self, metadata: Dict[str, Any]) -> float:
        """Calculate context completeness score (0-1)"""
        fields = [
            "industry",
            "organization_size",
            "maturity_level",
            "regulatory_frameworks",
            "data_types",
            "systems"
        ]
        
        present = sum(1 for field in fields if metadata.get(field))
        return present / len(fields) if fields else 0.0
    
    async def _enrich_contexts_with_stores(
        self,
        contexts: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Enrich contexts with data from all stores.
        
        Args:
            contexts: List of context dictionaries
            query: Search query
            
        Returns:
            Enriched contexts
        """
        if not self.collection_factory:
            return contexts
        
        enriched = []
        
        for ctx in contexts:
            enriched_ctx = ctx.copy()
            context_id = ctx.get("context_id")
            
            if not context_id:
                enriched.append(enriched_ctx)
                continue
            
            try:
                # Search all stores for this context
                all_results = await self.collection_factory.search_all(
                    query=query,
                    top_k=5,
                    filters={"context_id": context_id},
                    include_schemas=True
                )
                
                # Add store statistics
                enriched_ctx["store_statistics"] = {
                    "connectors_count": len(all_results.get("connectors", [])),
                    "domains_count": len(all_results.get("domains", [])),
                    "compliance_count": len(all_results.get("compliance", [])),
                    "risks_count": len(all_results.get("risks", [])),
                    "schemas_count": len(all_results.get("schemas", []))
                }
                
                # Add sample entities from each store
                enriched_ctx["sample_entities"] = {
                    "connectors": [r.get("id") or r.get("document_id") for r in all_results.get("connectors", [])[:2]],
                    "domains": [r.get("id") or r.get("document_id") for r in all_results.get("domains", [])[:2]],
                    "compliance": [r.get("id") or r.get("document_id") for r in all_results.get("compliance", [])[:2]]
                }
                
            except Exception as e:
                logger.warning(f"Error enriching context {context_id} with stores: {str(e)}")
            
            enriched.append(enriched_ctx)
        
        return enriched

