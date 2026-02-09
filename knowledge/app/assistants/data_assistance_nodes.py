"""
Specialized nodes for Data Assistance Assistant

These nodes handle:
- Retrieving data from tables via contextual data retrieval (ContextualDataRetrievalAgent)
- Question breakdown across entities (policies, data) is unchanged
- No contextual edge retrieval for now: data retrieval returns data; summarization is action-based
"""
import logging
import json
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.assistants.state import ContextualAssistantState
from app.assistants.actor_types import get_actor_config, get_actor_prompt_context

logger = logging.getLogger(__name__)


def _build_state_update(state: Dict[str, Any], required_fields: List[str], optional_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Build a state update dict with only the fields we actually updated.
    
    This prevents LangGraph conflicts when multiple nodes might update the same field.
    
    Args:
        state: The state dictionary
        required_fields: Fields that must be included (will be included even if None)
        optional_fields: Fields to include only if they're actually set (not None/empty)
        
    Returns:
        Dictionary with only the updated fields
    """
    result = {}
    for field in required_fields:
        if field in state:
            result[field] = state[field]
    
    if optional_fields:
        for field in optional_fields:
            if field in state and state[field] is not None:
                # For lists/dicts, also check if they're not empty
                value = state[field]
                if isinstance(value, (list, dict)) and len(value) == 0:
                    continue
                result[field] = value
    
    return result


class DataKnowledgeRetrievalNode:
    """
    Node that retrieves data for data assistance using ContextualDataRetrievalAgent when available.
    No contextual edge retrieval: returns data only; summarization is left to the QA node based on user action.
    When contextual_data_retrieval_agent is not set, falls back to legacy retrieval (schemas/metrics/controls/features).
    """
    
    def __init__(
        self,
        retrieval_helper: Any,
        contextual_graph_service: Any = None,
        contextual_data_retrieval_agent: Optional[Any] = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.retrieval_helper = retrieval_helper
        self.contextual_graph_service = contextual_graph_service
        self.contextual_data_retrieval_agent = contextual_data_retrieval_agent
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        
        # Legacy: collection_factory for feature search when not using contextual data agent
        self.collection_factory = None
        if contextual_graph_service and hasattr(contextual_graph_service, 'query_engine'):
            if hasattr(contextual_graph_service.query_engine, 'collection_factory'):
                self.collection_factory = contextual_graph_service.query_engine.collection_factory
                logger.info("DataKnowledgeRetrievalNode: Using CollectionFactory for legacy feature search")
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Retrieve data via ContextualDataRetrievalAgent (no contextual edge retrieval)."""
        query = state.get("query", "")
        project_id = state.get("project_id")
        user_context = state.get("user_context", {})
        # Session cache for table/schema retrieval so we reuse results within this run
        if state.get("retrieval_session_cache") is None:
            state["retrieval_session_cache"] = {}
        session_cache = state["retrieval_session_cache"]
        
        if not query:
            state["status"] = "error"
            state["error"] = "No query provided"
            return state
        
        if not project_id:
            state["status"] = "error"
            state["error"] = "project_id is required for data assistance"
            return state
        
        framework = self._extract_framework(query, user_context)
        
        # Use contextual data retrieval when agent is available (no LLM summary; QA will summarize by action)
        if self.contextual_data_retrieval_agent:
            try:
                logger.info("DataKnowledgeRetrievalNode: Using ContextualDataRetrievalAgent (no contextual edge retrieval)")
                result = await self.contextual_data_retrieval_agent.run(
                    user_question=query,
                    product_name=project_id,
                    project_id=project_id,
                    include_table_schemas=True,
                    include_summary=False,
                    session_cache=session_cache,
                )
                schemas = self._schemas_from_contextual_result(result)
                metrics = self._metrics_from_contextual_result(result)
                state["data_knowledge"] = {
                    "schemas": schemas,
                    "metrics": metrics,
                    "controls": [],  # No contextual retrieval for now
                    "features": [],
                    "framework": framework,
                    "project_id": project_id,
                }
                state["contextual_data_retrieval_result"] = result
                state["skip_deep_research"] = True  # No contextual edge retrieval; go straight to metric_generation
                state["current_node"] = "data_knowledge_retrieval"
                state["next_node"] = "metric_generation"
                logger.info(f"Contextual data retrieval: {len(schemas)} tables, {len(metrics)} metrics")
            except Exception as e:
                logger.error(f"Contextual data retrieval failed: {e}", exc_info=True)
                state["status"] = "error"
                state["error"] = str(e)
                state["data_knowledge"] = {
                    "schemas": [],
                    "metrics": [],
                    "controls": [],
                    "features": [],
                    "framework": framework,
                    "project_id": project_id,
                }
                state["next_node"] = "metric_generation"
            return _build_state_update(
                state,
                required_fields=["data_knowledge", "current_node", "next_node"],
                optional_fields=["status", "error", "contextual_data_retrieval_result", "skip_deep_research"]
            )
        
        # Legacy path: no contextual data agent (e.g. retrieval_helper has no collection_factory)
        return await self._legacy_retrieval(state, query, project_id, user_context, framework)
    
    def _schemas_from_contextual_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert tables_with_columns from ContextualDataRetrievalAgent to schema shape expected by QA/metric nodes.
        Preserves full column_metadata (name, type, description, display_name, etc.) so the LLM receives all columns."""
        tables = result.get("tables_with_columns") or []
        schemas = []
        for t in tables:
            col_meta = t.get("column_metadata")
            if col_meta and isinstance(col_meta, list) and len(col_meta) > 0 and isinstance(col_meta[0], dict):
                column_metadata = list(col_meta)
            else:
                cols = t.get("columns") or []
                column_metadata = [{"column_name": c} for c in cols] if cols and isinstance(cols[0], str) else (cols or [])
            schemas.append({
                "table_name": t.get("table_name", ""),
                "table_ddl": t.get("table_ddl", ""),
                "column_metadata": column_metadata,
                "relevance_score": t.get("score"),
                "description": t.get("description", ""),
                "relationships": t.get("relationships", []),
            })
        return schemas
    
    def _metrics_from_contextual_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert pruned_metrics and store_results mdl_metrics to metrics list for data_knowledge."""
        pruned = result.get("pruned_metrics") or []
        metrics = []
        for m in pruned:
            name = m.get("metric_name") or m.get("name", "")
            if name:
                metrics.append({
                    "metric_name": name,
                    "description": m.get("reason", ""),
                    "score": m.get("score"),
                })
        # Also add any metrics from mdl_metrics store content (all docs, full content)
        store_results = result.get("store_results") or {}
        for doc in store_results.get("mdl_metrics", []):
            meta = doc.get("metadata", {})
            content = doc.get("content", "")
            name = meta.get("metric_name") or meta.get("name") or (content.split("\n")[0] if content else "")
            if name and not any(x.get("metric_name") == name for x in metrics):
                metrics.append({"metric_name": name, "description": content or ""})
        return metrics
    
    async def _legacy_retrieval(
        self,
        state: ContextualAssistantState,
        query: str,
        project_id: str,
        user_context: Dict[str, Any],
        framework: Optional[str],
    ) -> ContextualAssistantState:
        """Legacy: retrieve schemas/metrics/controls/features without ContextualDataRetrievalAgent."""
        try:
            query_plan = state.get("query_plan") or state.get("context_breakdown") or {}
            retrieval_query = query_plan.get("user_intent") or query
            table_retrieval_config = {
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": True,
            }
            session_cache = state.get("retrieval_session_cache")
            if session_cache is None:
                state["retrieval_session_cache"] = {}
                session_cache = state["retrieval_session_cache"]
            db_schemas = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval=table_retrieval_config,
                query=retrieval_query,
                tables=None,
                session_cache=session_cache,
            )
            metrics_result = await self.retrieval_helper.get_metrics(query=query, project_id=project_id)
            schemas = db_schemas.get("schemas", [])
            state["data_knowledge"] = {
                "schemas": schemas,
                "metrics": metrics_result.get("metrics", []),
                "controls": [],
                "features": [],
                "framework": framework,
                "project_id": project_id,
            }
            state["current_node"] = "data_knowledge_retrieval"
            state["next_node"] = "metric_generation"
        except Exception as e:
            logger.error(f"Legacy data knowledge retrieval failed: {e}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["data_knowledge"] = {
                "schemas": [],
                "metrics": [],
                "controls": [],
                "features": [],
                "framework": framework,
                "project_id": project_id,
            }
            state["next_node"] = "metric_generation"
        return _build_state_update(
            state,
            required_fields=["data_knowledge", "current_node", "next_node"],
            optional_fields=["status", "error"]
        )
    
    def _extract_framework(self, query: str, user_context: Dict[str, Any]) -> Optional[str]:
        """Extract compliance framework from query or user context"""
        query_lower = query.lower()
        
        # Check user context first
        if user_context.get("framework"):
            return user_context["framework"].upper()
        
        # Check query for framework mentions
        frameworks = ["SOC2", "SOC 2", "GDPR", "HIPAA", "PCI-DSS", "PCI DSS", "ISO27001", "NIST"]
        for framework in frameworks:
            if framework.lower() in query_lower:
                return framework.upper()
        
        return None


class MetricGenerationNode:
    """Node that generates new metrics based on schema definitions and control requirements"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Generate new metrics based on schemas and controls"""
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        data_knowledge = state.get("data_knowledge", {})
        
        schemas = data_knowledge.get("schemas", [])
        existing_metrics = data_knowledge.get("metrics", [])
        controls = data_knowledge.get("controls", [])
        framework = data_knowledge.get("framework")
        
        # Check if metric generation is needed
        needs_generation = self._should_generate_metrics(query, existing_metrics, controls)
        
        if not needs_generation or not schemas:
            state["generated_metrics"] = []
            state["next_node"] = "data_assistance_qa"
            return state
        
        try:
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            actor_config = get_actor_config(actor_type)
            
            # Format schemas for prompt
            schema_text = self._format_schemas(schemas)
            
            # Format existing metrics
            existing_metrics_text = self._format_existing_metrics(existing_metrics)
            
            # Format controls
            controls_text = self._format_controls(controls, framework)
            
            # Generate metrics prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a data analyst expert at generating metrics for compliance and data analysis.

{actor_context}

Your task is to generate new metrics based on:
1. Available database schemas
2. Existing metrics (to avoid duplicates)
3. Compliance control requirements (if applicable)

Generate metrics that:
- Are useful for answering the user's question
- Can be calculated from the available schema
- Are relevant to compliance controls if framework is specified
- Follow best practices for metric definitions

Return JSON with:
- metrics: List of metric objects, each with:
  - name: Short metric name (snake_case)
  - display_name: Human-readable name
  - description: What the metric measures
  - metric_sql: SQL query to calculate the metric
  - metric_type: Type (e.g., 'count', 'sum', 'avg', 'percentage', 'ratio')
  - aggregation_type: How to aggregate (e.g., 'daily', 'monthly', 'total')
  - relevance_to_controls: How this metric helps with compliance controls (if applicable)
  - confidence: Confidence level (high/medium/low) that this metric can be calculated
"""),
                ("human", """Generate metrics based on:

User Query: {query}

Database Schemas:
{schema_text}

Existing Metrics:
{existing_metrics_text}

Compliance Controls:
{controls_text}

Framework: {framework}

Generate metrics that help answer the user's question and support compliance monitoring.
""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "schema_text": schema_text,
                "existing_metrics_text": existing_metrics_text,
                "controls_text": controls_text,
                "framework": framework or "None"
            }
            logger.info(f"[LLM Step: MetricGenerationNode] Starting LLM call for metric generation")
            logger.debug(f"[LLM Step: MetricGenerationNode] Input: query={query[:100]}, framework={framework}, schemas_count={len(schemas)}, existing_metrics_count={len(existing_metrics)}, controls_count={len(controls)}")
            
            result = await chain.ainvoke(llm_input)
            
            # Log LLM call output
            logger.info(f"[LLM Step: MetricGenerationNode] LLM call completed successfully")
            generated_metrics = result.get("metrics", [])
            logger.info(f"[LLM Step: MetricGenerationNode] Output: Generated {len(generated_metrics)} new metrics")
            logger.debug(f"[LLM Step: MetricGenerationNode] LLM Result: {json.dumps(result, indent=2)[:500]}...")
            
            state["generated_metrics"] = generated_metrics
            state["next_node"] = "data_assistance_qa"
            state["current_node"] = "metric_generation"
            
            logger.info(f"Generated {len(generated_metrics)} new metrics")
            
        except Exception as e:
            logger.error(f"Error in metric generation: {str(e)}", exc_info=True)
            state["generated_metrics"] = []
            state["next_node"] = "data_assistance_qa"
        
        # Return only the fields we updated to avoid conflicts
        return _build_state_update(
            state,
            required_fields=["generated_metrics", "next_node"],
            optional_fields=["current_node"]
        )
    
    def _should_generate_metrics(self, query: str, existing_metrics: List[Dict], controls: List[Dict]) -> bool:
        """Determine if metric generation is needed"""
        query_lower = query.lower()
        
        # Check for explicit requests
        generation_keywords = [
            "generate", "create", "new metric", "suggest metric", 
            "what metrics", "which metrics", "metric for"
        ]
        if any(keyword in query_lower for keyword in generation_keywords):
            return True
        
        # If controls are present and no relevant metrics exist, suggest generation
        if controls and len(existing_metrics) == 0:
            return True
        
        return False
    
    def _format_schemas(self, schemas: List[Dict]) -> str:
        """Format schemas for prompt with all columns (name, type, description); no limits so nothing is removed."""
        if not schemas:
            return "No schemas available"
        
        formatted = []
        for schema in schemas:
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            col_meta = schema.get("column_metadata") or []
            parts = [f"Table: {table_name}\n{table_ddl}"]
            if col_meta and isinstance(col_meta[0], dict):
                parts.append("Columns (all):")
                for c in col_meta:
                    name = c.get("column_name", "")
                    typ = c.get("type", "")
                    desc = (c.get("description") or c.get("display_name", "")) or ""
                    line = f"  - {name}" + (f" ({typ})" if typ else "")
                    if desc:
                        line += f": {desc}"
                    parts.append(line)
            formatted.append("\n".join(parts))
        
        return "\n\n".join(formatted)
    
    def _format_existing_metrics(self, metrics: List[Dict]) -> str:
        """Format existing metrics for prompt (all metrics, no limit)."""
        if not metrics:
            return "No existing metrics"
        
        formatted = []
        for metric in metrics:
            name = metric.get("metric_name") or metric.get("name", "Unknown")
            description = metric.get("description", "")
            formatted.append(f"- {name}: {description}")
        
        return "\n".join(formatted)
    
    def _format_controls(self, controls: List[Dict], framework: Optional[str]) -> str:
        """Format controls for prompt (all controls, full descriptions)."""
        if not controls:
            return "No compliance controls specified"
        
        formatted = []
        for control in controls:
            # Handle different control formats
            if isinstance(control, dict):
                control_obj = control.get("control") or control
                control_id = control_obj.get("control_id") or control.get("control_id", "Unknown")
                control_name = control_obj.get("control_name") or control.get("control_name", "")
                description = control_obj.get("control_description") or control.get("control_description", "")
                formatted.append(f"Control {control_id}: {control_name}\n{description}\n")
        
        return "\n".join(formatted)


class DataAssistanceQANode:
    """Node that answers data assistance questions using retrieved knowledge"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Answer data assistance questions"""
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        data_knowledge = state.get("data_knowledge", {})
        generated_metrics = state.get("generated_metrics", [])
        
        try:
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            actor_config = get_actor_config(actor_type)
            
            # Build context for answering: use all schemas, features, and deep research (no information removed)
            all_schemas = data_knowledge.get("schemas", [])
            schemas = all_schemas
            existing_metrics = data_knowledge.get("metrics", [])
            controls = data_knowledge.get("controls", [])
            all_features = data_knowledge.get("features", [])
            features = sorted(
                all_features,
                key=lambda f: float(f.get("relevance_score", f.get("score", 0)) or 0),
                reverse=True
            )
            framework = data_knowledge.get("framework")

            # Extract deep research results (all items, no limit)
            deep_research_review = state.get("deep_research_review", {})
            recommended_features = deep_research_review.get("recommended_features", [])
            evidence_gathering_plan = deep_research_review.get("evidence_gathering_plan", [])
            data_gaps = deep_research_review.get("data_gaps", [])
            deep_research_summary = deep_research_review.get("summary", "")
            
            # Extract table-specific reasoning
            table_specific_reasoning = state.get("table_specific_reasoning", {})
            table_insights = table_specific_reasoning.get("table_insights", [])
            combined_insights = table_specific_reasoning.get("combined_insights", {})
            
            # Also extract features from reasoning_path if available
            reasoning_path = state.get("reasoning_path", [])
            if reasoning_path and not features:
                for hop in reasoning_path:
                    store_results = hop.get("store_results", {})
                    hop_features = store_results.get("features", [])
                    if hop_features:
                        features.extend(hop_features)
            
            # Format context
            schema_summary = self._format_schema_summary(schemas)
            metrics_summary = self._format_metrics_summary(existing_metrics, generated_metrics)
            controls_summary = self._format_controls_summary(controls, framework)
            features_summary = self._format_features_summary(features, framework)
            risk_explanation = self._extract_risk_explanation(features, controls, reasoning_path)
            deep_research_summary_text = self._format_deep_research_summary(
                recommended_features, evidence_gathering_plan, data_gaps, deep_research_summary
            )
            table_specific_summary = self._format_table_specific_summary(table_insights, combined_insights)
            # Calculation plan (field/metric instructions + silver time series for SQL Planner handoff)
            calculation_plan = state.get("calculation_plan") or {}
            calculation_plan_summary = self._format_calculation_plan_summary(calculation_plan)
            # When knowledge base returned no metrics/features, still suggest what can be derived from tables
            no_metrics_no_features = (len(existing_metrics) == 0 and len(all_features) == 0
                and len(generated_metrics) == 0 and len(recommended_features) == 0)
            vector_store_note = (
                " [Note: The knowledge base returned no metrics and no features for this query. "
                "Clearly state that. Then suggest metrics/KPIs that can be derived from the tables "
                "(based on the schema), similar to found examples—e.g. Vulnerability Count from Issue table, "
                "Last Scan Date from AssetProjectAttributes, severity levels from SecurityDetails. "
                "Present these as 'suggestions that can be derived from the tables', not as if from the knowledge base.]"
            ) if no_metrics_no_features else ""

            # Q&A prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a data assistance expert that helps users understand their database schemas, metrics, compliance controls, and risk features.

{actor_context}

You answer questions about:
- What data tables are necessary for compliance and risk management
- What metrics are available and how to use them
- What metrics and features help with compliance controls (e.g., SOC2, GDPR, HIPAA)
- How to generate new metrics from database schemas
- Database schema structure and relationships
- Compliance control requirements and how data can support them
- Risk features and risk explanations for compliance validation
- Product-specific features (e.g., Snyk) and how they relate to compliance
- Evidence gathering for compliance questions (e.g., "why my assets are having a soc 2 control for user access high")
- Table-specific metrics, KPIs, and aggregations that help answer the question

Your answers should:
- Be clear and easy to understand
- Use {actor_config['communication_style']} style
- Provide {actor_config['preferred_detail_level']} level of detail
- Focus on: {', '.join(actor_config['focus_areas'])}
- Include relevant tables, columns, metrics, and features
- Explain how metrics and features relate to compliance controls when applicable
- Provide structured risk explanations when risk-related features are available
- Suggest new metrics when appropriate
- When product-specific features are mentioned (e.g., Snyk), explain how they help with compliance

REQUIRED - Tables in every response: You MUST always include a "Relevant Tables" (or "Top Tables") section that summarizes the top relevant tables from the Database Schemas provided. List each table name and a brief one-line description or purpose. The data assistant must always produce tables in the response—never return a generic answer without this tables summary. If schemas were provided, your response must explicitly list and describe those tables.

REQUIRED - Columns for each table: When Database Schemas include "Columns (all):" or CREATE TABLE DDL for a table, you MUST include that table's full column list (column name, type, and description when available) in your response. Do not output only "Table Name | Description"—for each table that has column information in the schemas above, your response MUST list its columns explicitly (e.g. as a bullet list or sub-table). Omitting columns when they are provided in Database Schemas is not allowed.

COLUMN-OR-TABLE-SPECIFIC questions: When the user asks about columns in a specific table by name (e.g. "What columns are in the DirectVulnerabilities table" or "columns available in X table"), the first table(s) in Database Schemas are the ones they asked for. You MUST lead your answer with that table and list ALL its columns (name, type, description) directly. Do not substitute other "relevant" tables as the main answer—answer with the requested table and its columns first, then optionally mention related tables.

IMPORTANT: When features are provided, use them to:
1. Explain what risk features are available and how they validate compliance
2. Connect features to specific controls and tables
3. Provide structured risk explanations based on feature data
4. Explain how features help answer the user's question

When the knowledge base returned no metrics and no features: state that clearly first. Then suggest metrics/KPIs that can be derived from the tables (based on the schema), similar to found examples—e.g. Vulnerability Count from Issue table, Last Scan Date from AssetProjectAttributes, severity levels from SecurityDetails. Present these as "suggestions that can be derived from the tables", not as if they came from the knowledge base.

Format your response in Markdown with proper headers, lists, and tables.
"""),
                ("human", """Answer this question: {query}
{vector_store_note}

Database Schemas:
{schema_summary}

Available Metrics:
{metrics_summary}

Compliance Controls:
{controls_summary}

Features:
{features_summary}

Risk Explanation:
{risk_explanation}

Deep Research Analysis:
{deep_research_summary}

Table-Specific Reasoning:
{table_specific_summary}

Calculation Plan (for SQL Planner handoff):
{calculation_plan_summary}

Framework: {framework}

Provide a comprehensive answer that helps the user understand:
1. **Relevant Tables (required):** A clear summary of the top relevant tables from Database Schemas above—list each table name, a brief description or purpose, and for each table that has "Columns (all):" or DDL in the schemas, list its columns (name, type, description). Always include this section when schemas were provided; do not omit column lists when they are in Database Schemas.
2. What data tables are necessary (from schemas and features)
3. What compliance controls apply (from controls)
4. What features/KPIs/metrics that are related to each table or can be derived from the tables (from features list and deep research)
5. What evidence needs to be gathered (from deep research evidence gathering plan)
6. Table-specific insights and recommendations (from table-specific reasoning)
7. Calculation plan: when present, summarize the field instructions, metric instructions, and any silver time series suggestion so the user knows what can be handed off to the SQL Planner (calculated columns, metrics, LAG/LEAD/trend steps).
8. What risks need to be validated (from risk explanation)
9. How everything connects together to answer their question
10. Action items with actor types (what needs to be done to answer the question)

Be specific about tables, features, controls, risks, evidence, and action items. Do not give a generic response—always summarize the retrieved tables first when Database Schemas are provided.
Include a summary report that combines all this information.
""")
            ])
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "vector_store_note": vector_store_note,
                "schema_summary": schema_summary,
                "metrics_summary": metrics_summary,
                "controls_summary": controls_summary,
                "features_summary": features_summary,
                "risk_explanation": risk_explanation,
                "deep_research_summary": deep_research_summary_text,
                "table_specific_summary": table_specific_summary,
                "calculation_plan_summary": calculation_plan_summary,
                "framework": framework or "None"
            }
            logger.info(f"[LLM Step: DataAssistanceQANode] Starting LLM call for Q&A")
            logger.info(f"[LLM Step: DataAssistanceQANode] Input - query={query[:100]}, framework={framework}")
            logger.info(f"[LLM Step: DataAssistanceQANode] Context sizes - schemas={len(schemas)}, metrics={len(existing_metrics)}, generated_metrics={len(generated_metrics)}, controls={len(controls)}, features={len(features)} (top 10 by relevance)")
            logger.debug(f"[LLM Step: DataAssistanceQANode] Summary lengths - schema={len(schema_summary) if schema_summary else 0}, metrics={len(metrics_summary) if metrics_summary else 0}, controls={len(controls_summary) if controls_summary else 0}, features={len(features_summary) if features_summary else 0}")
            
            chain = prompt | self.llm
            response = await chain.ainvoke(llm_input)
            
            # Log LLM call output
            answer = response.content if hasattr(response, "content") else str(response)
            logger.info(f"[LLM Step: DataAssistanceQANode] LLM call completed successfully")
            logger.info(f"[LLM Step: DataAssistanceQANode] Output: Answer length={len(answer) if answer else 0} characters")
            logger.info(f"[LLM Step: DataAssistanceQANode] Answer preview: {answer[:500] if answer else 'None'}...")
            logger.debug(f"[LLM Step: DataAssistanceQANode] Full answer (first 1000 chars): {answer[:1000] if answer else 'None'}...")
            
            state["qa_answer"] = answer
            state["qa_sources"] = {
                "schemas_count": len(schemas),
                "metrics_count": len(existing_metrics),
                "generated_metrics_count": len(generated_metrics),
                "controls_count": len(controls),
                "features_count": len(features),
                "deep_research_features_count": len(recommended_features),
                "table_insights_count": len(table_insights),
                "framework": framework
            }
            # Calculate confidence based on available data
            has_metrics = len(existing_metrics) > 0 or len(generated_metrics) > 0
            state["qa_confidence"] = 0.9 if schemas or has_metrics or controls else 0.5
            
            # Add to messages
            from langchain_core.messages import HumanMessage, AIMessage
            messages = list(state.get("messages", []))
            messages.append(HumanMessage(content=query))
            messages.append(AIMessage(content=answer))
            state["messages"] = messages
            
            state["next_node"] = "writer_agent"
            state["current_node"] = "data_assistance_qa"
            logger.info("Data assistance Q&A answer generated")
            
        except Exception as e:
            logger.error(f"Error in data assistance Q&A: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["qa_answer"] = f"Error generating answer: {str(e)}"
            state["next_node"] = "finalize"
        
        # Return only the fields we updated to avoid conflicts
        return _build_state_update(
            state,
            required_fields=["qa_answer", "qa_sources", "qa_confidence", "messages", "next_node"],
            optional_fields=["current_node", "status", "error"]
        )
    
    def _parse_columns_from_ddl(self, table_ddl: str) -> List[Dict[str, str]]:
        """Parse CREATE TABLE DDL to extract column name, type, and description (from -- comment)."""
        if not table_ddl or "CREATE TABLE" not in table_ddl.upper():
            return []
        columns = []
        # Get content between ( and ); handle multi-line
        start = table_ddl.upper().find("CREATE TABLE")
        if start < 0:
            return []
        rest = table_ddl[start + len("CREATE TABLE"):].strip()
        if "(" not in rest:
            return []
        rest = rest.split("(", 1)[1]
        if ")" in rest:
            rest = rest.rsplit(")", 1)[0]
        for line in rest.splitlines():
            line = line.strip().rstrip(",").strip()
            if not line:
                continue
            name, typ, desc = "", "", ""
            if " -- " in line:
                def_part, desc = line.split(" -- ", 1)
                desc = desc.strip()
            else:
                def_part = line
            tokens = def_part.split()
            if tokens:
                name = tokens[0]
                typ = tokens[1] if len(tokens) > 1 else ""
            if name:
                columns.append({
                    "column_name": name,
                    "type": typ,
                    "description": desc or "",
                })
        return columns

    def _format_schema_summary(self, schemas: List[Dict]) -> str:
        """Format schema summary for prompt with all columns and no truncation so the LLM gets full data."""
        if not schemas:
            return "No database schemas available"
        
        summary = []
        for schema in schemas:
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            description = schema.get("description", "")
            col_meta = schema.get("column_metadata") or []
            relationships = schema.get("relationships") or []
            # Use column_metadata when present and list of dicts; else parse from DDL so columns are always shown
            if col_meta and isinstance(col_meta[0], dict):
                pass
            elif table_ddl:
                col_meta = self._parse_columns_from_ddl(table_ddl)
            parts = [f"**{table_name}**"]
            if description:
                parts.append(description)
            if table_ddl:
                parts.append(table_ddl)
            if col_meta:
                parts.append("Columns (all):")
                for c in col_meta:
                    name = c.get("column_name", c.get("name", ""))
                    typ = c.get("type", "")
                    desc = (c.get("description") or c.get("display_name", c.get("comment", ""))) or ""
                    line = f"  - {name}" + (f" ({typ})" if typ else "")
                    if desc:
                        line += f": {desc}"
                    parts.append(line)
            if relationships:
                rel_strs = [str(r.get("name", r.get("condition", ""))) for r in relationships]
                parts.append("Relationships: " + "; ".join(rel_strs))
            summary.append("\n".join(parts))
        
        return "\n\n".join(summary)
    
    def _format_metrics_summary(self, existing_metrics: List[Dict], generated_metrics: List[Dict]) -> str:
        """Format metrics summary for prompt (all metrics, no truncation)."""
        parts = []
        
        if existing_metrics:
            parts.append("**Existing Metrics:**")
            for metric in existing_metrics:
                name = metric.get("metric_name") or metric.get("name", "Unknown")
                description = metric.get("description", "")
                parts.append(f"- {name}: {description}")
        
        if generated_metrics:
            parts.append("\n**Suggested New Metrics:**")
            for metric in generated_metrics:
                name = metric.get("name", "Unknown")
                display_name = metric.get("display_name", name)
                description = metric.get("description", "")
                parts.append(f"- {display_name} ({name}): {description}")
        
        if not parts:
            return "No metrics available"
        
        return "\n".join(parts)
    
    def _format_controls_summary(self, controls: List[Dict], framework: Optional[str]) -> str:
        """Format controls summary for prompt (all controls, full descriptions)."""
        if not controls:
            return "No compliance controls specified"
        
        parts = [f"**Compliance Framework: {framework or 'Unknown'}**\n"]
        for control in controls:
            if isinstance(control, dict):
                control_obj = control.get("control") or control
                control_id = control_obj.get("control_id") or control.get("control_id", "Unknown")
                control_name = control_obj.get("control_name") or control.get("control_name", "")
                description = control_obj.get("control_description") or control.get("control_description", "")
                parts.append(f"- **{control_id}**: {control_name}\n  {description}")
        
        return "\n".join(parts)
    
    def _format_features_summary(self, features: List[Dict], framework: Optional[str]) -> str:
        """Format features summary for prompt"""
        if not features:
            return "No features available"
        
        parts = [f"**Available Features ({len(features)} total)**\n"]
        
        # Group by feature type
        by_type = {}
        for feature in features:
            feature_type = feature.get("feature_type", "general")
            if feature_type not in by_type:
                by_type[feature_type] = []
            by_type[feature_type].append(feature)
        
        for feature_type, type_features in by_type.items():
            parts.append(f"\n**{feature_type.upper()} Features:**")
            for feature in type_features:
                feature_name = feature.get("display_name") or feature.get("feature_name", "Unknown")
                description = feature.get("description") or feature.get("purpose", "")
                compliance = feature.get("compliance", "")
                control = feature.get("control", "")
                
                feature_info = f"- **{feature_name}**"
                if compliance:
                    feature_info += f" (Compliance: {compliance})"
                if control:
                    feature_info += f" (Control: {control})"
                feature_info += f"\n  {description}"
                parts.append(feature_info)
        
        return "\n".join(parts)
    
    def _extract_risk_explanation(self, features: List[Dict], controls: List[Dict], reasoning_path: List[Dict]) -> str:
        """Extract and format risk explanation from features, controls, and reasoning path"""
        if not features and not controls:
            return "No risk information available"
        
        parts = []
        
        # Extract risk-related features
        risk_features = [f for f in features if f.get("feature_type", "").lower() in ["risk", "likelihood", "impact"]]
        
        if risk_features:
            parts.append("**Risk Features Available:**")
            for feature in risk_features:
                feature_name = feature.get("display_name") or feature.get("feature_name", "")
                description = feature.get("description", "")
                question = feature.get("question", "")
                
                risk_info = f"- **{feature_name}**"
                if description:
                    risk_info += f": {description}"
                if question:
                    risk_info += f"\n  Question: {question}"
                parts.append(risk_info)
        
        # Extract risk context from reasoning path
        if reasoning_path:
            risk_contexts = []
            for hop in reasoning_path:
                store_results = hop.get("store_results", {})
                risks = store_results.get("risks", [])
                if risks:
                    for risk in risks:
                        risk_doc = risk.get("document") or risk.get("content", "")
                        if risk_doc:
                            risk_contexts.append(risk_doc)
            
            if risk_contexts:
                parts.append("\n**Risk Context from Reasoning:**")
                for i, context in enumerate(risk_contexts, 1):
                    parts.append(f"{i}. {context}")
        
        # Extract risk-related controls
        risk_controls = [c for c in controls if "risk" in str(c).lower() or "access" in str(c).lower()]
        if risk_controls:
            parts.append("\n**Risk-Related Controls:**")
            for control in risk_controls:
                if isinstance(control, dict):
                    control_obj = control.get("control") or control
                    control_id = control_obj.get("control_id", "Unknown")
                    control_name = control_obj.get("control_name", "")
                    parts.append(f"- {control_id}: {control_name}")
        
        if not parts:
            return "No specific risk information extracted. Use available features and controls to assess risks."
        
        return "\n".join(parts)
    
    def _format_deep_research_summary(
        self,
        recommended_features: List[Dict],
        evidence_gathering_plan: List[Dict],
        data_gaps: List[Dict],
        deep_research_summary: str
    ) -> str:
        """Format deep research summary for prompt"""
        parts = []
        
        if deep_research_summary:
            parts.append(f"**Deep Research Summary:**\n{deep_research_summary}")
        
        if recommended_features:
            parts.append(f"\n**Recommended Features/KPIs/Metrics ({len(recommended_features)}):**")
            for i, feature in enumerate(recommended_features, 1):
                feature_name = feature.get("feature_name", "Unknown")
                question = feature.get("natural_language_question", "")
                feature_type = feature.get("feature_type", "metric")
                purpose = feature.get("purpose", "")
                related_tables = feature.get("related_tables", [])
                
                feature_info = f"{i}. **{feature_name}** ({feature_type})"
                if question:
                    feature_info += f"\n   Question: {question}"
                if purpose:
                    feature_info += f"\n   Purpose: {purpose}"
                if related_tables:
                    feature_info += f"\n   Related Tables: {', '.join(related_tables)}"
                parts.append(feature_info)
        
        if evidence_gathering_plan:
            parts.append(f"\n**Evidence Gathering Plan ({len(evidence_gathering_plan)} items):**")
            for i, evidence in enumerate(evidence_gathering_plan, 1):
                evidence_type = evidence.get("evidence_type", "Unknown")
                source_tables = evidence.get("source_tables", [])
                description = evidence.get("description", "")
                priority = evidence.get("priority", "medium")
                
                evidence_info = f"{i}. **{evidence_type}** (Priority: {priority})"
                if description:
                    evidence_info += f"\n   {description}"
                if source_tables:
                    evidence_info += f"\n   Source Tables: {', '.join(source_tables)}"
                parts.append(evidence_info)
        
        if data_gaps:
            parts.append(f"\n**Data Gaps ({len(data_gaps)}):**")
            for i, gap in enumerate(data_gaps, 1):
                if isinstance(gap, dict):
                    gap_desc = gap.get("description", "") or gap.get("gap", "")
                else:
                    gap_desc = str(gap)
                parts.append(f"{i}. {gap_desc}")
        
        if not parts:
            return "No deep research analysis available"
        
        return "\n".join(parts)
    
    def _format_table_specific_summary(
        self,
        table_insights: List[Dict],
        combined_insights: Dict[str, Any]
    ) -> str:
        """Format table-specific reasoning summary for prompt"""
        parts = []
        
        if combined_insights:
            total_tables = combined_insights.get("total_tables", 0)
            total_metrics = combined_insights.get("total_metrics", 0)
            parts.append(f"**Table-Specific Analysis:** {total_tables} tables analyzed, {total_metrics} metrics recommended")
            
            high_relevance = combined_insights.get("high_relevance_tables", [])
            if high_relevance:
                parts.append(f"\n**High Relevance Tables ({len(high_relevance)}):**")
                for table_info in high_relevance:
                    table_name = table_info.get("table_name", "Unknown")
                    relevance = table_info.get("relevance", 0.0)
                    metrics_count = table_info.get("metrics_count", 0)
                    parts.append(f"- {table_name} (relevance: {relevance:.2f}, {metrics_count} metrics)")
        
        if table_insights:
            parts.append(f"\n**Table-Specific Insights:**")
            for insight in table_insights:
                table_name = insight.get("table_name", "Unknown")
                relevance = insight.get("relevance_to_question", 0.0)
                recommended_metrics = insight.get("recommended_metrics", [])
                insights_text = insight.get("insights", "")
                
                parts.append(f"\n**{table_name}** (relevance: {relevance:.2f}):")
                if insights_text:
                    parts.append(f"  {insights_text}")
                if recommended_metrics:
                    parts.append(f"  Recommended Metrics ({len(recommended_metrics)}):")
                    for metric in recommended_metrics:
                        metric_name = metric.get("feature_name", "Unknown")
                        description = metric.get("description", "")
                        parts.append(f"    - {metric_name}: {description}")
        
        if not parts:
            return "No table-specific reasoning available"
        
        return "\n".join(parts)

    def _format_calculation_plan_summary(self, calculation_plan: Dict[str, Any]) -> str:
        """Format calculation plan (field/metric instructions + silver time series) for QA context."""
        if not calculation_plan or not isinstance(calculation_plan, dict):
            return "No calculation plan (SQL Planner handoff not run)."
        parts = []
        fields = calculation_plan.get("field_instructions") or []
        metrics = calculation_plan.get("metric_instructions") or []
        if fields:
            parts.append("**Field instructions:**")
            for f in fields:
                name = f.get("display_name", f.get("name", ""))
                basis = f.get("calculation_basis", "")
                parts.append(f"- {name}: {basis}")
        if metrics:
            parts.append("**Metric instructions:**")
            for m in metrics:
                name = m.get("display_name", m.get("name", ""))
                measure = m.get("measure", "")
                base = m.get("base_table", "")
                parts.append(f"- {name}: base_table={base}, measure={measure}")
        silver = calculation_plan.get("silver_time_series_suggestion")
        if silver and isinstance(silver, dict) and silver.get("suggest_silver_table"):
            tbl = silver.get("silver_table_suggestion") or {}
            parts.append(f"**Silver time series:** {tbl.get('purpose', '')}; grain: {tbl.get('grain', '')}")
            steps = silver.get("calculation_steps") or []
            for s in steps:
                parts.append(f"  - Step {s.get('step_number', '')}: {s.get('description', '')} [{s.get('technique', '')}]")
        if not parts:
            return "Calculation plan empty (no field/metric or silver suggestion)."
        return "\n".join(parts)

