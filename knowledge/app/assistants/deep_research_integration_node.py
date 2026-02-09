"""
Deep Research Integration Node for Data Assistance

Supports two modes:
1. **Config-driven (URL) mode**: Uses the common DeepResearchUtility with a configuration
   (context_name, urls e.g. docs.snyk.io, topic). Fetches data from URLs, asks LLM, merges
   and returns deep_research_review. No contextual edge retrieval in this path.
2. **Legacy mode**: Uses contextual graph storage, curated tables, and LLM to produce
   recommendations (when no deep_research_config is provided).
"""
import logging
import json
from typing import Dict, Any, Optional, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.assistants.state import ContextualAssistantState
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.utils.deep_research_utility import (
    DeepResearchUtility,
    DeepResearchConfig,
    default_snyk_config,
    DEEP_RESEARCH_GOAL_COMPLIANCE,
)

logger = logging.getLogger(__name__)


class DeepResearchIntegrationNode:
    """
    Node that runs deep research. When deep_research_config is provided, uses the
    common DeepResearchUtility (fetch URLs -> LLM -> merge). Otherwise uses legacy
    behavior (contextual edges + tables/schemas).
    """

    def __init__(
        self,
        contextual_graph_storage: Optional[ContextualGraphStorage] = None,
        deep_research_config: Optional[DeepResearchConfig] = None,
        deep_research_utility: Optional[DeepResearchUtility] = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
    ):
        """
        Args:
            contextual_graph_storage: Optional; used only in legacy mode for contextual edges.
            deep_research_config: Optional. When set, URL-based deep research is used (fetch URLs from config, LLM, merge).
            deep_research_utility: Optional. When None and config is set, a default utility is created.
            llm: Optional LLM (used for both utility and legacy prompt).
            model_name: Model name if llm not provided.
        """
        self.contextual_graph_storage = contextual_graph_storage
        self.deep_research_config = deep_research_config
        self.deep_research_utility = deep_research_utility or (
            DeepResearchUtility(llm=llm, model_name=model_name) if deep_research_config else None
        )
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.json_parser = JsonOutputParser()

    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """
        Run deep research. If config is set: fetch URLs from config, LLM, merge.
        Else: legacy path with contextual edges and curated tables.
        """
        query = state.get("query", "")
        # Config-driven URL mode: fetch URLs, LLM, merge (no contextual edges)
        if self.deep_research_config and self.deep_research_utility:
            config = self.deep_research_config
            next_node = getattr(config, "next_node_after", None) or "metric_generation"
            is_compliance = getattr(config, "goal", None) == DEEP_RESEARCH_GOAL_COMPLIANCE
            try:
                result = await self.deep_research_utility.run(config, query)
                state["deep_research_review"] = {
                    "review_content": result.get("merged_content", "")[:5000],
                    "recommended_features": result.get("recommended_features", []),
                    "evidence_gathering_plan": result.get("evidence_gathering_plan", []),
                    "data_gaps": result.get("data_gaps", []),
                    "summary": result.get("summary", ""),
                    "contextual_edges_used": 0,
                    "fetched_sources": result.get("fetched_sources", []),
                    "goal": getattr(config, "goal", "data_retrieval"),
                }
                state["deep_research_edges"] = []
                if not is_compliance:
                    self._merge_recommended_features_into_data_knowledge(state, result.get("recommended_features", []))
                state["current_node"] = "deep_research_integration"
                state["next_node"] = next_node
                logger.info(
                    "DeepResearchIntegrationNode: URL-based deep research completed (goal=%s). "
                    "Recommended %s items, fetched %s URL(s), next_node=%s",
                    getattr(config, "goal", "data_retrieval"),
                    len(result.get("recommended_features", [])),
                    len(result.get("fetched_sources", [])),
                    next_node,
                )
                return state
            except Exception as e:
                logger.warning(f"DeepResearchIntegrationNode: URL deep research failed: {e}, falling back to legacy")
                state["deep_research_review"] = {
                    "review_content": "",
                    "recommended_features": [],
                    "evidence_gathering_plan": [],
                    "data_gaps": [],
                    "summary": f"URL deep research failed: {e}",
                    "contextual_edges_used": 0,
                    "fetched_sources": [],
                    "goal": getattr(config, "goal", "data_retrieval"),
                }
                state["deep_research_edges"] = []
                state["next_node"] = next_node
                return state

        # Legacy path: curated tables + contextual edges + LLM
        curated_tables = (
            state.get("mdl_curated_tables", []) or
            state.get("suggested_tables", [])
        )
        data_knowledge = state.get("data_knowledge", {})
        
        # If no curated tables from MDL/breakdown, use schemas from data_knowledge
        if not curated_tables:
            schemas = data_knowledge.get("schemas", [])
            if schemas:
                # Convert schemas to curated_tables format
                curated_tables = [
                    {
                        "table_name": s.get("table_name", s.get("name", "")),
                        "description": s.get("description", ""),
                        "relevance_score": 1.0  # Default relevance since they were retrieved
                    }
                    for s in schemas
                ]
                logger.info(f"DeepResearchIntegrationNode: Using {len(curated_tables)} schemas from data_knowledge as curated tables")
        
        user_context = state.get("user_context", {})
        actor_type = state.get("actor_type", "consultant")
        
        # Get context breakdown from ContextRetrievalNode (should be available after context breakdown)
        context_breakdown = state.get("context_breakdown", {})
        generic_breakdown = state.get("generic_breakdown", {}) or context_breakdown
        mdl_contextual_plan = state.get("mdl_contextual_plan", {})
        mdl_edges_discovered = state.get("mdl_edges_discovered", [])
        context_ids = state.get("context_ids", [])
        
        # Log context breakdown availability
        if context_breakdown or generic_breakdown:
            breakdown_to_use = context_breakdown if context_breakdown else generic_breakdown
            logger.info(f"DeepResearchIntegrationNode: Context breakdown available - compliance={breakdown_to_use.get('compliance_context')}, action={breakdown_to_use.get('action_context')}, product={breakdown_to_use.get('product_context')}")
        else:
            logger.warning("DeepResearchIntegrationNode: No context breakdown found in state - deep research may not have full context")
        
        # Extract evidence gathering plan from breakdown (use context_breakdown if available, fallback to generic_breakdown)
        breakdown_to_use = context_breakdown if context_breakdown else generic_breakdown
        evidence_gathering_required = breakdown_to_use.get("evidence_gathering_required", False)
        data_retrieval_plan = breakdown_to_use.get("data_retrieval_plan", [])
        metrics_kpis_needed = breakdown_to_use.get("metrics_kpis_needed", [])
        evidence_types_needed = breakdown_to_use.get("evidence_types_needed", [])
        
        if not query:
            logger.warning("DeepResearchIntegrationNode: No query provided, skipping deep research")
            return state
        
        try:
            logger.info(f"DeepResearchIntegrationNode: Starting deep research for query: {query[:100]}")
            logger.info(f"DeepResearchIntegrationNode: Found {len(curated_tables)} curated tables")
            logger.info(f"DeepResearchIntegrationNode: Evidence gathering required: {evidence_gathering_required}")
            if evidence_gathering_required:
                logger.info(f"DeepResearchIntegrationNode: Data retrieval plan has {len(data_retrieval_plan)} items, "
                           f"{len(metrics_kpis_needed)} metrics/KPIs needed")
            
            # Retrieve contextual edges for richer context
            contextual_edges = []
            if self.contextual_graph_storage:
                try:
                    logger.info("DeepResearchIntegrationNode: Retrieving contextual edges for richer context...")
                    
                    # Get edges from MDL reasoning if available
                    if mdl_edges_discovered:
                        contextual_edges.extend(mdl_edges_discovered)
                        logger.info(f"DeepResearchIntegrationNode: Using {len(mdl_edges_discovered)} edges from MDL reasoning")
                    
                    # Search for additional edges related to the query and curated tables
                    # Build search query from curated table names
                    table_names = [t.get("table_name", "") for t in curated_tables if t.get("table_name")]
                    if table_names:
                        # Search for edges related to these tables
                        edge_query = f"{query} {' '.join(table_names[:5])}"  # Limit to first 5 tables
                        
                        # Search edges with context_ids if available
                        for context_id in context_ids[:1]:  # Use first context
                            edges = await self.contextual_graph_storage.search_edges(
                                query=edge_query,
                                context_id=context_id,
                                top_k=20
                            )
                            # Deduplicate by edge_id
                            existing_edge_ids = {e.edge_id for e in contextual_edges}
                            for edge in edges:
                                if edge.edge_id not in existing_edge_ids:
                                    contextual_edges.append(edge)
                        
                        # Also search without context_id filter for broader coverage
                        edges = await self.contextual_graph_storage.search_edges(
                            query=edge_query,
                            top_k=15
                        )
                        existing_edge_ids = {e.edge_id for e in contextual_edges}
                        for edge in edges:
                            if edge.edge_id not in existing_edge_ids:
                                contextual_edges.append(edge)
                    
                    logger.info(f"DeepResearchIntegrationNode: Retrieved {len(contextual_edges)} contextual edges")
                except Exception as e:
                    logger.warning(f"DeepResearchIntegrationNode: Error retrieving contextual edges: {str(e)}")
            
            # Extract schemas and available data
            schemas = data_knowledge.get("schemas", [])
            existing_metrics = data_knowledge.get("metrics", [])
            controls = data_knowledge.get("controls", [])
            framework = data_knowledge.get("framework")
            
            # Format curated tables
            tables_text = self._format_curated_tables(curated_tables)
            
            # Format available schemas
            schemas_text = self._format_schemas(schemas)
            
            # Format existing metrics
            metrics_text = self._format_metrics(existing_metrics)
            
            # Format controls
            controls_text = self._format_controls(controls, framework)
            
            # Format contextual edges for richer context
            edges_text = self._format_contextual_edges(contextual_edges, curated_tables)
            
            # Format breakdown plan for prompt
            breakdown_plan_text = self._format_breakdown_plan(
                evidence_gathering_required,
                data_retrieval_plan,
                metrics_kpis_needed,
                evidence_types_needed
            )
            
            # Extract context breakdown information for deep research prompt
            compliance_context = (context_breakdown.get("compliance_context") or 
                                generic_breakdown.get("compliance_context") or "")
            action_context = (context_breakdown.get("action_context") or 
                            generic_breakdown.get("action_context") or "")
            product_context = (context_breakdown.get("product_context") or 
                             generic_breakdown.get("product_context") or "")
            user_intent = (context_breakdown.get("user_intent") or 
                         generic_breakdown.get("user_intent") or "")
            frameworks = (context_breakdown.get("frameworks", []) or 
                         generic_breakdown.get("frameworks", []) or [])
            
            # Build deep research prompt with context breakdown information embedded
            system_prompt = f"""You are a deep research expert for compliance and risk analysis.

CONTEXT BREAKDOWN (from generic breakdown):
- Compliance Context: {compliance_context or 'Not specified'}
- Action Context: {action_context or 'Not specified'}
- Product Context: {product_context or 'Not specified'}
- User Intent: {user_intent or 'Not specified'}
- Frameworks: {', '.join(frameworks) if frameworks else 'Not specified'}
- Actor Type: {actor_type or 'Not specified'}

Your task is to:

Your task is to:
1. Review curated tables and available data for the user's question
2. Recommend features, KPIs, metrics, or aggregations as natural language questions
3. Identify what evidence needs to be gathered to answer the question
4. Provide actionable recommendations

CRITICAL: You MUST align your recommendations with the breakdown plan provided. The breakdown plan specifies:
- What data types should be retrieved (data_retrieval_plan)
- What metrics/KPIs are needed (metrics_kpis_needed)
- What evidence types are required (evidence_types_needed)

Your recommendations MUST match what was planned in the breakdown to ensure accuracy. Do NOT recommend features that don't align with the planned data retrieval.

IMPORTANT: Use the contextual edges provided to build a richer understanding of:
- How tables relate to each other
- What relationships exist between entities
- How controls connect to tables and data
- What contextual information is available for evidence gathering

For compliance questions (e.g., "why my assets are having a soc 2 control for user access high"), you should:
- Use the breakdown plan to guide your recommendations
- Use contextual edges to understand table relationships and build richer context
- Match recommended features to the metrics_kpis_needed from the breakdown
- Ensure evidence_gathering_plan aligns with data_retrieval_plan from the breakdown
- Leverage edge relationships to identify related tables and metrics
- Identify gaps between what was planned and what is actually available
- Provide natural language questions that match the planned metrics/KPIs

Your task is to:
1. Review curated tables and available data for the user's question
2. Recommend features, KPIs, metrics, or aggregations as natural language questions
3. Identify what evidence needs to be gathered to answer the question
4. Provide actionable recommendations

For compliance questions (e.g., "why my assets are having a soc 2 control for user access high"), you should:
- Identify all relevant tables that contain evidence
- Recommend specific metrics/KPIs that would help answer the question
- Suggest aggregations or calculations needed
- Provide natural language questions that can be used to retrieve or calculate these metrics
- Identify gaps in available data that might need to be addressed

Return JSON with:
- recommended_features: List of feature objects, each with:
  - feature_name: Name of the feature/KPI/metric
  - natural_language_question: Natural language question describing what needs to be calculated/retrieved
  - feature_type: Type (e.g., 'kpi', 'metric', 'aggregation', 'calculation')
  - related_tables: List of table names this feature relates to
  - purpose: What this feature helps answer or measure
  - evidence_type: Type of evidence this provides (e.g., 'access_control', 'user_activity', 'compliance_metric')
- evidence_gathering_plan: List of evidence objects, each with:
  - evidence_type: Type of evidence (e.g., 'table_data', 'metric', 'aggregation')
  - source_tables: List of tables that contain this evidence
  - description: What evidence this provides
  - priority: Priority level (high/medium/low)
- data_gaps: List of gaps in available data that might need to be addressed
- summary: Overall summary of what evidence is available and what needs to be gathered
"""
            
            prompt = f"""
User Question: {query}

CONTEXT BREAKDOWN INFORMATION:
- Compliance Context: {compliance_context or 'Not specified'}
- Action Context: {action_context or 'Not specified'}
- Product Context: {product_context or 'Not specified'}
- User Intent: {user_intent or 'Not specified'}
- Frameworks: {', '.join(frameworks) if frameworks else 'Not specified'}
- Actor Type: {actor_type or 'Not specified'}

{breakdown_plan_text}

Curated Tables ({len(curated_tables)}):
{tables_text}

Available Database Schemas ({len(schemas)}):
{schemas_text}

Existing Metrics ({len(existing_metrics)}):
{metrics_text}

Compliance Controls ({len(controls)}):
{controls_text}

Contextual Edges ({len(contextual_edges)}):
{edges_text}

Framework: {framework or compliance_context or 'Not specified'}

CRITICAL INSTRUCTIONS:
1. **ALIGN WITH BREAKDOWN PLAN**: Your recommendations MUST align with the breakdown plan above
2. **MATCH DATA RETRIEVAL PLAN**: Ensure your evidence_gathering_plan matches the data_retrieval_plan from the breakdown
3. **USE PLANNED METRICS/KPIs**: Base your recommended_features on the metrics_kpis_needed from the breakdown
4. **VERIFY AVAILABILITY**: Check if the planned data is actually available in the curated tables and schemas
5. **IDENTIFY GAPS**: Identify any gaps between what was planned and what is available

Based on the breakdown plan, curated tables, contextual edges, and available data:
1. Use contextual edges to understand relationships and build richer context
2. Recommend features/KPIs/metrics/aggregations that match the breakdown plan
3. Leverage edge relationships to identify related tables and metrics for evidence gathering
4. Create evidence gathering plan that aligns with data_retrieval_plan
5. Use edge information to identify connections between tables, controls, and metrics
6. Identify any data gaps between the plan and what's available

Focus on providing actionable recommendations that align with the breakdown plan, leverage contextual edges for richer context, and help answer the user's question.
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # Call LLM
            logger.info("DeepResearchIntegrationNode: Calling LLM for deep research review...")
            response = await self.llm.ainvoke(messages)
            
            review_content = response.content if hasattr(response, 'content') else str(response)
            
            # Try to parse as JSON first
            try:
                # Extract JSON from response if it's wrapped in markdown code blocks
                if "```json" in review_content:
                    json_start = review_content.find("```json") + 7
                    json_end = review_content.find("```", json_start)
                    review_content = review_content[json_start:json_end].strip()
                elif "```" in review_content:
                    json_start = review_content.find("```") + 3
                    json_end = review_content.find("```", json_start)
                    review_content = review_content[json_start:json_end].strip()
                
                result = json.loads(review_content)
            except json.JSONDecodeError:
                # If not JSON, parse the text response
                logger.warning("DeepResearchIntegrationNode: LLM response not in JSON format, parsing text...")
                result = self._parse_text_response(review_content)
            
            # Store deep research results in state
            state["deep_research_review"] = {
                "review_content": review_content,
                "recommended_features": result.get("recommended_features", []),
                "evidence_gathering_plan": result.get("evidence_gathering_plan", []),
                "data_gaps": result.get("data_gaps", []),
                "summary": result.get("summary", ""),
                "contextual_edges_used": len(contextual_edges)  # Track how many edges were used
            }
            
            # Store contextual edges in state for downstream nodes
            state["deep_research_edges"] = contextual_edges
            
            # Merge recommended features into data_knowledge for downstream nodes
            self._merge_recommended_features_into_data_knowledge(state, result.get("recommended_features", []))
            
            state["current_node"] = "deep_research_integration"
            state["next_node"] = "metric_generation"
            
            logger.info(f"DeepResearchIntegrationNode: Deep research completed. "
                       f"Recommended {len(result.get('recommended_features', []))} features, "
                       f"{len(result.get('evidence_gathering_plan', []))} evidence items, "
                       f"used {len(contextual_edges)} contextual edges for richer context")
            
        except Exception as e:
            logger.error(f"DeepResearchIntegrationNode: Error in deep research: {str(e)}", exc_info=True)
            # Continue anyway - don't fail the entire workflow
            state["deep_research_review"] = {
                "review_content": f"Deep research error: {str(e)}",
                "recommended_features": [],
                "evidence_gathering_plan": [],
                "data_gaps": [],
                "summary": "",
                "contextual_edges_used": 0
            }
            state["deep_research_edges"] = []
            state["next_node"] = "metric_generation"
        
        return state
    
    def _format_curated_tables(self, curated_tables: List[Dict[str, Any]]) -> str:
        """Format curated tables for prompt"""
        if not curated_tables:
            return "No curated tables available"
        
        formatted = []
        for i, table in enumerate(curated_tables, 1):
            table_name = table.get("table_name", "Unknown")
            description = table.get("description", "")
            relevance_score = table.get("relevance_score", 0.0)
            
            formatted.append(f"{i}. **{table_name}** (relevance: {relevance_score:.2f})")
            if description:
                formatted.append(f"   {description[:200]}")
        
        return "\n".join(formatted)
    
    def _format_schemas(self, schemas: List[Dict[str, Any]]) -> str:
        """Format schemas for prompt"""
        if not schemas:
            return "No database schemas available"
        
        formatted = []
        for schema in schemas[:10]:  # Limit to 10 schemas
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            formatted.append(f"**{table_name}**\n{table_ddl[:500]}...")
        
        return "\n\n".join(formatted)
    
    def _format_metrics(self, metrics: List[Dict[str, Any]]) -> str:
        """Format metrics for prompt"""
        if not metrics:
            return "No existing metrics available"
        
        formatted = []
        for metric in metrics[:10]:  # Limit to 10 metrics
            name = metric.get("metric_name") or metric.get("name", "Unknown")
            description = metric.get("description", "")
            formatted.append(f"- {name}: {description[:150]}")
        
        return "\n".join(formatted)
    
    def _format_breakdown_plan(
        self,
        evidence_gathering_required: bool,
        data_retrieval_plan: List[Dict[str, Any]],
        metrics_kpis_needed: List[Dict[str, Any]],
        evidence_types_needed: List[str]
    ) -> str:
        """Format breakdown plan for prompt"""
        if not evidence_gathering_required:
            return "**Breakdown Plan**: No evidence gathering required for this query."
        
        parts = ["**BREAKDOWN PLAN (MUST FOLLOW THIS PLAN):**"]
        parts.append(f"\nEvidence Gathering Required: Yes")
        parts.append(f"Evidence Types Needed: {', '.join(evidence_types_needed) if evidence_types_needed else 'Not specified'}")
        
        if data_retrieval_plan:
            parts.append(f"\n**Data Retrieval Plan ({len(data_retrieval_plan)} items):**")
            for i, plan_item in enumerate(data_retrieval_plan, 1):
                # Handle both dict and string formats
                if isinstance(plan_item, str):
                    parts.append(f"{i}. {plan_item}")
                elif isinstance(plan_item, dict):
                    data_type = plan_item.get("data_type", "Unknown")
                    purpose = plan_item.get("purpose", "")
                    priority = plan_item.get("priority", "medium")
                    expected_tables = plan_item.get("expected_tables", [])
                    
                    parts.append(f"{i}. **{data_type}** (Priority: {priority})")
                    if purpose:
                        parts.append(f"   Purpose: {purpose}")
                    if expected_tables:
                        parts.append(f"   Expected Tables: {', '.join(expected_tables)}")
                else:
                    parts.append(f"{i}. {str(plan_item)}")
        
        if metrics_kpis_needed:
            parts.append(f"\n**Metrics/KPIs Needed ({len(metrics_kpis_needed)} items):**")
            for i, metric_plan in enumerate(metrics_kpis_needed, 1):
                # Handle both dict and string formats
                if isinstance(metric_plan, str):
                    parts.append(f"{i}. {metric_plan}")
                elif isinstance(metric_plan, dict):
                    metric_type = metric_plan.get("metric_type", "Unknown")
                    purpose = metric_plan.get("purpose", "")
                    related_tables = metric_plan.get("related_tables", [])
                    question = metric_plan.get("natural_language_question", "")
                    
                    parts.append(f"{i}. **{metric_type}**")
                    if purpose:
                        parts.append(f"   Purpose: {purpose}")
                    if question:
                        parts.append(f"   Question: {question}")
                    if related_tables:
                        parts.append(f"   Related Tables: {', '.join(related_tables)}")
                else:
                    parts.append(f"{i}. {str(metric_plan)}")
        
        parts.append("\n**CRITICAL**: Your recommendations MUST align with this plan. Match your recommended_features to metrics_kpis_needed, and your evidence_gathering_plan to data_retrieval_plan.")
        
        return "\n".join(parts)
    
    def _format_controls(self, controls: List[Dict[str, Any]], framework: Optional[str]) -> str:
        """Format controls for prompt"""
        if not controls:
            return "No compliance controls specified"
        
        formatted = [f"**Compliance Framework: {framework or 'Unknown'}**\n"]
        for control in controls[:10]:  # Limit to 10 controls
            if isinstance(control, dict):
                control_obj = control.get("control") or control
                control_id = control_obj.get("control_id") or control.get("control_id", "Unknown")
                control_name = control_obj.get("control_name") or control.get("control_name", "")
                description = control_obj.get("control_description") or control.get("control_description", "")
                formatted.append(f"- **{control_id}**: {control_name}\n  {description[:200]}...")
        
        return "\n".join(formatted)
    
    def _format_contextual_edges(self, edges: List[Any], curated_tables: List[Dict[str, Any]]) -> str:
        """Format contextual edges for prompt"""
        if not edges:
            return "No contextual edges available"
        
        # Get table names for filtering relevant edges
        table_names = {t.get("table_name", "").lower() for t in curated_tables if t.get("table_name")}
        
        # Group edges by type and filter for relevance
        relevant_edges = []
        for edge in edges[:30]:  # Limit to 30 edges
            # Check if edge is relevant to curated tables
            edge_doc = edge.document if hasattr(edge, 'document') else str(edge)
            edge_doc_lower = edge_doc.lower()
            
            # Check if edge mentions any curated table
            is_relevant = False
            if table_names:
                for table_name in table_names:
                    if table_name and table_name in edge_doc_lower:
                        is_relevant = True
                        break
            else:
                # If no table names, include all edges
                is_relevant = True
            
            if is_relevant:
                relevant_edges.append(edge)
        
        if not relevant_edges:
            return "No relevant contextual edges found for curated tables"
        
        parts = [f"**Contextual Edges ({len(relevant_edges)} relevant edges):**\n"]
        
        # Group by edge type
        by_type = {}
        for edge in relevant_edges:
            edge_type = edge.edge_type if hasattr(edge, 'edge_type') else "unknown"
            if edge_type not in by_type:
                by_type[edge_type] = []
            by_type[edge_type].append(edge)
        
        for edge_type, type_edges in list(by_type.items())[:5]:  # Limit to 5 edge types
            parts.append(f"\n**{edge_type} Edges ({len(type_edges)}):**")
            for edge in type_edges[:3]:  # Limit to 3 edges per type
                edge_doc = edge.document if hasattr(edge, 'document') else str(edge)
                source_entity = edge.source_entity_id if hasattr(edge, 'source_entity_id') else ""
                target_entity = edge.target_entity_id if hasattr(edge, 'target_entity_id') else ""
                
                edge_info = f"- {edge_doc[:200]}"
                if source_entity:
                    edge_info += f"\n  Source: {source_entity[:50]}"
                if target_entity:
                    edge_info += f"\n  Target: {target_entity[:50]}"
                parts.append(edge_info)
        
        return "\n".join(parts)
    
    def _parse_text_response(self, content: str) -> Dict[str, Any]:
        """Parse text response into structured format"""
        result = {
            "recommended_features": [],
            "evidence_gathering_plan": [],
            "data_gaps": [],
            "summary": content[:500]
        }
        
        # Try to extract features from text
        # This is a fallback - ideally LLM should return JSON
        lines = content.split("\n")
        current_section = None
        
        for line in lines:
            line_lower = line.lower()
            if "feature" in line_lower or "kpi" in line_lower or "metric" in line_lower:
                current_section = "features"
            elif "evidence" in line_lower or "gathering" in line_lower:
                current_section = "evidence"
            elif "gap" in line_lower or "missing" in line_lower:
                current_section = "gaps"
            elif line.strip().startswith("-") or line.strip().startswith("*"):
                # Extract item
                item_text = line.strip().lstrip("-*").strip()
                if current_section == "features" and item_text:
                    result["recommended_features"].append({
                        "feature_name": item_text[:100],
                        "natural_language_question": item_text,
                        "feature_type": "metric",
                        "related_tables": [],
                        "purpose": item_text,
                        "evidence_type": "metric"
                    })

        return result

    def _merge_recommended_features_into_data_knowledge(
        self,
        state: ContextualAssistantState,
        recommended_features: List[Dict[str, Any]],
    ) -> None:
        """Merge recommended features into state['data_knowledge']['features']."""
        if "data_knowledge" not in state:
            state["data_knowledge"] = {}
        existing_features = state["data_knowledge"].get("features", [])
        formatted = []
        for rf in recommended_features:
            formatted.append({
                "feature_id": rf.get("feature_name", "").lower().replace(" ", "_"),
                "feature_name": rf.get("feature_name", ""),
                "display_name": rf.get("feature_name", ""),
                "feature_type": rf.get("feature_type", "metric"),
                "description": rf.get("purpose", ""),
                "question": rf.get("natural_language_question", ""),
                "related_tables": rf.get("related_tables", []),
                "evidence_type": rf.get("evidence_type", ""),
                "source": "deep_research",
                "relevance_score": 0.9,
            })
        all_features = {}
        for feature in existing_features + formatted:
            name = feature.get("feature_name", "")
            if name and name not in all_features:
                all_features[name] = feature
            elif name in all_features:
                if (feature.get("relevance_score") or 0) > (all_features[name].get("relevance_score") or 0):
                    all_features[name] = feature
        state["data_knowledge"]["features"] = list(all_features.values())
