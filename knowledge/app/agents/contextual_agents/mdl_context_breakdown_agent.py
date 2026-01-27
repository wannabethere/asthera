"""
MDL Context Breakdown Agent
Specialized agent for breaking down MDL semantic layer queries.

Handles:
- Tables, relations, metrics, features
- Examples, histories, instructions
- Semantic information, use cases
- MDL edge types (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.)
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
import json

from .base_context_breakdown_agent import BaseContextBreakdownAgent, ContextBreakdown
from app.utils.mdl_prompt_generator import (
    get_mdl_context_breakdown_system_prompt,
    get_mdl_edge_type_semantics,
    get_mdl_schema_category_semantics
)

logger = logging.getLogger(__name__)


class MDLContextBreakdownAgent(BaseContextBreakdownAgent):
    """
    Agent that breaks down MDL semantic layer queries using LLM.
    
    Specializes in:
    - Table queries (schema, model, entity)
    - Relationship queries (joins, references, links)
    - Column queries (fields, attributes, properties)
    - Category queries (groups, types, classifications)
    - Compliance queries (controls, frameworks, audits)
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
        super().__init__(llm, model_name, prompts_file)
        
        # Load MDL-specific semantics
        self.mdl_edge_semantics = get_mdl_edge_type_semantics()
    
    async def _detect_query_type(self, user_question: str) -> Dict[str, Any]:
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
        
        # Detect table names and categories using LLM
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
    
    async def breakdown_question(
        self,
        user_question: str,
        product_name: Optional[str] = None,
        available_frameworks: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        **kwargs
    ) -> ContextBreakdown:
        """
        Break down an MDL semantic layer query using LLM.
        
        Args:
            user_question: User's question about MDL schema
            product_name: Optional product name (Snyk, Cornerstone, etc.)
            available_frameworks: Optional list of available frameworks
            available_products: Optional list of available products
            **kwargs: Additional parameters
            
        Returns:
            ContextBreakdown object with MDL-aware context information
        """
        try:
            # Detect MDL query type
            mdl_detection = await self._detect_query_type(user_question)
            
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
            ])
            
            # Build evidence planning instructions
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
- evidence_types_needed: List of evidence types (e.g., ["table_data", "metrics", "aggregations", "kpis"])
- data_retrieval_plan: List of data retrieval plan objects
- metrics_kpis_needed: List of metric/KPI objects needed
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
                ("human", """Break down this MDL query to identify entities and search questions:

User Question: {user_question}
{mdl_context}
{frameworks_context}
{products_context}

Provide a JSON breakdown with:
- query_type: Type of query (mdl, compliance, policy, risk, product, etc.)
- identified_entities: List of entity names from the available entities
- entity_sub_types: List of sub-types for identified entities
- search_questions: List of search question objects, each with:
  - entity: Entity name
  - question: Natural language search question (HIGH-LEVEL, no specific table/entity names)
  - metadata_filters: Dictionary of metadata filters (use product_name, but avoid specific table/entity filters)
  - response_type: Description of what should be retrieved
{evidence_planning_instructions}

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
            
            result = await chain.ainvoke(prompt_input)
            
            # Log result
            logger.info(f"MDL context breakdown result: {json.dumps(result, indent=2)[:500]}")
            
            # Build ContextBreakdown from result
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type=result.get("query_type", "mdl"),
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
            
            # Store MDL-specific data in metadata
            breakdown.metadata["mdl_detection"] = mdl_detection
            breakdown.search_questions = result.get("search_questions", [])
            
            # Store evidence gathering planning data
            breakdown.evidence_gathering_required = result.get("evidence_gathering_required", False)
            breakdown.evidence_types_needed = result.get("evidence_types_needed", [])
            breakdown.data_retrieval_plan = result.get("data_retrieval_plan", [])
            breakdown.metrics_kpis_needed = result.get("metrics_kpis_needed", [])
            
            logger.info(f"MDL context breakdown: {len(breakdown.identified_entities)} entities, "
                       f"{len(breakdown.search_questions)} search questions")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down MDL question: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type="mdl",
                identified_entities=[]
            )
            breakdown.search_questions = []
            return breakdown
