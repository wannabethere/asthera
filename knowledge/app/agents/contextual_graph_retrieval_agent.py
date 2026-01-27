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

from app.services.context_breakdown_service import ContextBreakdownService, ContextBreakdown
from app.services.edge_pruning_service import EdgePruningService
from app.services.contextual_graph_storage import ContextualEdge

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
        
        # Initialize context breakdown and edge pruning services
        self.context_breakdown_service = ContextBreakdownService(llm=self.llm)
        self.edge_pruning_service = EdgePruningService(llm=self.llm)
    
    async def retrieve_contexts(
        self,
        query: str,
        context_ids: Optional[List[str]] = None,
        include_all_contexts: bool = True,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        use_context_breakdown: bool = True,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_frameworks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve relevant contexts for a query using context breakdown for better understanding.
        
        Args:
            query: Natural language query or description
            context_ids: Optional list of specific context IDs to retrieve
            include_all_contexts: Whether to search all contexts if context_ids not provided
            top_k: Number of contexts to return
            filters: Optional metadata filters
            use_context_breakdown: Whether to use context breakdown to enhance query (default: True)
            available_actors: Optional list of available actor types (e.g., ["Compliance Officer", "Data Analyst"])
            available_domains: Optional list of available domains (e.g., ["compliance", "security", "risk"])
            available_products: Optional list of available products (e.g., ["Snyk", "Okta"])
            available_frameworks: Optional list of available frameworks (e.g., ["SOC2", "HIPAA"])
            
        Returns:
            Dictionary with retrieved contexts and metadata
        """
        try:
            from app.services.models import ContextSearchRequest
            
            # Use context breakdown to enhance query understanding
            context_breakdown = None
            enhanced_query = query
            enhanced_filters = filters.copy() if filters else {}
            
            if use_context_breakdown and not context_ids:
                try:
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=query,
                        available_actors=available_actors,
                        available_domains=available_domains,
                        available_products=available_products,
                        available_frameworks=available_frameworks
                    )
                    
                    # Use breakdown to enhance search query
                    enhanced_query = context_breakdown.to_search_query() or query
                    
                    # Add framework filters from breakdown
                    breakdown_filters = context_breakdown.to_metadata_filters()
                    if breakdown_filters:
                        enhanced_filters.update(breakdown_filters)
                    
                    logger.info(f"Enhanced query with context breakdown: {enhanced_query[:100]}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown, using original query: {str(e)}")
            
            # If specific context IDs provided, retrieve them directly
            if context_ids:
                contexts = []
                for ctx_id in context_ids[:top_k]:
                    # Search for specific context
                    response = await self.contextual_graph_service.search_contexts(
                        ContextSearchRequest(
                            description=f"context_id: {ctx_id}",
                            top_k=1,
                            filters={"context_id": ctx_id} if enhanced_filters else None,
                            request_id=f"retrieve_{ctx_id}"
                        )
                    )
                    if response.success and response.data:
                        contexts.extend(response.data.get("contexts", []))
            else:
                # Search all contexts using enhanced query
                response = await self.contextual_graph_service.search_contexts(
                    ContextSearchRequest(
                        description=enhanced_query,
                        top_k=top_k,
                        filters=enhanced_filters if enhanced_filters else None,
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
                    query=enhanced_query
                )
            
            result = {
                "success": True,
                "contexts": enriched_contexts,
                "count": len(enriched_contexts),
                "query": query,
                "enhanced_query": enhanced_query
            }
            
            # Include context breakdown if available
            if context_breakdown:
                result["context_breakdown"] = {
                    "compliance_context": context_breakdown.compliance_context,
                    "action_context": context_breakdown.action_context,
                    "frameworks": context_breakdown.frameworks,
                    "identified_entities": context_breakdown.identified_entities
                }
            
            return result
            
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
        schema_info: Optional[Dict[str, Any]] = None,
        use_context_breakdown: bool = True,
        include_table_relationships: bool = True,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_frameworks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a reasoning plan based on user action and retrieved contexts.
        Uses context breakdown to better understand the user action.
        Now includes table relationship information for better data query planning.
        
        Args:
            user_action: User's action or query
            retrieved_contexts: List of retrieved context dictionaries
            target_domain: Optional target domain for domain-specific planning
            schema_info: Optional schema information for data-related queries
            use_context_breakdown: Whether to use context breakdown (default: True)
            include_table_relationships: Whether to include table relationship information (default: True)
            available_actors: Optional list of available actor types (e.g., ["Compliance Officer", "Data Analyst"])
            available_domains: Optional list of available domains (e.g., ["compliance", "security", "risk"])
            available_products: Optional list of available products (e.g., ["Snyk", "Okta"])
            available_frameworks: Optional list of available frameworks (e.g., ["SOC2", "HIPAA"])
            
        Returns:
            Dictionary with reasoning plan including steps, context information, and strategy
        """
        try:
            # Use context breakdown to understand user action better
            context_breakdown = None
            if use_context_breakdown:
                try:
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=user_action,
                        available_actors=available_actors,
                        available_domains=available_domains,
                        available_products=available_products,
                        available_frameworks=available_frameworks
                    )
                    logger.info(f"Created context breakdown for reasoning plan: {context_breakdown.action_context}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown for reasoning plan: {str(e)}")
            
            # Extract table relationship information from contexts if available
            table_relationships_info = None
            if include_table_relationships and retrieved_contexts:
                try:
                    # Try to get related tables information from the first context
                    # This assumes contexts are entity contexts (table entities)
                    primary_context = retrieved_contexts[0] if retrieved_contexts else None
                    if primary_context:
                        context_id = primary_context.get("context_id")
                        # Try to extract table name from context
                        context_doc = primary_context.get("document", "") or primary_context.get("metadata", {}).get("document", "")
                        table_name = None
                        product_name = None
                        
                        if context_doc and "Entity:" in context_doc:
                            lines = context_doc.split("\n")
                            for line in lines:
                                if line.startswith("Entity:"):
                                    table_name = line.replace("Entity:", "").strip()
                                elif line.startswith("Product:"):
                                    product_name = line.replace("Product:", "").strip()
                        
                        # If we have a table name and context_id, get related tables
                        if table_name and context_id:
                            # Import here to avoid circular dependency
                            from app.agents.contextual_graph_reasoning_agent import ContextualGraphReasoningAgent
                            
                            # Create a temporary reasoning agent to get related tables
                            # We need the contextual_graph_service which should be available
                            if hasattr(self, 'contextual_graph_service'):
                                reasoning_agent = ContextualGraphReasoningAgent(
                                    contextual_graph_service=self.contextual_graph_service,
                                    llm=self.llm,
                                    collection_factory=self.collection_factory
                                )
                                
                                related_tables_result = await reasoning_agent.get_related_tables(
                                    table_name=table_name,
                                    context_id=context_id,
                                    product_name=product_name
                                )
                                
                                if related_tables_result.get("success"):
                                    table_relationships_info = {
                                        "primary_table": table_name,
                                        "related_tables": related_tables_result.get("related_tables", []),
                                        "total_relationships": related_tables_result.get("total_relationships", 0),
                                        "outgoing_count": related_tables_result.get("outgoing_count", 0),
                                        "incoming_count": related_tables_result.get("incoming_count", 0)
                                    }
                                    logger.info(f"Found {len(table_relationships_info['related_tables'])} related tables for {table_name}")
                except Exception as e:
                    logger.warning(f"Error extracting table relationships for reasoning plan: {str(e)}")
            
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
            
            # Build context breakdown context for prompt
            breakdown_context = ""
            if context_breakdown:
                breakdown_context = f"""

IMPORTANT: Context Breakdown Analysis
- Compliance Context: {context_breakdown.compliance_context or 'N/A'}
- Action Context: {context_breakdown.action_context or 'N/A'}
- Product Context: {context_breakdown.product_context or 'N/A'}
- User Intent: {context_breakdown.user_intent or 'N/A'}
- Frameworks: {', '.join(context_breakdown.frameworks) if context_breakdown.frameworks else 'None'}
- Identified Entities: {', '.join(context_breakdown.identified_entities) if context_breakdown.identified_entities else 'None'}
- Entity Types: {', '.join(context_breakdown.entity_types) if context_breakdown.entity_types else 'None'}
- Edge Types: {', '.join(context_breakdown.edge_types) if context_breakdown.edge_types else 'None'}

Use this breakdown to:
1. Focus on the most relevant entity types and stores
2. Understand the compliance framework requirements
3. Identify which edge types to traverse
4. Prioritize entities based on the breakdown
"""
            
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
            
            # Build table relationships context for prompt
            relationships_context = ""
            if table_relationships_info:
                primary_table = table_relationships_info.get("primary_table", "")
                related_tables = table_relationships_info.get("related_tables", [])
                total_relationships = table_relationships_info.get("total_relationships", 0)
                
                # Format related tables information
                related_tables_summary = []
                for rt in related_tables[:10]:  # Limit to top 10
                    table_name = rt.get("table_name", "")
                    relationships = rt.get("relationships", [])
                    direction = rt.get("direction", "")
                    relevance = rt.get("relevance_score", 0.0)
                    
                    # Extract relationship types
                    rel_types = [r.get("edge_type", "") for r in relationships[:3]]
                    rel_types_str = ", ".join(rel_types) if rel_types else "related"
                    
                    related_tables_summary.append(
                        f"  - {table_name} ({direction}, relevance: {relevance:.2f}): {rel_types_str}"
                    )
                
                relationships_context = f"""

IMPORTANT: Table Relationship Information Available
The contextual graph contains explicit relationships between tables created from MDL definitions.

Primary Table: {primary_table}
Total Relationships: {total_relationships}

Related Tables (with relationship types):
{chr(10).join(related_tables_summary) if related_tables_summary else "  - No related tables found"}

Available Relationship Types:
- BELONGS_TO_TABLE: Table belongs to another table (many-to-one)
- HAS_MANY_TABLES: Table has many related tables (one-to-many)
- REFERENCES_TABLE: Table references another table (one-to-one)
- MANY_TO_MANY_TABLE: Many-to-many relationship
- LINKED_TO_TABLE: General linked relationship
- RELATED_TO_TABLE: General related relationship

When creating the reasoning plan, consider:
1. Use relationship edges to discover related tables automatically
2. Include related tables in schema retrieval steps when they're relevant
3. Leverage relationship metadata (join types, conditions) for SQL generation
4. Traverse relationship edges to find all relevant tables for complex queries
5. Use relationship categories (belongs_to, has_many, references) to understand data model structure
6. For queries about a specific table, automatically include its related tables in the reasoning steps

Example: If querying "AccessRequest", automatically consider related tables like "groups", "assets", "users" based on relationship edges.
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
7. **IMPORTANT FOR DATA-RELATED QUERIES**: Always include schema/table retrieval steps

CRITICAL: For queries that involve data, metrics, tables, schemas, or database information:
- You MUST include a reasoning step that retrieves database schemas/tables
- Include "schemas" in the stores_to_query field for relevant steps
- Use table-related stores: table_definitions, table_descriptions, column_definitions, schema_descriptions, db_schema
- The reasoning plan should explicitly request schema retrieval even if schema_info is provided
- Schema retrieval should happen early in the reasoning steps to inform subsequent analysis

Available schema-related stores:
- table_definitions: Table structure definitions with columns
- table_descriptions: Detailed table descriptions and business context
- column_definitions: Individual column definitions with metadata
- schema_descriptions: Schema-level descriptions
- db_schema: Complete database schema documents

{breakdown_context if breakdown_context else ""}
{schema_context if schema_context else ""}
{relationships_context if relationships_context else ""}
{store_context if store_context else ""}

Return a JSON object with:
- reasoning_steps: Array of step objects with fields: step_number, step_type, description, required_pipelines, context_ids, stores_to_query (MUST include "schemas" for data-related queries), consider_schemas (set to true for data queries), table_retrieval_needed (true if schemas should be retrieved), use_table_relationships (set to true if relationship edges should be used to find related tables), related_tables (list of related table names to include if relationships are available)
- context_priorities: Array of context priorities with fields: context_id, priority_score, reasoning
- strategy: Overall strategy description (include schema, relationship, and store considerations, explicitly mention schema retrieval and table relationships if needed)
- expected_outputs: What outputs to expect from each step (include schema/table information and relationship information for data queries)
- multi_context_considerations: How to handle multiple contexts
- store_traversal: How to traverse the knowledge stores (connector -> domain -> compliance -> risks -> schemas)
- table_relationship_strategy: How to leverage table relationships for better query planning (if relationships are available)
"""),
                ("human", """Create a reasoning plan for:

User Action: {user_action}
Target Domain: {target_domain}

Retrieved Contexts:
{contexts}
{schema_section}
{relationships_section}

Provide the reasoning plan as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            schema_section = ""
            if schema_info:
                schema_section = f"\n\nAvailable Database Schemas:\n{schema_info.get('schema_summary', '')[:1000]}"
            
            relationships_section = ""
            if table_relationships_info:
                primary_table = table_relationships_info.get("primary_table", "")
                related_tables = table_relationships_info.get("related_tables", [])
                relationships_section = f"\n\nTable Relationships:\nPrimary Table: {primary_table}\n"
                relationships_section += f"Related Tables ({len(related_tables)}):\n"
                for rt in related_tables[:10]:
                    table_name = rt.get("table_name", "")
                    relationships = rt.get("relationships", [])
                    rel_types = [r.get("edge_type", "") for r in relationships[:3]]
                    relationships_section += f"  - {table_name}: {', '.join(rel_types) if rel_types else 'related'}\n"
            
            result = await chain.ainvoke({
                "user_action": user_action,
                "target_domain": target_domain or "general",
                "contexts": json.dumps(context_summaries, indent=2),
                "schema_section": schema_section,
                "relationships_section": relationships_section
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
                "store_traversal": result.get("store_traversal", ""),
                "table_relationship_strategy": result.get("table_relationship_strategy", ""),
                "contexts_used": [ctx.get("context_id") for ctx in retrieved_contexts]
            }
            
            # Add table relationships info if available
            if table_relationships_info:
                reasoning_plan["table_relationships"] = table_relationships_info
            
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
    
    async def discover_and_prune_edges(
        self,
        user_question: str,
        context_id: Optional[str] = None,
        top_k: int = 10,
        use_context_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Discover and prune edges based on user question using context breakdown.
        
        This is the main method that:
        1. Breaks down user question into context components
        2. Discovers edges using vector similarity search
        3. Prunes edges using LLM to select best ones
        4. Returns pruned edges for entity retrieval
        
        Args:
            user_question: User's question
            context_id: Optional context ID to filter edges
            top_k: Number of edges to return after pruning
            use_context_breakdown: Whether to use context breakdown (default: True)
            
        Returns:
            Dictionary with pruned edges, context breakdown, and metadata
        """
        try:
            # Step 1: Break down user question into context components
            context_breakdown = None
            if use_context_breakdown:
                context_breakdown = await self.context_breakdown_service.breakdown_question(
                    user_question=user_question
                )
            else:
                # Use default prompt
                context_breakdown = await self.context_breakdown_service.get_default_prompt(
                    user_question=user_question
                )
            
            # Step 2: Discover edges using vector similarity search
            # Use entity queries from breakdown if available (from vector_store_prompts.json)
            discovered_edges = []
            
            if hasattr(context_breakdown, 'identified_entities') and context_breakdown.identified_entities:
                # Use entity queries from vector_store_prompts.json breakdown
                entity_queries = context_breakdown.get_entity_queries(
                    self.context_breakdown_service.prompts_data
                )
                
                # Discover edges for each entity query
                for entity_query in entity_queries:
                    query = entity_query["query"]
                    filters = entity_query["metadata_filters"].copy()
                    if context_id:
                        filters["context_id"] = context_id
                    
                    edges = await self.contextual_graph_service.vector_storage.discover_edges_by_context(
                        context_query=query,
                        top_k=top_k * 2,  # Get more edges per entity
                        filters=filters if filters else None
                    )
                    discovered_edges.extend(edges)
                
                # Deduplicate edges by edge_id
                seen_edge_ids = set()
                unique_edges = []
                for edge in discovered_edges:
                    if edge.edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge.edge_id)
                        unique_edges.append(edge)
                discovered_edges = unique_edges
            else:
                # Fallback to simple search query
                search_query = context_breakdown.to_search_query()
                metadata_filters = context_breakdown.to_metadata_filters()
                if context_id:
                    metadata_filters["context_id"] = context_id
                
                discovered_edges = await self.contextual_graph_service.vector_storage.discover_edges_by_context(
                    context_query=search_query,
                    top_k=top_k * 3,  # Discover more edges than we need for pruning
                    filters=metadata_filters if metadata_filters else None
                )
            
            if not discovered_edges:
                logger.warning(f"No edges discovered for query: {user_question[:50]}")
                return {
                    "success": True,
                    "edges": [],
                    "context_breakdown": context_breakdown,
                    "discovered_count": 0,
                    "pruned_count": 0,
                    "used_default_prompt": not use_context_breakdown
                }
            
            # Step 3: Prune edges using LLM
            pruned_edges = await self.edge_pruning_service.prune_edges(
                user_question=user_question,
                discovered_edges=discovered_edges,
                max_edges=top_k,
                context_breakdown=context_breakdown.__dict__ if context_breakdown else None
            )
            
            logger.info(f"Discovered {len(discovered_edges)} edges, pruned to {len(pruned_edges)} edges")
            
            return {
                "success": True,
                "edges": pruned_edges,
                "context_breakdown": context_breakdown,
                "discovered_count": len(discovered_edges),
                "pruned_count": len(pruned_edges),
                "used_default_prompt": not use_context_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error in discover_and_prune_edges: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "edges": [],
                "context_breakdown": None,
                "discovered_count": 0,
                "pruned_count": 0
            }
    
    async def get_entities_from_edges(
        self,
        edges: List[ContextualEdge],
        user_question: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Get relevant entities from pruned edges with specific questions.
        
        Args:
            edges: List of pruned contextual edges
            user_question: Original user question
            top_k: Number of entities to return per entity type
            
        Returns:
            Dictionary with entities organized by type
        """
        try:
            entities_by_type = {}
            
            for edge in edges[:top_k * 2]:  # Limit to avoid too many queries
                # Get source entity
                source_type = edge.source_entity_type
                source_id = edge.source_entity_id
                
                if source_type not in entities_by_type:
                    entities_by_type[source_type] = []
                
                # Create entity-specific question
                entity_question = f"{user_question} (related to {edge.edge_type} edge from {source_type})"
                
                # Get entity from appropriate store
                entity_data = await self._get_entity_from_store(
                    entity_id=source_id,
                    entity_type=source_type,
                    question=entity_question
                )
                
                if entity_data:
                    entities_by_type[source_type].append({
                        "entity_id": source_id,
                        "entity_type": source_type,
                        "data": entity_data,
                        "edge_id": edge.edge_id,
                        "edge_type": edge.edge_type,
                        "relevance_score": edge.relevance_score
                    })
                
                # Get target entity
                target_type = edge.target_entity_type
                target_id = edge.target_entity_id
                
                if target_type not in entities_by_type:
                    entities_by_type[target_type] = []
                
                entity_question = f"{user_question} (related to {edge.edge_type} edge to {target_type})"
                
                entity_data = await self._get_entity_from_store(
                    entity_id=target_id,
                    entity_type=target_type,
                    question=entity_question
                )
                
                if entity_data:
                    entities_by_type[target_type].append({
                        "entity_id": target_id,
                        "entity_type": target_type,
                        "data": entity_data,
                        "edge_id": edge.edge_id,
                        "edge_type": edge.edge_type,
                        "relevance_score": edge.relevance_score
                    })
            
            # Limit entities per type
            for entity_type in entities_by_type:
                entities_by_type[entity_type] = entities_by_type[entity_type][:top_k]
            
            return {
                "success": True,
                "entities": entities_by_type,
                "total_entities": sum(len(entities) for entities in entities_by_type.values())
            }
            
        except Exception as e:
            logger.error(f"Error getting entities from edges: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "entities": {}
            }
    
    async def find_similar_features_for_entity(
        self,
        entity_id: str,
        entity_type: str,
        context_id: str,
        query: Optional[str] = None,
        top_k: int = 5,
        use_context_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Find similar features for an entity using the feature knowledge base.
        
        Args:
            entity_id: Entity ID (control, requirement, etc.)
            entity_type: Entity type
            context_id: Context ID
            query: Optional query (if not provided, will use entity_id)
            top_k: Number of similar features to return
            use_context_breakdown: Whether to use context breakdown (default: True)
            
        Returns:
            Dictionary with similar features
        """
        try:
            # Use context breakdown to enhance query
            context_breakdown = None
            search_query = query or f"{entity_type} {entity_id}"
            enhanced_query = search_query
            
            if use_context_breakdown:
                try:
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=search_query
                    )
                    enhanced_query = context_breakdown.to_search_query() or search_query
                    logger.info(f"Enhanced feature search query: {enhanced_query[:100]}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown for feature search: {str(e)}")
            
            # Search features using collection factory
            similar_features = []
            if self.collection_factory:
                features_collection = self.collection_factory.get_collection_by_store_name("features")
                if features_collection:
                    results = await features_collection.hybrid_search(
                        query=enhanced_query,
                        top_k=top_k,
                        where={"context_id": context_id} if context_id else None
                    )
                    
                    for result in results:
                        metadata = result.get("metadata", {})
                        content = result.get("content") or result.get("document", "")
                        
                        # Parse content if it's JSON
                        try:
                            import json
                            content_data = json.loads(content) if isinstance(content, str) and content.strip().startswith("{") else {}
                        except:
                            content_data = {}
                        
                        similar_features.append({
                            "feature_id": result.get("id") or metadata.get("feature_name", ""),
                            "feature_name": metadata.get("feature_name") or content_data.get("feature_name", ""),
                            "display_name": content_data.get("display_name", ""),
                            "feature_type": metadata.get("feature_type") or content_data.get("feature_type", ""),
                            "compliance": metadata.get("compliance") or content_data.get("compliance", ""),
                            "control": metadata.get("control") or content_data.get("control"),
                            "category": metadata.get("category", ""),
                            "description": content_data.get("description", ""),
                            "purpose": content_data.get("purpose", ""),
                            "question": content_data.get("question", ""),
                            "relevance_score": result.get("score", result.get("distance", 0.0)),
                            "source": "feature_knowledge"
                        })
                else:
                    logger.warning("Features collection not found in collection factory")
            else:
                logger.warning("Collection factory not available for feature search")
            
            # Sort by relevance score
            similar_features.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
            
            result = {
                "success": True,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "query": search_query,
                "enhanced_query": enhanced_query,
                "similar_features": similar_features[:top_k],
                "count": len(similar_features)
            }
            
            # Include context breakdown if available
            if context_breakdown:
                result["context_breakdown"] = {
                    "compliance_context": context_breakdown.compliance_context,
                    "action_context": context_breakdown.action_context,
                    "frameworks": context_breakdown.frameworks
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error finding similar features for entity: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "similar_features": []
            }
    
    async def _get_entity_from_store(
        self,
        entity_id: str,
        entity_type: str,
        question: str
    ) -> Optional[Dict[str, Any]]:
        """Get entity from appropriate store based on entity type"""
        try:
            if not self.contextual_graph_service.vector_storage:
                return None
            
            # Map entity types to stores
            store_mapping = {
                "control": "controls",
                "requirement": "domain_knowledge",  # Requirements might be in domain_knowledge
                "evidence": "evidence",
                "entity": "entities",
                "field": "fields",
                "schema": "table_definitions",
                "feature": "features"  # Add features support
            }
            
            # For now, use hybrid search to find entity
            # This could be enhanced to use direct ID lookup if available
            if entity_type in store_mapping:
                # Try to get from collection factory if available
                if self.collection_factory:
                    collection = self.collection_factory.get_collection_by_store_name(
                        store_mapping[entity_type]
                    )
                    if collection:
                        results = await collection.hybrid_search(
                            query=question,
                            top_k=1,
                            where={"id": entity_id} if entity_id else {}
                        )
                        if results:
                            return results[0]
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting entity {entity_id} from store: {str(e)}")
            return None

