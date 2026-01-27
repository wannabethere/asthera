"""
Specialized nodes for Data Assistance Assistant

These nodes handle:
- Retrieving schemas, metrics, and controls from contextual retrieval
- Generating new metrics based on schema definitions
- Answering questions about metrics for compliance controls
"""
import logging
import json
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .state import ContextualAssistantState
from .actor_types import get_actor_config, get_actor_prompt_context

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
    """Node that retrieves schemas, metrics, controls, and features for data assistance"""
    
    def __init__(
        self,
        retrieval_helper: Any,
        contextual_graph_service: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.retrieval_helper = retrieval_helper
        self.contextual_graph_service = contextual_graph_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        
        # Get collection_factory for feature search if available
        self.collection_factory = None
        if contextual_graph_service and hasattr(contextual_graph_service, 'query_engine'):
            if hasattr(contextual_graph_service.query_engine, 'collection_factory'):
                self.collection_factory = contextual_graph_service.query_engine.collection_factory
                logger.info("DataKnowledgeRetrievalNode: Using CollectionFactory for feature search")
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Retrieve schemas, metrics, and controls based on query
        
        This node integrates with the framework's context retrieval:
        - Uses context_ids from framework's context retrieval (already in state)
        - Retrieves schemas and metrics using RetrievalHelper
        - Retrieves controls using framework's contextual graph service
        
        The contextual graph service uses the same collections as the ingestion scripts
        (ingest_mdl_contextual_graph.py, ingest_preview_files.py) which use empty collection_prefix
        to match collection_factory.py collections. This ensures contexts, edges, and controls
        created by ingestion scripts are accessible here.
        """
        query = state.get("query", "")
        project_id = state.get("project_id")
        user_context = state.get("user_context", {})
        
        # Use context_ids from framework's context retrieval (already retrieved)
        context_ids = state.get("context_ids", [])
        if not context_ids:
            # Fallback to user_context if framework didn't retrieve any
            context_ids = user_context.get("context_ids", [])
        
        if not query:
            state["status"] = "error"
            state["error"] = "No query provided"
            return state
        
        if not project_id:
            state["status"] = "error"
            state["error"] = "project_id is required for data assistance"
            return state
        
        try:
            # Extract framework from query or user context (e.g., SOC2, GDPR, HIPAA)
            framework = self._extract_framework(query, user_context)
            
            # Get suggested tables from contextual reasoning (if available)
            suggested_tables = state.get("suggested_tables", [])
            table_suggestion_strategy = state.get("table_suggestion_strategy", "")
            
            # Extract table names from suggestions to pass to retrieval helper
            suggested_table_names = None
            if suggested_tables:
                # Extract table names from suggestions
                table_names = [t.get("table_name") for t in suggested_tables if t.get("table_name")]
                if table_names:
                    suggested_table_names = table_names
                    logger.info(f"Using {len(table_names)} suggested tables from contextual reasoning: {table_names[:5]}")
                    logger.info(f"Table suggestion strategy: {table_suggestion_strategy[:200] if table_suggestion_strategy else 'None'}")
                else:
                    logger.info("Suggested tables list is empty, using general schema retrieval")
            else:
                logger.info("No suggested tables from contextual reasoning, using general schema retrieval")
            
            # 1. Retrieve database schemas
            # Use suggested tables if available, otherwise use general retrieval
            logger.info(f"Retrieving database schemas for project {project_id}")
            table_retrieval_config = {
                "table_retrieval_size": len(suggested_tables) if suggested_tables else 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
            
            # Pass suggested table names directly to get_database_schemas
            # The tables parameter allows us to retrieve specific tables
            db_schemas = await self.retrieval_helper.get_database_schemas(
                project_id=project_id,
                table_retrieval=table_retrieval_config,
                query=query,
                tables=suggested_table_names  # Pass suggested tables directly
            )
            
            # Log which tables were actually retrieved
            retrieved_table_names = [s.get("table_name", "") for s in db_schemas.get("schemas", [])]
            if suggested_table_names:
                matched = [t for t in suggested_table_names if t in retrieved_table_names]
                logger.info(f"Retrieved {len(retrieved_table_names)} tables, {len(matched)} matched suggested tables")
                if len(matched) < len(suggested_table_names):
                    missing = [t for t in suggested_table_names if t not in retrieved_table_names]
                    logger.info(f"Suggested tables not found in project: {missing[:5]}")
            
            # 2. Retrieve existing metrics
            logger.info(f"Retrieving metrics for project {project_id}")
            metrics_result = await self.retrieval_helper.get_metrics(
                query=query,
                project_id=project_id
            )
            
            # 3. Extract features from reasoning_path (if available from contextual reasoning)
            features_from_reasoning = []
            reasoning_path = state.get("reasoning_path", [])
            if reasoning_path:
                for hop in reasoning_path:
                    store_results = hop.get("store_results", {})
                    hop_features = store_results.get("features", [])
                    if hop_features:
                        features_from_reasoning.extend(hop_features)
                        logger.info(f"Extracted {len(hop_features)} features from reasoning path hop")
            
            # 4. Search features directly if collection_factory available
            features_from_search = []
            if self.collection_factory:
                try:
                    logger.info(f"Searching features store for query: {query[:100]}")
                    features_collection = self.collection_factory.get_collection_by_store_name("features")
                    if features_collection:
                        # Build filters
                        feature_filters = {}
                        if framework:
                            feature_filters["compliance"] = framework
                        if context_ids:
                            feature_filters["context_id"] = context_ids[0]
                        
                        feature_results = await features_collection.hybrid_search(
                            query=query,
                            top_k=10,
                            where=feature_filters if feature_filters else None
                        )
                        
                        for result in feature_results:
                            metadata = result.get("metadata", {})
                            content = result.get("content") or result.get("document", "")
                            
                            # Parse content if it's JSON
                            try:
                                import json
                                content_data = json.loads(content) if isinstance(content, str) and content.strip().startswith("{") else {}
                            except:
                                content_data = {}
                            
                            features_from_search.append({
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
                        
                        logger.info(f"Found {len(features_from_search)} features from direct search")
                except Exception as e:
                    logger.warning(f"Error searching features: {e}")
            
            # Combine features from reasoning and direct search (deduplicate by feature_id)
            all_features = {}
            for feature in features_from_reasoning + features_from_search:
                feature_id = feature.get("feature_id") or feature.get("feature_name", "")
                if feature_id and feature_id not in all_features:
                    all_features[feature_id] = feature
                elif feature_id in all_features:
                    # Merge if duplicate - keep higher relevance score
                    existing = all_features[feature_id]
                    new_score = feature.get("relevance_score", 0.0)
                    existing_score = existing.get("relevance_score", 0.0)
                    if new_score > existing_score:
                        all_features[feature_id] = feature
            
            features = list(all_features.values())
            logger.info(f"Total unique features found: {len(features)}")
            
            # 5. Retrieve controls from contextual graph if available
            # Use context_ids from framework's context retrieval
            controls = []
            if self.contextual_graph_service and framework and context_ids:
                logger.info(f"Retrieving controls for framework {framework} using context_ids from framework")
                try:
                    # Get controls for contexts retrieved by framework
                    for context_id in context_ids[:1]:  # Use first context
                        if context_id:
                            from app.services.models import ControlSearchRequest
                            search_request = ControlSearchRequest(
                                context_id=context_id,
                                framework=framework,
                                query=query,
                                top_k=10,
                                request_id=f"data_assistance_{context_id}"
                            )
                            search_response = await self.contextual_graph_service.search_controls(search_request)
                            if search_response.success and search_response.data:
                                context_controls = search_response.data.get("controls", [])
                                controls.extend(context_controls)
                except Exception as e:
                    logger.warning(f"Error retrieving controls: {e}")
            elif self.contextual_graph_service and framework:
                # Fallback: try to find contexts if framework didn't retrieve any
                logger.info(f"Framework didn't retrieve contexts, trying to find contexts for framework {framework}")
                try:
                    if hasattr(self.contextual_graph_service, 'query_engine'):
                        contexts = await self.contextual_graph_service.query_engine.find_relevant_contexts(
                            user_context_description=query,
                            top_k=3
                        )
                        fallback_context_ids = [ctx.get("context_id") for ctx in contexts if ctx.get("context_id")]
                        for context_id in fallback_context_ids[:1]:
                            if context_id:
                                from app.services.models import ControlSearchRequest
                                search_request = ControlSearchRequest(
                                    context_id=context_id,
                                    framework=framework,
                                    query=query,
                                    top_k=10,
                                    request_id=f"data_assistance_{context_id}"
                                )
                                search_response = await self.contextual_graph_service.search_controls(search_request)
                                if search_response.success and search_response.data:
                                    context_controls = search_response.data.get("controls", [])
                                    controls.extend(context_controls)
                except Exception as e:
                    logger.warning(f"Error retrieving controls with fallback: {e}")
            
            # Store retrieved knowledge in state
            state["data_knowledge"] = {
                "schemas": db_schemas.get("schemas", []),
                "metrics": metrics_result.get("metrics", []),
                "controls": controls,
                "features": features,  # Include features
                "framework": framework,
                "project_id": project_id
            }
            
            state["current_node"] = "data_knowledge_retrieval"
            state["next_node"] = "data_assistance_qa"
            logger.info(f"Retrieved {len(db_schemas.get('schemas', []))} schemas, "
                       f"{len(metrics_result.get('metrics', []))} metrics, "
                       f"{len(controls)} controls, "
                       f"{len(features)} features")
            
        except Exception as e:
            logger.error(f"Error in data knowledge retrieval: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["data_knowledge"] = {
                "schemas": [],
                "metrics": [],
                "controls": [],
                "features": [],  # Include features even on error
                "framework": None,
                "project_id": project_id
            }
            state["next_node"] = "data_assistance_qa"  # Continue anyway
        
        # Return only the fields we updated to avoid conflicts
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
        """Format schemas for prompt"""
        if not schemas:
            return "No schemas available"
        
        formatted = []
        for schema in schemas[:10]:  # Limit to 10 schemas
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            formatted.append(f"Table: {table_name}\n{table_ddl}\n")
        
        return "\n".join(formatted)
    
    def _format_existing_metrics(self, metrics: List[Dict]) -> str:
        """Format existing metrics for prompt"""
        if not metrics:
            return "No existing metrics"
        
        formatted = []
        for metric in metrics[:20]:  # Limit to 20 metrics
            name = metric.get("metric_name") or metric.get("name", "Unknown")
            description = metric.get("description", "")
            formatted.append(f"- {name}: {description}")
        
        return "\n".join(formatted)
    
    def _format_controls(self, controls: List[Dict], framework: Optional[str]) -> str:
        """Format controls for prompt"""
        if not controls:
            return "No compliance controls specified"
        
        formatted = []
        for control in controls[:10]:  # Limit to 10 controls
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
            
            # Build context for answering
            schemas = data_knowledge.get("schemas", [])
            existing_metrics = data_knowledge.get("metrics", [])
            controls = data_knowledge.get("controls", [])
            features = data_knowledge.get("features", [])
            framework = data_knowledge.get("framework")
            
            # Extract deep research results
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

IMPORTANT: When features are provided, use them to:
1. Explain what risk features are available and how they validate compliance
2. Connect features to specific controls and tables
3. Provide structured risk explanations based on feature data
4. Explain how features help answer the user's question

Format your response in Markdown with proper headers, lists, and tables.
"""),
                ("human", """Answer this question: {query}

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

Framework: {framework}

Provide a comprehensive answer that helps the user understand:
1. What data tables are necessary (from schemas and features)
2. What compliance controls apply (from controls)
3. What features/KPIs/metrics are needed (from features list and deep research)
4. What evidence needs to be gathered (from deep research evidence gathering plan)
5. Table-specific insights and recommendations (from table-specific reasoning)
6. What risks need to be validated (from risk explanation)
7. How everything connects together to answer their question
8. Action items with actor types (what needs to be done to answer the question)

Be specific about tables, features, controls, risks, evidence, and action items.
Include a summary report that combines all this information.
""")
            ])
            
            # Log LLM call input
            llm_input = {
                "query": query,
                "schema_summary": schema_summary,
                "metrics_summary": metrics_summary,
                "controls_summary": controls_summary,
                "features_summary": features_summary,
                "risk_explanation": risk_explanation,
                "deep_research_summary": deep_research_summary_text,
                "table_specific_summary": table_specific_summary,
                "framework": framework or "None"
            }
            logger.info(f"[LLM Step: DataAssistanceQANode] Starting LLM call for Q&A")
            logger.info(f"[LLM Step: DataAssistanceQANode] Input - query={query[:100]}, framework={framework}")
            logger.info(f"[LLM Step: DataAssistanceQANode] Context sizes - schemas={len(schemas)}, metrics={len(existing_metrics)}, generated_metrics={len(generated_metrics)}, controls={len(controls)}, features={len(features)}")
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
    
    def _format_schema_summary(self, schemas: List[Dict]) -> str:
        """Format schema summary for prompt"""
        if not schemas:
            return "No database schemas available"
        
        summary = []
        for schema in schemas[:10]:
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            # Extract key info from DDL
            summary.append(f"**{table_name}**\n{table_ddl[:500]}...")
        
        return "\n\n".join(summary)
    
    def _format_metrics_summary(self, existing_metrics: List[Dict], generated_metrics: List[Dict]) -> str:
        """Format metrics summary for prompt"""
        parts = []
        
        if existing_metrics:
            parts.append("**Existing Metrics:**")
            for metric in existing_metrics[:10]:
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
        """Format controls summary for prompt"""
        if not controls:
            return "No compliance controls specified"
        
        parts = [f"**Compliance Framework: {framework or 'Unknown'}**\n"]
        for control in controls[:10]:
            if isinstance(control, dict):
                control_obj = control.get("control") or control
                control_id = control_obj.get("control_id") or control.get("control_id", "Unknown")
                control_name = control_obj.get("control_name") or control.get("control_name", "")
                description = control_obj.get("control_description") or control.get("control_description", "")
                parts.append(f"- **{control_id}**: {control_name}\n  {description[:200]}...")
        
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
            for feature in type_features[:5]:  # Limit to 5 per type
                feature_name = feature.get("display_name") or feature.get("feature_name", "Unknown")
                description = feature.get("description") or feature.get("purpose", "")
                compliance = feature.get("compliance", "")
                control = feature.get("control", "")
                
                feature_info = f"- **{feature_name}**"
                if compliance:
                    feature_info += f" (Compliance: {compliance})"
                if control:
                    feature_info += f" (Control: {control})"
                feature_info += f"\n  {description[:200]}..."
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
            for feature in risk_features[:5]:
                feature_name = feature.get("display_name") or feature.get("feature_name", "")
                description = feature.get("description", "")
                question = feature.get("question", "")
                
                risk_info = f"- **{feature_name}**"
                if description:
                    risk_info += f": {description[:150]}"
                if question:
                    risk_info += f"\n  Question: {question[:200]}"
                parts.append(risk_info)
        
        # Extract risk context from reasoning path
        if reasoning_path:
            risk_contexts = []
            for hop in reasoning_path:
                store_results = hop.get("store_results", {})
                risks = store_results.get("risks", [])
                if risks:
                    for risk in risks[:2]:
                        risk_doc = risk.get("document") or risk.get("content", "")
                        if risk_doc:
                            risk_contexts.append(risk_doc[:200])
            
            if risk_contexts:
                parts.append("\n**Risk Context from Reasoning:**")
                for i, context in enumerate(risk_contexts[:3], 1):
                    parts.append(f"{i}. {context}...")
        
        # Extract risk-related controls
        risk_controls = [c for c in controls if "risk" in str(c).lower() or "access" in str(c).lower()]
        if risk_controls:
            parts.append("\n**Risk-Related Controls:**")
            for control in risk_controls[:3]:
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
            for i, feature in enumerate(recommended_features[:10], 1):
                feature_name = feature.get("feature_name", "Unknown")
                question = feature.get("natural_language_question", "")
                feature_type = feature.get("feature_type", "metric")
                purpose = feature.get("purpose", "")
                related_tables = feature.get("related_tables", [])
                
                feature_info = f"{i}. **{feature_name}** ({feature_type})"
                if question:
                    feature_info += f"\n   Question: {question[:200]}"
                if purpose:
                    feature_info += f"\n   Purpose: {purpose[:150]}"
                if related_tables:
                    feature_info += f"\n   Related Tables: {', '.join(related_tables[:5])}"
                parts.append(feature_info)
        
        if evidence_gathering_plan:
            parts.append(f"\n**Evidence Gathering Plan ({len(evidence_gathering_plan)} items):**")
            for i, evidence in enumerate(evidence_gathering_plan[:10], 1):
                evidence_type = evidence.get("evidence_type", "Unknown")
                source_tables = evidence.get("source_tables", [])
                description = evidence.get("description", "")
                priority = evidence.get("priority", "medium")
                
                evidence_info = f"{i}. **{evidence_type}** (Priority: {priority})"
                if description:
                    evidence_info += f"\n   {description[:200]}"
                if source_tables:
                    evidence_info += f"\n   Source Tables: {', '.join(source_tables[:5])}"
                parts.append(evidence_info)
        
        if data_gaps:
            parts.append(f"\n**Data Gaps ({len(data_gaps)}):**")
            for i, gap in enumerate(data_gaps[:5], 1):
                if isinstance(gap, dict):
                    gap_desc = gap.get("description", "") or gap.get("gap", "")
                else:
                    gap_desc = str(gap)
                parts.append(f"{i}. {gap_desc[:200]}")
        
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
                for table_info in high_relevance[:5]:
                    table_name = table_info.get("table_name", "Unknown")
                    relevance = table_info.get("relevance", 0.0)
                    metrics_count = table_info.get("metrics_count", 0)
                    parts.append(f"- {table_name} (relevance: {relevance:.2f}, {metrics_count} metrics)")
        
        if table_insights:
            parts.append(f"\n**Table-Specific Insights:**")
            for insight in table_insights[:5]:
                table_name = insight.get("table_name", "Unknown")
                relevance = insight.get("relevance_to_question", 0.0)
                recommended_metrics = insight.get("recommended_metrics", [])
                insights_text = insight.get("insights", "")
                
                parts.append(f"\n**{table_name}** (relevance: {relevance:.2f}):")
                if insights_text:
                    parts.append(f"  {insights_text[:300]}")
                if recommended_metrics:
                    parts.append(f"  Recommended Metrics ({len(recommended_metrics)}):")
                    for metric in recommended_metrics[:3]:
                        metric_name = metric.get("feature_name", "Unknown")
                        description = metric.get("description", "")
                        parts.append(f"    - {metric_name}: {description[:150]}")
        
        if not parts:
            return "No table-specific reasoning available"
        
        return "\n".join(parts)

