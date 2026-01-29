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

from app.agents.contextual_agents.base_context_breakdown_agent import BaseContextBreakdownAgent, ContextBreakdown
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
        
        # Cache for schema categories by product
        self._category_cache = {}
    
    def _get_schema_categories(self, product_name: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Get available schema categories for a product.
        
        Args:
            product_name: Product name (Snyk, Cornerstone, etc.)
            
        Returns:
            List of category dictionaries with name and description
        """
        if not product_name:
            return []
        
        # Check cache first
        if product_name in self._category_cache:
            return self._category_cache[product_name]
        
        # Get categories from mdl_prompt_generator
        category_semantics = get_mdl_schema_category_semantics(product_name)
        
        categories = []
        for category_name, category_info in category_semantics.items():
            categories.append({
                "name": category_name,
                "description": category_info.get("description", ""),
                "semantic_meaning": category_info.get("semantic_meaning", "")
            })
        
        # Cache the result
        self._category_cache[product_name] = categories
        
        return categories
    
    def _format_categories_for_prompt(self, categories: List[Dict[str, str]]) -> str:
        """
        Format categories for inclusion in prompt.
        
        Args:
            categories: List of category dictionaries
            
        Returns:
            Formatted string for prompt
        """
        if not categories:
            return "No categories available for this product."
        
        formatted = "\n".join([
            f"{i+1}. **{cat['name']}** - {cat['description']}"
            for i, cat in enumerate(categories)
        ])
        
        return formatted
    
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
            # Check if this is a table listing/discovery query
            question_lower = user_question.lower()
            is_listing_query = any(phrase in question_lower for phrase in [
                "what tables", "which tables", "tables for", "list tables", 
                "show tables", "all tables", "tables related to", "tables about"
            ])
            
            listing_context = ""
            if is_listing_query:
                listing_context = """
IMPORTANT: This is a TABLE LISTING/DISCOVERY query. The user wants to find ALL tables related to a concept.
- Extract the concept/category they're asking about (e.g., "Assets", "Access", "Projects")
- Add this concept to potential_categories so we can search for ALL tables matching this pattern
- Be LIBERAL in identifying the category - this is for pattern matching, not specific table references
"""
            
            prompt = f"""You are a database expert. Analyze the following question and identify:
1. Potential database table names mentioned (e.g., "AccessRequest", "user_access", "assets table")
2. Data categories/types that are referenced (e.g., "access requests", "assets", "vulnerabilities")

{listing_context}
Question: {user_question}

Instructions:
1. Identify table names that are EXPLICITLY mentioned (CamelCase, snake_case, or with "table" keyword)
2. Identify IMPLICIT table references through data categories (e.g., "user access data" -> "access requests" category)
3. For table listing queries ("What tables for X?"), extract the concept X as a category for pattern matching
4. Map identified tables to appropriate categories
5. Return a JSON object with:
   - "potential_tables": array of table names found (empty if this is a discovery query)
   - "potential_categories": array of data categories/types identified (be liberal for listing queries)
   - "is_table_listing_query": boolean indicating if this is asking for a list of tables

Examples:

Question: "What are the Tables for Assets?"
Response:
{{
  "potential_tables": [],
  "potential_categories": ["assets", "asset"],
  "is_table_listing_query": true
}}

Question: "What tables contain user access data for assets?"
Response:
{{
  "potential_tables": [],
  "potential_categories": ["user access", "access", "assets", "asset"],
  "is_table_listing_query": true
}}

Question: "Show me the columns in the AccessRequest table"
Response:
{{
  "potential_tables": ["AccessRequest"],
  "potential_categories": ["access requests"],
  "is_table_listing_query": false
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
                is_table_listing = result.get("is_table_listing_query", is_listing_query)
                
                logger.info(f"MDLContextBreakdownAgent: LLM detected {len(potential_tables)} tables, "
                           f"{len(potential_categories)} categories, is_listing={is_table_listing}")
                
                # Store listing query flag for later use
                if not hasattr(self, '_query_metadata'):
                    self._query_metadata = {}
                self._query_metadata['is_table_listing_query'] = is_table_listing
                
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
            
            # Get schema categories for the product
            schema_categories = self._get_schema_categories(product_name)
            categories_formatted = self._format_categories_for_prompt(schema_categories)
            
            # Build context for prompt
            frameworks_context = ""
            if available_frameworks:
                frameworks_context = f"\n\nAvailable frameworks: {', '.join(available_frameworks)}"
            
            products_context = ""
            if available_products:
                products_context = f"\n\nAvailable products: {', '.join(available_products)}"
            elif product_name:
                products_context = f"\n\nProduct context: {product_name}"
            
            # Add available categories
            categories_context = f"""

Available Categories for {product_name or 'product'}:
{categories_formatted}

CRITICAL: When generating search questions or data_retrieval_plan, use ONLY the categories listed above.
These are DATABASE TABLE categories, not compliance or policy concepts."""
            
            # Add MDL detection results
            potential_categories = mdl_detection.get('potential_categories', [])
            is_table_listing = getattr(self, '_query_metadata', {}).get('is_table_listing_query', False)
            
            mdl_context = f"""
MDL Query Detection:
- Is table query: {mdl_detection['query_type']['is_table_query']}
- Is table listing query: {is_table_listing}
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
            
            # Build table listing instructions with category-based approach
            if is_table_listing:
                # Map detected categories to available categories
                matching_categories = []
                for pot_cat in potential_categories:
                    pot_cat_lower = pot_cat.lower()
                    for schema_cat in schema_categories:
                        cat_name = schema_cat['name'].lower()
                        if pot_cat_lower in cat_name or cat_name in pot_cat_lower:
                            matching_categories.append(schema_cat['name'])
                            break
                
                if matching_categories:
                    categories_str = ', '.join(matching_categories)
                else:
                    categories_str = ', '.join(potential_categories) if potential_categories else 'identified concept'
                
                table_listing_instructions = f"""

TABLE LISTING QUERY DETECTED - CATEGORY-BASED MDL QUERY REQUIRED:
This query is asking for a LIST of ALL tables related to: {categories_str}

CRITICAL: For table listing queries, you MUST generate data_retrieval_plan with category-based MDL queries:

1. **Generate data_retrieval_plan** with one entry per category:
   - data_type: "database_schemas" (ONLY available data source)
   - category: Use EXACT category name from Available Categories list (e.g., "assets", "access requests")
   - purpose: Why this category is needed
   - priority: "high" for main categories, "medium" for supporting ones

2. **MDL Query Format** (will be auto-generated from data_retrieval_plan):
   - Format: "what are [category] related tables? category: [category]"
   - Example: "what are asset related tables? category: assets"
   - Example: "what are access request related tables? category: access requests"

3. **DO NOT create search_questions for table listing** - Use data_retrieval_plan instead

4. **Set evidence_gathering_required: false** for simple table listing (no metrics needed)

Example for "What are the Tables for Assets?":
{{
  "query_type": "mdl",
  "identified_entities": ["table_descriptions", "schema_descriptions"],
  "evidence_gathering_required": false,
  "data_retrieval_plan": [
    {{
      "data_type": "database_schemas",
      "category": "assets",
      "purpose": "Find all asset-related tables",
      "priority": "high"
    }}
  ],
  "search_questions": []
}}
"""
            else:
                table_listing_instructions = ""
            
            # Build evidence planning instructions with category-based approach
            evidence_planning_instructions = ""
            if is_evidence_query:
                evidence_planning_instructions = f"""

EVIDENCE GATHERING PLANNING (REQUIRED for this query):
This query requires evidence gathering for compliance/risk analysis. You MUST plan for:
1. What database schemas are needed (ONLY database schemas - these are the only available data sources)
2. What categories of tables are relevant (use the available categories from the list provided)
3. What metrics/KPIs need to be calculated from the database tables

CRITICAL REQUIREMENTS:
- ONLY generate queries for DATABASE SCHEMAS - no other data sources are available
- Use EXACTLY the categories from the Available Categories list shown above - DO NOT invent new categories
- Categories are DATABASE TABLE CATEGORIES ONLY (e.g., "assets", "access requests", "vulnerabilities")
- DO NOT use compliance/policy concepts as categories (e.g., "soc2 controls", "compliance controls", "policies")
- If the question mentions compliance/SOC2/policies, map it to the DATABASE TABLE categories that contain relevant data
- MDL queries MUST be GENERIC and category-based, NOT specific table names
- Format for MDL queries (auto-generated from data_retrieval_plan): "what are [category] related tables? category: [category]"

Add to your JSON breakdown:
- evidence_gathering_required: true
- evidence_types_needed: MUST ONLY include ["database_schemas"] - no other data types are available
- data_retrieval_plan: List of data retrieval plan objects, each with:
  - data_type: MUST be "database_schemas" (ONLY database schemas available)
  - category: The category name from available categories (e.g., "assets", "access requests", "vulnerabilities")
  - purpose: Why this category of tables is needed for evidence gathering
  - priority: Priority level (high/medium/low)
- metrics_kpis_needed: List of metric/KPI objects needed for evidence, each with:
  - metric_type: Type of metric (e.g., "count", "percentage", "aggregation", "calculation")
  - purpose: What this metric helps prove or measure
  - related_categories: List of table categories that would contain this metric (use category names from available categories)
  - natural_language_question: Natural language question describing what needs to be calculated

Example for "why my assets are having a soc 2 control for user access high":
{{
  "evidence_gathering_required": true,
  "evidence_types_needed": ["database_schemas"],
  "data_retrieval_plan": [
    {{"data_type": "database_schemas", "category": "assets", "purpose": "Find asset related tables to identify which assets have access controls", "priority": "high"}},
    {{"data_type": "database_schemas", "category": "access requests", "purpose": "Find access request tables to analyze user access patterns", "priority": "high"}},
    {{"data_type": "database_schemas", "category": "audit logs", "purpose": "Find audit log tables to track access control changes", "priority": "medium"}}
  ],
  "metrics_kpis_needed": [
    {{"metric_type": "count", "purpose": "Count high-priority access control findings for assets", "related_categories": ["assets", "access requests"], "natural_language_question": "How many assets have high-priority access control issues?"}},
    {{"metric_type": "percentage", "purpose": "Calculate percentage of assets failing SOC2 access controls", "related_categories": ["assets", "access requests"], "natural_language_question": "What percentage of assets are failing SOC2 user access controls?"}}
  ]
}}
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
                ("human", """Break down this MDL query to identify entities and create a retrieval plan:

User Question: {user_question}
{mdl_context}
{frameworks_context}
{products_context}
{categories_context}
{table_listing_instructions}

Provide a JSON breakdown with:
- query_type: Type of query (mdl, compliance, policy, risk, product, etc.)
- identified_entities: List of entity names from the available entities (use "table_descriptions", "schema_descriptions" for MDL queries)
- entity_sub_types: List of sub-types for identified entities

FOR MDL TABLE QUERIES (when query_type is "mdl"):
- Use data_retrieval_plan for category-based table discovery (REQUIRED for MDL queries)
- data_retrieval_plan: List of retrieval plan objects, each with:
  - data_type: "database_schemas" (ONLY available data source)
  - category: Exact category name from Available Categories list
  - purpose: Why this category is needed
  - priority: "high", "medium", or "low"
- search_questions: EMPTY array for category-based MDL queries (use data_retrieval_plan instead)

FOR NON-MDL QUERIES:
- search_questions: List of search question objects, each with:
  - entity: Entity name
  - question: Natural language search question
  - metadata_filters: Dictionary of metadata filters
  - response_type: Description of what should be retrieved
- data_retrieval_plan: EMPTY array

{evidence_planning_instructions}

Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Prepare input for logging
            prompt_input = {
                "user_question": user_question,
                "mdl_context": mdl_context,
                "frameworks_context": frameworks_context,
                "products_context": products_context,
                "categories_context": categories_context,
                "table_listing_instructions": table_listing_instructions,
                "evidence_planning_instructions": evidence_planning_instructions
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
