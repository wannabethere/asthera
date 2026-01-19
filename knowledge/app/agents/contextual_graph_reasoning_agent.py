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
    
    async def reason_with_context(
        self,
        query: str,
        context_id: str,
        max_hops: int = 3,
        reasoning_plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform context-aware reasoning for a query
        
        Args:
            query: User query or question
            context_id: Context ID to reason within
            max_hops: Maximum number of reasoning hops
            reasoning_plan: Optional pre-computed reasoning plan
            
        Returns:
            Dictionary with reasoning path, final answer, and context-specific insights
        """
        try:
            from app.services.models import MultiHopQueryRequest
            
            # Perform multi-hop query
            response = await self.contextual_graph_service.multi_hop_query(
                MultiHopQueryRequest(
                    query=query,
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
            
            # Enhance reasoning path with data from all stores
            enriched_path = await self._enrich_reasoning_path(
                reasoning_path=reasoning_path,
                context_id=context_id
            )
            
            # If collection factory available, enrich with multi-store data
            if self.collection_factory:
                enriched_path = await self._enrich_with_all_stores(
                    reasoning_path=enriched_path,
                    context_id=context_id,
                    query=query
                )
            
            # Enhance with context-specific insights
            insights = await self._generate_context_insights(
                query=query,
                context_id=context_id,
                reasoning_path=enriched_path
            )
            
            return {
                "success": True,
                "query": query,
                "context_id": context_id,
                "reasoning_path": enriched_path,
                "final_answer": final_answer,
                "context_insights": insights,
                "reasoning_plan_used": reasoning_plan is not None
            }
            
        except Exception as e:
            logger.error(f"Error in context-aware reasoning: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "reasoning_path": [],
                "final_answer": ""
            }
    
    async def suggest_relevant_tables(
        self,
        query: str,
        context_id: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Suggest relevant database tables based on query and context.
        
        Uses contextual graph to understand what tables would be most relevant
        for answering the query within the given context.
        
        Args:
            query: User query
            context_id: Context ID to reason within
            project_id: Optional project ID for project-specific suggestions
            top_k: Number of table suggestions to return
            
        Returns:
            Dictionary with suggested_tables list and reasoning
        """
        try:
            # Get context information
            context_definition = await self.contextual_graph_service.vector_storage.get_context_definition(context_id)
            
            # Search contextual graph for entities/tables related to this context
            # Look for entities in the contextual graph that might represent tables
            if self.collection_factory:
                # Search entities collection for table-like entities
                entities_collection = self.collection_factory.get_collection_by_store_name("entities")
                if entities_collection:
                    # Search for entities related to the context
                    entity_results = await entities_collection.hybrid_search(
                        query=f"{query} {context_definition.document[:500] if context_definition else ''}",
                        top_k=top_k * 2,
                        where={"context_id": context_id} if context_id else {}
                    )
                    
                    # Also search table_definitions if available
                    table_def_collection = self.collection_factory.get_collection_by_store_name("table_definitions")
                    table_suggestions = []
                    if table_def_collection:
                        table_results = await table_def_collection.hybrid_search(
                            query=query,
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
            
            # Use LLM to analyze query and context to suggest tables
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

{existing_suggestions}

Provide table suggestions as JSON.""")
            ])
            
            existing_suggestions_text = ""
            if table_suggestions:
                existing_suggestions_text = "\n\nExisting table suggestions from search:\n"
                for suggestion in table_suggestions[:5]:
                    existing_suggestions_text += f"- {suggestion['table_name']}: {suggestion['reasoning']}\n"
            
            chain = prompt | self.llm | self.json_parser
            result = await chain.ainvoke({
                "query": query,
                "project_id": project_id or "unknown",
                "context_doc": context_doc[:2000],
                "frameworks": ", ".join(context_frameworks) if context_frameworks else "None",
                "existing_suggestions": existing_suggestions_text
            })
            
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
            
            return {
                "success": True,
                "suggested_tables": sorted_suggestions,
                "overall_strategy": result.get("overall_strategy", ""),
                "table_relationships": result.get("table_relationships", []),
                "context_id": context_id
            }
            
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
        include_measurements: bool = True
    ) -> Dict[str, Any]:
        """
        Get priority controls for a context with context-aware prioritization
        Enriched with requirements, evidence, and measurements from all data stores
        
        Args:
            context_id: Context ID
            query: Optional query to filter controls
            filters: Optional metadata filters
            top_k: Number of controls to return
            include_requirements: Whether to include requirements for each control
            include_evidence: Whether to include evidence types
            include_measurements: Whether to include measurements and analytics
            
        Returns:
            Dictionary with priority controls enriched with all available data
        """
        try:
            from app.services.models import PriorityControlsRequest
            
            response = await self.contextual_graph_service.get_priority_controls(
                PriorityControlsRequest(
                    context_id=context_id,
                    query=query,
                    filters=filters,
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
            
            # Enrich with all available data from data stores
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
                enhanced_controls = await self._enrich_controls_with_stores(
                    controls=enhanced_controls,
                    context_id=context_id,
                    query=query
                )
            
            return {
                "success": True,
                "context_id": context_id,
                "controls": enhanced_controls,
                "count": len(enhanced_controls)
            }
            
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
            
            result = await chain.ainvoke({
                "query": query,
                "context_results": json.dumps(context_summaries, indent=2)
            })
            
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
            
            result = await chain.ainvoke({
                "entity_id": entity_id,
                "entity_type": entity_type,
                "context_id": context_id,
                "entity_info": json.dumps(entity_info, indent=2, default=str)
            })
            
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
            
            result = await chain.ainvoke({
                "query": query,
                "context_id": context_id,
                "reasoning_path": json.dumps(reasoning_path, indent=2)
            })
            
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
    
    async def _enrich_with_all_stores(
        self,
        reasoning_path: List[Dict[str, Any]],
        context_id: str,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Enrich reasoning path with data from all stores (connectors, domains, compliance, risks, schemas).
        
        Args:
            reasoning_path: Current reasoning path
            context_id: Context ID
            query: Original query
            
        Returns:
            Enriched reasoning path
        """
        if not self.collection_factory:
            return reasoning_path
        
        enriched_path = []
        
        for hop in reasoning_path:
            enriched_hop = hop.copy()
            entity_type = hop.get("entity_type", "")
            entities_found = hop.get("entities_found", [])
            
            # Search all stores for related entities
            try:
                all_results = self.collection_factory.search_all(
                    query=query,
                    top_k=5,
                    filters={"context_id": context_id} if context_id else None,
                    include_schemas=True
                )
                
                # Add store results to hop
                enriched_hop["store_results"] = {
                    "connectors": all_results.get("connectors", [])[:3],
                    "domains": all_results.get("domains", [])[:3],
                    "compliance": all_results.get("compliance", [])[:3],
                    "risks": all_results.get("risks", [])[:3],
                    "schemas": all_results.get("schemas", [])[:3]
                }
                
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
                    include_schemas=True
                )
                
                # Add store connections
                enriched_control["store_connections"] = {
                    "related_connectors": all_results.get("connectors", [])[:2],
                    "related_domains": all_results.get("domains", [])[:2],
                    "related_risks": all_results.get("risks", [])[:2],
                    "related_schemas": all_results.get("schemas", [])[:2]
                }
                
            except Exception as e:
                logger.warning(f"Error enriching control {control_id} with stores: {str(e)}")
            
            enriched.append(enriched_control)
        
        return enriched

