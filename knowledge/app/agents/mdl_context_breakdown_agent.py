"""
MDL Context Breakdown Agent
LLM-based agent that breaks down MDL semantic layer queries into context components.
"""
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
import json
import json

from app.services.context_breakdown_service import ContextBreakdown
from app.utils.mdl_prompt_generator import (
    get_mdl_context_breakdown_system_prompt,
    get_mdl_edge_type_semantics,
    get_mdl_schema_category_semantics
)

logger = logging.getLogger(__name__)


class MDLContextBreakdownAgent:
    """
    Agent that uses LLM to break down MDL semantic layer queries.
    
    This is an AGENT (uses LLM) that:
    - Analyzes user questions about MDL schemas
    - Detects MDL query types (table, relationship, column, category, compliance)
    - Generates MDL-specific search questions
    - Identifies relevant entities and metadata filters
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the MDL context breakdown agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
        # Load prompts file
        if prompts_file is None:
            base_path = Path(__file__).parent.parent
            prompts_file = base_path / "indexing" / "vector_store_prompts.json"
        
        self.prompts_file = Path(prompts_file)
        self.prompts_data = self._load_prompts()
        
        # Load MDL-specific semantics
        self.mdl_edge_semantics = get_mdl_edge_type_semantics()
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load vector_store_prompts.json"""
        try:
            if self.prompts_file.exists():
                with open(self.prompts_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Prompts file not found: {self.prompts_file}")
                return {}
        except Exception as e:
            logger.error(f"Error loading prompts file: {str(e)}")
            return {}
    
    async def _detect_mdl_query_type(self, user_question: str) -> Dict[str, Any]:
        """
        Detect the type of MDL query from user question.
        
        Returns:
            Dictionary with query_type and detected entities
        """
        question_lower = user_question.lower()
        
        query_type = {
            "is_table_query": any(keyword in question_lower for keyword in [
                "table", "schema", "model", "entity"
            ]),
            "is_relationship_query": any(keyword in question_lower for keyword in [
                "related", "relationship", "join", "belongs", "has many", "references", "linked"
            ]),
            "is_column_query": any(keyword in question_lower for keyword in [
                "column", "field", "attribute", "property"
            ]),
            "is_category_query": any(keyword in question_lower for keyword in [
                "category", "group", "type", "classification"
            ]),
            "is_compliance_query": any(keyword in question_lower for keyword in [
                "compliance", "control", "framework", "soc2", "hipaa", "audit"
            ])
        }
        
        # Detect product name
        detected_products = []
        if "snyk" in question_lower:
            detected_products.append("Snyk")
        if "cornerstone" in question_lower:
            detected_products.append("Cornerstone")
        
        # Detect table names and categories using LLM (replaces regex CamelCase detection)
        potential_tables, potential_categories = await self._detect_tables_and_categories(user_question)
        
        return {
            "query_type": query_type,
            "detected_products": detected_products,
            "potential_tables": potential_tables,
            "potential_categories": potential_categories
        }
    
    async def _detect_tables_and_categories(
        self,
        user_question: str
    ) -> tuple[List[str], List[str]]:
        """
        Use LLM to detect table names and map them to categories.
        Replaces regex-based CamelCase detection with intelligent LLM analysis.
        
        Args:
            user_question: The user question to analyze
            
        Returns:
            Tuple of (potential_tables, potential_categories)
        """
        try:
            prompt = f"""You are a database expert. Analyze the following question and identify:
1. Potential database table names mentioned (e.g., "AccessRequest", "user_access", "assets table")
2. Data categories/types that are referenced (e.g., "access requests", "assets", "vulnerabilities")

Question: {user_question}

Instructions:
1. Identify table names that are EXPLICITLY mentioned (CamelCase, snake_case, or with "table" keyword)
2. Identify IMPLICIT table references through data categories (e.g., "user access data" -> "access requests" category)
3. Map identified tables to appropriate categories
4. Be conservative - only include clear references
5. Return a JSON object with:
   - "potential_tables": array of table names found
   - "potential_categories": array of data categories/types identified

Example:
Question: "What tables contain user access data for assets?"
Response:
{{
  "potential_tables": ["AccessRequest", "UserAccess", "assets"],
  "potential_categories": ["access requests", "user access", "assets"]
}}

Return ONLY a JSON object:"""

            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                potential_tables = result.get("potential_tables", [])
                potential_categories = result.get("potential_categories", [])
                logger.info(f"MDLContextBreakdownAgent: LLM detected {len(potential_tables)} tables and {len(potential_categories)} categories")
                return potential_tables, potential_categories
            else:
                logger.warning(f"MDLContextBreakdownAgent: Could not parse LLM response: {response_text[:200]}")
                return [], []
                
        except Exception as e:
            logger.warning(f"MDLContextBreakdownAgent: Error detecting tables/categories with LLM: {e}. Returning empty lists.")
            return [], []
    
    async def breakdown_mdl_question(
        self,
        user_question: str,
        product_name: Optional[str] = None,
        available_frameworks: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None
    ) -> ContextBreakdown:
        """
        Break down an MDL semantic layer query using LLM.
        
        This is the main AGENT method that uses LLM to:
        1. Analyze the question
        2. Detect MDL query types
        3. Generate search questions
        4. Identify entities and filters
        
        Args:
            user_question: User's question about MDL schema
            product_name: Optional product name (Snyk, Cornerstone, etc.)
            available_frameworks: Optional list of available frameworks
            available_products: Optional list of available products
            
        Returns:
            ContextBreakdown object with MDL-aware context information
        """
        try:
            # Detect MDL query type
            mdl_detection = await self._detect_mdl_query_type(user_question)
            
            # Get MDL-specific system prompt
            mdl_system_prompt = get_mdl_context_breakdown_system_prompt(
                prompts_file=str(self.prompts_file) if self.prompts_file else None,
                include_examples=True
            )
            
            # Build context for prompt
            frameworks_context = ""
            if available_frameworks:
                frameworks_context = f"\n\nAvailable frameworks: {', '.join(available_frameworks)}"
            
            products_context = ""
            if available_products:
                products_context = f"\n\nAvailable products: {', '.join(available_products)}"
            elif product_name:
                products_context = f"\n\nProduct context: {product_name}"
            
            # Add MDL detection results
            potential_categories = mdl_detection.get('potential_categories', [])
            mdl_context = f"""
MDL Query Detection:
- Is table query: {mdl_detection['query_type']['is_table_query']}
- Is relationship query: {mdl_detection['query_type']['is_relationship_query']}
- Is column query: {mdl_detection['query_type']['is_column_query']}
- Is category query: {mdl_detection['query_type']['is_category_query']}
- Is compliance query: {mdl_detection['query_type']['is_compliance_query']}
- Detected products: {', '.join(mdl_detection['detected_products']) if mdl_detection['detected_products'] else 'None'}
- Potential tables: {', '.join(mdl_detection['potential_tables']) if mdl_detection['potential_tables'] else 'None'}
- Potential categories: {', '.join(potential_categories) if potential_categories else 'None'}
"""
            
            # Detect if this is an evidence gathering query
            question_lower = user_question.lower()
            is_evidence_query = any(keyword in question_lower for keyword in [
                "why", "how", "evidence", "gather", "collect", "analyze", "investigate",
                "having", "high", "low", "failing", "passing", "compliance", "control"
            ]) or any(phrase in question_lower for phrase in [
                "why my", "why are", "why is", "why do", "why does",
                "gather evidence", "collect evidence", "find evidence"
            ])
            
            # Build prompt
            # Use SystemMessage to avoid template parsing of the system prompt
            evidence_planning_instructions = ""
            if is_evidence_query:
                evidence_planning_instructions = """

EVIDENCE GATHERING PLANNING (REQUIRED for this query):
This query requires evidence gathering for compliance/risk analysis. You MUST plan for:
1. What types of evidence are needed (tables, metrics, KPIs, aggregations)
2. What data needs to be retrieved to support evidence gathering
3. What metrics/KPIs/aggregations are needed to answer the question
4. What tables contain the evidence

Add to your JSON breakdown:
- evidence_gathering_required: true
- evidence_types_needed: List of evidence types (e.g., ["table_data", "metrics", "aggregations", "kpis", "user_activity", "access_control", "compliance_metrics"])
- data_retrieval_plan: List of data retrieval plan objects, each with:
  - data_type: Type of data to retrieve (e.g., "table_schemas", "existing_metrics", "compliance_controls", "table_data_samples")
  - purpose: Why this data is needed for evidence gathering
  - priority: Priority level (high/medium/low)
  - expected_tables: List of table names or categories expected (e.g., ["access_requests", "user_activity", "audit_logs"])
- metrics_kpis_needed: List of metric/KPI objects needed for evidence, each with:
  - metric_type: Type of metric (e.g., "count", "percentage", "aggregation", "calculation")
  - purpose: What this metric helps prove or measure
  - related_tables: List of table categories or types that would contain this metric
  - natural_language_question: Natural language question describing what needs to be calculated

CRITICAL: The data_retrieval_plan must match what will actually be retrieved. Be specific about:
- Which table categories/types are needed (e.g., "access_requests", "user_activity", "audit_logs")
- What types of metrics are needed (e.g., "count of access requests", "percentage of failed access attempts")
- What compliance controls are relevant (if applicable)

Example for "why my assets are having a soc 2 control for user access high":
  * evidence_gathering_required: true
  * evidence_types_needed: ["table_data", "metrics", "aggregations", "access_control", "user_activity"]
  * data_retrieval_plan: [
      {{"data_type": "table_schemas", "purpose": "Identify tables with user access data", "priority": "high", "expected_tables": ["access_requests", "user_activity", "audit_logs"]}},
      {{"data_type": "existing_metrics", "purpose": "Find existing metrics for access control", "priority": "high", "expected_tables": ["access_requests"]}},
      {{"data_type": "compliance_controls", "purpose": "Get SOC2 user access control requirements", "priority": "high", "expected_tables": []}}
    ]
  * metrics_kpis_needed: [
      {{"metric_type": "count", "purpose": "Count total access requests", "related_tables": ["access_requests"], "natural_language_question": "How many access requests are there?"}},
      {{"metric_type": "percentage", "purpose": "Calculate percentage of failed access attempts", "related_tables": ["access_requests"], "natural_language_question": "What percentage of access requests are denied or failed?"}}
    ]
"""
            else:
                evidence_planning_instructions = """
- evidence_gathering_required: false
- evidence_types_needed: []
- data_retrieval_plan: []
- metrics_kpis_needed: []
"""
            
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=mdl_system_prompt),
                ("human", """Break down this query to identify what TYPE of entity it is asking about:

User Question: {user_question}
{mdl_context}
{frameworks_context}
{products_context}

Provide a JSON breakdown with:
- query_type: Type of query (e.g., "mdl", "compliance", "policy", "risk", "product", etc.)
- identified_entities: List of entity names from the available entities
- entity_sub_types: List of sub-types for identified entities
- search_questions: List of search question objects, each with:
  - entity: Entity name
  - question: Natural language search question (HIGH-LEVEL, no specific table/entity names)
  - metadata_filters: Dictionary of metadata filters (use product_name, but avoid specific table/entity filters)
  - response_type: Description of what should be retrieved
{evidence_planning_instructions}

CRITICAL FIRST BREAKDOWN RULE: This is the FIRST breakdown - identify the QUERY TYPE and generate HIGH-LEVEL search questions:
- DO identify what type of query this is (mdl, compliance, policy, risk, product, etc.)
- DO NOT use specific table names, entity IDs, or context_ids in filters
- DO NOT use specific source_entity_id or target_entity_id in filters
- DO use high-level discovery questions like "What types of tables are available for X in Y?"
- DO use product_name filters
- DO use "categories" filter when relevant semantic categories are identified from the question:
  * Available categories: "access requests", "assets", "projects", "vulnerabilities", "integrations", 
    "configuration", "audit logs", "risk management", "deployment", "groups", "organizations", 
    "memberships and roles", "issues", "artifacts", "application data", "user management", "security"
  * Categories are NOW INDEXED and can be used for filtering
- DO use generic entity stores (table_descriptions, contextual_edges, compliance_controls, etc.)
- Example: For "What are the relationships from AccessRequest table to other tables in Snyk?"
  * query_type: "mdl"
  * Entity: "table_descriptions" with question: "What types of tables are available for access requests in Snyk?"
  * Entity: "contextual_edges" with question: "What table relationships exist in Snyk?"
  * Filters: {{"product_name": "Snyk", "categories": ["access requests"]}}

The MDL-specific rules and detailed filters will be used in the SECOND step (MDL retrieval queries) if query_type is "mdl".

Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Prepare input for logging
            prompt_input = {
                "user_question": user_question,
                "mdl_context": mdl_context,
                "frameworks_context": frameworks_context,
                "products_context": products_context
            }
            
            # Log full prompt without truncation
            logger.info("=" * 80)
            logger.info("MDLContextBreakdownAgent: Full LLM Prompt (NO TRUNCATION)")
            logger.info("=" * 80)
            # Format prompt to get actual content
            try:
                formatted_messages = prompt.format_messages(**prompt_input)
                logger.info(f"System Prompt:\n{formatted_messages[0].content}")
                logger.info(f"Human Prompt:\n{formatted_messages[1].content}")
            except Exception as e:
                logger.warning(f"Could not format prompt for logging: {e}")
                logger.info(f"System Prompt Template: {prompt.messages[0]}")
                logger.info(f"Human Prompt Template: {prompt.messages[1]}")
            logger.info(f"Prompt Variables:")
            for key, value in prompt_input.items():
                logger.info(f"  {key}:")
                logger.info(f"    {value}")
            logger.info("=" * 80)
            
            result = await chain.ainvoke(prompt_input)
            
            # Log full LLM response without truncation
            logger.info("=" * 80)
            logger.info("MDLContextBreakdownAgent: Full LLM Response (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
            logger.info("=" * 80)
            
            # Build ContextBreakdown from result
            breakdown = ContextBreakdown(
                user_question=user_question,
                compliance_context=result.get("compliance_context"),
                action_context=result.get("action_context"),
                product_context=product_name or result.get("product_context"),
                user_intent=result.get("user_intent"),
                frameworks=result.get("frameworks", []),
                entity_types=result.get("entity_types", []),
                edge_types=result.get("edge_types", []),
                query_keywords=result.get("query_keywords", []),
                identified_entities=result.get("identified_entities", []),
                entity_sub_types=result.get("entity_sub_types", [])
            )
            
            # Store MDL-specific data
            breakdown.mdl_detection = mdl_detection
            breakdown.search_questions = result.get("search_questions", [])
            breakdown.query_type = result.get("query_type", "unknown")  # Store query type (mdl, compliance, etc.)
            
            # Store evidence gathering planning data
            breakdown.evidence_gathering_required = result.get("evidence_gathering_required", False)
            breakdown.evidence_types_needed = result.get("evidence_types_needed", [])
            breakdown.data_retrieval_plan = result.get("data_retrieval_plan", [])
            breakdown.metrics_kpis_needed = result.get("metrics_kpis_needed", [])
            
            logger.info(f"MDL context breakdown: {len(breakdown.identified_entities)} entities, {len(breakdown.search_questions)} search questions")
            if breakdown.evidence_gathering_required:
                logger.info(f"Evidence gathering required: {len(breakdown.evidence_types_needed)} evidence types, "
                           f"{len(breakdown.data_retrieval_plan)} data retrieval items, "
                           f"{len(breakdown.metrics_kpis_needed)} metrics/KPIs needed")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down MDL question: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            breakdown = ContextBreakdown(
                user_question=user_question,
                identified_entities=[]
            )
            # Set search_questions as attribute (not in __init__)
            breakdown.search_questions = []
            return breakdown

