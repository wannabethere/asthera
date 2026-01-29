"""
Contextual Graph Reasoning Agent
Performs context-aware reasoning using retrieved contexts and reasoning plans
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextualGraphReasoningAgent:
    """
    Agent that performs context-aware reasoning using the contextual graph.
    
    Performs:
    - Multi-hop contextual reasoning
    - Context-aware control prioritization
    - Context-dependent property inference
    - Multi-context synthesis
    """
    
    def __init__(
        self,
        contextual_graph_service: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        collection_factory: Optional[Any] = None
    ):
        """
        Initialize the contextual graph reasoning agent
        
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
        
        from app.services.context_breakdown_service import ContextBreakdownService
        from app.services.edge_pruning_service import EdgePruningService
        self.context_breakdown_service = ContextBreakdownService(llm=self.llm)
        self.edge_pruning_service = EdgePruningService(llm=self.llm)
    
    async def reason_with_context(
        self,
        query: str,
        context_id: str,
        max_hops: int = 3,
        reasoning_plan: Optional[Dict[str, Any]] = None,
        use_context_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Perform context-aware reasoning for a query using context breakdown for better understanding.
        
        Args:
            query: User query or question
            context_id: Context ID to reason within
            max_hops: Maximum number of reasoning hops
            reasoning_plan: Optional pre-computed reasoning plan
            use_context_breakdown: Whether to use context breakdown to enhance query (default: True)
            
        Returns:
            Dictionary with reasoning path, final answer, and context-specific insights
        """
        try:
            from app.models.service import MultiHopQueryRequest
            
            # Use context breakdown to enhance query understanding
            context_breakdown = None
            enhanced_query = query
            
            if use_context_breakdown:
                try:
                    logger.info(f"[Step: reason_with_context] Starting context breakdown for query: {query[:100]}")
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=query
                    )
                    # Use breakdown to enhance search query
                    enhanced_query = context_breakdown.to_search_query() or query
                    logger.info(f"[Step: reason_with_context] Context breakdown completed. Enhanced query: {enhanced_query[:100]}")
                    logger.debug(f"[Step: reason_with_context] Breakdown details: frameworks={context_breakdown.frameworks}, entities={context_breakdown.identified_entities[:5]}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown for reasoning, using original query: {str(e)}")
            
            # Perform multi-hop query with enhanced query
            logger.info(f"[Step: reason_with_context] Starting multi-hop query with max_hops={max_hops}, context_id={context_id}")
            response = await self.contextual_graph_service.multi_hop_query(
                MultiHopQueryRequest(
                    query=enhanced_query,
                    context_id=context_id,
                    max_hops=max_hops,
                    request_id=f"reason_{context_id}"
                )
            )
            
            if not response.success:
                logger.warning(f"Multi-hop query failed: {response.error}")
                return {
                    "success": False,
                    "error": response.error,
                    "reasoning_path": [],
                    "final_answer": ""
                }
            
            result = response.data or {}
            reasoning_path = result.get("reasoning_path", [])
            final_answer = result.get("final_answer", "")
            
            logger.info(f"[Step: reason_with_context] Multi-hop query completed. Reasoning path has {len(reasoning_path)} hops")
            logger.debug(f"[Step: reason_with_context] Final answer preview: {final_answer[:200]}...")
            
            # Enhance reasoning path with data from all stores
            logger.info(f"[Step: reason_with_context] Starting reasoning path enrichment")
            enriched_path = await self._enrich_reasoning_path(
                reasoning_path=reasoning_path,
                context_id=context_id
            )
            
            # If collection factory available, enrich with multi-store data
            # Only enrich last hop by default for performance (can be overridden)
            if self.collection_factory:
                logger.info(f"[Step: reason_with_context] Starting multi-store enrichment")
                enriched_path = await self._enrich_with_all_stores(
                    reasoning_path=enriched_path,
                    context_id=context_id,
                    query=query,
                    context_breakdown=context_breakdown,
                    enrich_all_hops=False  # Only enrich last hop for speed
                )
                logger.info(f"[Step: reason_with_context] Multi-store enrichment completed")
            
            # Enhance with context-specific insights
            logger.info(f"[Step: reason_with_context] Starting context insights generation")
            insights = await self._generate_context_insights(
                query=query,
                context_id=context_id,
                reasoning_path=enriched_path
            )
            logger.info(f"[Step: reason_with_context] Context insights generation completed")
            
            result = {
                "success": True,
                "query": query,
                "enhanced_query": enhanced_query,
                "context_id": context_id,
                "reasoning_path": enriched_path,
                "final_answer": final_answer,
                "context_insights": insights,
                "reasoning_plan_used": reasoning_plan is not None
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
            logger.error(f"Error in context-aware reasoning: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "reasoning_path": [],
                "final_answer": ""
            }
    
    async def get_related_tables(
        self,
        table_name: str,
        context_id: str,
        product_name: Optional[str] = None,
        relationship_types: Optional[List[str]] = None,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get related tables for a given table using relationship edges from contextual graph.
        
        This method retrieves tables that are connected to the given table through
        relationship edges (BELONGS_TO_TABLE, HAS_MANY_TABLES, REFERENCES_TABLE, etc.)
        created during MDL ingestion.
        
        Args:
            table_name: Name of the table to find related tables for
            context_id: Context ID for the table entity
            product_name: Optional product name to construct entity IDs
            relationship_types: Optional list of edge types to filter by (e.g., ["BELONGS_TO_TABLE", "HAS_MANY_TABLES"])
            max_depth: Maximum depth to traverse relationships (default: 2)
            
        Returns:
            Dictionary with related_tables list and relationship information
        """
        try:
            # Construct entity ID if product_name provided
            if product_name:
                entity_id = f"entity_{product_name}_{table_name}".lower().replace(" ", "_")
            else:
                # Try to extract from context_id
                entity_id = context_id
            
            logger.info(f"[Step: get_related_tables] Getting related tables for {table_name} (entity_id={entity_id})")
            
            # Get outgoing edges (tables this table relates to)
            outgoing_edges = self.contextual_graph_service.vector_storage.get_edges_for_context(
                context_id=context_id,
                source_entity_id=entity_id,
                top_k=100
            )
            
            # Filter by relationship types if specified
            if relationship_types:
                outgoing_edges = [
                    e for e in outgoing_edges 
                    if e.edge_type in relationship_types
                ]
            
            # Get incoming edges (tables that relate to this table)
            incoming_edges = self.contextual_graph_service.vector_storage.search_edges(
                query="",
                context_id=context_id,
                filters={"target_entity_id": entity_id},
                top_k=100
            )
            
            if relationship_types:
                incoming_edges = [
                    e for e in incoming_edges
                    if e.edge_type in relationship_types
                ]
            
            # Extract related table information
            related_tables = {}
            
            # Process outgoing edges
            for edge in outgoing_edges:
                if edge.target_entity_type == "entity":
                    target_id = edge.target_entity_id
                    # Extract table name from entity ID (entity_product_tablename)
                    if "_" in target_id:
                        parts = target_id.split("_", 2)
                        if len(parts) >= 3:
                            related_table_name = parts[2]
                        else:
                            related_table_name = target_id
                    else:
                        related_table_name = target_id
                    
                    if related_table_name not in related_tables:
                        related_tables[related_table_name] = {
                            "table_name": related_table_name,
                            "entity_id": target_id,
                            "relationships": [],
                            "direction": "outgoing"
                        }
                    
                    # Extract relationship metadata
                    rel_info = {
                        "edge_type": edge.edge_type,
                        "edge_id": edge.edge_id,
                        "relevance_score": edge.relevance_score,
                        "document": edge.document[:200] if edge.document else ""
                    }
                    
                    # Try to extract metadata from edge document
                    # Relationship metadata is stored in the document in a structured format
                    if edge.document and "Relationship Metadata:" in edge.document:
                        doc_lines = edge.document.split("\n")
                        in_metadata = False
                        for line in doc_lines:
                            if "Relationship Metadata:" in line:
                                in_metadata = True
                                continue
                            if in_metadata and ":" in line:
                                parts = line.strip().split(":", 1)
                                if len(parts) == 2:
                                    key = parts[0].strip().replace("-", "").lower()
                                    value = parts[1].strip()
                                    if "relationship name" in key:
                                        rel_info["relationship_name"] = value
                                    elif "join type" in key:
                                        rel_info["join_type"] = value
                                    elif "relationship category" in key:
                                        rel_info["relationship_category"] = value
                    
                    related_tables[related_table_name]["relationships"].append(rel_info)
            
            # Process incoming edges
            for edge in incoming_edges:
                if edge.source_entity_type == "entity":
                    source_id = edge.source_entity_id
                    # Extract table name from entity ID
                    if "_" in source_id:
                        parts = source_id.split("_", 2)
                        if len(parts) >= 3:
                            related_table_name = parts[2]
                        else:
                            related_table_name = source_id
                    else:
                        related_table_name = source_id
                    
                    if related_table_name not in related_tables:
                        related_tables[related_table_name] = {
                            "table_name": related_table_name,
                            "entity_id": source_id,
                            "relationships": [],
                            "direction": "incoming"
                        }
                    else:
                        related_tables[related_table_name]["direction"] = "bidirectional"
                    
                    # Extract relationship metadata
                    rel_info = {
                        "edge_type": edge.edge_type,
                        "edge_id": edge.edge_id,
                        "relevance_score": edge.relevance_score,
                        "document": edge.document[:200] if edge.document else ""
                    }
                    
                    # Try to extract metadata from edge document (same logic as above)
                    if edge.document and "Relationship Metadata:" in edge.document:
                        doc_lines = edge.document.split("\n")
                        in_metadata = False
                        for line in doc_lines:
                            if "Relationship Metadata:" in line:
                                in_metadata = True
                                continue
                            if in_metadata and ":" in line:
                                parts = line.strip().split(":", 1)
                                if len(parts) == 2:
                                    key = parts[0].strip().replace("-", "").lower()
                                    value = parts[1].strip()
                                    if "relationship name" in key:
                                        rel_info["relationship_name"] = value
                                    elif "join type" in key:
                                        rel_info["join_type"] = value
                                    elif "relationship category" in key:
                                        rel_info["relationship_category"] = value
                    
                    related_tables[related_table_name]["relationships"].append(rel_info)
            
            # Convert to list and sort by relevance
            related_tables_list = list(related_tables.values())
            for rt in related_tables_list:
                # Calculate average relevance score
                if rt["relationships"]:
                    avg_relevance = sum(r.get("relevance_score", 0.5) for r in rt["relationships"]) / len(rt["relationships"])
                    rt["relevance_score"] = avg_relevance
                else:
                    rt["relevance_score"] = 0.5
            
            # Sort by relevance
            related_tables_list.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
            
            logger.info(f"[Step: get_related_tables] Found {len(related_tables_list)} related tables for {table_name}")
            
            return {
                "success": True,
                "table_name": table_name,
                "context_id": context_id,
                "related_tables": related_tables_list,
                "total_relationships": sum(len(rt["relationships"]) for rt in related_tables_list),
                "outgoing_count": len([e for e in outgoing_edges if e.target_entity_type == "entity"]),
                "incoming_count": len([e for e in incoming_edges if e.source_entity_type == "entity"])
            }
            
        except Exception as e:
            logger.error(f"Error getting related tables: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "table_name": table_name,
                "related_tables": []
            }
    
    async def suggest_relevant_tables(
        self,
        query: str,
        context_id: str,
        project_id: Optional[str] = None,
        top_k: int = 10,
        use_context_breakdown: bool = True,
        reasoning_plan: Optional[Dict[str, Any]] = None,
        include_related_tables: bool = True
    ) -> Dict[str, Any]:
        """
        Suggest relevant database tables based on query and context.
        Uses context breakdown to better understand query intent.
        
        Uses contextual graph to understand what tables would be most relevant
        for answering the query within the given context.
        
        Args:
            query: User query
            context_id: Context ID to reason within
            project_id: Optional project ID for project-specific suggestions
            top_k: Number of table suggestions to return
            use_context_breakdown: Whether to use context breakdown (default: True)
            reasoning_plan: Optional reasoning plan that may specify schema/table retrieval needs
            
        Returns:
            Dictionary with suggested_tables list and reasoning
        """
        try:
            # Use context breakdown to enhance query understanding
            context_breakdown = None
            enhanced_query = query
            
            # If reasoning plan is provided and requires schema retrieval, prioritize it
            if reasoning_plan:
                reasoning_steps = reasoning_plan.get("reasoning_steps", [])
                for step in reasoning_steps:
                    stores_to_query = step.get("stores_to_query", [])
                    if isinstance(stores_to_query, list) and "schemas" in stores_to_query:
                        logger.info("Reasoning plan requires schema retrieval - prioritizing table suggestions")
                        # Enhance query with reasoning plan context
                        step_description = step.get("description", "")
                        if step_description:
                            enhanced_query = f"{query} {step_description}"
                        break
            
            if use_context_breakdown:
                try:
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=query
                    )
                    # Use breakdown keywords and context for better table suggestions
                    breakdown_query = context_breakdown.to_search_query() or query
                    # Combine with reasoning plan enhanced query if available
                    if enhanced_query != query:
                        enhanced_query = f"{enhanced_query} {breakdown_query}"
                    else:
                        enhanced_query = breakdown_query
                    logger.info(f"Enhanced table suggestion query: {enhanced_query[:100]}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown for table suggestions: {str(e)}")
            
            # Get context information
            logger.info(f"[Step: suggest_relevant_tables] Getting context definition for context_id={context_id}")
            context_definition = await self.contextual_graph_service.vector_storage.get_context_definition(context_id)
            logger.debug(f"[Step: suggest_relevant_tables] Context definition retrieved: {context_definition.document[:200] if context_definition else 'None'}...")
            
            # Extract table name from context if possible
            table_name_from_context = None
            product_name_from_context = None
            if context_definition:
                # Try to extract table name from context document or metadata
                context_doc = context_definition.document
                if "Entity:" in context_doc:
                    # Extract from "Entity: TableName" pattern
                    lines = context_doc.split("\n")
                    for line in lines:
                        if line.startswith("Entity:"):
                            table_name_from_context = line.replace("Entity:", "").strip()
                            break
                
                # Extract product name
                if context_definition.systems:
                    product_name_from_context = context_definition.systems[0] if context_definition.systems else None
            
            # Initialize table_suggestions list
            table_suggestions = []
            
            # Get related tables using relationship edges if table name can be extracted
            related_tables_from_edges = []
            if include_related_tables and table_name_from_context:
                try:
                    logger.info(f"[Step: suggest_relevant_tables] Getting related tables for {table_name_from_context}")
                    related_tables_result = await self.get_related_tables(
                        table_name=table_name_from_context,
                        context_id=context_id,
                        product_name=product_name_from_context
                    )
                    
                    if related_tables_result.get("success"):
                        related_tables_from_edges = related_tables_result.get("related_tables", [])
                        logger.info(f"[Step: suggest_relevant_tables] Found {len(related_tables_from_edges)} related tables from relationship edges")
                        
                        # Convert to table suggestions format
                        for rt in related_tables_from_edges:
                            rt_name = rt.get("table_name", "")
                            if rt_name:
                                table_suggestions.append({
                                    "table_name": rt_name,
                                    "schema": "public",  # Default schema
                                    "relevance_score": rt.get("relevance_score", 0.7),
                                    "description": f"Related to {table_name_from_context} via {len(rt.get('relationships', []))} relationship(s)",
                                    "reasoning": f"Found via relationship edges: {', '.join([r.get('edge_type', '') for r in rt.get('relationships', [])[:3]])}",
                                    "source": "relationship_edges",
                                    "relationships": rt.get("relationships", [])
                                })
                except Exception as e:
                    logger.warning(f"Error getting related tables: {str(e)}")
            
            # Search contextual graph for entities/tables related to this context
            logger.info(f"[Step: suggest_relevant_tables] Starting entity and table search")
            # Look for entities in the contextual graph that might represent tables
            if self.collection_factory:
                # Search entities collection for table-like entities using enhanced query
                entities_collection = self.collection_factory.get_collection_by_store_name("entities")
                if entities_collection:
                    # Search for entities related to the context
                    entity_results = await entities_collection.hybrid_search(
                        query=f"{enhanced_query} {context_definition.document[:500] if context_definition else ''}",
                        top_k=top_k * 2,
                        where={"context_id": context_id} if context_id else {}
                    )
                    
                    # Also search table_definitions if available using enhanced query
                    table_def_collection = self.collection_factory.get_collection_by_store_name("table_definitions")
                    if table_def_collection:
                        table_results = await table_def_collection.hybrid_search(
                            query=enhanced_query,
                            top_k=top_k * 2,
                            where={"project_id": project_id} if project_id else {}
                        )
                        for result in table_results:
                            metadata = result.get("metadata", {})
                            table_name = metadata.get("table_name") or metadata.get("name")
                            if table_name:
                                table_suggestions.append({
                                    "table_name": table_name,
                                    "schema": metadata.get("schema", "public"),
                                    "relevance_score": result.get("score", 0.0),
                                    "description": result.get("document", "")[:200],
                                    "reasoning": f"Found in table_definitions collection based on query relevance"
                                })
                        logger.info(f"[Step: suggest_relevant_tables] Found {len(table_suggestions)} tables from table_definitions collection")
            
            # Use LLM to analyze query and context to suggest tables
            logger.info(f"[Step: suggest_relevant_tables] Preparing LLM call for table suggestions")
            context_doc = context_definition.document if context_definition else ""
            context_frameworks = context_definition.regulatory_frameworks if context_definition else []
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert data analyst that suggests relevant database tables for queries.

Given a user query and context information, suggest the most relevant database tables that would help answer the query.

Consider:
1. The query's intent and what data it needs
2. The context's domain, frameworks, and systems
3. Common table patterns for similar queries
4. Relationships between tables

Return a JSON object with:
- suggested_tables: Array of table objects with fields:
  - table_name: Name of the table (e.g., "users", "access_logs", "audit_events")
  - schema: Schema name (default: "public")
  - reasoning: Why this table is relevant
  - confidence: Confidence score (0.0-1.0)
  - expected_columns: List of column names that might be useful
- overall_strategy: Strategy for using these tables
- table_relationships: How tables might be joined or related"""),
                ("human", """Suggest relevant tables for:

Query: {query}
Project ID: {project_id}
Context: {context_doc}
Frameworks: {frameworks}
{breakdown_info}
{existing_suggestions}

Provide table suggestions as JSON.""")
            ])
            
            existing_suggestions_text = ""
            if table_suggestions:
                existing_suggestions_text = "\n\nExisting table suggestions from search:\n"
                for suggestion in table_suggestions[:5]:
                    existing_suggestions_text += f"- {suggestion['table_name']}: {suggestion['reasoning']}\n"
            
            # Add context breakdown info to prompt if available
            breakdown_info = ""
            if context_breakdown:
                breakdown_info = f"""
Context Breakdown:
- Action Context: {context_breakdown.action_context or 'N/A'}
- Query Keywords: {', '.join(context_breakdown.query_keywords[:10]) if context_breakdown.query_keywords else 'N/A'}
- Identified Entities: {', '.join(context_breakdown.identified_entities[:5]) if context_breakdown.identified_entities else 'N/A'}
"""
            
            chain = prompt | self.llm | self.json_parser
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "project_id": project_id or "unknown",
                "context_doc": context_doc[:2000],
                "frameworks": ", ".join(context_frameworks) if context_frameworks else "None",
                "existing_suggestions": existing_suggestions_text,
                "breakdown_info": breakdown_info
            }
            from app.utils import traced_llm_call
            
            logger.info(f"[LLM Step: suggest_relevant_tables] Starting LLM call for table suggestions with tracing")
            logger.debug(f"[LLM Step: suggest_relevant_tables] Input: query={query[:100]}, project_id={project_id}, frameworks={context_frameworks}")
            
            result = await traced_llm_call(
                llm=self.llm,
                prompt=prompt,
                inputs=llm_input,
                operation_name="suggest_relevant_tables",
                parse_json=True,
                metadata={
                    "project_id": project_id,
                    "has_reasoning_plan": bool(reasoning_plan),
                    "top_k": top_k
                }
            )
            
            # Log LLM call output
            logger.info(f"[LLM Step: suggest_relevant_tables] LLM call completed successfully")
            logger.info(f"[LLM Step: suggest_relevant_tables] Output: Found {len(result.get('suggested_tables', []))} table suggestions")
            logger.debug(f"[LLM Step: suggest_relevant_tables] LLM Result: {json.dumps(result, indent=2)[:500]}...")
            
            # Merge LLM suggestions with search results
            llm_suggestions = result.get("suggested_tables", [])
            
            # Combine and deduplicate
            all_suggestions = {}
            for suggestion in table_suggestions:
                table_name = suggestion["table_name"]
                if table_name not in all_suggestions:
                    all_suggestions[table_name] = suggestion
            
            for suggestion in llm_suggestions:
                table_name = suggestion.get("table_name")
                if table_name:
                    if table_name not in all_suggestions:
                        all_suggestions[table_name] = {
                            "table_name": table_name,
                            "schema": suggestion.get("schema", "public"),
                            "relevance_score": suggestion.get("confidence", 0.5),
                            "description": "",
                            "reasoning": suggestion.get("reasoning", ""),
                            "expected_columns": suggestion.get("expected_columns", [])
                        }
                    else:
                        # Merge reasoning
                        existing = all_suggestions[table_name]
                        existing["reasoning"] = f"{existing['reasoning']}; {suggestion.get('reasoning', '')}"
                        if suggestion.get("expected_columns"):
                            existing["expected_columns"] = suggestion.get("expected_columns", [])
            
            # Sort by relevance and take top_k
            sorted_suggestions = sorted(
                all_suggestions.values(),
                key=lambda x: x.get("relevance_score", 0.0),
                reverse=True
            )[:top_k]
            
            logger.info(f"[Step: suggest_relevant_tables] Merged and sorted suggestions. Returning top {len(sorted_suggestions)} tables")
            
            response = {
                "success": True,
                "suggested_tables": sorted_suggestions,
                "overall_strategy": result.get("overall_strategy", ""),
                "table_relationships": result.get("table_relationships", []),
                "context_id": context_id,
                "enhanced_query": enhanced_query
            }
            
            # Include context breakdown if available
            if context_breakdown:
                response["context_breakdown"] = {
                    "action_context": context_breakdown.action_context,
                    "query_keywords": context_breakdown.query_keywords
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Error suggesting tables: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "suggested_tables": [],
                "overall_strategy": "",
                "table_relationships": []
            }
    
    async def get_priority_controls(
        self,
        context_id: str,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        include_requirements: bool = True,
        include_evidence: bool = True,
        include_measurements: bool = True,
        use_context_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Get priority controls for a context with context-aware prioritization.
        Uses context breakdown to better understand query when provided.
        Enriched with requirements, evidence, and measurements from all data stores
        
        Args:
            context_id: Context ID
            query: Optional query to filter controls
            filters: Optional metadata filters
            top_k: Number of controls to return
            include_requirements: Whether to include requirements for each control
            include_evidence: Whether to include evidence types
            include_measurements: Whether to include measurements and analytics
            use_context_breakdown: Whether to use context breakdown when query provided (default: True)
            
        Returns:
            Dictionary with priority controls enriched with all available data
        """
        try:
            from app.models.service import PriorityControlsRequest
            
            # Use context breakdown to enhance query if provided
            context_breakdown = None
            enhanced_query = query
            enhanced_filters = filters.copy() if filters else {}
            
            if use_context_breakdown and query:
                try:
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=query
                    )
                    # Use breakdown to enhance search query
                    enhanced_query = context_breakdown.to_search_query() or query
                    
                    # Add framework filters from breakdown
                    breakdown_filters = context_breakdown.to_metadata_filters()
                    if breakdown_filters:
                        enhanced_filters.update(breakdown_filters)
                    
                    logger.info(f"Enhanced priority controls query: {enhanced_query[:100]}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown for priority controls: {str(e)}")
            
            response = await self.contextual_graph_service.get_priority_controls(
                PriorityControlsRequest(
                    context_id=context_id,
                    query=enhanced_query,
                    filters=enhanced_filters if enhanced_filters else None,
                    top_k=top_k,
                    request_id=f"priority_{context_id}"
                )
            )
            
            if not response.success:
                logger.warning(f"Priority controls query failed: {response.error}")
                return {
                    "success": False,
                    "error": response.error,
                    "controls": []
                }
            
            controls = response.data.get("controls", []) if response.data else []
            logger.info(f"[Step: get_priority_controls] Retrieved {len(controls)} controls from priority controls query")
            
            # Enrich with all available data from data stores
            logger.info(f"[Step: get_priority_controls] Starting control enrichment (requirements={include_requirements}, evidence={include_evidence}, measurements={include_measurements})")
            enhanced_controls = await self._enrich_controls_with_all_data(
                controls=controls,
                context_id=context_id,
                query=query,
                include_requirements=include_requirements,
                include_evidence=include_evidence,
                include_measurements=include_measurements
            )
            
            # If collection factory available, enrich with multi-store data
            if self.collection_factory:
                logger.info(f"[Step: get_priority_controls] Starting multi-store enrichment for controls")
                enhanced_controls = await self._enrich_controls_with_stores(
                    controls=enhanced_controls,
                    context_id=context_id,
                    query=query
                )
                logger.info(f"[Step: get_priority_controls] Multi-store enrichment completed")
            
            logger.info(f"[Step: get_priority_controls] Complete. Returning {len(enhanced_controls)} enriched controls")
            result = {
                "success": True,
                "context_id": context_id,
                "controls": enhanced_controls,
                "count": len(enhanced_controls),
                "enhanced_query": enhanced_query if query else None
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
            logger.error(f"Error getting priority controls: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "controls": []
            }
    
    async def synthesize_multi_context(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        reasoning_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synthesize reasoning results from multiple contexts
        
        Args:
            query: Original query
            contexts: List of context dictionaries
            reasoning_results: List of reasoning results from each context
            
        Returns:
            Dictionary with synthesized answer and multi-context insights
        """
        try:
            # Prepare context summaries
            context_summaries = []
            for ctx, result in zip(contexts, reasoning_results):
                summary = {
                    "context_id": ctx.get("context_id"),
                    "industry": ctx.get("metadata", {}).get("industry"),
                    "maturity_level": ctx.get("metadata", {}).get("maturity_level"),
                    "reasoning_path": result.get("reasoning_path", []),
                    "final_answer": result.get("final_answer", "")
                }
                context_summaries.append(summary)
            
            # Synthesize using LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at synthesizing compliance information across multiple organizational contexts.

Given reasoning results from multiple contexts, synthesize a comprehensive answer that:
1. Identifies common patterns across contexts
2. Highlights context-specific differences
3. Provides actionable recommendations considering all contexts
4. Explains why recommendations differ by context

Return a JSON object with:
- synthesized_answer: Comprehensive answer considering all contexts
- common_patterns: Patterns found across all contexts
- context_differences: How recommendations differ by context
- actionable_recommendations: Context-aware recommendations
- reasoning_summary: Summary of reasoning across contexts
"""),
                ("human", """Synthesize reasoning from multiple contexts:

Query: {query}

Context Results:
{context_results}

Provide synthesis as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "context_results": json.dumps(context_summaries, indent=2)
            }
            from app.utils import traced_llm_call
            
            logger.info(f"[LLM Step: synthesize_multi_context] Starting LLM call for multi-context synthesis with tracing")
            logger.debug(f"[LLM Step: synthesize_multi_context] Input: query={query[:100]}, contexts_count={len(contexts)}")
            
            result = await traced_llm_call(
                llm=self.llm,
                prompt=prompt,
                inputs=llm_input,
                operation_name="synthesize_multi_context",
                parse_json=True,
                metadata={
                    "contexts_count": len(contexts),
                    "has_reasoning_results": bool(reasoning_results)
                }
            )
            
            # Log LLM call output
            logger.info(f"[LLM Step: synthesize_multi_context] LLM call completed successfully")
            logger.info(f"[LLM Step: synthesize_multi_context] Output: Synthesis generated with {len(result.get('common_patterns', []))} common patterns")
            logger.debug(f"[LLM Step: synthesize_multi_context] LLM Result: {json.dumps(result, indent=2)[:500]}...")
            
            return {
                "success": True,
                "query": query,
                "synthesis": result,
                "contexts_considered": len(contexts)
            }
            
        except Exception as e:
            logger.error(f"Error synthesizing multi-context: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "synthesis": {}
            }
    
    async def get_comprehensive_entity_info(
        self,
        entity_id: str,
        entity_type: str,
        context_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive information about an entity from all data stores
        
        Args:
            entity_id: Entity identifier
            entity_type: Entity type ('control', 'requirement', 'evidence', etc.)
            context_id: Context ID
            
        Returns:
            Dictionary with all available information about the entity
        """
        try:
            info = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "context_id": context_id,
                "success": True
            }
            
            # Get contextual edges for this entity
            edges = self.contextual_graph_service.vector_storage.get_edges_for_context(
                context_id=context_id,
                source_entity_id=entity_id,
                top_k=50
            )
            info["outgoing_edges"] = [
                {
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type,
                    "target_entity_id": edge.target_entity_id,
                    "target_entity_type": edge.target_entity_type,
                    "relevance_score": edge.relevance_score
                }
                for edge in edges
            ]
            
            # Get incoming edges
            incoming_edges = self.contextual_graph_service.vector_storage.search_edges(
                query="",
                context_id=context_id,
                filters={"target_entity_id": entity_id},
                top_k=50
            )
            info["incoming_edges"] = [
                {
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type,
                    "source_entity_id": edge.source_entity_id,
                    "source_entity_type": edge.source_entity_type,
                    "relevance_score": edge.relevance_score
                }
                for edge in incoming_edges
            ]
            
            # Entity-specific data
            if entity_type == "control":
                # Get control details
                control = await self.contextual_graph_service.control_service.get_control(entity_id)
                if control:
                    info["control"] = {
                        "control_id": control.control_id,
                        "framework": control.framework,
                        "control_name": control.control_name,
                        "control_description": control.control_description,
                        "category": control.category
                    }
                
                # Get requirements
                requirements = await self.contextual_graph_service.requirement_service.get_requirements_for_control(
                    entity_id
                )
                info["requirements"] = [
                    {
                        "requirement_id": req.requirement_id,
                        "requirement_text": req.requirement_text,
                        "requirement_type": req.requirement_type
                    }
                    for req in requirements
                ]
                
                # Get measurements
                measurements = await self.contextual_graph_service.measurement_service.get_measurements_for_control(
                    control_id=entity_id,
                    context_id=context_id,
                    days=90
                )
                info["measurements"] = [
                    {
                        "measurement_id": m.measurement_id,
                        "measured_value": m.measured_value,
                        "passed": m.passed,
                        "measurement_date": m.measurement_date.isoformat() if m.measurement_date else None
                    }
                    for m in measurements[:10]
                ]
                
                # Get analytics
                analytics = await self.contextual_graph_service.measurement_service.get_risk_analytics(
                    entity_id
                )
                if analytics:
                    info["risk_analytics"] = {
                        "avg_compliance_score": analytics.avg_compliance_score,
                        "current_risk_score": analytics.current_risk_score,
                        "risk_level": analytics.risk_level,
                        "trend": analytics.trend
                    }
            
            elif entity_type == "requirement":
                # Get requirement details
                requirement = await self.contextual_graph_service.requirement_service.get_requirement(entity_id)
                if requirement:
                    info["requirement"] = {
                        "requirement_id": requirement.requirement_id,
                        "requirement_text": requirement.requirement_text,
                        "requirement_type": requirement.requirement_type,
                        "control_id": requirement.control_id
                    }
            
            elif entity_type == "evidence":
                # Get evidence details
                evidence = await self.contextual_graph_service.evidence_service.get_evidence_type(entity_id)
                if evidence:
                    info["evidence"] = {
                        "evidence_id": evidence.evidence_id,
                        "evidence_name": evidence.evidence_name,
                        "evidence_category": evidence.evidence_category,
                        "collection_method": evidence.collection_method
                    }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting comprehensive entity info: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "entity_id": entity_id,
                "entity_type": entity_type
            }
    
    async def infer_context_properties(
        self,
        entity_id: str,
        entity_type: str,
        context_id: str
    ) -> Dict[str, Any]:
        """
        Infer context-dependent properties for an entity
        Uses comprehensive entity info from all data stores
        
        Args:
            entity_id: Entity identifier (e.g., control_id)
            entity_type: Entity type (e.g., 'control', 'requirement')
            context_id: Context ID
            
        Returns:
            Dictionary with context-dependent properties
        """
        try:
            # Get comprehensive entity information first
            entity_info = await self.get_comprehensive_entity_info(
                entity_id=entity_id,
                entity_type=entity_type,
                context_id=context_id
            )
            
            # Use LLM to infer properties based on context and entity info
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at inferring context-dependent properties for compliance entities.

Given an entity and context, infer:
- Risk score in this context
- Implementation complexity in this context
- Evidence availability in this context
- Measurement feasibility in this context
- Priority in this context

Use the entity information provided to make informed inferences.

Return a JSON object with inferred properties."""),
                ("human", """Infer properties for:

Entity ID: {entity_id}
Entity Type: {entity_type}
Context ID: {context_id}

Entity Information:
{entity_info}

Provide inferred properties as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Log LLM call input
            llm_input = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "context_id": context_id,
                "entity_info": json.dumps(entity_info, indent=2, default=str)
            }
            from app.utils import traced_llm_call
            
            logger.info(f"[LLM Step: infer_context_properties] Starting LLM call for property inference with tracing")
            logger.debug(f"[LLM Step: infer_context_properties] Input: entity_id={entity_id}, entity_type={entity_type}, context_id={context_id}")
            
            result = await traced_llm_call(
                llm=self.llm,
                prompt=prompt,
                inputs=llm_input,
                operation_name="infer_context_properties",
                parse_json=True,
                metadata={
                    "entity_type": entity_type,
                    "context_id": context_id,
                    "has_context_doc": bool(llm_input.get("context_doc"))
                }
            )
            
            # Log LLM call output
            logger.info(f"[LLM Step: infer_context_properties] LLM call completed successfully")
            logger.info(f"[LLM Step: infer_context_properties] Output: Properties inferred for {entity_type} {entity_id}")
            logger.debug(f"[LLM Step: infer_context_properties] LLM Result: {json.dumps(result, indent=2)[:500]}...")
            
            return {
                "success": True,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "context_id": context_id,
                "properties": result,
                "entity_info": entity_info  # Include full entity info
            }
            
        except Exception as e:
            logger.error(f"Error inferring context properties: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "properties": {}
            }
    
    async def _enrich_reasoning_path(
        self,
        reasoning_path: List[Dict[str, Any]],
        context_id: str
    ) -> List[Dict[str, Any]]:
        """
        Enrich reasoning path with data from all stores:
        - Requirements for controls
        - Evidence types
        - Measurements
        - Contextual edges
        """
        enriched_path = []
        
        for hop in reasoning_path:
            enriched_hop = hop.copy()
            entities_found = hop.get("entities_found", [])
            entity_type = hop.get("entity_type", "")
            
            try:
                # For control entities, get requirements and evidence
                if entity_type == "controls" and entities_found:
                    controls_data = []
                    for control_id in entities_found[:5]:  # Limit to avoid too many queries
                        # Get requirements
                        requirements = await self.contextual_graph_service.requirement_service.get_requirements_for_control(
                            control_id
                        )
                        
                        # Get edges for this control
                        edges = self.contextual_graph_service.vector_storage.get_edges_for_context(
                            context_id=context_id,
                            source_entity_id=control_id,
                            top_k=10
                        )
                        
                        # Get analytics
                        analytics = await self.contextual_graph_service.measurement_service.get_risk_analytics(
                            control_id
                        )
                        
                        controls_data.append({
                            "control_id": control_id,
                            "requirements_count": len(requirements),
                            "edges_count": len(edges),
                            "has_analytics": analytics is not None,
                            "risk_level": analytics.risk_level if analytics else None
                        })
                    
                    enriched_hop["entities_enriched"] = controls_data
                
                # For requirement entities, get evidence
                elif entity_type == "requirements" and entities_found:
                    requirements_data = []
                    for req_id in entities_found[:5]:
                        # Get edges pointing to evidence
                        edges = self.contextual_graph_service.vector_storage.get_edges_for_context(
                            context_id=context_id,
                            source_entity_id=req_id,
                            edge_type="PROVED_BY",
                            top_k=10
                        )
                        requirements_data.append({
                            "requirement_id": req_id,
                            "evidence_edges_count": len(edges)
                        })
                    
                    enriched_hop["entities_enriched"] = requirements_data
                
            except Exception as e:
                logger.warning(f"Error enriching reasoning path hop: {str(e)}")
            
            enriched_path.append(enriched_hop)
        
        return enriched_path
    
    async def _generate_context_insights(
        self,
        query: str,
        context_id: str,
        reasoning_path: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate context-specific insights from reasoning path"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at generating context-specific insights from reasoning paths.

Analyze the reasoning path and generate insights about:
- Why this answer is specific to this context
- What factors in this context affect the answer
- How the answer might differ in other contexts

Return a JSON object with insights."""),
                ("human", """Generate insights for:

Query: {query}
Context ID: {context_id}
Reasoning Path: {reasoning_path}

Provide insights as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "context_id": context_id,
                "reasoning_path": json.dumps(reasoning_path, indent=2)
            }
            from app.utils import traced_llm_call
            
            logger.info(f"[LLM Step: _generate_context_insights] Starting LLM call for context insights generation with tracing")
            logger.debug(f"[LLM Step: _generate_context_insights] Input: query={query[:100]}, context_id={context_id}, reasoning_path_hops={len(reasoning_path)}")
            
            result = await traced_llm_call(
                llm=self.llm,
                prompt=prompt,
                inputs=llm_input,
                operation_name="generate_context_insights",
                parse_json=True,
                metadata={
                    "context_id": context_id,
                    "reasoning_path_hops": len(reasoning_path)
                }
            )
            
            # Log LLM call output
            logger.info(f"[LLM Step: _generate_context_insights] LLM call completed successfully")
            logger.info(f"[LLM Step: _generate_context_insights] Output: Context insights generated for context {context_id}")
            logger.debug(f"[LLM Step: _generate_context_insights] LLM Result: {json.dumps(result, indent=2)[:500] if isinstance(result, dict) else str(result)[:500]}...")
            
            return result if isinstance(result, dict) else {}
            
        except Exception as e:
            logger.warning(f"Error generating insights: {str(e)}")
            return {}
    
    async def _enrich_controls_with_all_data(
        self,
        controls: List[Dict[str, Any]],
        context_id: str,
        query: Optional[str] = None,
        include_requirements: bool = True,
        include_evidence: bool = True,
        include_measurements: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Enrich control results with all available data from data stores:
        - Requirements from requirement_service
        - Evidence types from evidence_service
        - Measurements and analytics from measurement_service
        - Contextual edges from vector_storage
        """
        enhanced = []
        
        for control_info in controls:
            enhanced_control = control_info.copy()
            control = control_info.get("control")
            control_id = None
            
            # Extract control_id
            if isinstance(control, dict):
                control_id = control.get("control_id")
            elif hasattr(control, "control_id"):
                control_id = control.control_id
            
            if not control_id:
                enhanced.append(enhanced_control)
                continue
            
            try:
                # 1. Get requirements for this control
                if include_requirements:
                    requirements = await self.contextual_graph_service.requirement_service.get_requirements_for_control(
                        control_id
                    )
                    enhanced_control["requirements"] = [
                        {
                            "requirement_id": req.requirement_id,
                            "requirement_text": req.requirement_text,
                            "requirement_type": req.requirement_type
                        }
                        for req in requirements
                    ]
                    enhanced_control["requirements_count"] = len(requirements)
                
                # 2. Get contextual edges for this control in this context
                edges = self.contextual_graph_service.vector_storage.get_edges_for_context(
                    context_id=context_id,
                    source_entity_id=control_id,
                    top_k=50
                )
                enhanced_control["contextual_edges"] = [
                    {
                        "edge_id": edge.edge_id,
                        "edge_type": edge.edge_type,
                        "target_entity_id": edge.target_entity_id,
                        "target_entity_type": edge.target_entity_type,
                        "relevance_score": edge.relevance_score,
                        "document": edge.document[:200]  # Truncate for size
                    }
                    for edge in edges
                ]
                enhanced_control["edges_count"] = len(edges)
                
                # 3. Extract evidence types from edges
                if include_evidence:
                    evidence_edges = [e for e in edges if e.target_entity_type == "evidence"]
                    evidence_ids = [e.target_entity_id for e in evidence_edges]
                    
                    # Get evidence details from storage
                    evidence_types = []
                    for evidence_id in evidence_ids[:10]:  # Limit to avoid too many queries
                        try:
                            evidence = await self.contextual_graph_service.evidence_service.get_evidence_type(
                                evidence_id
                            )
                            if evidence:
                                evidence_types.append({
                                    "evidence_id": evidence.evidence_id,
                                    "evidence_name": evidence.evidence_name,
                                    "evidence_category": evidence.evidence_category,
                                    "collection_method": evidence.collection_method
                                })
                        except Exception as e:
                            logger.debug(f"Could not fetch evidence {evidence_id}: {str(e)}")
                    
                    enhanced_control["evidence_types"] = evidence_types
                    enhanced_control["evidence_count"] = len(evidence_types)
                
                # 4. Get measurements and analytics
                if include_measurements:
                    measurements = await self.contextual_graph_service.measurement_service.get_measurements_for_control(
                        control_id=control_id,
                        context_id=context_id,
                        days=90  # Last 90 days
                    )
                    enhanced_control["measurements"] = [
                        {
                            "measurement_id": m.measurement_id,
                            "measured_value": m.measured_value,
                            "measurement_date": m.measurement_date.isoformat() if m.measurement_date else None,
                            "passed": m.passed,
                            "data_source": m.data_source,
                            "quality_score": m.quality_score
                        }
                        for m in measurements[:10]  # Limit recent measurements
                    ]
                    enhanced_control["measurements_count"] = len(measurements)
                    
                    # Get risk analytics
                    analytics = await self.contextual_graph_service.measurement_service.get_risk_analytics(
                        control_id
                    )
                    if analytics:
                        enhanced_control["risk_analytics"] = {
                            "avg_compliance_score": analytics.avg_compliance_score,
                            "trend": analytics.trend,
                            "current_risk_score": analytics.current_risk_score,
                            "risk_level": analytics.risk_level,
                            "failure_count_30d": analytics.failure_count_30d,
                            "failure_count_90d": analytics.failure_count_90d
                        }
                
                # 5. Add context-specific reasoning
                if query:
                    enhanced_control["context_reasoning"] = (
                        f"Prioritized in context {context_id} because it addresses: {query}"
                    )
                
            except Exception as e:
                logger.warning(f"Error enriching control {control_id}: {str(e)}")
                # Continue with basic control info
            
            enhanced.append(enhanced_control)
        
        return enhanced
    
    async def _enhance_controls_with_reasoning(
        self,
        controls: List[Dict[str, Any]],
        context_id: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Legacy method - now calls enriched version"""
        return await self._enrich_controls_with_all_data(
            controls=controls,
            context_id=context_id,
            query=query,
            include_requirements=True,
            include_evidence=True,
            include_measurements=True
        )
    
    async def _generate_mdl_enrichment_questions(
        self,
        tables: List[str],
        categories: List[str],
        query: str,
        frameworks: List[str] = None,
        entities: List[str] = None
    ) -> Dict[str, List[str]]:
        """
        Generate targeted questions to enrich MDL entities with domain, product, and control knowledge.
        
        Args:
            tables: List of table names identified
            categories: List of categories identified
            query: Original user query
            frameworks: List of frameworks mentioned (SOC2, HIPAA, etc.)
            entities: List of entities identified (access reviews, vulnerabilities, etc.)
            
        Returns:
            Dictionary with questions for each collection type:
            {
                "domain_knowledge": [...],
                "product_docs": [...],
                "controls": [...]
            }
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You generate specific questions to retrieve relevant knowledge about database tables.

Given tables, categories, and context, generate 2-3 targeted questions for each knowledge area:
1. Domain Knowledge: Questions about compliance frameworks, trust service criteria, and domain concepts
2. Product Documentation: Questions about product features, capabilities, and how tables are used
3. Controls: Questions about which controls the tables support or provide evidence for

Keep questions specific to the tables mentioned. Focus on compliance and product context."""),
                ("human", """Generate retrieval questions for:

Tables: {tables}
Categories: {categories}
Original Query: {query}
Frameworks: {frameworks}
Entities: {entities}

Return JSON with:
{{
  "domain_knowledge": ["question1", "question2", ...],
  "product_docs": ["question1", "question2", ...],
  "controls": ["question1", "question2", ...]
}}""")
            ])
            
            from app.utils import traced_llm_call
            
            result = await traced_llm_call(
                llm=self.llm,
                prompt=prompt,
                inputs={
                    "tables": ", ".join(tables[:5]) if tables else "None",
                    "categories": ", ".join(categories[:5]) if categories else "None",
                    "query": query,
                    "frameworks": ", ".join(frameworks) if frameworks else "Not specified",
                    "entities": ", ".join(entities[:5]) if entities else "Not specified"
                },
                operation_name="generate_mdl_enrichment_questions",
                parse_json=True,
                metadata={
                    "tables_count": len(tables),
                    "categories_count": len(categories),
                    "has_frameworks": bool(frameworks),
                    "has_entities": bool(entities)
                }
            )
            
            logger.info(f"[LLM Step: generate_mdl_enrichment_questions] Generated questions for {len(tables)} tables")
            return result
            
        except Exception as e:
            logger.warning(f"Error generating enrichment questions: {str(e)}")
            return {
                "domain_knowledge": [],
                "product_docs": [],
                "controls": []
            }
    
    async def _enrich_with_all_stores(
        self,
        reasoning_path: List[Dict[str, Any]],
        context_id: str,
        query: str,
        context_breakdown: Optional[Any] = None,
        enrich_all_hops: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Enrich reasoning path with data from all stores (connectors, domains, compliance, risks, schemas).
        Uses LLM-generated questions to target domain, product, and control knowledge for identified tables.
        
        Args:
            reasoning_path: Current reasoning path
            context_id: Context ID
            query: Original query
            context_breakdown: Optional context breakdown with frameworks and entities
            enrich_all_hops: If False, only enrich the last hop (default for performance)
            
        Returns:
            Enriched reasoning path
        """
        if not self.collection_factory:
            return reasoning_path
        
        # Extract tables and categories from reasoning path
        tables = []
        categories = []
        for hop in reasoning_path:
            entities = hop.get("entities_found", [])
            for entity in entities:
                entity_type = entity.get("entity_type", "")
                entity_id = entity.get("entity_id", "")
                if entity_type == "table":
                    table_name = entity_id.replace("table_", "")
                    if table_name not in tables:
                        tables.append(table_name)
                elif entity_type == "category":
                    category_name = entity_id.replace("category_", "")
                    if category_name not in categories:
                        categories.append(category_name)
        
        # Get context breakdown if available
        frameworks = context_breakdown.frameworks if context_breakdown else []
        entities_list = context_breakdown.identified_entities if context_breakdown else []
        
        # Generate targeted enrichment questions for MDL entities
        mdl_questions = {}
        if tables or categories:
            logger.info(f"[Step: enrich_with_all_stores] Generating enrichment questions for {len(tables)} tables, {len(categories)} categories")
            mdl_questions = await self._generate_mdl_enrichment_questions(
                tables=tables,
                categories=categories,
                query=query,
                frameworks=frameworks,
                entities=entities_list
            )
            logger.info(f"[Step: enrich_with_all_stores] Generated {len(mdl_questions.get('domain_knowledge', []))} domain questions, "
                       f"{len(mdl_questions.get('product_docs', []))} product questions, "
                       f"{len(mdl_questions.get('controls', []))} control questions")
        
        enriched_path = []
        
        for idx, hop in enumerate(reasoning_path):
            enriched_hop = hop.copy()
            
            # Skip enrichment for non-final hops if enrich_all_hops is False
            is_last_hop = (idx == len(reasoning_path) - 1)
            if not enrich_all_hops and not is_last_hop:
                logger.info(f"[Step: enrich_with_all_stores] Skipping enrichment for hop {idx+1}/{len(reasoning_path)} (only enriching last hop)")
                enriched_path.append(enriched_hop)
                continue
            
            logger.info(f"[Step: enrich_with_all_stores] Enriching hop {idx+1}/{len(reasoning_path)}")
            
            # Search with both original query and generated questions
            try:
                # Original broad search
                all_results = self.collection_factory.search_all(
                    query=query,
                    top_k=3,
                    filters={"context_id": context_id} if context_id else None,
                    include_schemas=True,
                    include_features=True
                )
                
                # Targeted searches with generated questions - PARALLELIZED for speed
                mdl_enrichment = {
                    "domain_knowledge": [],
                    "product_docs": [],
                    "controls": []
                }
                
                # Build all search tasks for parallel execution
                domain_tasks = [
                    self.collection_factory.search_domains(
                        query=q,
                        top_k=2,
                        filters={"context_id": context_id} if context_id else None
                    )
                    for q in mdl_questions.get("domain_knowledge", [])[:2]
                ]
                
                product_tasks = [
                    self.collection_factory.search_domains(
                        query=q,
                        top_k=2,
                        filters={"type": "product"}
                    )
                    for q in mdl_questions.get("product_docs", [])[:2]
                ]
                
                control_tasks = [
                    self.collection_factory.search_compliance(
                        query=q,
                        top_k=2,
                        filters={"context_id": context_id} if context_id else None
                    )
                    for q in mdl_questions.get("controls", [])[:2]
                ]
                
                # Execute all searches in parallel
                all_tasks = domain_tasks + product_tasks + control_tasks
                if all_tasks:
                    import asyncio
                    results = await asyncio.gather(*all_tasks, return_exceptions=True)
                    
                    # Process results
                    domain_count = len(domain_tasks)
                    product_count = len(product_tasks)
                    
                    # Extract domain results
                    for i in range(domain_count):
                        if not isinstance(results[i], Exception):
                            mdl_enrichment["domain_knowledge"].extend(results[i])
                        else:
                            logger.debug(f"Error in domain search: {str(results[i])}")
                    
                    # Extract product results
                    for i in range(domain_count, domain_count + product_count):
                        if not isinstance(results[i], Exception):
                            mdl_enrichment["product_docs"].extend(results[i])
                        else:
                            logger.debug(f"Error in product search: {str(results[i])}")
                    
                    # Extract control results
                    for i in range(domain_count + product_count, len(results)):
                        if not isinstance(results[i], Exception):
                            mdl_enrichment["controls"].extend(results[i])
                        else:
                            logger.debug(f"Error in control search: {str(results[i])}")
                
                # Add both store results and MDL enrichment to hop
                enriched_hop["store_results"] = {
                    "connectors": all_results.get("connectors", [])[:3],
                    "domains": all_results.get("domains", [])[:3],
                    "compliance": all_results.get("compliance", [])[:3],
                    "risks": all_results.get("risks", [])[:3],
                    "schemas": all_results.get("schemas", [])[:3],
                    "features": all_results.get("features", [])[:3]
                }
                
                enriched_hop["mdl_enrichment"] = {
                    "domain_knowledge": mdl_enrichment["domain_knowledge"][:3],
                    "product_docs": mdl_enrichment["product_docs"][:3],
                    "controls": mdl_enrichment["controls"][:3],
                    "questions_used": mdl_questions
                }
                
                logger.info(f"[Step: enrich_with_all_stores] Enriched hop with {len(mdl_enrichment['domain_knowledge'])} domain results, "
                           f"{len(mdl_enrichment['product_docs'])} product results, {len(mdl_enrichment['controls'])} control results")
                
            except Exception as e:
                logger.warning(f"Error enriching with stores: {str(e)}")
            
            enriched_path.append(enriched_hop)
        
        return enriched_path
    
    async def _enrich_controls_with_stores(
        self,
        controls: List[Dict[str, Any]],
        context_id: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Enrich controls with data from all stores.
        
        Args:
            controls: List of control dictionaries
            context_id: Context ID
            query: Optional query
            
        Returns:
            Enriched controls
        """
        if not self.collection_factory:
            return controls
        
        enriched = []
        
        for control in controls:
            enriched_control = control.copy()
            control_id = control.get("control_id") or control.get("control", {}).get("control_id")
            
            if not control_id:
                enriched.append(enriched_control)
                continue
            
            try:
                # Search for related entities across all stores
                search_query = query or f"control {control_id}"
                all_results = self.collection_factory.search_all(
                    query=search_query,
                    top_k=3,
                    filters={"context_id": context_id} if context_id else None,
                    include_schemas=True,
                    include_features=True
                )
                
                # Add store connections
                enriched_control["store_connections"] = {
                    "related_connectors": all_results.get("connectors", [])[:2],
                    "related_domains": all_results.get("domains", [])[:2],
                    "related_risks": all_results.get("risks", [])[:2],
                    "related_schemas": all_results.get("schemas", [])[:2],
                    "related_features": all_results.get("features", [])[:2]
                }
                
            except Exception as e:
                logger.warning(f"Error enriching control {control_id} with stores: {str(e)}")
            
            enriched.append(enriched_control)
        
        return enriched
    
    async def find_similar_features(
        self,
        query: str,
        context_id: Optional[str] = None,
        feature_type: Optional[str] = None,
        framework: Optional[str] = None,
        top_k: int = 10,
        use_context_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Find similar features from the feature knowledge base.
        Uses context breakdown to enhance the search query.
        
        Args:
            query: Query to find similar features
            context_id: Optional context ID for filtering
            feature_type: Optional feature type filter (control, risk, evidence, etc.)
            framework: Optional compliance framework filter (SOC2, HIPAA, etc.)
            top_k: Number of features to return
            use_context_breakdown: Whether to use context breakdown (default: True)
            
        Returns:
            Dictionary with similar features and metadata
        """
        try:
            # Use context breakdown to enhance query
            context_breakdown = None
            enhanced_query = query
            
            if use_context_breakdown:
                try:
                    context_breakdown = await self.context_breakdown_service.breakdown_question(
                        user_question=query
                    )
                    # Use breakdown to enhance search query
                    enhanced_query = context_breakdown.to_search_query() or query
                    logger.info(f"Enhanced feature search query: {enhanced_query[:100]}")
                except Exception as e:
                    logger.warning(f"Error in context breakdown for feature search: {str(e)}")
            
            # Build filters
            filters = {}
            if context_id:
                filters["context_id"] = context_id
            if feature_type:
                filters["feature_type"] = feature_type
            if framework:
                filters["compliance"] = framework
            
            # Search features using collection factory
            similar_features = []
            if self.collection_factory:
                features_collection = self.collection_factory.get_collection_by_store_name("features")
                if features_collection:
                    results = await features_collection.hybrid_search(
                        query=enhanced_query,
                        top_k=top_k,
                        where=filters if filters else None
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
                "query": query,
                "enhanced_query": enhanced_query,
                "similar_features": similar_features[:top_k],
                "count": len(similar_features)
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
            logger.error(f"Error finding similar features: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "similar_features": [],
                "count": 0
            }
    
    async def create_feature_edges(
        self,
        entity_id: str,
        entity_type: str,
        context_id: str,
        similar_features: List[Dict[str, Any]],
        save_to_vector: bool = True,
        save_to_postgres: bool = True
    ) -> Dict[str, Any]:
        """
        Create contextual edges connecting entities to similar features.
        
        Args:
            entity_id: Source entity ID (control, requirement, etc.)
            entity_type: Source entity type
            context_id: Context ID
            similar_features: List of similar features from find_similar_features
            save_to_vector: Whether to save edges to vector store (default: True)
            save_to_postgres: Whether to save edges to postgres (default: True)
            
        Returns:
            Dictionary with edge creation results
        """
        try:
            from app.services.contextual_graph_storage import ContextualEdge
            new_edges = []
            
            for feature in similar_features:
                feature_id = feature.get("feature_id")
                if not feature_id:
                    continue
                
                # Create edge document
                edge_document = (
                    f"Entity {entity_id} ({entity_type}) has similar feature {feature.get('feature_name', feature_id)} "
                    f"({feature.get('feature_type', 'feature')}) in context {context_id}. "
                    f"Feature description: {feature.get('description', '')[:200]}"
                )
                
                # Create edge
                edge = ContextualEdge(
                    edge_id=f"edge_{context_id}_{entity_id}_feature_{feature_id}_{datetime.utcnow().timestamp()}",
                    document=edge_document,
                    source_entity_id=entity_id,
                    source_entity_type=entity_type,
                    target_entity_id=feature_id,
                    target_entity_type="feature",
                    edge_type="HAS_SIMILAR_FEATURE",
                    context_id=context_id,
                    relevance_score=feature.get("relevance_score", 0.7),
                    created_at=datetime.utcnow().isoformat() + "Z"
                )
                
                new_edges.append(edge)
            
            if not new_edges:
                logger.info("No feature edges to create")
                return {
                    "success": True,
                    "edges_created": 0,
                    "edges_saved_to_vector": 0,
                    "edges_saved_to_postgres": 0
                }
            
            # Save to vector store
            edge_ids = []
            if save_to_vector:
                vector_storage = self.contextual_graph_service.vector_storage
                edge_ids = await vector_storage.save_contextual_edges(new_edges)
                logger.info(f"Saved {len(edge_ids)} feature edges to vector store")
            
            # Save to postgres if requested
            postgres_count = 0
            if save_to_postgres:
                try:
                    vector_storage = self.contextual_graph_service.vector_storage
                    postgres_count = await vector_storage.save_edges_to_postgres(new_edges)
                    logger.info(f"Saved {postgres_count} feature edges to postgres")
                except Exception as e:
                    logger.warning(f"Error saving feature edges to postgres: {str(e)}")
            
            return {
                "success": True,
                "edges_created": len(new_edges),
                "edges_saved_to_vector": len(edge_ids),
                "edges_saved_to_postgres": postgres_count,
                "edge_ids": edge_ids
            }
            
        except Exception as e:
            logger.error(f"Error creating feature edges: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "edges_created": 0,
                "edges_saved_to_vector": 0,
                "edges_saved_to_postgres": 0
            }
    
    async def store_new_edges_from_processing(
        self,
        user_question: str,
        context_id: str,
        entities_found: List[Dict[str, Any]],
        save_to_postgres: bool = True
    ) -> Dict[str, Any]:
        """
        Store new edges discovered during processing back to vector store and postgres.
        
        This method creates edges from the source question and entities found during processing,
        then stores them for future use.
        
        Args:
            user_question: Original user question
            context_id: Context ID
            entities_found: List of entities found during processing
            save_to_postgres: Whether to save to postgres (default: True)
            
        Returns:
            Dictionary with storage results
        """
        try:
            from app.services.contextual_graph_storage import ContextualEdge
            new_edges = []
            
            # Create edges between entities found during processing
            for i, entity1 in enumerate(entities_found):
                entity1_id = entity1.get("entity_id") or entity1.get("id")
                entity1_type = entity1.get("entity_type") or entity1.get("type", "entity")
                
                if not entity1_id:
                    continue
                
                # Create edges to other entities
                for j, entity2 in enumerate(entities_found[i+1:], start=i+1):
                    entity2_id = entity2.get("entity_id") or entity2.get("id")
                    entity2_type = entity2.get("entity_type") or entity2.get("type", "entity")
                    
                    if not entity2_id or entity1_id == entity2_id:
                        continue
                    
                    # Create edge document
                    edge_document = (
                        f"Entities {entity1_id} ({entity1_type}) and {entity2_id} ({entity2_type}) "
                        f"are related in context of: {user_question[:200]}"
                    )
                    
                    # Create edge
                    edge = ContextualEdge(
                        edge_id=f"edge_{context_id}_{entity1_id}_{entity2_id}_{datetime.utcnow().timestamp()}",
                        document=edge_document,
                        source_entity_id=entity1_id,
                        source_entity_type=entity1_type,
                        target_entity_id=entity2_id,
                        target_entity_type=entity2_type,
                        edge_type="RELATED_TO_IN_CONTEXT",
                        context_id=context_id,
                        relevance_score=0.7,  # Default relevance
                        created_at=datetime.utcnow().isoformat() + "Z"
                    )
                    
                    new_edges.append(edge)
            
            if not new_edges:
                logger.info("No new edges to store from processing")
                return {
                    "success": True,
                    "edges_created": 0,
                    "edges_saved_to_vector": 0,
                    "edges_saved_to_postgres": 0
                }
            
            # Save to vector store
            vector_storage = self.contextual_graph_service.vector_storage
            edge_ids = await vector_storage.save_contextual_edges(new_edges)
            
            logger.info(f"Saved {len(edge_ids)} new edges to vector store")
            
            # Save to postgres if requested
            postgres_count = 0
            if save_to_postgres:
                try:
                    postgres_count = await vector_storage.save_edges_to_postgres(new_edges)
                    logger.info(f"Saved {postgres_count} new edges to postgres")
                except Exception as e:
                    logger.warning(f"Error saving edges to postgres: {str(e)}")
            
            return {
                "success": True,
                "edges_created": len(new_edges),
                "edges_saved_to_vector": len(edge_ids),
                "edges_saved_to_postgres": postgres_count,
                "edge_ids": edge_ids
            }
            
        except Exception as e:
            logger.error(f"Error storing new edges: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "edges_created": 0,
                "edges_saved_to_vector": 0,
                "edges_saved_to_postgres": 0
            }

