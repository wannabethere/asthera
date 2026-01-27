"""
MDL Reasoning and Planning Graph

This module contains:
1. Node functions for the MDL reasoning graph workflow
2. Graph builder to create and compile the LangGraph workflow

Each node performs a specific function:
1. Context Breakdown - Breaks down user question using MDL context breakdown agent
2. Entity Identification - Identifies tables and entities from breakdown
3. Context Retrieval - Retrieves contexts and edges from contextual graph
4. Planning - Creates reasoning plan for product, controls, risks, metrics
"""
import logging
import json
import re
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END

from app.agents.mdl_reasoning_state import MDLReasoningState
from app.agents.mdl_table_retrieval_agent import MDLTableRetrievalAgent
from app.agents.data.mdl_semantic_retriever import MDLSemanticRetriever
from app.services.mdl_semantic_layer_service import MDLSemanticLayerService
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.services.context_breakdown_service import ContextBreakdownService
from app.storage.query.collection_factory import CollectionFactory
from app.utils.prompt_generator import get_context_breakdown_system_prompt

logger = logging.getLogger(__name__)

# Product-specific category configurations
# For Snyk product categories, see: @FINAL_CATEGORIES.md (9-23)
PRODUCT_CATEGORIES = {
    "Snyk": [
        "1. **access requests** - Access request management tables",
        "2. **application data** - Application data and resource tables",
        "3. **assets** - Asset management tables (Asset* pattern)",
        "4. **projects** - Project management tables (Project* pattern)",
        "5. **vulnerabilities** - Vulnerability and finding tables",
        "6. **integrations** - Integration and broker connection tables",
        "7. **configuration** - Configuration and settings tables",
        "8. **audit logs** - Audit log and catalog progress tables",
        "9. **risk management** - Risk assessment and management tables (Risk* pattern)",
        "10. **deployment** - Deployment process tables",
        "11. **groups** - Group management and policy tables (Group* pattern)",
        "12. **organizations** - Organization management tables (Org* pattern)",
        "13. **memberships and roles** - Membership and role management tables (Membership*, Role* patterns)",
        "14. **issues** - Issue tracking and management tables (Issue*, Issues* patterns)",
        "15. **artifacts** - Artifact repository tables (Artifact* pattern)",
    ]
}


def get_product_categories(product_name: Optional[str] = None) -> List[str]:
    """
    Get the list of available categories for a given product.
    
    For Snyk categories, see: @FINAL_CATEGORIES.md (9-23)
    
    Args:
        product_name: Name of the product (e.g., "Snyk"). If None, returns empty list.
        
    Returns:
        List of category names for the product, or empty list if product not found.
    """
    if not product_name:
        return []
    
    return PRODUCT_CATEGORIES.get(product_name, [])


def safe_parse_llm_response(result: Any, expected_fields: Dict[str, type]) -> Dict[str, Any]:
    """
    Safely parse and validate LLM JSON response, ensuring correct types and formats.
    
    Args:
        result: Raw result from LLM/JSON parser
        expected_fields: Dict mapping field names to expected types (list, dict, str, etc.)
        
    Returns:
        Validated and normalized dictionary
    """
    if not isinstance(result, dict):
        logger.warning(f"safe_parse_llm_response: Result is not a dict (type: {type(result)}), converting")
        if isinstance(result, str):
            try:
                import json
                result = json.loads(result)
            except:
                logger.error(f"safe_parse_llm_response: Failed to parse string as JSON")
                return {}
        else:
            return {}
    
    validated = {}
    for field_name, expected_type in expected_fields.items():
        value = result.get(field_name)
        
        if value is None:
            # Use default based on type
            if expected_type == list:
                validated[field_name] = []
            elif expected_type == dict:
                validated[field_name] = {}
            else:
                validated[field_name] = None
            continue
        
        # Validate and normalize based on expected type
        if expected_type == list:
            validated[field_name] = normalize_string_list(value, field_name)
        elif expected_type == dict:
            if isinstance(value, dict):
                validated[field_name] = value
            elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                # List of dicts - take first one or merge
                validated[field_name] = value[0] if len(value) == 1 else {}
                logger.warning(f"safe_parse_llm_response: {field_name} was a list, using first dict")
            else:
                logger.warning(f"safe_parse_llm_response: {field_name} expected dict, got {type(value)}, using empty dict")
                validated[field_name] = {}
        elif expected_type == str:
            if isinstance(value, str):
                validated[field_name] = value
            elif isinstance(value, list) and len(value) > 0:
                # Might be a character array - reconstruct
                if all(isinstance(e, str) and len(e) == 1 for e in value):
                    validated[field_name] = ''.join(value)
                    logger.warning(f"safe_parse_llm_response: {field_name} was character array, reconstructed")
                else:
                    validated[field_name] = str(value[0]) if value else ""
            else:
                validated[field_name] = str(value) if value else ""
        else:
            validated[field_name] = value
    
    return validated


def normalize_string_list(value, field_name="list"):
    """
    Normalize a value that should be a list of strings, handling cases where:
    - It's a string (convert to single-item list)
    - It's a list of single characters (reconstruct string, then convert to list)
    - It's a list with mixed content (filter out single characters)
    
    Args:
        value: The value to normalize
        field_name: Name of the field for logging
        
    Returns:
        Normalized list of strings
    """
    if isinstance(value, str):
        return [value]
    elif isinstance(value, list):
        if len(value) == 0:
            return []
        # Check if this is a list of single characters (indicating a string was incorrectly split)
        if all(isinstance(e, str) and len(e.strip()) == 1 for e in value if e):
            # Reconstruct the original string
            reconstructed = ''.join([str(e) for e in value if e])
            logger.warning(f"normalize_string_list: {field_name} was incorrectly split into characters, reconstructed as '{reconstructed[:100]}...'")
            return [reconstructed]
        else:
            # Filter to ensure all items are strings and meaningful (not single characters)
            normalized = []
            for item in value:
                if isinstance(item, str) and len(item.strip()) > 1:
                    normalized.append(item.strip())
                elif item and not (isinstance(item, str) and len(item.strip()) == 1):
                    item_str = str(item).strip()
                    if len(item_str) > 1:
                        normalized.append(item_str)
            return normalized
    else:
        return []


class GenericContextBreakdownNode:
    """Node that breaks down user question using generic context breakdown (identifies data sources)"""
    
    def __init__(
        self,
        context_breakdown_service: ContextBreakdownService,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.context_breakdown_service = context_breakdown_service
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Break down user question to identify query type and data sources using prompt_generator.py rules"""
        logger.info("GenericContextBreakdownNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name")
        
        if not user_question:
            logger.error("GenericContextBreakdownNode: No user question provided")
            state["status"] = "error"
            state["error"] = "No user question provided"
            return state
        
        try:
            # Get available categories for the product
            available_categories = get_product_categories(product_name)
            categories_text = "\n".join(available_categories) if available_categories else "No categories available"
            
            logger.info(f"GenericContextBreakdownNode: Using {len(available_categories)} categories for product {product_name}")
            
            # Detect if this is an evidence gathering query
            question_lower = user_question.lower()
            is_evidence_query = any(keyword in question_lower for keyword in [
                "why", "how", "evidence", "gather", "collect", "analyze", "investigate",
                "having", "high", "low", "failing", "passing", "compliance", "control"
            ]) or any(phrase in question_lower for phrase in [
                "why my", "why are", "why is", "why do", "why does",
                "gather evidence", "collect evidence", "find evidence"
            ])
            
            # Get generic system prompt from prompt_generator.py
            system_prompt = get_context_breakdown_system_prompt(include_examples=True)
            
            # Build evidence planning instructions
            evidence_planning_instructions = ""
            if is_evidence_query:
                evidence_planning_instructions = """

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
- Format: "what are [category name] related tables? category: [category name]"
- Example: "what are asset related tables? category: assets"

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

CRITICAL PLANNING RULES:
1. **Use ONLY Available Database Table Categories**: You MUST map entities in the question to DATABASE TABLE categories from the available categories list above
   - Categories are for DATABASE TABLES ONLY - never use compliance/policy concepts as categories
   - Example: "assets" → use "assets" category (correct - it's a database table category)
   - Example: "user access" → use "access requests" category (correct - it's a database table category)
   - Example: "vulnerabilities" → use "vulnerabilities" category (correct - it's a database table category)
   - Example: "SOC2 controls" → DO NOT use "soc2 controls" as category! Instead, map to relevant database categories like "access requests", "audit logs", "configuration"
   - Example: "compliance controls" → DO NOT use as category! Map to database table categories that contain compliance-relevant data

2. **Create Separate Plan Items Per Category**: For each relevant DATABASE TABLE category, create a separate data_retrieval_plan item
   
3. **Generic Category-Based Queries**: Each plan item should reference the DATABASE TABLE CATEGORY, not specific table names or compliance concepts

Example for "why my assets are having a soc 2 control for user access high":
  * evidence_gathering_required: true
  * evidence_types_needed: ["database_schemas"]
  * data_retrieval_plan: [
      {{"data_type": "database_schemas", "category": "assets", "purpose": "Find asset-related tables to identify which assets have access controls", "priority": "high"}},
      {{"data_type": "database_schemas", "category": "access requests", "purpose": "Find access request tables to analyze user access patterns", "priority": "high"}},
      {{"data_type": "database_schemas", "category": "audit logs", "purpose": "Find audit log tables to track access control changes", "priority": "medium"}}
    ]
  * metrics_kpis_needed: [
      {{"metric_type": "count", "purpose": "Count high-priority access control findings for assets", "related_categories": ["assets", "access requests"], "natural_language_question": "How many assets have high-priority access control issues?"}},
      {{"metric_type": "percentage", "purpose": "Calculate percentage of assets failing SOC2 access controls", "related_categories": ["assets", "access requests"], "natural_language_question": "What percentage of assets are failing SOC2 user access controls?"}}
    ]
"""
            else:
                evidence_planning_instructions = """
- evidence_gathering_required: false
- evidence_types_needed: []
- data_retrieval_plan: []
- metrics_kpis_needed: []

FOR MDL QUERIES (if query_type is "mdl"):
If the query is about database tables/schemas, you MUST generate mdl_queries using the available DATABASE TABLE categories.

CRITICAL MDL QUERY REQUIREMENTS:
- Use ONLY the DATABASE TABLE CATEGORIES from the Available Categories list shown above
- DO NOT use compliance/policy concepts as categories (e.g., "soc2 controls", "compliance controls")
- Map compliance/policy mentions to relevant DATABASE TABLE categories (e.g., "access requests", "audit logs")
- MDL queries MUST be GENERIC and category-based, NOT specific table names
- Format: "what are [category name] related tables? category: [category name]"
- Set the "type" field to the DATABASE TABLE category name

Example for "What tables are related to user access request?":
  * mdl_queries: [
      {{"query": "what are access request related tables? category: access requests", "type": "access requests", "execution_order": 1, "depends_on": [], "required_context": "", "can_parallelize": true}}
    ]

Example for "What tables are related to user access request and their soc2 compliance controls?":
  * mdl_queries: [
      {{"query": "what are access request related tables? category: access requests", "type": "access requests", "execution_order": 1, "depends_on": [], "required_context": "", "can_parallelize": true}},
      {{"query": "what are audit log related tables? category: audit logs", "type": "audit logs", "execution_order": 2, "depends_on": [], "required_context": "", "can_parallelize": true}}
    ]
  * NOTE: "soc2 compliance controls" is NOT a database table category. We map it to relevant database categories like "access requests" and "audit logs" that contain compliance-relevant data.
"""
            
            # Build prompt using prompt_generator.py rules
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", """Break down this query to identify what TYPE of query it is, what data sources are needed, and PLAN the execution order with dependencies:

User Question: {user_question}
Product: {product_name}

Available DATABASE TABLE Categories for {product_name}:
{categories_text}

CRITICAL CATEGORY RULES:
- The categories above are DATABASE TABLE CATEGORIES ONLY (e.g., "assets", "access requests", "vulnerabilities")
- You MUST use ONLY these exact categories when generating MDL queries
- DO NOT invent new categories or use compliance/policy concepts as categories
- If the question mentions "SOC2", "compliance controls", "policies", "risk controls" → these are NOT categories
- Instead, map them to the relevant DATABASE TABLE categories above (e.g., "access requests", "audit logs", "configuration")
- Database schemas are the ONLY data source available - no other data types exist

Provide a JSON breakdown with:
- query_type: Type of query - MUST be determined from the question AND identified entities:
  
  CRITICAL DECISION RULES:
  * If the question asks about TABLES, SCHEMAS, DATABASE, COLUMNS → query_type MUST be "mdl"
    - Keywords: "tables", "schema", "database", "columns", "table structure", "what tables", "which tables"
    - Entities: table_definitions, table_descriptions, column_definitions, schema_descriptions, db_schema, category_mapping
    - Example: "What tables are related to X?" → query_type="mdl"
    - Example: "Which tables contain Y data?" → query_type="mdl"
  
  * POLICY entities → "policy" (NOT mdl, NOT available)
    - Entities: policy_documents, policy_entities, policy_evidence, policy_fields
  * RISK entities → "risk_control" (NOT mdl, NOT available)
    - Entities: risk_controls, risk_entities, risk_evidence, risk_fields
  * COMPLIANCE entities → "compliance_framework" (NOT mdl, NOT available)
    - Entities: compliance_controls
  * PRODUCT entities → "product" (NOT mdl, NOT available)
    - Entities: product_descriptions, product_knowledge, product_entities
  * "unknown" - if no entities match the above categories
  
  IMPORTANT: Database schemas are the ONLY data source available. If the question is about tables/schemas, use query_type="mdl".
- identified_entities: List of entity names from the available entities list
- entity_sub_types: List of sub-types for identified entities
- search_questions: List of search question objects, each with:
  - entity: Entity name
  - question: Natural language search question (HIGH-LEVEL, no specific table/entity names)
  - metadata_filters: Dictionary of metadata filters (use product_name, but avoid specific table/entity filters)
  - response_type: Description of what should be retrieved
  - execution_order: Integer indicating the order this query should be executed (1 = first, 2 = second, etc.)
  - depends_on: List of entity names or query indices that this query depends on (empty if no dependencies)
  - required_context: Description of what context/information is needed from dependent queries (empty if no dependencies)
- mdl_queries: (REQUIRED ALWAYS when query_type is "mdl" - even for simple table queries) List of MDL sub-queries with execution planning, each as an object with:
  - query: The MDL sub-query text (MUST follow the generic category-based format)
  - type: The DATABASE TABLE category name from available categories (e.g., "assets", "access requests", "vulnerabilities") - NOT compliance/policy concepts
  - execution_order: Integer indicating the order this query should be executed (1 = first, 2 = second, etc.)
  - depends_on: List of indices (0-based) of other mdl_queries this query depends on (empty if no dependencies)
  - required_context: Description of what context/information is needed from dependent queries (empty if no dependencies)
  - can_parallelize: Boolean indicating if this query can run in parallel with others (true if no dependencies, false if it depends on others)
  
  CRITICAL MDL QUERY FORMAT REQUIREMENTS:
  - MDL queries MUST be GENERIC and CATEGORY-BASED using DATABASE TABLE categories ONLY
  - Format: "what are [category] related tables? category: [category]"
  - DO NOT use specific table names in MDL queries
  - DO NOT use compliance/policy concepts as categories (e.g., "soc2 controls", "compliance controls", "policies")
  - The "type" field MUST be a DATABASE TABLE category name from the Available Categories list
  - Example: {{"query": "what are asset related tables? category: assets", "type": "assets", "execution_order": 1, "depends_on": [], "required_context": "", "can_parallelize": true}}
  
  - If evidence_gathering_required is true, you MUST create MDL queries from data_retrieval_plan:
    * For each data_retrieval_plan item with data_type "database_schemas", create an MDL query
    * Use the "category" field from data_retrieval_plan to create the MDL query
    * Format: "what are [category] related tables? category: [category]"
    * Set "type" to the category name
    * Example: If data_retrieval_plan has category "assets", create:
      {{"query": "what are asset related tables? category: assets", "type": "assets", "execution_order": 1, "depends_on": [], "required_context": "", "can_parallelize": true}}
    * Example: If data_retrieval_plan has category "access requests", create:
      {{"query": "what are access request related tables? category: access requests", "type": "access requests", "execution_order": 2, "depends_on": [], "required_context": "", "can_parallelize": true}}
  
  - All MDL queries for evidence gathering can typically run in parallel (set can_parallelize: true) since they query different categories
  - DO NOT use search_questions for MDL queries when evidence_gathering_required is true - ONLY use data_retrieval_plan
  
  - If query_type is "mdl" but evidence_gathering_required is false (regular table query), you MUST still generate mdl_queries:
    * Identify the categories mentioned in the question from the Available Categories list
    * For each category, create an MDL query using the generic format
    * Format: "what are [category] related tables? category: [category]"
    * Set "type" to the category name
    * Example: For "What tables are related to user access request and their soc2 compliance controls?":
      {{"query": "what are access request related tables? category: access requests", "type": "access requests", "execution_order": 1, "depends_on": [], "required_context": "", "can_parallelize": true}}

PLANNING RULES:
1. **Execution Order**: Determine the logical order of operations:
   - Queries that discover entities (tables, controls) should come FIRST
   - Queries that use discovered entities should come AFTER
   - Example: "What tables are related to X?" → order 1, "What are the compliance controls for those tables?" → order 2 (depends on order 1)

2. **Dependencies**: Identify when one query needs results from another:
   - If query B mentions "those tables", "the controls", "the entities" from query A → B depends on A
   - If query B needs specific table names/IDs from query A → B depends on A
   - If queries are independent (e.g., "tables for X" and "tables for Y") → no dependencies, can parallelize

3. **Required Context**: For dependent queries, specify what information is needed:
   - "Table names from query 0 to filter compliance controls"
   - "Compliance control IDs from query 1 to find related evidence"
   - "Entity IDs from query 0 to discover relationships"

4. **Parallelization**: Mark queries that can run in parallel:
   - Queries with no dependencies can run in parallel
   - Queries that depend on others must wait for dependencies to complete

CRITICAL: This is the FIRST breakdown - identify the QUERY TYPE based on identified entities:
- Map SCHEMA & DATABASE entities to "mdl" query type
- Map POLICY entities to "policy" query type
- Map RISK entities to "risk_control" query type
- Map COMPLIANCE entities to "compliance_framework" query type
- Map PRODUCT entities to "product" query type
- DO NOT use specific table names, entity IDs, or context_ids in filters
- DO use high-level discovery questions
- DO use product_name filters, but avoid table_name, context_id, or specific entity filters

{evidence_planning_instructions}

Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            prompt_input = {
                "user_question": user_question,
                "product_name": product_name or "Snyk",
                "categories_text": categories_text,
                "evidence_planning_instructions": evidence_planning_instructions
            }
            
            # Log full prompt without truncation
            logger.info("=" * 80)
            logger.info("GenericContextBreakdownNode: Full LLM Prompt (NO TRUNCATION)")
            logger.info("=" * 80)
            try:
                formatted_messages = prompt.format_messages(**prompt_input)
                logger.info(f"System Prompt:\n{formatted_messages[0].content}")
                logger.info(f"Human Prompt:\n{formatted_messages[1].content}")
            except Exception as e:
                logger.warning(f"Could not format prompt for logging: {e}")
            logger.info(f"Prompt Variables:")
            for key, value in prompt_input.items():
                logger.info(f"  {key}: {value}")
            logger.info("=" * 80)
            
            result = await chain.ainvoke(prompt_input)
            
            # Log full LLM response without truncation
            logger.info("=" * 80)
            logger.info("GenericContextBreakdownNode: Full LLM Response (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
            logger.info("=" * 80)
            
            # Safely parse and validate the response
            expected_fields = {
                "query_type": str,
                "identified_entities": list,
                "entity_sub_types": list,
                "search_questions": list,
                "mdl_queries": list,
                "evidence_gathering_required": bool,
                "evidence_types_needed": list,
                "data_retrieval_plan": list,
                "metrics_kpis_needed": list
            }
            validated_result = safe_parse_llm_response(result, expected_fields)
            
            # Extract validated results
            query_type = validated_result.get("query_type", "unknown")
            identified_entities = validated_result.get("identified_entities", [])
            entity_sub_types_raw = validated_result.get("entity_sub_types", [])
            search_questions_raw = validated_result.get("search_questions", [])
            mdl_queries = validated_result.get("mdl_queries", [])
            
            # Normalize entity_sub_types - ensure it's a list of strings
            entity_sub_types = normalize_string_list(entity_sub_types_raw, "entity_sub_types")
            
            # Normalize search_questions - ensure it's a list of dicts, not strings or characters
            search_questions = []
            if isinstance(search_questions_raw, list):
                for item in search_questions_raw:
                    if isinstance(item, dict):
                        # Valid search question dict
                        search_questions.append(item)
                    elif isinstance(item, str):
                        # String item - might be a dict key or character, skip it
                        if len(item) > 1 and item not in ["entity", "question", "metadata_filters", "response_type"]:
                            logger.warning(f"GenericContextBreakdownNode: Skipping string in search_questions: '{item[:50]}...' (expected dict)")
                    # Skip other types
            elif search_questions_raw:
                logger.warning(f"GenericContextBreakdownNode: search_questions was not a list (type: {type(search_questions_raw)}), using empty list")
            
            # Initialize variables before use
            parsed_mdl_queries = []
            mdl_queries_list = []
            mdl_queries_planning = []
            
            # Normalize and parse mdl_queries - handle both old format (list of strings) and new format (list of objects with planning)
            if isinstance(mdl_queries, list) and len(mdl_queries) > 0:
                # Check if first item is a dict (new format) or string (old format)
                if isinstance(mdl_queries[0], dict):
                    # New format with planning information
                    for i, query_obj in enumerate(mdl_queries):
                        if isinstance(query_obj, dict):
                            query_text = query_obj.get("query", "")
                            if query_text:
                                parsed_mdl_queries.append({
                                    "query": query_text,
                                    "type": query_obj.get("type", ""),  # Category/type field
                                    "execution_order": query_obj.get("execution_order", i + 1),
                                    "depends_on": query_obj.get("depends_on", []),
                                    "required_context": query_obj.get("required_context", ""),
                                    "can_parallelize": query_obj.get("can_parallelize", len(query_obj.get("depends_on", [])) == 0)
                                })
                            else:
                                logger.warning(f"GenericContextBreakdownNode: mdl_queries[{i}] dict missing 'query' field")
                        else:
                            logger.warning(f"GenericContextBreakdownNode: mdl_queries[{i}] is not a dict, skipping")
                else:
                    # Old format - list of strings, convert to new format
                    normalized_strings = normalize_string_list(mdl_queries, "mdl_queries")
                    for i, query_text in enumerate(normalized_strings):
                        parsed_mdl_queries.append({
                            "query": query_text,
                            "type": "",  # No type in old format
                            "execution_order": i + 1,
                            "depends_on": [],
                            "required_context": "",
                            "can_parallelize": True
                        })
                    logger.info("GenericContextBreakdownNode: Converted old format mdl_queries (strings) to new format (objects with planning)")
            elif isinstance(mdl_queries, str):
                # Single string - convert to new format
                parsed_mdl_queries = [{
                    "query": mdl_queries,
                    "type": "",  # No type for single string
                    "execution_order": 1,
                    "depends_on": [],
                    "required_context": "",
                    "can_parallelize": True
                }]
            
            # If query_type is mdl but no mdl_queries provided, use original question
            if query_type == "mdl" and not parsed_mdl_queries:
                parsed_mdl_queries = [{
                    "query": user_question,
                    "type": "",  # No type for fallback
                    "execution_order": 1,
                    "depends_on": [],
                    "required_context": "",
                    "can_parallelize": True
                }]
                logger.info("GenericContextBreakdownNode: No mdl_queries provided, using original question as single MDL query")
            
            # Sort by execution_order and extract just the query strings for backward compatibility
            if parsed_mdl_queries:
                parsed_mdl_queries.sort(key=lambda x: x.get("execution_order", 999))
                mdl_queries_list = [q["query"] for q in parsed_mdl_queries]
                mdl_queries_planning = parsed_mdl_queries
            # else: already initialized as empty lists above
            
            # Map entities to query type if not explicitly set or if validation needed
            # SCHEMA & DATABASE entities → "mdl"
            schema_entities = ["table_definitions", "table_descriptions", "column_definitions", 
                             "schema_descriptions", "db_schema", "category_mapping"]
            # POLICY entities → "policy"
            policy_entities = ["policy_documents", "policy_entities", "policy_evidence", "policy_fields"]
            # RISK entities → "risk_control"
            risk_entities = ["risk_controls", "risk_entities", "risk_evidence", "risk_fields"]
            # COMPLIANCE entities → "compliance_framework"
            compliance_entities = ["compliance_controls"]
            # PRODUCT entities → "product"
            product_entities = ["product_descriptions", "product_knowledge", "product_entities"]
            
            # Auto-detect query type from entities if not set or if set incorrectly
            # Ensure we're comparing strings to strings
            detected_type = None
            if identified_entities:
                identified_entities_str = [str(e).strip() for e in identified_entities if e]
                if any(str(entity).strip() in schema_entities for entity in identified_entities_str):
                    detected_type = "mdl"
                elif any(str(entity).strip() in policy_entities for entity in identified_entities_str):
                    detected_type = "policy"
                elif any(str(entity).strip() in risk_entities for entity in identified_entities_str):
                    detected_type = "risk_control"
                elif any(str(entity).strip() in compliance_entities for entity in identified_entities_str):
                    detected_type = "compliance_framework"
                elif any(str(entity).strip() in product_entities for entity in identified_entities_str):
                    detected_type = "product"
            
            # Use detected type if query_type is unknown or doesn't match entities
            if query_type == "unknown" and detected_type:
                query_type = detected_type
                logger.info(f"GenericContextBreakdownNode: Auto-detected query_type '{query_type}' from entities")
            elif detected_type and query_type != detected_type:
                logger.warning(f"GenericContextBreakdownNode: Query type '{query_type}' doesn't match entities, using detected '{detected_type}'")
                query_type = detected_type
            
            # Normalize query_type: "table_related" -> "mdl" for consistency
            if query_type == "table_related":
                query_type = "mdl"
                logger.info("GenericContextBreakdownNode: Normalized 'table_related' to 'mdl'")
            
            # Validate query_type
            valid_query_types = ["mdl", "policy", "risk_control", "compliance_framework", "product", "unknown"]
            if query_type not in valid_query_types:
                logger.warning(f"GenericContextBreakdownNode: Invalid query_type '{query_type}', defaulting to 'unknown'")
                query_type = "unknown"
            
            # Also get context breakdown from service to extract user_intent, action_context, etc.
            try:
                context_breakdown_service_result = await self.context_breakdown_service.breakdown_question(
                    user_question=user_question,
                    available_products=[product_name] if product_name else None
                )
                user_intent = context_breakdown_service_result.user_intent
                action_context = context_breakdown_service_result.action_context
                compliance_context = context_breakdown_service_result.compliance_context
                product_context = context_breakdown_service_result.product_context
                frameworks = context_breakdown_service_result.frameworks
            except Exception as e:
                logger.warning(f"GenericContextBreakdownNode: Could not get context breakdown from service: {e}")
                user_intent = None
                action_context = None
                compliance_context = None
                product_context = product_name
                frameworks = []
            
            # Extract evidence gathering planning from result (if available)
            evidence_gathering_required = validated_result.get("evidence_gathering_required", False)
            evidence_types_needed = validated_result.get("evidence_types_needed", [])
            data_retrieval_plan = validated_result.get("data_retrieval_plan", [])
            metrics_kpis_needed = validated_result.get("metrics_kpis_needed", [])
            
            # If evidence gathering is required but no MDL queries were generated, create them from data_retrieval_plan
            if evidence_gathering_required and (not parsed_mdl_queries or len(parsed_mdl_queries) == 0):
                logger.warning("GenericContextBreakdownNode: evidence_gathering_required is true but no MDL queries found. Generating from data_retrieval_plan...")
                for plan_item in data_retrieval_plan:
                    if isinstance(plan_item, dict):
                        data_type = plan_item.get("data_type", "")
                        category = plan_item.get("category", "")  # Use category field
                        
                        # Generate MDL query from category - use the generic format
                        # Format: "what are {category} related tables? category: {category}"
                        if data_type == "database_schemas" and category:
                            # Create generic category-based query
                            # Convert category name to natural language (e.g., "access requests" -> "access request")
                            category_singular = category.rstrip('s') if category.endswith('s') and len(category) > 1 else category
                            mdl_query = f"what are {category_singular} related tables? category: {category}"
                            
                            parsed_mdl_queries.append({
                                "query": mdl_query,
                                "type": category,  # Type is the category
                                "execution_order": len(parsed_mdl_queries) + 1,
                                "depends_on": [],
                                "required_context": "",
                                "can_parallelize": True
                            })
                            logger.info(f"GenericContextBreakdownNode: Generated MDL query from data_retrieval_plan: query='{mdl_query}', type='{category}'")
                
                # Update mdl_queries list and planning after generating from data_retrieval_plan
                if parsed_mdl_queries:
                    # Sort by execution_order and extract just the query strings for backward compatibility
                    parsed_mdl_queries.sort(key=lambda x: x.get("execution_order", 999))
                    mdl_queries_list = [q["query"] for q in parsed_mdl_queries]
                    mdl_queries_planning = parsed_mdl_queries
                    logger.info(f"GenericContextBreakdownNode: Generated {len(parsed_mdl_queries)} MDL queries from data_retrieval_plan")
                
                # If still no queries, create a default one
                if not parsed_mdl_queries:
                    parsed_mdl_queries.append({
                        "query": user_question,
                        "type": "",  # No type for default query
                        "execution_order": 1,
                        "depends_on": [],
                        "required_context": "",
                        "can_parallelize": True
                    })
                    mdl_queries_list = [user_question]
                    mdl_queries_planning = parsed_mdl_queries
                    logger.warning("GenericContextBreakdownNode: Created default MDL query from user question")
            
            # Update state with generic breakdown including planning information
            state["generic_breakdown"] = {
                "user_question": user_question,
                "query_type": query_type,
                "identified_entities": identified_entities,
                "entity_sub_types": entity_sub_types,
                "search_questions": search_questions,
                "mdl_queries": mdl_queries_list,  # Multiple MDL sub-queries (strings for backward compatibility)
                "mdl_queries_planning": mdl_queries_planning,  # Full planning information with execution order and dependencies
                "user_intent": user_intent,
                "action_context": action_context,
                "compliance_context": compliance_context,
                "product_context": product_context,
                "frameworks": frameworks,
                # Evidence gathering planning
                "evidence_gathering_required": evidence_gathering_required,
                "evidence_types_needed": evidence_types_needed,
                "data_retrieval_plan": data_retrieval_plan,
                "metrics_kpis_needed": metrics_kpis_needed
            }
            state["query_type"] = query_type
            state["identified_entities"] = identified_entities
            state["search_questions"] = search_questions
            state["mdl_queries"] = mdl_queries_list  # Store multiple MDL queries (strings)
            state["mdl_queries_planning"] = mdl_queries_planning  # Store planning information
            state["current_step"] = "generic_breakdown"
            state["status"] = "processing"
            
            logger.info(f"GenericContextBreakdownNode: Query type: {query_type}, Identified {len(identified_entities)} entities, {len(search_questions)} search questions")
            if mdl_queries_planning:
                logger.info(f"GenericContextBreakdownNode: Execution Plan for {len(mdl_queries_planning)} MDL queries:")
                for plan in mdl_queries_planning:
                    order = plan.get("execution_order", "?")
                    query = plan.get("query", "")[:80]
                    query_type_field = plan.get("type", "")
                    deps = plan.get("depends_on", [])
                    parallel = plan.get("can_parallelize", False)
                    context = plan.get("required_context", "")
                    logger.info(f"  Order {order}: '{query}...' (type: '{query_type_field}', depends_on: {deps}, parallel: {parallel})")
                    if context:
                        logger.info(f"    Required context: {context}")
            elif mdl_queries_list:
                logger.info(f"GenericContextBreakdownNode: Identified {len(mdl_queries_list)} MDL sub-queries (no planning info, will process in parallel)")
            logger.info(f"GenericContextBreakdownNode: Query will {'proceed to MDL breakdown' if query_type == 'mdl' else 'skip MDL breakdown'}")
            
            return state
            
        except Exception as e:
            logger.error(f"GenericContextBreakdownNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Generic context breakdown failed: {str(e)}"
            return state


class MDLTableCurationNode:
    """Node that curates, scores, and prunes tables: fetches table schemas, scores relevance, and returns curated tables with descriptions"""
    
    def __init__(
        self,
        retriever: MDLSemanticRetriever,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        retrieval_helper: Optional[Any] = None
    ):
        self.retriever = retriever
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        self.retrieval_helper = retrieval_helper
    
    async def _detect_mentioned_tables(
        self,
        query: str,
        available_table_names: List[str]
    ) -> List[str]:
        """
        Use LLM to detect which tables are mentioned in the query.
        Replaces regex-based word matching with intelligent LLM detection.
        
        Args:
            query: The query text to analyze
            available_table_names: List of available table names to check against
            
        Returns:
            List of table names that are mentioned in the query
        """
        if not available_table_names:
            return []
        
        try:
            # Limit to top 50 tables to avoid token limits
            tables_to_check = available_table_names[:50]
            
            prompt = f"""You are a database expert. Analyze the following query and identify which database tables are mentioned or referenced.

Query: {query}

Available Tables ({len(tables_to_check)}):
{chr(10).join(f"- {table}" for table in tables_to_check)}

Instructions:
1. Identify tables that are EXPLICITLY mentioned in the query (e.g., "AccessRequest", "user_access", "assets table")
2. Identify tables that are IMPLICITLY referenced through their purpose (e.g., if query mentions "user access data", look for tables like "user_access", "access_requests", "access_logs")
3. Consider variations in naming (CamelCase, snake_case, spaces, etc.)
4. Be conservative - only include tables that are clearly relevant to the query
5. Return a JSON array of table names that are mentioned

Return ONLY a JSON array, e.g.:
["table1", "table2", "table3"]

If no tables are mentioned, return an empty array: []"""

            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                mentioned_tables = json.loads(json_match.group())
                # Filter to only include tables that actually exist in available_table_names
                mentioned_tables = [t for t in mentioned_tables if t in available_table_names]
                logger.info(f"MDLTableCurationNode: LLM detected {len(mentioned_tables)} mentioned tables: {mentioned_tables}")
                return mentioned_tables
            else:
                logger.warning(f"MDLTableCurationNode: Could not parse LLM response for table detection: {response_text[:200]}")
                return []
                
        except Exception as e:
            logger.warning(f"MDLTableCurationNode: Error detecting mentioned tables with LLM: {e}. Falling back to empty list.")
            return []
    
    async def _generate_table_retrieval_questions(
        self,
        user_question: str,
        identified_entities: List[str],
        generic_breakdown: Dict[str, Any]
    ) -> List[str]:
        """
        Generate natural language questions for table retrieval using LLM.
        Creates questions for ALL entities mentioned in the query.
        
        Args:
            user_question: Original user question
            identified_entities: List of entities identified in the breakdown
            generic_breakdown: Generic breakdown dictionary
            
        Returns:
            List of natural language questions for table retrieval
        """
        try:
            # Extract additional context from breakdown
            entity_sub_types = generic_breakdown.get("entity_sub_types", [])
            compliance_context = generic_breakdown.get("compliance_context", "")
            frameworks = generic_breakdown.get("frameworks", [])
            
            # Build prompt for LLM to generate table retrieval questions
            entities_text = ", ".join(identified_entities) if identified_entities else "the entities mentioned"
            entity_sub_types_text = ", ".join(entity_sub_types) if entity_sub_types else "N/A"
            frameworks_text = ", ".join(frameworks) if frameworks else "N/A"
            
            prompt = f"""You are a data retrieval expert. Your task is to generate natural language questions that will help find database tables related to the user's question.

User Question: {user_question}

Identified Entities: {entities_text}
Entity Sub-types: {entity_sub_types_text}
Compliance Context: {compliance_context}
Frameworks: {frameworks_text}

IMPORTANT RULES:
1. Generate a SEPARATE question for EACH identified entity (e.g., if entities are "Assets" and "User Access", generate questions for both)
2. Each question should be a natural language query that would help find tables related to that specific entity
3. Questions should be specific and focused (e.g., "What tables contain user access data?" not "What tables are there?")
4. Include context from the original question (e.g., if the question mentions "SOC 2 control", include that in relevant questions)
5. Generate 1-3 questions per entity, prioritizing the most important entities first

Examples:
- If entities are ["Assets", "User Access"] and question is about "SOC 2 control for user access high":
  - "What tables contain asset data related to user access controls?"
  - "What tables store user access information for SOC 2 compliance?"
  - "What tables track assets and their access control status?"

Return a JSON array of questions, e.g.:
["question 1", "question 2", "question 3"]

Generate questions now:"""

            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            # Try to extract JSON array from response
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
            else:
                # Fallback: split by lines and clean up
                questions = [q.strip().strip('"').strip("'") for q in response_text.split('\n') if q.strip() and not q.strip().startswith('#')]
                # Remove empty questions
                questions = [q for q in questions if q]
            
            # Ensure we have at least one question (fallback to original question)
            if not questions:
                questions = [user_question]
            
            logger.info(f"MDLTableCurationNode: Generated {len(questions)} table retrieval questions using LLM")
            return questions[:10]  # Limit to 10 questions max
            
        except Exception as e:
            logger.warning(f"MDLTableCurationNode: Error generating table retrieval questions: {e}. Using original question as fallback.")
            return [user_question]
    
    async def _curate_tables_for_query(
        self,
        mdl_query: str,
        user_question: str,
        product_name: str,
        table_descriptions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Curate, score, and prune tables for a single MDL query using batches of 50 tables
        
        Note: table_descriptions already contain full DDL and metadata - no separate schema context needed
        """
        logger.info(f"MDLTableCurationNode: Curating tables")
        logger.info(f"  User Question: {user_question[:80]}...")
        logger.info(f"  MDL Query: {mdl_query[:80]}...")
        logger.info(f"  Total tables to process: {len(table_descriptions)}")
        
        # Process tables in batches of 10 for better focus on high relevance
        BATCH_SIZE = 10
        all_curated_tables = []
        all_reasoning = []
        total_considered = 0
        total_pruned = 0
        
        # Create prompt template (reusable across batches)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at curating and scoring tables for MDL queries.

Given a user question and available table schemas, your task is to:
1. Score each table's relevance to the question (0.0 to 1.0)
2. Curate the most relevant tables
3. Prune tables that are not relevant
4. Return the best table descriptions with scores

CRITICAL RULES:
- **ALWAYS include tables that are explicitly mentioned in the MDL query** - if the query asks about a specific table name, that table MUST be in the curated_tables list, even if it seems less relevant
- **ALWAYS include tables that are directly related to tables mentioned in the query** - if the query asks "what tables are related to TableX", include TableX and all tables that relate to it
- Tables mentioned in the query should receive the highest relevance scores (1.0)
- When the query asks about relationships to a specific table, prioritize that table and its related tables over general product-related tables
- **Focus on HIGH RELEVANCE** - Only include tables with relevance_score >= 0.7 unless they are explicitly mentioned in the query
- Be selective - this is a small batch, so prioritize the most relevant tables

Return JSON with:
- curated_tables: List of curated table objects, each with:
  - table_name: Name of the table
  - relevance_score: Score from 0.0 to 1.0 indicating relevance to the question
  - description: Best description/context for why this table is relevant
  - categories: Categories this table belongs to (if available)
- reasoning: Brief explanation of the curation and scoring process for this batch
- total_tables_considered: Number of tables that were evaluated in this batch
- tables_pruned: Number of tables that were pruned (not included in curated_tables) in this batch
"""),
            ("human", """Curate and score tables for this query:

User's Overall Question: {user_question}

Specific MDL Query: {mdl_query}

Product: {product_name}
{table_schemas_text}

IMPORTANT: 
- Consider both the overall user question AND the specific MDL query when scoring relevance
- The overall question provides the broader context and purpose
- The MDL query focuses on a specific aspect that should be prioritized
- If the MDL query mentions specific table names, those tables MUST be included in curated_tables with high relevance scores

Score each table's relevance (0.0 to 1.0) based on how well it helps answer BOTH the overall question and the specific MDL query.
Curate only the MOST RELEVANT ones (relevance_score >= 0.7), and prune irrelevant tables.
Focus on quality over quantity - return only the best, most relevant tables with their scores and descriptions.

Return as JSON.""")
        ])
        
        chain = prompt | self.llm | self.json_parser
        
        # Process in batches
        num_batches = (len(table_descriptions) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"MDLTableCurationNode: Processing {len(table_descriptions)} tables in {num_batches} batches of {BATCH_SIZE}")
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(table_descriptions))
            batch_tables = table_descriptions[start_idx:end_idx]
            
            logger.info(f"MDLTableCurationNode: Processing batch {batch_idx + 1}/{num_batches} (tables {start_idx + 1}-{end_idx})")
            
            # Build table schemas text for this batch
            table_schemas_text = "\n\n## Available Table Schemas:\n\n"
            for i, table_desc in enumerate(batch_tables, 1):
                metadata = table_desc.get("metadata", {})
                table_name = metadata.get("table_name", "Unknown")
                content = table_desc.get("content", "")[:800]  # More content for better curation
                categories = metadata.get("categories", [])
                
                table_schemas_text += f"### Table {i}: {table_name}\n"
                if categories:
                    table_schemas_text += f"Categories: {', '.join(categories)}\n"
                table_schemas_text += f"Description: {content}\n\n"
            
            prompt_input = {
                "user_question": user_question,
                "mdl_query": mdl_query,
                "product_name": product_name,
                "table_schemas_text": table_schemas_text
            }
            
            try:
                batch_result = await chain.ainvoke(prompt_input)
                
                # Extract curated tables from this batch
                batch_curated = batch_result.get('curated_tables', [])
                batch_reasoning = batch_result.get('reasoning', '')
                batch_considered = batch_result.get('total_tables_considered', len(batch_tables))
                batch_pruned = batch_result.get('tables_pruned', 0)
                
                # Add to aggregated results
                all_curated_tables.extend(batch_curated)
                if batch_reasoning:
                    all_reasoning.append(f"Batch {batch_idx + 1}: {batch_reasoning}")
                total_considered += batch_considered
                total_pruned += batch_pruned
                
                logger.info(f"MDLTableCurationNode: Batch {batch_idx + 1} curated {len(batch_curated)} tables")
                
            except Exception as e:
                logger.error(f"MDLTableCurationNode: Error processing batch {batch_idx + 1}: {e}")
                # Continue with next batch
                total_considered += len(batch_tables)
                total_pruned += len(batch_tables)
        
        # Deduplicate curated tables by table_name (keep highest score if duplicate)
        seen_tables = {}
        for table in all_curated_tables:
            if isinstance(table, dict):
                table_name = table.get('table_name', '')
                if table_name:
                    if table_name not in seen_tables:
                        seen_tables[table_name] = table
                    else:
                        # Keep the one with higher relevance score
                        current_score = seen_tables[table_name].get('relevance_score', 0.0)
                        new_score = table.get('relevance_score', 0.0)
                        if new_score > current_score:
                            seen_tables[table_name] = table
        
        # Sort by relevance_score (highest first) and limit to top 10
        all_tables = list(seen_tables.values())
        all_tables.sort(key=lambda x: x.get('relevance_score', 0.0), reverse=True)
        final_curated_tables = all_tables[:10]
        
        logger.info(f"MDLTableCurationNode: Filtered {len(all_tables)} deduplicated tables → top 10 by relevance score")
        
        # Combine all results
        result = {
            'curated_tables': final_curated_tables,
            'reasoning': ' | '.join(all_reasoning) if all_reasoning else 'Processed tables in batches',
            'total_tables_considered': total_considered,
            'tables_pruned': total_pruned
        }
        
        # Log response for this specific MDL query
        logger.info("=" * 80)
        logger.info(f"MDLTableCurationNode: Response for Query '{mdl_query[:50]}...' (NO TRUNCATION)")
        logger.info("=" * 80)
        logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
        logger.info("=" * 80)
        
        curated_tables = result.get('curated_tables', [])
        curated_table_names = {table.get('table_name', '') for table in curated_tables if isinstance(table, dict)}
        
        # Extract table names mentioned in the query using LLM (replaces regex word matching)
        mentioned_tables = []
        
        # Get all available table names from table_descriptions
        available_table_names = []
        for table_desc in table_descriptions:
            metadata = table_desc.get("metadata", {})
            table_name = metadata.get("table_name", "")
            if table_name:
                available_table_names.append(table_name)
        
        # Use LLM to detect which tables are mentioned in the query
        if available_table_names:
            mentioned_tables = await self._detect_mentioned_tables(
                query=mdl_query,
                available_table_names=available_table_names
            )
            
            # Filter to only include tables not already in curated list
            mentioned_tables = [t for t in mentioned_tables if t not in curated_table_names]
            
            if mentioned_tables:
                logger.info(f"MDLTableCurationNode: LLM detected {len(mentioned_tables)} mentioned tables not in curated list: {mentioned_tables}")
        
        # Add mentioned tables that are missing from curated list
        if mentioned_tables:
            for table_name in mentioned_tables:
                # Find the table description for this table
                table_desc = None
                for desc in table_descriptions:
                    metadata = desc.get("metadata", {})
                    if metadata.get("table_name", "") == table_name:
                        table_desc = desc
                        break
                
                if table_desc:
                    metadata = table_desc.get("metadata", {})
                    content = table_desc.get("content", "")[:500]
                    categories = metadata.get("categories", [])
                    
                    # Add with high relevance score since it was mentioned in query
                    curated_tables.append({
                        "table_name": table_name,
                        "relevance_score": 1.0,
                        "description": content or f"Table {table_name} mentioned in the query",
                        "categories": categories
                    })
                    logger.info(f"MDLTableCurationNode: Added mentioned table '{table_name}' to curated list")
            
            # Update the result
            result['curated_tables'] = curated_tables
            result['total_tables_considered'] = result.get('total_tables_considered', 0)
            result['tables_pruned'] = result.get('tables_pruned', 0) - len(mentioned_tables)
        
        curated_count = len(curated_tables)
        logger.info(f"MDLTableCurationNode: Curated {curated_count} tables for query '{mdl_query[:50]}...' (added {len(mentioned_tables)} mentioned tables)")
        
        # Log registered tables after this curation query
        if curated_tables:
            logger.info(f"MDLTableCurationNode: Registered tables for query '{mdl_query[:50]}...':")
            for i, table in enumerate(curated_tables[:10], 1):  # Log first 10
                if isinstance(table, dict):
                    table_name = table.get('table_name', 'Unknown')
                    score = table.get('relevance_score', 0.0)
                    logger.info(f"  {i}. {table_name} (score: {score:.2f})")
                else:
                    logger.warning(f"  {i}. Non-dict table entry: {type(table)}")
            if len(curated_tables) > 10:
                logger.info(f"  ... and {len(curated_tables) - 10} more tables")
        
        return {
            "mdl_query": mdl_query,
            "result": result
        }
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Fetch table schemas, curate, score, and prune tables (handles multiple MDL queries in parallel)"""
        logger.info("MDLTableCurationNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name", "Snyk")
        query_type = state.get("query_type", "unknown")
        generic_breakdown = state.get("generic_breakdown", {})
        identified_entities = state.get("identified_entities", []) or generic_breakdown.get("identified_entities", [])
        mdl_queries_raw = state.get("mdl_queries", []) or generic_breakdown.get("mdl_queries", [])
        
        # Log what we received for debugging
        logger.info(f"MDLTableCurationNode: Raw mdl_queries type: {type(mdl_queries_raw)}, value: {repr(mdl_queries_raw)[:200]}")
        
        # Parse mdl_queries - they can be list of dicts (new format) or list of strings (old format)
        parsed_mdl_queries = []
        if isinstance(mdl_queries_raw, list) and len(mdl_queries_raw) > 0:
            if isinstance(mdl_queries_raw[0], dict):
                # New format: list of dicts with "query" field
                for query_obj in mdl_queries_raw:
                    if isinstance(query_obj, dict):
                        query_text = query_obj.get("query", "")
                        if query_text:
                            parsed_mdl_queries.append(query_text)
            else:
                # Old format: list of strings
                parsed_mdl_queries = normalize_string_list(mdl_queries_raw, "mdl_queries")
        elif isinstance(mdl_queries_raw, str):
            # Single string
            parsed_mdl_queries = [mdl_queries_raw]
        
        mdl_queries = parsed_mdl_queries
        
        logger.info(f"MDLTableCurationNode: Parsed {len(mdl_queries)} valid MDL queries")
        if mdl_queries:
            logger.info(f"MDLTableCurationNode: Sample queries: {[q[:50] + '...' if len(q) > 50 else q for q in mdl_queries[:3]]}")
        
        # Only do MDL curation if query type is MDL or table_related
        # Also check if the question is about tables/schemas even if query_type wasn't detected correctly
        question_lower = user_question.lower()
        is_table_related_question = any(keyword in question_lower for keyword in [
            "table", "schema", "database", "asset", "access", "user", "control", "compliance"
        ])
        
        if query_type not in ["mdl", "table_related"]:
            if is_table_related_question:
                logger.warning(f"MDLTableCurationNode: Query type is '{query_type}' but question seems table-related. "
                             f"Proceeding with table curation anyway.")
                # Override query_type for table curation
                query_type = "mdl"
            else:
                logger.info(f"MDLTableCurationNode: Query type is '{query_type}', skipping MDL table curation (only runs for 'mdl' or 'table_related')")
                state["current_step"] = "mdl_curation"
                state["context_breakdown"] = generic_breakdown  # Use generic breakdown
                return state
        
        if not user_question:
            logger.error("MDLTableCurationNode: No user question provided")
            state["status"] = "error"
            state["error"] = "No user question provided"
            return state
        
        try:
            # Step 0: Use mdl_queries from the breakdown (already parsed above)
            # These are the queries generated by GenericContextBreakdownNode based on data_retrieval_plan
            table_retrieval_questions = mdl_queries if mdl_queries else []
            
            if not table_retrieval_questions:
                error_msg = "MDLTableCurationNode: No mdl_queries found in breakdown. Cannot proceed with table retrieval. " \
                           "The GenericContextBreakdownNode should have generated mdl_queries based on the data_retrieval_plan. " \
                           "Check that evidence_gathering_required is true and that the breakdown includes mdl_queries."
                logger.error(error_msg)
                state["status"] = "error"
                state["error"] = error_msg
                state["current_step"] = "mdl_curation"
                return state
            
            logger.info(f"MDLTableCurationNode: Using {len(table_retrieval_questions)} mdl_queries from breakdown for table retrieval")
            logger.info(f"MDLTableCurationNode: Queries: {[q[:80] + '...' if len(q) > 80 else q for q in table_retrieval_questions[:5]]}")
            
            # Step 1: Fetch all table schemas using get_database_schemas from RetrievalHelper
            # Use all generated questions to retrieve tables
            logger.info(f"MDLTableCurationNode: Fetching table schemas for question: {user_question[:100]}...")
            
            # Use RetrievalHelper.get_table_names_and_schema_contexts if available, otherwise fall back to retriever
            table_descriptions = []
            schema_descriptions = []
            
            if self.retrieval_helper and hasattr(self.retrieval_helper, 'get_table_names_and_schema_contexts'):
                logger.info("MDLTableCurationNode: Using RetrievalHelper.get_table_names_and_schema_contexts for data retrieval")
                
                try:
                    # Use product_name as project_id (or get from state if available)
                    project_id = state.get("project_id") or product_name or "Snyk"
                    
                    # Build table_retrieval config (matching the format expected by get_table_names_and_schema_contexts)
                    table_retrieval = {
                        "table_retrieval_size": 30,  # Retrieve 30 tables - curation will filter to top 10
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": True  # Skip column pruning - return full DDL for markdown
                    }
                    
                    # PARALLEL RETRIEVAL: Use all generated questions to retrieve tables in parallel
                    all_table_names = []
                    seen_table_names = set()
                    
                    # Create parallel tasks for all MDL queries
                    async def fetch_for_question(question: str):
                        try:
                            # Extract category from the mdl_query if it's in the format: "what are X related tables? category: Y"
                            category = None
                            if "category:" in question:
                                category_match = re.search(r'category:\s*([^,\n]+)', question)
                                if category_match:
                                    category = category_match.group(1).strip()
                                    logger.info(f"MDLTableCurationNode: Extracted category '{category}' from query")
                            
                            # Combine user question and MDL query for better context
                            combined_query = f"User Question: {user_question}\n\nSpecific MDL Query: {question}"
                            
                            logger.info(f"MDLTableCurationNode: [PARALLEL] Fetching for query: '{question[:80]}...'")
                            
                            result = await self.retrieval_helper.get_table_names_and_schema_contexts(
                                query=combined_query,
                                project_id=project_id,
                                table_retrieval=table_retrieval,
                                histories=None,
                                tables=None
                            )
                            
                            return (question, result)
                        except Exception as e:
                            logger.warning(f"MDLTableCurationNode: [PARALLEL] Error for question '{question[:50]}...': {e}")
                            return (question, None)
                    
                    # Execute all queries in parallel
                    logger.info(f"MDLTableCurationNode: Starting PARALLEL retrieval for {len(table_retrieval_questions)} queries")
                    import asyncio
                    results = await asyncio.gather(*[fetch_for_question(q) for q in table_retrieval_questions])
                    logger.info(f"MDLTableCurationNode: PARALLEL retrieval completed, processing {len(results)} results")
                    
                    # Process results
                    for question, result in results:
                        if result and "table_names" in result:
                            table_names = result.get("table_names", [])
                            schema_contexts = result.get("schema_contexts", [])
                            
                            # Combine table names with their schema contexts
                            for i, table_name in enumerate(table_names):
                                if table_name and table_name not in seen_table_names:
                                    seen_table_names.add(table_name)
                                    all_table_names.append(table_name)
                                    
                                    # Get corresponding schema context if available
                                    schema_context = schema_contexts[i] if i < len(schema_contexts) else ""
                                    
                                    table_descriptions.append({
                                        "content": schema_context if schema_context else f"Table: {table_name}",
                                        "metadata": {
                                            "table_name": table_name,
                                            "product_name": product_name,
                                            "project_id": project_id,
                                            "relationships": result.get("relationships", [])
                                        }
                                    })
                            
                            logger.info(f"MDLTableCurationNode: Question '{question[:50]}...' returned {len(table_names)} tables with full DDL")
                        else:
                            error_msg = result.get("error", "Unknown error") if result else "No result returned"
                            logger.warning(f"MDLTableCurationNode: No tables found for question '{question[:50]}...': {error_msg}")
                    
                    logger.info(f"MDLTableCurationNode: Retrieved {len(table_descriptions)} unique table descriptions from PARALLEL get_table_names_and_schema_contexts (from {len(table_retrieval_questions)} questions)")
                    logger.info(f"MDLTableCurationNode: Schema contexts collected but not needed - table_descriptions contain full DDL")
                    
                except Exception as e:
                    logger.error(f"MDLTableCurationNode: Error using RetrievalHelper.get_table_names_and_schema_contexts: {e}", exc_info=True)
                    table_descriptions = []
                    schema_descriptions = []
            else:
                # Fallback to retriever if RetrievalHelper not available or doesn't have get_database_schemas
                logger.info("MDLTableCurationNode: RetrievalHelper.get_database_schemas not available, using MDLSemanticRetriever")
                
                try:
                    # PARALLEL RETRIEVAL: Use all generated questions to retrieve tables in parallel
                    async def fetch_table_descriptions(question: str):
                        try:
                            # Combine user question and MDL query for better context
                            combined_query = f"User Question: {user_question}\n\nSpecific MDL Query: {question}"
                            
                            project_id = state.get("project_id") or product_name or "Snyk"
                            question_results = await self.retriever.retrieve_table_descriptions(
                                query=combined_query,
                                filters={"product_name": product_name} if product_name else None,
                                top_k=30,  # Retrieve 30 tables - curation will filter to top 10
                                project_id=project_id
                            )
                            logger.info(f"MDLTableCurationNode: [PARALLEL] Query '{question[:50]}...' returned {len(question_results)} tables")
                            return question_results
                        except Exception as e:
                            logger.warning(f"MDLTableCurationNode: [PARALLEL] Error for question '{question[:50]}...': {e}")
                            return []
                    
                    # Execute all queries in parallel
                    logger.info(f"MDLTableCurationNode: Starting PARALLEL retrieval for {len(table_retrieval_questions)} fallback queries")
                    import asyncio
                    results_list = await asyncio.gather(*[fetch_table_descriptions(q) for q in table_retrieval_questions])
                    logger.info(f"MDLTableCurationNode: PARALLEL fallback retrieval completed")
                    
                    # Flatten results
                    all_table_results = []
                    for question_results in results_list:
                        all_table_results.extend(question_results)
                    
                    # Deduplicate by table name
                    seen_tables = set()
                    for result in all_table_results:
                        metadata = result.get("metadata", {})
                        table_name = metadata.get("table_name", "")
                        if table_name and table_name not in seen_tables:
                            seen_tables.add(table_name)
                            table_descriptions.append(result)
                    
                    logger.info(f"MDLTableCurationNode: MDLSemanticRetriever returned {len(table_descriptions)} complete table schemas with full DDL (from {len(table_retrieval_questions)} MDL queries)")
                    
                    # Schema descriptions not needed - table_descriptions already contains full DDL for markdown conversion
                    schema_descriptions = []
                except Exception as e:
                    logger.error(f"MDLTableCurationNode: Error using MDLSemanticRetriever: {e}", exc_info=True)
                    table_descriptions = []
                    schema_descriptions = []
            
            logger.info(f"MDLTableCurationNode: Ready to process {len(table_descriptions)} complete table schemas (full DDL available for LLM)")
            
            # Check if collections exist and have data
            if len(table_descriptions) == 0:
                logger.warning("MDLTableCurationNode: No table descriptions found. Checking if collections exist...")
                try:
                    if hasattr(self.retriever, 'collection_factory') and self.retriever.collection_factory:
                        table_desc_collection = self.retriever.collection_factory.get_collection_by_store_name("table_descriptions")
                        if table_desc_collection:
                            # Check collection count (synchronous method)
                            try:
                                if hasattr(table_desc_collection, 'count'):
                                    count = table_desc_collection.count()
                                    logger.info(f"MDLTableCurationNode: table_descriptions collection exists with {count} documents")
                                    if count == 0:
                                        logger.warning("MDLTableCurationNode: table_descriptions collection is empty - no tables available")
                                else:
                                    logger.info("MDLTableCurationNode: table_descriptions collection exists (count method not available)")
                            except Exception as count_error:
                                logger.warning(f"MDLTableCurationNode: Could not get collection count: {count_error}")
                        else:
                            logger.warning("MDLTableCurationNode: table_descriptions collection not found in collection_factory")
                except Exception as e:
                    logger.warning(f"MDLTableCurationNode: Error checking collections: {e}")
            
            # Fallback 1: If table_descriptions is empty, try using retrieval_helper.get_table_names_and_schema_contexts with original question
            if len(table_descriptions) == 0 and self.retrieval_helper and hasattr(self.retrieval_helper, 'get_table_names_and_schema_contexts'):
                logger.warning("MDLTableCurationNode: No table descriptions found via generated questions, trying with original user question...")
                try:
                    project_id = state.get("project_id") or product_name or "Snyk"
                    table_retrieval = {
                        "table_retrieval_size": 30,  # Retrieve 30 tables - curation will filter to top 10
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": True  # Skip column pruning - return full DDL for markdown
                    }
                    
                    result = await self.retrieval_helper.get_table_names_and_schema_contexts(
                        query=user_question,
                        project_id=project_id,
                        table_retrieval=table_retrieval,
                        histories=None,
                        tables=None
                    )
                    
                    if result and "table_names" in result:
                        table_names = result.get("table_names", [])
                        schema_contexts = result.get("schema_contexts", [])
                        
                        for i, table_name in enumerate(table_names):
                            schema_context = schema_contexts[i] if i < len(schema_contexts) else ""
                            table_descriptions.append({
                                "content": schema_context if schema_context else f"Table: {table_name}",
                                "metadata": {
                                    "table_name": table_name,
                                    "product_name": product_name,
                                    "project_id": project_id
                                }
                            })
                        
                        logger.info(f"MDLTableCurationNode: Retrieved {len(table_descriptions)} table descriptions using original question as fallback")
                except Exception as e:
                    logger.warning(f"MDLTableCurationNode: Error using retrieval_helper fallback: {e}", exc_info=True)
            
            # Fallback 2: If table_descriptions is empty but schema_descriptions exist, try to extract tables from schema descriptions
            if len(table_descriptions) == 0 and len(schema_descriptions) > 0:
                logger.warning("MDLTableCurationNode: table_descriptions is empty but schema_descriptions found. Attempting to extract tables from schema descriptions...")
                try:
                    # Try to retrieve table_definitions as a fallback
                    if self.retriever:
                        logger.info("MDLTableCurationNode: Attempting to retrieve table_definitions as fallback...")
                        table_defs = await self.retriever.retrieve_by_entity(
                            entity="table_definitions",
                            query=user_question,
                            filters={"product_name": product_name} if product_name else None,
                            top_k=20
                        )
                        if table_defs:
                            # Convert table_definitions to table_descriptions format
                            for table_def in table_defs:
                                metadata = table_def.get("metadata", {})
                                table_name = metadata.get("table_name", "")
                                if table_name:
                                    table_descriptions.append({
                                        "content": table_def.get("content", ""),
                                        "metadata": {
                                            "table_name": table_name,
                                            "product_name": product_name,
                                            **metadata
                                        }
                                    })
                            logger.info(f"MDLTableCurationNode: Extracted {len(table_descriptions)} tables from table_definitions")
                    
                    # If still empty, try to extract from schema_descriptions content using LLM
                    if len(table_descriptions) == 0 and schema_descriptions:
                        logger.info("MDLTableCurationNode: Attempting to extract table names from schema_descriptions using LLM...")
                        
                        # Collect all schema description content
                        schema_content = "\n\n".join([
                            schema_desc.get("content", "")[:2000] 
                            for schema_desc in schema_descriptions[:3]  # Limit to first 3 to avoid token limits
                        ])
                        
                        if schema_content:
                            # Use LLM to extract table names from schema descriptions
                            extraction_prompt = f"""Extract all table names mentioned in the following schema descriptions. 
Return a JSON list of table names found.

Schema Descriptions:
{schema_content}

Return only a JSON array of table names, e.g., ["Table1", "Table2", "Table3"]"""

                            try:
                                extraction_chain = ChatPromptTemplate.from_messages([
                                    ("system", "You are a helpful assistant that extracts table names from schema descriptions. Return only valid JSON."),
                                    ("human", extraction_prompt)
                                ]) | self.llm | self.json_parser
                                
                                extraction_result = await extraction_chain.ainvoke({})
                                
                                # Handle different response formats
                                if isinstance(extraction_result, list):
                                    extracted_table_names = extraction_result
                                elif isinstance(extraction_result, dict):
                                    # Try common keys
                                    extracted_table_names = (
                                        extraction_result.get("tables", []) or
                                        extraction_result.get("table_names", []) or
                                        extraction_result.get("names", []) or
                                        []
                                    )
                                else:
                                    extracted_table_names = []
                                
                                if extracted_table_names:
                                    logger.info(f"MDLTableCurationNode: Extracted {len(extracted_table_names)} table names from schema descriptions: {extracted_table_names[:5]}...")
                                    
                                    # Create table_descriptions entries from extracted names and schema content
                                    for table_name in extracted_table_names[:20]:  # Limit to 20 tables
                                        # Find relevant schema description content for this table
                                        table_content = ""
                                        for schema_desc in schema_descriptions:
                                            schema_text = schema_desc.get("content", "")
                                            if table_name.lower() in schema_text.lower():
                                                table_content = schema_text[:1000]  # Use first 1000 chars
                                                break
                                        
                                        if not table_content:
                                            # Use first schema description as fallback
                                            table_content = schema_descriptions[0].get("content", "")[:1000]
                                        
                                        table_descriptions.append({
                                            "content": f"Table: {table_name}\n\n{table_content}",
                                            "metadata": {
                                                "table_name": table_name,
                                                "product_name": product_name,
                                                "extracted_from_schema": True
                                            }
                                        })
                                    
                                    logger.info(f"MDLTableCurationNode: Created {len(table_descriptions)} table descriptions from extracted table names")
                            except Exception as e:
                                logger.warning(f"MDLTableCurationNode: Error extracting tables from schema descriptions using LLM: {e}")
                except Exception as e:
                    logger.warning(f"MDLTableCurationNode: Error in fallback table extraction: {e}")
            
            logger.info(f"MDLTableCurationNode: Final count - {len(table_descriptions)} table descriptions, {len(schema_descriptions)} schema descriptions")
            
            # Step 2: Get execution plan and process queries in order with dependencies
            mdl_queries_planning = state.get("mdl_queries_planning") or generic_breakdown.get("mdl_queries_planning", [])
            
            # Final safety check - ensure mdl_queries is a list of strings, not characters
            if isinstance(mdl_queries, str):
                logger.error(f"MDLTableCurationNode: CRITICAL - mdl_queries is still a string! Converting: '{mdl_queries[:50]}...'")
                mdl_queries = [mdl_queries]
            elif not isinstance(mdl_queries, list):
                logger.error(f"MDLTableCurationNode: CRITICAL - mdl_queries is not a list (type: {type(mdl_queries)}), using user_question")
                mdl_queries = [user_question]
            else:
                # Double-check for single-character items (indicates string was iterated)
                if mdl_queries and all(len(str(q)) == 1 for q in mdl_queries):
                    logger.error(f"MDLTableCurationNode: CRITICAL - All queries are single characters! This means a string was iterated. Reconstructing from user_question.")
                    mdl_queries = [user_question]
                # Filter out any remaining single characters
                mdl_queries = [q for q in mdl_queries if isinstance(q, str) and len(q.strip()) > 1]
            
            if not mdl_queries:
                # Single MDL query - use original question
                mdl_queries = [user_question]
                logger.info("MDLTableCurationNode: Processing single MDL query (no valid queries found, using user_question)")
            
            # Reconstruct planning if missing or if lengths don't match
            if not mdl_queries_planning or len(mdl_queries_planning) != len(mdl_queries):
                logger.info("MDLTableCurationNode: Reconstructing planning info from mdl_queries")
                mdl_queries_planning = [
                    {
                        "query": q,
                        "execution_order": i + 1,
                        "depends_on": [],
                        "required_context": "",
                        "can_parallelize": True
                    }
                    for i, q in enumerate(mdl_queries)
                ]
            
            # Step 3: Process queries respecting execution order and dependencies
            import asyncio
            from collections import defaultdict
            
            # Group queries by execution order
            queries_by_order = defaultdict(list)
            for i, plan in enumerate(mdl_queries_planning):
                order = plan.get("execution_order", i + 1)
                queries_by_order[order].append((i, plan))
            
            # Process queries in order
            all_parallel_results = []
            previous_results = {}  # Store results from previous queries for context
            
            logger.info("=" * 80)
            logger.info(f"MDLTableCurationNode: Processing {len(mdl_queries)} MDL queries with execution plan")
            logger.info("=" * 80)
            
            for order in sorted(queries_by_order.keys()):
                queries_in_order = queries_by_order[order]
                logger.info(f"MDLTableCurationNode: Processing execution order {order} ({len(queries_in_order)} queries)")
                
                # Build context from dependent queries
                order_results = []
                for query_idx, plan in queries_in_order:
                    query_text = plan.get("query", mdl_queries[query_idx] if query_idx < len(mdl_queries) else "")
                    depends_on = plan.get("depends_on", [])
                    required_context = plan.get("required_context", "")
                    can_parallelize = plan.get("can_parallelize", len(depends_on) == 0)
                    
                    # Build context string from dependent queries
                    context_info = ""
                    if depends_on and previous_results:
                        context_parts = []
                        for dep_idx in depends_on:
                            if dep_idx in previous_results:
                                dep_result = previous_results[dep_idx]
                                curated_tables = dep_result.get("result", {}).get("curated_tables", [])
                                if curated_tables:
                                    table_names = [t.get("table_name", "") for t in curated_tables if isinstance(t, dict) and t.get("table_name")]
                                    if table_names:
                                        context_parts.append(f"Tables from query {dep_idx}: {', '.join(table_names[:5])}")
                        if context_parts:
                            context_info = " | ".join(context_parts)
                            logger.info(f"MDLTableCurationNode: Query {query_idx} (order {order}) context: {context_info}")
                    
                    # Enhance query with context if available
                    enhanced_query = query_text
                    if context_info:
                        enhanced_query = f"{query_text} (Context: {context_info})"
                    
                    logger.info(f"MDLTableCurationNode: Processing query {query_idx} (order {order}): '{query_text[:80]}...'")
                    if depends_on:
                        logger.info(f"  Depends on queries: {depends_on}, Required context: {required_context}")
                    
                    # Curate tables for this query
                    result = await self._curate_tables_for_query(
                        mdl_query=enhanced_query,  # Use enhanced query with context
                        user_question=user_question,  # Pass user question for full context
                        product_name=product_name,
                        table_descriptions=table_descriptions
                    )
                    
                    order_results.append({
                        "query_idx": query_idx,
                        "plan": plan,
                        "result": result
                    })
                    # Store result for context passing (result is {"mdl_query": ..., "result": {...}})
                    previous_results[query_idx] = result
                
                all_parallel_results.extend(order_results)
            
            logger.info("=" * 80)
            logger.info(f"MDLTableCurationNode: Completed sequential curation respecting execution order")
            logger.info("=" * 80)
            
            # Convert to format expected by rest of code
            # _curate_tables_for_query returns {"mdl_query": ..., "result": {...}}
            parallel_results = [r["result"] for r in all_parallel_results]
            
            # Step 4: Combine curated tables from all parallel MDL queries
            all_curated_tables = []
            all_reasoning = []
            all_mdl_results = []
            
            for parallel_result in parallel_results:
                mdl_query = parallel_result["mdl_query"]
                result = parallel_result["result"]
                
                curated_tables = result.get("curated_tables", [])
                reasoning = result.get("reasoning", "")
                
                all_curated_tables.extend(curated_tables)
                all_reasoning.append(f"Query: {mdl_query}\nReasoning: {reasoning}")
                all_mdl_results.append({
                    "mdl_query": mdl_query,
                    "curated_tables": curated_tables,
                    "reasoning": reasoning,
                    "total_tables_considered": result.get("total_tables_considered", 0),
                    "tables_pruned": result.get("tables_pruned", 0)
                })
            
            # Remove duplicate tables while preserving highest score
            table_scores = {}
            for curated_table in all_curated_tables:
                table_name = curated_table.get("table_name")
                score = curated_table.get("relevance_score", 0.0)
                if table_name:
                    if table_name not in table_scores or score > table_scores[table_name]["relevance_score"]:
                        table_scores[table_name] = curated_table
            
            # Sort by relevance score (descending)
            curated_tables_final = sorted(
                table_scores.values(),
                key=lambda x: x.get("relevance_score", 0.0),
                reverse=True
            )
            
            # Build curated tables info using ALREADY FETCHED data (no re-retrieval needed!)
            # The table_descriptions from parallel retrieval already contain full DDL
            curated_tables_info = []
            logger.info(f"MDLTableCurationNode: Building final table info for {len(curated_tables_final)} curated tables using already-fetched data")
            
            for curated_table in curated_tables_final:
                table_name = curated_table.get("table_name")
                relevance_score = curated_table.get("relevance_score", 0.0)
                description = curated_table.get("description", "")
                categories = curated_table.get("categories", [])
                
                # PERFORMANCE FIX: Use already-fetched data instead of re-retrieving!
                # Find matching table description from initially fetched schemas
                matching_table = None
                for table_desc in table_descriptions:
                    metadata = table_desc.get("metadata", {})
                    if metadata.get("table_name") == table_name:
                        matching_table = table_desc
                        break
                
                # Extract data from already-fetched table descriptions
                full_table_description = ""
                table_comments = ""
                table_ddl = ""
                table_columns = []
                table_metadata = {}
                
                try:
                    # Use the already-fetched data from initial parallel retrieval
                    if matching_table:
                        full_table_description = matching_table.get("content", "")
                        table_metadata = matching_table.get("metadata", {})
                        table_comments = table_metadata.get("comment", "") or table_metadata.get("comments", "") or table_metadata.get("description", "")
                        
                        # The content field contains the full DDL from initial retrieval
                        table_ddl = full_table_description
                        
                        # Extract column info from metadata if available
                        column_metadata = table_metadata.get("column_metadata", [])
                        if column_metadata:
                            table_columns = [
                                {
                                    "name": col.get("column_name", ""),
                                    "type": col.get("type", ""),
                                    "description": col.get("description", ""),
                                    "is_calculated": col.get("is_calculated", False),
                                    "is_primary_key": col.get("is_primary_key", False),
                                    "is_foreign_key": col.get("is_foreign_key", False)
                                }
                                for col in column_metadata
                            ]
                        
                        logger.info(f"MDLTableCurationNode: Using already-fetched data for {table_name} ({len(full_table_description)} chars)")
                    else:
                        logger.warning(f"MDLTableCurationNode: No matching data found for {table_name} in initial fetch")
                    
                except Exception as e:
                    logger.warning(f"MDLTableCurationNode: Error extracting data for {table_name}: {e}")
                    # Minimal fallback
                    if matching_table:
                        full_table_description = matching_table.get("content", "")
                        table_ddl = full_table_description
                
                # Convert JSON DDL to markdown comment format if needed
                # For MDL reasoning, we should never use JSON structure but use markdown comment format
                if table_ddl:
                    try:
                        # Check if DDL is JSON format
                        ddl_json = json.loads(table_ddl)
                        if isinstance(ddl_json, dict) and "columns" in ddl_json:
                            # It's JSON format, convert to markdown comment format using _build_table_ddl
                            if self.retrieval_helper and "table_retrieval" in self.retrieval_helper.retrievers:
                                table_retrieval = self.retrieval_helper.retrievers["table_retrieval"]
                                # Extract table name, description, and columns from JSON
                                json_table_name = ddl_json.get("table_name", table_name)
                                json_description = ddl_json.get("description", description or full_table_description)
                                json_columns = ddl_json.get("columns", table_columns)
                                
                                # Convert columns to format expected by _build_table_ddl
                                columns_for_ddl = []
                                for col in json_columns:
                                    if isinstance(col, dict):
                                        columns_for_ddl.append({
                                            "name": col.get("name", ""),
                                            "type": col.get("type", ""),
                                            "description": col.get("description", ""),
                                            "data_type": col.get("type", ""),  # _build_table_ddl looks for data_type or type
                                        })
                                
                                # Build DDL in markdown comment format
                                table_ddl = table_retrieval._build_table_ddl(
                                    table_name=json_table_name,
                                    description=json_description,
                                    columns=columns_for_ddl
                                )
                                logger.info(f"MDLTableCurationNode: Converted JSON DDL to markdown format for {table_name}")
                            else:
                                logger.warning(f"MDLTableCurationNode: Cannot convert JSON DDL - TableRetrieval not available")
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        # Not JSON format or error parsing, use DDL as-is (should already be markdown format)
                        pass
                
                # Build comprehensive table info with full description, comments, DDL, and columns
                table_info = {
                    "table_name": table_name,
                    "relevance_score": relevance_score,
                    "description": description,  # Brief description from curation
                    "full_description": full_table_description,  # Full table description retrieved
                    "comments": table_comments,  # Table comments
                    "ddl": table_ddl,  # Table DDL in markdown comment format (-- description\nCREATE TABLE ...)
                    "columns": table_columns,  # Table columns from column_metadata
                    "categories": categories,
                    "metadata": table_metadata if table_metadata else (matching_table.get("metadata", {}) if matching_table else {"table_name": table_name, "product_name": product_name}),
                    "content": full_table_description or (matching_table.get("content", "")[:1000] if matching_table else ""),  # Full content for contextual planner
                    "source": "mdl_curation"
                }
                curated_tables_info.append(table_info)
            
            logger.info(f"MDLTableCurationNode: Enriched {len(curated_tables_info)} curated tables with full descriptions and comments")
            
            # Step 4: Fetch document contexts for curated tables
            contexts_retrieved = []
            logger.info(f"MDLTableCurationNode: Fetching document contexts for {len(curated_tables_info)} curated tables")
            
            for table_info in curated_tables_info:
                table_name = table_info.get("table_name", "")
                if not table_name:
                    continue
                
                # Check if context_id is already in table_info or metadata
                context_id = table_info.get("context_id")
                if not context_id:
                    metadata = table_info.get("metadata", {})
                    context_id = metadata.get("context_id")
                
                # If not found, construct context_id in format: entity_{product_name}_{table_name}
                if not context_id:
                    context_id = f"entity_{product_name}_{table_name}" if product_name else f"entity_{table_name}"
                
                try:
                    # Try to retrieve context using context_id
                    if self.retriever:
                        context_results = await self.retriever.retrieve_context_definitions(
                            query=f"Context for {table_name}",
                            filters={"context_id": context_id},
                            top_k=1
                        )
                        
                        if context_results:
                            context_data = context_results[0]
                            metadata = context_data.get("metadata", {})
                            context_entry = {
                                "context_id": context_id,
                                "table_name": table_name,
                                "metadata": metadata,
                                "content": context_data.get("content", ""),
                                "source": "mdl_table_curation",
                                "retrieval_method": "context_definitions_by_id",
                                "node": "MDLTableCurationNode"
                            }
                            contexts_retrieved.append(context_entry)
                            logger.info(f"MDLTableCurationNode: Retrieved context for table '{table_name}' (context_id: {context_id})")
                            
                            # Also add context_id to table_info for reference
                            if "context_id" not in table_info:
                                table_info["context_id"] = context_id
                        else:
                            # Try alternative context_id format (without product_name prefix)
                            alt_context_id = f"entity_{table_name}"
                            if alt_context_id != context_id:
                                alt_context_results = await self.retriever.retrieve_context_definitions(
                                    query=f"Context for {table_name}",
                                    filters={"context_id": alt_context_id},
                                    top_k=1
                                )
                                if alt_context_results:
                                    context_data = alt_context_results[0]
                                    metadata = context_data.get("metadata", {})
                                    context_entry = {
                                        "context_id": alt_context_id,
                                        "table_name": table_name,
                                        "metadata": metadata,
                                        "content": context_data.get("content", ""),
                                        "source": "mdl_table_curation",
                                        "retrieval_method": "context_definitions_by_id_alt",
                                        "node": "MDLTableCurationNode"
                                    }
                                    contexts_retrieved.append(context_entry)
                                    table_info["context_id"] = alt_context_id
                                    logger.info(f"MDLTableCurationNode: Retrieved context for table '{table_name}' (context_id: {alt_context_id})")
                                else:
                                    logger.debug(f"MDLTableCurationNode: No context found for table '{table_name}' (tried {context_id} and {alt_context_id})")
                            else:
                                logger.debug(f"MDLTableCurationNode: No context found for table '{table_name}' (context_id: {context_id})")
                    else:
                        logger.warning(f"MDLTableCurationNode: Retriever not available, cannot fetch context for table '{table_name}'")
                except Exception as e:
                    logger.warning(f"MDLTableCurationNode: Error fetching context for table '{table_name}': {e}")
            
            logger.info(f"MDLTableCurationNode: Retrieved {len(contexts_retrieved)} document contexts for curated tables")
            
            # Initialize contexts_retrieved in state if not present, then extend
            if "contexts_retrieved" not in state:
                state["contexts_retrieved"] = []
            elif not isinstance(state["contexts_retrieved"], list):
                state["contexts_retrieved"] = []
            
            # Validate contexts before adding
            validated_contexts = []
            for ctx in contexts_retrieved:
                if isinstance(ctx, dict) and ctx.get("context_id"):
                    validated_contexts.append(ctx)
                elif isinstance(ctx, str):
                    # Skip dictionary keys or single characters
                    if len(ctx) > 1 and ctx not in ["context_id", "table_name", "metadata", "content", "source"]:
                        logger.warning(f"MDLTableCurationNode: Skipping string in contexts_retrieved: '{ctx[:50]}...'")
            
            state["contexts_retrieved"].extend(validated_contexts)
            logger.info(f"MDLTableCurationNode: Added {len(validated_contexts)} contexts to state (total: {len(state['contexts_retrieved'])})")
            
            # Log full LLM responses for all queries
            logger.info("=" * 80)
            logger.info("MDLTableCurationNode: Full LLM Responses for All MDL Queries (NO TRUNCATION)")
            logger.info("=" * 80)
            for i, mdl_result in enumerate(all_mdl_results, 1):
                logger.info(f"\nMDL Query {i}: {mdl_result['mdl_query']}")
                logger.info(f"Curated Tables: {len(mdl_result['curated_tables'])}")
                logger.info(f"Tables Considered: {mdl_result['total_tables_considered']}, Pruned: {mdl_result['tables_pruned']}")
                logger.info(f"Reasoning: {mdl_result['reasoning']}")
            logger.info("=" * 80)
            
            # Update state with curated tables
            state["context_breakdown"] = {
                "user_question": user_question,
                "query_type": query_type,
                "mdl_queries": mdl_queries,  # Store all MDL queries processed
                "mdl_results": all_mdl_results,  # Store curation results for each MDL query
                "curated_tables": curated_tables_final,  # Curated tables with scores
                "curated_tables_info": curated_tables_info,  # Curated tables with full descriptions
                "reasoning": "\n\n".join(all_reasoning),
                "identified_entities": generic_breakdown.get("identified_entities", []),
                "entity_sub_types": generic_breakdown.get("entity_sub_types", []),
                "generic_breakdown": generic_breakdown
            }
            # Normalize identified_entities from generic_breakdown before storing in state
            identified_entities_from_breakdown = generic_breakdown.get("identified_entities", [])
            identified_entities_from_breakdown = normalize_string_list(identified_entities_from_breakdown, "identified_entities")
            state["identified_entities"] = identified_entities_from_breakdown
            
            # Normalize relevant_tables - ensure table names are strings, not characters
            relevant_tables_list = []
            for t in curated_tables_final:
                if isinstance(t, dict):
                    table_name = t.get("table_name")
                    if table_name and isinstance(table_name, str) and len(table_name.strip()) > 1:
                        relevant_tables_list.append(table_name)
                elif isinstance(t, str) and len(t.strip()) > 1:
                    # Fallback if table_name is passed directly
                    relevant_tables_list.append(t)
            state["relevant_tables"] = relevant_tables_list  # Store curated table names
            
            # Validate and set tables_found - must be a list of dicts
            validated_tables_found = []
            if isinstance(curated_tables_info, list):
                for item in curated_tables_info:
                    if isinstance(item, dict):
                        validated_tables_found.append(item)
                    elif isinstance(item, str):
                        # Skip dictionary keys or single characters
                        if len(item) > 1 and item not in ["table_name", "relevance_score", "description", "full_description", 
                                                          "comments", "ddl", "columns", "categories", "metadata", "content", "source"]:
                            logger.warning(f"MDLTableCurationNode: Skipping string in curated_tables_info: '{item[:50]}...'")
            elif isinstance(curated_tables_info, dict):
                # If a single dict was passed, wrap it in a list
                logger.warning("MDLTableCurationNode: curated_tables_info was a dict, wrapping in list")
                validated_tables_found = [curated_tables_info]
            else:
                logger.warning(f"MDLTableCurationNode: curated_tables_info was unexpected type {type(curated_tables_info)}, using empty list")
            
            state["tables_found"] = validated_tables_found  # Store curated tables with full info
            state["current_step"] = "mdl_curation"
            state["status"] = "processing"
            
            total_considered = sum(r.get("total_tables_considered", 0) for r in all_mdl_results)
            total_pruned = sum(r.get("tables_pruned", 0) for r in all_mdl_results)
            
            logger.info(f"MDLTableCurationNode: Processed {len(mdl_queries)} MDL queries in parallel")
            logger.info(f"MDLTableCurationNode: Curated {len(curated_tables_final)} unique tables (considered {total_considered}, pruned {total_pruned})")
            top_tables_str = ', '.join([f"{t['table_name']}({t.get('relevance_score', 0):.2f})" for t in curated_tables_final[:5]])
            logger.info(f"MDLTableCurationNode: Top tables by score: {top_tables_str}")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLTableCurationNode: Error: {str(e)}", exc_info=True)
            # Fallback to generic breakdown on error
            state["context_breakdown"] = generic_breakdown
            state["current_step"] = "mdl_curation"
            return state


class MDLEntityIdentificationNode:
    """Node that identifies tables and entities from context breakdown"""
    
    def __init__(
        self,
        retriever: MDLSemanticRetriever,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.retriever = retriever
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Identify tables and entities from context breakdown"""
        logger.info("MDLEntityIdentificationNode: Starting execution")
        
        context_breakdown = state.get("context_breakdown", {})
        search_questions_raw = state.get("search_questions", [])
        product_name = state.get("product_name")
        
        # Ensure search_questions is a list of dicts (handle reducer merging issues)
        search_questions = []
        for item in search_questions_raw:
            if isinstance(item, dict):
                search_questions.append(item)
            elif isinstance(item, str):
                # Try to parse if it's a JSON string
                try:
                    import json
                    parsed = json.loads(item)
                    if isinstance(parsed, dict):
                        search_questions.append(parsed)
                    else:
                        logger.warning(f"MDLEntityIdentificationNode: Skipping non-dict parsed item: {type(parsed)}")
                except:
                    logger.warning(f"MDLEntityIdentificationNode: Skipping string search question: {item[:50]}...")
            else:
                logger.warning(f"MDLEntityIdentificationNode: Skipping non-dict search question: {type(item)}")
        
        if not search_questions:
            logger.warning("MDLEntityIdentificationNode: No valid search questions available")
            state["current_step"] = "entity_identification"
            return state
        
        logger.info(f"MDLEntityIdentificationNode: Processing {len(search_questions)} search questions")
        
        try:
            tables_found = []
            entities_found = []
            entity_questions = []
            
            # Process each search question to identify entities
            for sq in search_questions:
                entity_name = sq.get("entity", "")
                question = sq.get("question", "")
                filters = sq.get("metadata_filters", {})
                
                # Identify tables from schema-related entities
                # Note: schema_descriptions are now handled by project_reader.py via table_description component
                # Only use table_definitions, table_descriptions, and context_definitions
                if entity_name in ["table_definitions", "table_descriptions", "context_definitions"]:
                    # Retrieve table information
                    if entity_name == "context_definitions":
                        results = await self.retriever.retrieve_context_definitions(
                            query=question,
                            filters=filters,
                            top_k=10
                        )
                        for result in results:
                            metadata = result.get("metadata", {})
                            context_id = metadata.get("context_id", "")
                            
                            # Check if this is a table entity
                            if context_id.startswith("entity_") and product_name:
                                # Extract table name from context_id
                                table_name = context_id.replace(f"entity_{product_name}_", "").replace("entity_", "")
                                table_entry = {
                                    "table_name": table_name,
                                    "context_id": context_id,
                                    "entity_type": "table",
                                    "metadata": metadata,
                                    "source": "context_definitions"
                                }
                                tables_found.append(table_entry)
                                logger.info(f"MDLEntityIdentificationNode: Found table '{table_name}' from context_definitions (context_id: {context_id})")
                    elif entity_name in ["table_definitions", "table_descriptions"]:
                        project_id = state.get("project_id") or filters.get("product_name") if filters else state.get("product_name") or "Snyk"
                        results = await self.retriever.retrieve_table_descriptions(
                            query=question,
                            filters=filters,
                            top_k=10,
                            project_id=project_id
                        )
                        for result in results:
                            metadata = result.get("metadata", {})
                            table_name = metadata.get("table_name", "")
                            if table_name:
                                table_entry = {
                                    "table_name": table_name,
                                    "entity_type": "table",
                                    "metadata": metadata,
                                    "source": entity_name
                                }
                                tables_found.append(table_entry)
                                logger.info(f"MDLEntityIdentificationNode: Found table '{table_name}' from {entity_name}")
                
                # Note: Non-schema entities (compliance_controls, policy entities, risk entities, etc.) 
                # are handled in contextual reasoning nodes AFTER tables are curated.
                # This ensures tables are retrieved first, then contexts are fetched based on curated tables.
                
                # Generate natural language questions for entities
                if entity_name and question:
                    entity_questions.append({
                        "entity": entity_name,
                        "question": question,
                        "filters": filters
                    })
            
            # Use LLM to extract and structure entity information
            if tables_found or entities_found:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are an expert at identifying and structuring entities from MDL queries.

Given tables and entities found, create structured entity information with:
- Entity names and types
- Natural language questions for each entity
- Relationships between entities
- Key attributes

Return JSON with:
- structured_entities: List of structured entity objects with name, type, attributes, questions
- entity_relationships: List of relationships between entities
- natural_language_questions: List of natural language questions for each entity
"""),
                    ("human", """Structure these entities:

Tables Found:
{tables}

Entities Found:
{entities}

User Question: {user_question}
Product: {product_name}

Return structured entity information as JSON.""")
                ])
                
                chain = prompt | self.llm | self.json_parser
                
                # Prepare input for logging
                tables_json = json.dumps(tables_found[:20], indent=2)
                entities_json = json.dumps(entities_found[:20], indent=2)
                prompt_input = {
                    "tables": tables_json,
                    "entities": entities_json,
                    "user_question": state.get("user_question", ""),
                    "product_name": product_name or "Unknown"
                }
                
                # Log full prompt without truncation
                logger.info("=" * 80)
                logger.info("MDLEntityIdentificationNode: Full LLM Prompt (NO TRUNCATION)")
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
                logger.info(f"  user_question: {prompt_input['user_question']}")
                logger.info(f"  product_name: {prompt_input['product_name']}")
                logger.info(f"  tables (full JSON, {len(tables_json)} chars):\n{tables_json}")
                logger.info(f"  entities (full JSON, {len(entities_json)} chars):\n{entities_json}")
                logger.info("=" * 80)
                
                result = await chain.ainvoke(prompt_input)
                
                # Log full LLM response without truncation
                logger.info("=" * 80)
                logger.info("MDLEntityIdentificationNode: Full LLM Response (NO TRUNCATION)")
                logger.info("=" * 80)
                logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
                logger.info("=" * 80)
                
                # Update state with structured entities
                structured_entities = result.get("structured_entities", [])
                # Ensure structured_entities is a list, not a dict (which would cause keys to be added)
                if isinstance(structured_entities, dict):
                    logger.warning(f"MDLEntityIdentificationNode: structured_entities is a dict, not a list. Converting to list of values.")
                    structured_entities = list(structured_entities.values())
                elif not isinstance(structured_entities, list):
                    logger.warning(f"MDLEntityIdentificationNode: structured_entities is {type(structured_entities)}, expected list. Skipping.")
                    structured_entities = []
                entities_found.extend(structured_entities)
                
                # Add natural language questions
                nl_questions = result.get("natural_language_questions", [])
                if "natural_language_questions" not in state:
                    state["natural_language_questions"] = []
                state["natural_language_questions"].extend(nl_questions)
            
            # Validate tables_found and entities_found - ensure they're lists of dicts
            validated_tables_found = []
            if isinstance(tables_found, list):
                for item in tables_found:
                    if isinstance(item, dict):
                        validated_tables_found.append(item)
                    elif isinstance(item, str):
                        # Skip dictionary keys and single characters
                        if len(item) > 1 and item not in ["table_name", "entity_type", "metadata", "source", "context_id"]:
                            logger.warning(f"MDLEntityIdentificationNode: Skipping string in tables_found: '{item[:50]}...'")
            elif isinstance(tables_found, dict):
                validated_tables_found = [tables_found]
                logger.warning("MDLEntityIdentificationNode: tables_found was a dict, wrapping in list")
            else:
                logger.warning(f"MDLEntityIdentificationNode: tables_found was unexpected type {type(tables_found)}, using empty list")
            
            validated_entities_found = []
            if isinstance(entities_found, list):
                for item in entities_found:
                    if isinstance(item, dict):
                        validated_entities_found.append(item)
                    elif isinstance(item, str) and len(item) > 1:
                        logger.warning(f"MDLEntityIdentificationNode: Skipping string in entities_found: '{item[:50]}...'")
            elif isinstance(entities_found, dict):
                validated_entities_found = [entities_found]
                logger.warning("MDLEntityIdentificationNode: entities_found was a dict, wrapping in list")
            else:
                logger.warning(f"MDLEntityIdentificationNode: entities_found was unexpected type {type(entities_found)}, using empty list")
            
            # Log state before update for debugging
            logger.info("=" * 80)
            logger.info("MDLEntityIdentificationNode: State BEFORE Update (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Current tables_found in state: {json.dumps(state.get('tables_found', []), indent=2, default=str)}")
            logger.info(f"New tables_found to add: {json.dumps(validated_tables_found, indent=2, default=str)}")
            logger.info(f"Current entities_found in state: {json.dumps(state.get('entities_found', []), indent=2, default=str)}")
            logger.info(f"New entities_found to add: {json.dumps(validated_entities_found, indent=2, default=str)}")
            logger.info("=" * 80)
            
            # Update state with validated data
            state["tables_found"] = validated_tables_found
            state["entities_found"] = validated_entities_found
            state["entity_questions"] = entity_questions
            state["current_step"] = "entity_identification"
            state["status"] = "processing"
            
            # Log state after update
            logger.info("=" * 80)
            logger.info("MDLEntityIdentificationNode: State AFTER Update (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Updated tables_found: {json.dumps(state.get('tables_found', []), indent=2, default=str)}")
            logger.info(f"Updated entities_found: {json.dumps(state.get('entities_found', []), indent=2, default=str)}")
            logger.info("=" * 80)
            
            logger.info(f"MDLEntityIdentificationNode: Found {len(tables_found)} tables, {len(entities_found)} entities")
            if tables_found:
                logger.info("MDLEntityIdentificationNode: All identified tables:")
                for table in tables_found:
                    table_name = table.get("table_name", "Unknown")
                    source = table.get("source", "Unknown")
                    context_id = table.get("context_id", "N/A")
                    logger.info(f"  - {table_name} (source: {source}, context_id: {context_id})")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLEntityIdentificationNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Entity identification failed: {str(e)}"
            return state


class MDLTableRetrievalNode:
    """Node that uses LLM to generate retrieval queries and retrieves tables/entities"""
    
    def __init__(
        self,
        table_retrieval_agent: MDLTableRetrievalAgent,
        retriever: MDLSemanticRetriever
    ):
        self.table_retrieval_agent = table_retrieval_agent
        self.retriever = retriever
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Generate retrieval queries and retrieve tables/entities"""
        logger.info("MDLTableRetrievalNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name")
        context_breakdown = state.get("context_breakdown", {})
        
        if not user_question:
            logger.warning("MDLTableRetrievalNode: No user question available")
            state["current_step"] = "table_retrieval"
            return state
        
        try:
            # Step 1: Generate retrieval queries using LLM agent
            logger.info("MDLTableRetrievalNode: Generating retrieval queries with LLM")
            retrieval_plan = await self.table_retrieval_agent.generate_retrieval_queries(
                user_question=user_question,
                context_breakdown=context_breakdown,
                product_name=product_name
            )
            
            retrieval_queries = retrieval_plan.get("retrieval_queries", [])
            logger.info(f"MDLTableRetrievalNode: Generated {len(retrieval_queries)} retrieval queries")
            
            # Step 2: Execute retrieval queries
            tables_found = []
            entities_found = []
            contexts_retrieved = []
            
            for rq in retrieval_queries:
                entity = rq.get("entity", "")
                query = rq.get("query", "")
                filters = rq.get("metadata_filters", {})
                
                logger.info(f"MDLTableRetrievalNode: Retrieving from {entity} with query: {query[:80]}...")
                
                try:
                    # Note: schema_descriptions are now handled by project_reader.py via table_description component
                    # Skip schema_descriptions entity type
                    if entity == "schema_descriptions":
                        logger.warning(f"MDLTableRetrievalNode: schema_descriptions entity type is deprecated. Use table_descriptions instead.")
                        continue
                    
                    if entity == "table_definitions":
                        results = await self.retriever.retrieve_by_entity(
                            entity=entity,
                            query=query,
                            filters=filters,
                            top_k=10
                        )
                        for result in results:
                            metadata = result.get("metadata", {})
                            table_name = metadata.get("table_name", "")
                            if table_name:
                                table_entry = {
                                    "table_name": table_name,
                                    "entity_type": "table",
                                    "metadata": metadata,
                                    "content": result.get("content", "")[:200],
                                    "source": "table_definitions"
                                }
                                tables_found.append(table_entry)
                                logger.info(f"MDLTableRetrievalNode: Retrieved table '{table_name}' from table_definitions")
                    
                    elif entity == "table_descriptions":
                        project_id = state.get("project_id") or filters.get("product_name") if filters else state.get("product_name") or "Snyk"
                        results = await self.retriever.retrieve_table_descriptions(
                            query=query,
                            filters=filters,
                            top_k=10,
                            project_id=project_id
                        )
                        for result in results:
                            metadata = result.get("metadata", {})
                            table_name = metadata.get("table_name", "")
                            if table_name:
                                table_entry = {
                                    "table_name": table_name,
                                    "entity_type": "table",
                                    "metadata": metadata,
                                    "content": result.get("content", "")[:200],
                                    "source": "table_descriptions"
                                }
                                tables_found.append(table_entry)
                                logger.info(f"MDLTableRetrievalNode: Retrieved table '{table_name}' from table_descriptions")
                    
                    elif entity == "context_definitions":
                        results = await self.retriever.retrieve_context_definitions(
                            query=query,
                            filters=filters,
                            top_k=10
                        )
                        for result in results:
                            metadata = result.get("metadata", {})
                            context_id = metadata.get("context_id", "")
                            if context_id.startswith("entity_") and product_name:
                                table_name = context_id.replace(f"entity_{product_name}_", "").replace("entity_", "")
                                table_entry = {
                                    "table_name": table_name,
                                    "context_id": context_id,
                                    "entity_type": "table",
                                    "metadata": metadata,
                                    "content": result.get("content", "")[:200],
                                    "source": "context_definitions"
                                }
                                tables_found.append(table_entry)
                                logger.info(f"MDLTableRetrievalNode: Retrieved table '{table_name}' from context_definitions (context_id: {context_id})")
                            else:
                                contexts_retrieved.append({
                                    "context_id": context_id,
                                    "metadata": metadata,
                                    "content": result.get("content", "")[:200],
                                    "source": "mdl_table_retrieval",
                                    "entity_type": entity,
                                    "retrieval_method": "context_definitions_by_query"
                                })
                    
                    elif entity == "contextual_edges":
                        edges = await self.retriever.retrieve_edges(
                            query=query,
                            filters=filters,
                            top_k=10
                        )
                        for edge in edges:
                            entities_found.append({
                                "entity_type": "edge",
                                "edge_type": edge.edge_type,
                                "source_entity_id": edge.source_entity_id,
                                "target_entity_id": edge.target_entity_id,
                                "relevance_score": edge.relevance_score,
                                "source": "contextual_edges"
                            })
                        results = edges  # For logging
                    
                    result_count = len(results) if results else 0
                    logger.info(f"MDLTableRetrievalNode: Retrieved {result_count} results from {entity}")
                    if result_count == 0:
                        logger.warning(f"MDLTableRetrievalNode: No results from {entity} with query '{query[:80]}...' and filters {filters}")
                    
                except Exception as e:
                    logger.warning(f"MDLTableRetrievalNode: Error retrieving from {entity}: {str(e)}")
                    continue
            
            # Log state before update for debugging
            logger.info("=" * 80)
            logger.info("MDLTableRetrievalNode: State BEFORE Update (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Current tables_found in state: {json.dumps(state.get('tables_found', []), indent=2, default=str)}")
            logger.info(f"New tables_found to add: {json.dumps(tables_found, indent=2, default=str)}")
            logger.info(f"Current entities_found in state: {json.dumps(state.get('entities_found', []), indent=2, default=str)}")
            logger.info(f"New entities_found to add: {json.dumps(entities_found, indent=2, default=str)}")
            logger.info("=" * 80)
            
            # Update state (reducers will merge with existing values)
            # Append new results - reducers will handle deduplication
            state["tables_found"] = tables_found
            state["entities_found"] = entities_found
            state["contexts_retrieved"] = contexts_retrieved
            state["current_step"] = "table_retrieval"
            state["status"] = "processing"
            
            # Log state after update
            logger.info("=" * 80)
            logger.info("MDLTableRetrievalNode: State AFTER Update (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Updated tables_found: {json.dumps(state.get('tables_found', []), indent=2, default=str)}")
            logger.info(f"Updated entities_found: {json.dumps(state.get('entities_found', []), indent=2, default=str)}")
            logger.info("=" * 80)
            
            total_tables = len(state.get("tables_found", []))
            total_entities = len(state.get("entities_found", []))
            total_contexts = len(state.get("contexts_retrieved", []))
            
            # Log all retrieved tables with details
            logger.info(f"MDLTableRetrievalNode: Retrieved {len(tables_found)} new tables, {len(entities_found)} new entities, {len(contexts_retrieved)} new contexts")
            if tables_found:
                logger.info("MDLTableRetrievalNode: All retrieved tables:")
                for table in tables_found:
                    table_name = table.get("table_name", "Unknown")
                    source = table.get("source", "Unknown")
                    context_id = table.get("context_id", "N/A")
                    logger.info(f"  - {table_name} (source: {source}, context_id: {context_id})")
            logger.info(f"MDLTableRetrievalNode: Total state: {total_tables} tables, {total_entities} entities, {total_contexts} contexts")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLTableRetrievalNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Table retrieval failed: {str(e)}"
            return state


class MDLTablePruningNode:
    """Node that prunes retrieved tables using MDL rules and user question"""
    
    def __init__(
        self,
        retriever: MDLSemanticRetriever,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.retriever = retriever
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Prune retrieved tables and query specific table contexts/relationships"""
        logger.info("MDLTablePruningNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name")
        all_tables_found = state.get("tables_found", [])
        context_breakdown = state.get("context_breakdown", {})
        
        if not user_question:
            logger.warning("MDLTablePruningNode: No user question available")
            state["current_step"] = "table_pruning"
            return state
        
        try:
            # Filter to only tables retrieved from vector store
            vector_store_sources = {"table_definitions", "table_descriptions", "context_definitions"}
            tables_found = [
                table for table in all_tables_found 
                if isinstance(table, dict) and table.get("source") in vector_store_sources
            ]
            
            logger.info(f"MDLTablePruningNode: Pruning {len(tables_found)} tables based on user question and MDL rules")
            
            if not tables_found:
                logger.warning("MDLTablePruningNode: No tables found to prune")
                state["current_step"] = "table_pruning"
                state["pruned_tables"] = []
                return state
            
            # Use LLM to prune tables based on user question and MDL rules
            # Following prompts.txt rules: use schema_descriptions, table_descriptions, contextual_edges
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at pruning tables for MDL semantic layer queries.

Given a user question and retrieved tables, prune tables that are relevant to the question.
Follow MDL semantic layer rules:
- For table queries, use schema_descriptions for available categories
- Table relationships use specific edge types: BELONGS_TO_TABLE, HAS_MANY_TABLES, REFERENCES_TABLE, etc.
- Table entity IDs follow format: entity_{{product_name}}_{{table_name}}
- Always include product_name and table_name in metadata filters
- Use contextual_edges with appropriate edge_type filters for relationship queries

After pruning, generate specific queries for:
1. Table contexts (context_definitions with context_id = entity_{{product}}_{{table}})
2. Table relationships (contextual_edges with source_entity_id = entity_{{product}}_{{table}})

Return JSON with:
- pruned_tables: List of relevant table names (pruned from input)
- table_context_queries: List of queries for table contexts
- table_relationship_queries: List of queries for table relationships
"""),
                ("human", """Prune tables and generate specific queries:

User Question: {user_question}
Product: {product_name}
Retrieved Tables: {tables_json}

Context Breakdown:
{context_breakdown_json}

Prune tables that are relevant to the question and generate specific queries for:
1. Table contexts using context_definitions with context_id filters
2. Table relationships using contextual_edges with source_entity_id and edge_type filters

Return JSON with pruned_tables, table_context_queries, and table_relationship_queries.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Prepare input
            tables_json = json.dumps(tables_found[:50], indent=2)  # Limit to avoid token limits
            context_breakdown_json = json.dumps(context_breakdown, indent=2, default=str)
            
            prompt_input = {
                "user_question": user_question,
                "product_name": product_name or "Unknown",
                "tables_json": tables_json,
                "context_breakdown_json": context_breakdown_json
            }
            
            # Log full prompt without truncation
            logger.info("=" * 80)
            logger.info("MDLTablePruningNode: Full LLM Prompt (NO TRUNCATION)")
            logger.info("=" * 80)
            try:
                formatted_messages = prompt.format_messages(**prompt_input)
                logger.info(f"System Prompt:\n{formatted_messages[0].content}")
                logger.info(f"Human Prompt:\n{formatted_messages[1].content}")
            except Exception as e:
                logger.warning(f"Could not format prompt for logging: {e}")
            logger.info(f"Prompt Variables:")
            logger.info(f"  user_question: {prompt_input['user_question']}")
            logger.info(f"  product_name: {prompt_input['product_name']}")
            logger.info(f"  tables_json ({len(tables_json)} chars):\n{tables_json}")
            logger.info("=" * 80)
            
            result = await chain.ainvoke(prompt_input)
            
            # Log full LLM response without truncation
            logger.info("=" * 80)
            logger.info("MDLTablePruningNode: Full LLM Response (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
            logger.info("=" * 80)
            
            pruned_table_names = result.get("pruned_tables", [])
            table_context_queries = result.get("table_context_queries", [])
            table_relationship_queries = result.get("table_relationship_queries", [])
            
            # Filter tables to only pruned ones
            pruned_tables = [
                table for table in tables_found
                if isinstance(table, dict) and table.get("table_name") in pruned_table_names
            ]
            
            logger.info(f"MDLTablePruningNode: Pruned from {len(tables_found)} to {len(pruned_tables)} tables")
            logger.info(f"MDLTablePruningNode: Generated {len(table_context_queries)} context queries, {len(table_relationship_queries)} relationship queries")
            
            # Execute context queries for pruned tables
            contexts_retrieved = []
            for query_obj in table_context_queries:
                entity = query_obj.get("entity", "context_definitions")
                query = query_obj.get("query", "")
                filters = query_obj.get("metadata_filters", {})
                
                try:
                    results = await self.retriever.retrieve_context_definitions(
                        query=query,
                        filters=filters,
                        top_k=5
                    )
                    for result in results:
                        metadata = result.get("metadata", {})
                        context_id = metadata.get("context_id", "")
                        contexts_retrieved.append({
                            "context_id": context_id,
                            "metadata": metadata,
                            "content": result.get("content", "")[:500],
                            "source": "mdl_table_pruning",
                            "entity_type": entity,
                            "retrieval_method": "context_definitions_by_query",
                            "query": query[:200] if query else ""
                        })
                except Exception as e:
                    logger.warning(f"MDLTablePruningNode: Error retrieving context: {str(e)}")
            
            # Execute relationship queries for pruned tables
            edges_discovered = []
            for query_obj in table_relationship_queries:
                entity = query_obj.get("entity", "contextual_edges")
                query = query_obj.get("query", "")
                filters = query_obj.get("metadata_filters", {})
                
                try:
                    edges = await self.retriever.retrieve_edges(
                        query=query,
                        filters=filters,
                        top_k=10
                    )
                    for edge in edges:
                        edges_discovered.append({
                            "edge_type": edge.edge_type,
                            "source_entity_id": edge.source_entity_id,
                            "target_entity_id": edge.target_entity_id,
                            "relevance_score": edge.relevance_score,
                            "source": "mdl_table_pruning",
                            "retrieval_method": "contextual_edges_by_query",
                            "node": "MDLTablePruningNode",
                            "query": query[:200] if query else ""
                        })
                except Exception as e:
                    logger.warning(f"MDLTablePruningNode: Error retrieving relationships: {str(e)}")
            
            # Update state with pruned tables and additional contexts/edges
            state["pruned_tables"] = pruned_tables
            state["table_context_queries"] = table_context_queries
            state["table_relationship_queries"] = table_relationship_queries
            
            # Validate before merging - ensure lists contain only dicts
            validated_contexts = [item for item in contexts_retrieved if isinstance(item, dict)]
            validated_edges = [item for item in edges_discovered if isinstance(item, dict)]
            
            # Merge with existing contexts and edges (reducers will handle deduplication)
            if "contexts_retrieved" not in state:
                state["contexts_retrieved"] = []
            state["contexts_retrieved"].extend(validated_contexts)
            
            if "edges_discovered" not in state:
                state["edges_discovered"] = []
            state["edges_discovered"].extend(validated_edges)
            
            state["current_step"] = "table_pruning"
            state["status"] = "processing"
            
            logger.info(f"MDLTablePruningNode: Added {len(contexts_retrieved)} contexts, {len(edges_discovered)} edges from pruning")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLTablePruningNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Table pruning failed: {str(e)}"
            return state


class MDLContextRetrievalNode:
    """Node that retrieves contexts and edges from contextual graph"""
    
    def __init__(
        self,
        mdl_semantic_layer_service: MDLSemanticLayerService
    ):
        self.mdl_semantic_layer_service = mdl_semantic_layer_service
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Retrieve contexts and edges from contextual graph"""
        logger.info("MDLContextRetrievalNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name")
        all_tables_found = state.get("tables_found", [])
        
        # Filter to only tables retrieved from vector store (from MDLTableRetrievalNode)
        # These have sources: "table_definitions", "table_descriptions", "context_definitions"
        # Exclude tables from entity identification which may not have been retrieved from vector store yet
        vector_store_sources = {"table_definitions", "table_descriptions", "context_definitions"}
        tables_found = [
            table for table in all_tables_found 
            if isinstance(table, dict) and table.get("source") in vector_store_sources
        ]
        
        logger.info(f"MDLContextRetrievalNode: Using {len(tables_found)} tables from vector store (out of {len(all_tables_found)} total tables in state)")
        
        if not user_question:
            logger.warning("MDLContextRetrievalNode: No user question available")
            state["current_step"] = "context_retrieval"
            return state
        
        try:
            contexts_retrieved = []
            edges_discovered = []
            related_entities = []
            
            # Discover MDL semantic edges
            edge_result = await self.mdl_semantic_layer_service.discover_mdl_semantic_edges(
                user_question=user_question,
                product_name=product_name,
                top_k=20
            )
            
            edges = edge_result.get("edges", [])
            for edge in edges:
                edges_discovered.append({
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type,
                    "source_entity_id": edge.source_entity_id,
                    "target_entity_id": edge.target_entity_id,
                    "source_entity_type": edge.source_entity_type,
                    "target_entity_type": edge.target_entity_type,
                    "document": edge.document,
                    "relevance_score": edge.relevance_score,
                    "source": "mdl_context_retrieval",
                    "retrieval_method": "mdl_semantic_edges"
                })
                
                # Collect related entities
                if edge.source_entity_id:
                    related_entities.append({
                        "entity_id": edge.source_entity_id,
                        "entity_type": edge.source_entity_type,
                        "role": "source"
                    })
                if edge.target_entity_id:
                    related_entities.append({
                        "entity_id": edge.target_entity_id,
                        "entity_type": edge.target_entity_type,
                        "role": "target"
                    })
            
            # Get entities from edges
            if edges:
                entities_result = await self.mdl_semantic_layer_service.get_entities_from_mdl_edges(
                    edges=edges,
                    user_question=user_question,
                    top_k=10
                )
                related_entities.extend(entities_result.get("entities", []))
            
            # Retrieve contexts for tables retrieved from vector store
            for table in tables_found:
                # Ensure table is a dict (handle cases where it might be a string or other type)
                logger.info(f"MDLContextRetrievalNode: Retrieving context for table: {table}")
                if not isinstance(table, dict):
                    table_value = str(table)[:200] if table else "None"
                    logger.warning(f"MDLContextRetrievalNode: Skipping non-dict table entry: {type(table)} - value: {table_value}")
                    continue
                
                context_id = table.get("context_id")
                if context_id:
                    # Retrieve context definition using retriever
                    retriever = self.mdl_semantic_layer_service.retriever
                    table_name = table.get("table_name", "unknown")
                    contexts = await retriever.retrieve_context_definitions(
                        query=f"Context for {table_name}",
                        filters={"context_id": context_id},
                        top_k=1
                    )
                    if contexts:
                        contexts_retrieved.append({
                            "context_id": context_id,
                            "table_name": table_name,
                            "context_data": contexts[0],
                            "source": "mdl_context_retrieval",
                            "retrieval_method": "context_definitions_by_id"
                        })
            
            # Validate edges_discovered - ensure it's a list of dicts
            validated_edges_discovered = []
            if isinstance(edges_discovered, list):
                for item in edges_discovered:
                    if isinstance(item, dict):
                        validated_edges_discovered.append(item)
                    elif isinstance(item, str):
                        # Skip dictionary keys and single characters
                        if len(item) > 1 and item not in ["edge_id", "edge_type", "source_entity_id", 
                                                          "target_entity_id", "source_entity_type", 
                                                          "target_entity_type", "document", "relevance_score"]:
                            logger.warning(f"MDLContextRetrievalNode: Skipping string in edges_discovered: '{item[:50]}...'")
            elif isinstance(edges_discovered, dict):
                # If a single dict was passed, wrap it
                validated_edges_discovered = [edges_discovered]
                logger.warning("MDLContextRetrievalNode: edges_discovered was a dict, wrapping in list")
            else:
                logger.warning(f"MDLContextRetrievalNode: edges_discovered was unexpected type {type(edges_discovered)}, using empty list")
            
            # Validate contexts_retrieved - ensure it's a list of dicts
            validated_contexts_retrieved = []
            if isinstance(contexts_retrieved, list):
                for item in contexts_retrieved:
                    if isinstance(item, dict):
                        validated_contexts_retrieved.append(item)
                    elif isinstance(item, str) and len(item) > 1:
                        # Skip non-dict items
                        logger.warning(f"MDLContextRetrievalNode: Skipping string in contexts_retrieved: '{item[:50]}...'")
            elif isinstance(contexts_retrieved, dict):
                validated_contexts_retrieved = [contexts_retrieved]
                logger.warning("MDLContextRetrievalNode: contexts_retrieved was a dict, wrapping in list")
            
            # Update state with validated data
            state["contexts_retrieved"] = validated_contexts_retrieved
            state["edges_discovered"] = validated_edges_discovered
            state["related_entities"] = related_entities
            state["current_step"] = "context_retrieval"
            state["status"] = "processing"
            
            logger.info(f"MDLContextRetrievalNode: Retrieved {len(contexts_retrieved)} contexts, {len(edges_discovered)} edges, {len(related_entities)} related entities")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLContextRetrievalNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Context retrieval failed: {str(e)}"
            return state


class MDLContextualPlannerNode:
    """Node that identifies most relevant edges for each curated table based on user question and contexts"""
    
    def __init__(
        self,
        retriever: MDLSemanticRetriever,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.retriever = retriever
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """First retrieve relations via hybrid search, then use LLM to create edge plan"""
        logger.info("MDLContextualPlannerNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name", "Snyk")
        curated_tables_info_raw = state.get("tables_found", [])
        context_breakdown = state.get("context_breakdown", {})
        generic_breakdown = state.get("generic_breakdown", {})
        
        # Filter and normalize curated_tables_info - ensure all entries are dicts
        curated_tables_info = []
        for item in curated_tables_info_raw:
            if isinstance(item, dict):
                curated_tables_info.append(item)
            elif isinstance(item, str):
                # If it's a string, try to parse it or create a minimal dict
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, dict):
                        curated_tables_info.append(parsed)
                    else:
                        logger.warning(f"MDLContextualPlannerNode: Skipping non-dict parsed item: {type(parsed)}")
                except:
                    # If parsing fails, create a minimal dict from the string
                    logger.warning(f"MDLContextualPlannerNode: Creating dict from string table name: {item}")
                    curated_tables_info.append({"table_name": item})
            else:
                logger.warning(f"MDLContextualPlannerNode: Skipping non-dict, non-string item: {type(item)}")
        
        if not curated_tables_info:
            logger.warning("MDLContextualPlannerNode: No curated tables found, skipping edge identification")
            state["current_step"] = "contextual_planning"
            return state
        
        try:
            # Extract context information from generic breakdown
            user_intent = generic_breakdown.get("user_intent") if isinstance(generic_breakdown, dict) else None
            action_context = generic_breakdown.get("action_context") if isinstance(generic_breakdown, dict) else None
            compliance_context = generic_breakdown.get("compliance_context") if isinstance(generic_breakdown, dict) else None
            frameworks = generic_breakdown.get("frameworks", []) if isinstance(generic_breakdown, dict) else []
            product_context = (generic_breakdown.get("product_context") if isinstance(generic_breakdown, dict) else None) or product_name
            
            # STEP 1: Use hybrid search to find relations for each curated table
            logger.info("MDLContextualPlannerNode: Step 1 - Using hybrid search to find relations for curated tables")
            discovered_relations = {}
            
            for table_info in curated_tables_info[:20]:  # Limit to top 20 tables
                if not isinstance(table_info, dict):
                    logger.warning(f"MDLContextualPlannerNode: Skipping non-dict table_info: {type(table_info)}")
                    continue
                    
                table_name = table_info.get("table_name", "Unknown")
                # Validate table_name - must be a string and not a dictionary key
                if not isinstance(table_name, str):
                    table_name = str(table_name) if table_name else "Unknown"
                # Filter out dictionary keys that might have been incorrectly used as table names
                dict_keys = {"table_name", "relevance_score", "description", "full_description", 
                            "comments", "ddl", "columns", "categories", "metadata", "content", "source"}
                if table_name in dict_keys:
                    logger.warning(f"MDLContextualPlannerNode: Skipping table_name '{table_name}' as it's a dictionary key, not a table name")
                    continue
                if len(table_name.strip()) <= 1:
                    logger.warning(f"MDLContextualPlannerNode: Skipping invalid table_name '{table_name}' (too short)")
                    continue
                    
                description = table_info.get("description", "")
                
                # Build search query for this table
                search_query = f"{user_question} {table_name} {description}"
                
                # Search for edges/relations for this table
                table_relations = {
                    "table_name": table_name,
                    "edges": [],
                    "products": [],
                    "policies": [],
                    "compliance_controls": [],
                    "risk_controls": []
                }
                
                # 1. Search for table-to-table edges - retrieve edges specifically for this curated table using MDLSemanticRetriever
                try:
                    # Build entity ID for this table (format: entity_{product}_{table})
                    table_entity_id = f"entity_{product_name}_{table_name}" if product_name and table_name else None
                    
                    # Use MDLSemanticRetriever to get accurate edges for this curated table
                    # This ensures we retrieve edges where the table is actually involved
                    all_edges = []
                    
                    # Search 1: Retrieve edges where this table is the source entity
                    if table_entity_id:
                        try:
                            edges_as_source = await self.retriever.retrieve_edges(
                                query=f"{table_name} {user_question}",
                                filters={"source_entity_id": table_entity_id, "product_name": product_name} if product_name else {"source_entity_id": table_entity_id},
                                top_k=15
                            )
                            all_edges.extend(edges_as_source)
                            logger.debug(f"MDLContextualPlannerNode: Found {len(edges_as_source)} edges where {table_name} is source")
                        except Exception as e:
                            logger.debug(f"MDLContextualPlannerNode: Error retrieving source edges for {table_name}: {e}")
                        
                        # Search 2: Retrieve edges where this table is the target entity
                        try:
                            edges_as_target = await self.retriever.retrieve_edges(
                                query=f"{table_name} {user_question}",
                                filters={"target_entity_id": table_entity_id, "product_name": product_name} if product_name else {"target_entity_id": table_entity_id},
                                top_k=15
                            )
                            all_edges.extend(edges_as_target)
                            logger.debug(f"MDLContextualPlannerNode: Found {len(edges_as_target)} edges where {table_name} is target")
                        except Exception as e:
                            logger.debug(f"MDLContextualPlannerNode: Error retrieving target edges for {table_name}: {e}")
                    
                    # Search 3: General semantic search for related edges (as fallback and to catch other relationships)
                    try:
                        general_edges = await self.retriever.retrieve_edges(
                            query=search_query,
                            filters={"product_name": product_name} if product_name else None,
                            top_k=10
                        )
                        all_edges.extend(general_edges)
                        logger.debug(f"MDLContextualPlannerNode: Found {len(general_edges)} general edges for {table_name}")
                    except Exception as e:
                        logger.debug(f"MDLContextualPlannerNode: Error retrieving general edges for {table_name}: {e}")
                    
                    # Deduplicate edges by edge_id and filter to only relevant edges
                    seen_edge_ids = set()
                    for edge in all_edges:
                        if edge.edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge.edge_id)
                            
                            # Check if this edge is actually related to our curated table
                            is_related = False
                            table_role = "related"
                            
                            if table_entity_id:
                                # Edge is related if table is source or target
                                if edge.source_entity_id == table_entity_id:
                                    is_related = True
                                    table_role = "source"
                                elif edge.target_entity_id == table_entity_id:
                                    is_related = True
                                    table_role = "target"
                            else:
                                # If no entity ID, check if table name appears in edge document or entity IDs
                                edge_text = (edge.document or "").lower()
                                table_name_lower = table_name.lower()
                                is_related = (table_name_lower in edge_text or
                                            table_name_lower in (edge.source_entity_id or "").lower() or
                                            table_name_lower in (edge.target_entity_id or "").lower())
                            
                            if is_related:
                                table_relations["edges"].append({
                                    "edge_id": edge.edge_id,
                                    "edge_type": edge.edge_type,
                                    "source_entity_id": edge.source_entity_id,
                                    "target_entity_id": edge.target_entity_id,
                                    "source_entity_type": edge.source_entity_type,
                                    "target_entity_type": edge.target_entity_type,
                                    "relevance_score": edge.relevance_score,
                                    "document": edge.document[:500] if edge.document else "",
                                    "table_role": table_role  # "source", "target", or "related"
                                })
                    
                    logger.info(f"MDLContextualPlannerNode: Retrieved {len(table_relations['edges'])} relevant edges for curated table {table_name} (entity_id: {table_entity_id})")
                    
                except Exception as e:
                    logger.warning(f"MDLContextualPlannerNode: Error retrieving edges for {table_name}: {e}")
                
                # 2. Search for products related to this table
                try:
                    products = await self.retriever.retrieve_by_entity(
                        entity="product_descriptions",
                        query=f"{table_name} {product_name} product",
                        filters={"product_name": product_name} if product_name else None,
                        top_k=5
                    )
                    for product in products:
                        if isinstance(product, dict):
                            table_relations["products"].append({
                                "id": product.get("metadata", {}).get("id", ""),
                                "content": product.get("content", "")[:300],
                                "metadata": product.get("metadata", {})
                            })
                except Exception as e:
                    logger.warning(f"MDLContextualPlannerNode: Error retrieving products for {table_name}: {e}")
                
                # 3. Search for policies related to this table
                # Note: policy_documents routes to general stores (domain_knowledge, entities, evidence, fields)
                # with type="policy" filter. This is handled in mdl_semantic_retriever.retrieve_by_entity()
                for policy_entity in ["policy_documents", "policy_entities", "policy_evidence"]:
                    try:
                        policies = await self.retriever.retrieve_by_entity(
                            entity=policy_entity,
                            query=f"{table_name} {user_question} policy",
                            filters={"product_name": product_name} if product_name else None,
                            top_k=5
                        )
                        for policy in policies:
                            if isinstance(policy, dict):
                                table_relations["policies"].append({
                                    "entity_type": policy_entity,
                                    "id": policy.get("metadata", {}).get("id", "") or policy.get("metadata", {}).get("policy_id", ""),
                                    "content": policy.get("content", "")[:300],
                                    "metadata": policy.get("metadata", {})
                                })
                    except Exception as e:
                        logger.warning(f"MDLContextualPlannerNode: Error retrieving {policy_entity} for {table_name}: {e}")
                
                # 4. Search for compliance controls based on curated tables and search_questions
                try:
                    # Get compliance context from generic_breakdown search_questions if available
                    generic_breakdown = state.get("generic_breakdown", {})
                    search_questions = generic_breakdown.get("search_questions", []) or state.get("search_questions", [])
                    
                    # Find compliance_controls search questions
                    compliance_questions = [
                        sq for sq in search_questions 
                        if isinstance(sq, dict) and sq.get("entity") == "compliance_controls"
                    ]
                    
                    # Build query using table name and compliance question context
                    compliance_query = f"{table_name}"
                    compliance_filters = {"product_name": product_name} if product_name else {}
                    
                    if compliance_questions:
                        # Use the question from search_questions for better context
                        compliance_question = compliance_questions[0].get("question", "")
                        compliance_query = f"{table_name} {compliance_question}"
                        
                        # Merge metadata filters from search_questions (e.g., framework: "SOC2")
                        compliance_filters.update(compliance_questions[0].get("metadata_filters", {}))
                    
                    # Add compliance_context if available
                    if compliance_context:
                        compliance_query = f"{compliance_query} {compliance_context}"
                    
                    controls = await self.retriever.retrieve_by_entity(
                        entity="compliance_controls",
                        query=compliance_query,
                        filters=compliance_filters if compliance_filters else None,
                        top_k=10  # Increased to get more relevant controls
                    )
                    
                    # Store controls in table_relations and also add to contexts_retrieved
                    for control in controls:
                        if isinstance(control, dict):
                            metadata = control.get("metadata", {})
                            control_id = metadata.get("id") or metadata.get("control_id") or metadata.get("context_id") or f"compliance_{len(table_relations['compliance_controls'])}"
                            
                            control_entry = {
                                "id": control_id,
                                "content": control.get("content", "")[:500],  # More content for contexts
                                "metadata": metadata,
                                "table_name": table_name,  # Link to the table
                                "source": "compliance_controls"
                            }
                            table_relations["compliance_controls"].append(control_entry)
                            
                            # Also add to contexts_retrieved for use in subsequent nodes
                            if "contexts_retrieved" not in state:
                                state["contexts_retrieved"] = []
                            elif not isinstance(state["contexts_retrieved"], list):
                                state["contexts_retrieved"] = []
                            
                            context_entry = {
                                "context_id": control_id,
                                "entity_name": "compliance_controls",
                                "entity_type": "compliance_controls",
                                "table_name": table_name,
                                "metadata": metadata,
                                "content": control.get("content", "")[:1000],
                                "source": "mdl_contextual_planner",
                                "retrieval_method": "compliance_controls_by_table",
                                "node": "MDLContextualPlannerNode",
                                "query": compliance_query[:200] if compliance_query else ""
                            }
                            state["contexts_retrieved"].append(context_entry)
                            
                    logger.info(f"MDLContextualPlannerNode: Retrieved {len(table_relations['compliance_controls'])} compliance controls for table '{table_name}' using query: {compliance_query[:100]}...")
                except Exception as e:
                    logger.warning(f"MDLContextualPlannerNode: Error retrieving compliance controls for {table_name}: {e}")
                
                # 5. Search for risk controls
                # Note: risk_controls routes to domain_knowledge with type="risk" or controls with type="risk"
                # This is handled in mdl_semantic_retriever.retrieve_by_entity()
                try:
                    risks = await self.retriever.retrieve_by_entity(
                        entity="risk_controls",
                        query=f"{table_name} risk control",
                        filters={"product_name": product_name} if product_name else None,
                        top_k=5
                    )
                    for risk in risks:
                        if isinstance(risk, dict):
                            table_relations["risk_controls"].append({
                                "id": risk.get("metadata", {}).get("id", "") or risk.get("metadata", {}).get("risk_id", ""),
                                "content": risk.get("content", "")[:300],
                                "metadata": risk.get("metadata", {})
                            })
                except Exception as e:
                    logger.warning(f"MDLContextualPlannerNode: Error retrieving risk controls for {table_name}: {e}")
                
                discovered_relations[table_name] = table_relations
                logger.info(f"MDLContextualPlannerNode: Found {len(table_relations['edges'])} edges, {len(table_relations['products'])} products, {len(table_relations['policies'])} policies, {len(table_relations['compliance_controls'])} compliance controls, {len(table_relations['risk_controls'])} risk controls for {table_name}")
            
            # STEP 2: Pass discovered relations to LLM to create refined edge plan
            logger.info("MDLContextualPlannerNode: Step 2 - Using LLM to create edge plan from discovered relations")
            
            # Build context summary
            context_summary = f"""
User Question: {user_question}
Product: {product_name}
User Intent: {user_intent or 'Not specified'}
Action Context: {action_context or 'Not specified'}
Compliance Context: {compliance_context or 'Not specified'}
Frameworks: {', '.join(frameworks) if frameworks else 'Not specified'}
Product Context: {product_context or 'Not specified'}
"""
            
            # Prepare curated tables with full descriptions, comments, DDL, and columns
            curated_tables_text = ""
            for i, table_info in enumerate(curated_tables_info[:20], 1):
                if not isinstance(table_info, dict):
                    continue
                    
                table_name = table_info.get("table_name", "Unknown")
                description = table_info.get("description", "")  # Brief description from curation
                full_description = table_info.get("full_description", "")  # Full table description
                comments = table_info.get("comments", "")  # Table comments
                ddl = table_info.get("ddl", "")  # Table DDL
                columns = table_info.get("columns", [])  # Table columns
                content = table_info.get("content", "")  # Fallback content
                relevance_score = table_info.get("relevance_score", 0.0)
                categories = table_info.get("categories", [])
                
                curated_tables_text += f"### Table {i}: {table_name} (Score: {relevance_score:.2f})\n"
                if categories:
                    curated_tables_text += f"Categories: {', '.join(categories)}\n"
                if description:
                    curated_tables_text += f"Brief Description: {description}\n"
                if full_description:
                    curated_tables_text += f"Full Description: {full_description[:1000]}\n"
                elif content:
                    curated_tables_text += f"Content: {content[:1000]}\n"
                if comments:
                    curated_tables_text += f"Comments: {comments[:500]}\n"
                if ddl:
                    curated_tables_text += f"DDL: {ddl[:1500]}\n"  # Include DDL for column structure
                if columns:
                    columns_str = ", ".join([f"{col.get('name', '')} ({col.get('type', '')})" for col in columns[:20]])
                    curated_tables_text += f"Columns ({len(columns)}): {columns_str}\n"
                curated_tables_text += "\n"
            
            # Prepare discovered relations summary
            relations_summary = ""
            for table_name, relations in list(discovered_relations.items())[:20]:
                relations_summary += f"\n### Relations for {table_name}:\n"
                if relations["edges"]:
                    relations_summary += f"  Edges ({len(relations['edges'])}):\n"
                    for edge in relations["edges"][:5]:
                        relations_summary += f"    - {edge['edge_type']}: {edge['source_entity_id']} -> {edge['target_entity_id']} (score: {edge.get('relevance_score', 0):.2f})\n"
                if relations["products"]:
                    relations_summary += f"  Products ({len(relations['products'])}): {len(relations['products'])} found\n"
                if relations["policies"]:
                    relations_summary += f"  Policies ({len(relations['policies'])}): {len(relations['policies'])} found\n"
                if relations["compliance_controls"]:
                    relations_summary += f"  Compliance Controls ({len(relations['compliance_controls'])}): {len(relations['compliance_controls'])} found\n"
                if relations["risk_controls"]:
                    relations_summary += f"  Risk Controls ({len(relations['risk_controls'])}): {len(relations['risk_controls'])} found\n"
            
            # Use LLM to create refined edge plan based on discovered relations
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at creating edge plans for MDL tables based on discovered relations.

Given curated tables, user question, context information, and discovered relations (from hybrid search), create a refined edge plan that identifies the most relevant edges for each table.

The discovered relations show what actually exists in the knowledge base. Use these to create accurate edge plans.

Return JSON with:
- table_edges: List of edge objects, each with:
  - table_name: Name of the table
  - edge_type: Type of edge (e.g., "RELEVANT_TO_CONTROL", "BELONGS_TO_TABLE", "HAS_MANY_TABLES", "RELATED_TO_POLICY", "RELATED_TO_RISK", "RELATED_TO_PRODUCT", etc.)
  - target_entity_type: Type of target entity (e.g., "compliance_control", "policy_document", "risk_control", "table", "product")
  - target_entity_id: ID or identifier for target entity (from discovered relations if available)
  - relevance_score: Score from 0.0 to 1.0 indicating relevance
  - reasoning: Why this edge is relevant to the user question
  - search_query: Natural language query to retrieve this edge (for final retrieval step)
  - metadata_filters: Dictionary of metadata filters for retrieving the edge
- reasoning: Overall reasoning for edge plan creation
"""),
                ("human", """Create an edge plan for these curated tables based on discovered relations:

{context_summary}

Curated Tables:
{curated_tables_text}

Discovered Relations (from hybrid search):
{relations_summary}

Based on the discovered relations and user question, create a refined edge plan that:
1. Uses the actual discovered relations to identify relevant edges
2. Prioritizes edges that were found in the hybrid search
3. Includes edges to products, policies, compliance controls, risk controls, and other tables
4. Provides search queries and metadata filters for final retrieval

Return JSON with table_edges for each curated table.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            prompt_input = {
                "context_summary": context_summary,
                "curated_tables_text": curated_tables_text,
                "relations_summary": relations_summary
            }
            
            # Log full prompt without truncation
            logger.info("=" * 80)
            logger.info("MDLContextualPlannerNode: Full LLM Prompt (NO TRUNCATION)")
            logger.info("=" * 80)
            try:
                formatted_messages = prompt.format_messages(**prompt_input)
                logger.info(f"System Prompt:\n{formatted_messages[0].content}")
                logger.info(f"Human Prompt:\n{formatted_messages[1].content}")
            except Exception as e:
                logger.warning(f"Could not format prompt for logging: {e}")
            logger.info(f"Prompt Variables:")
            logger.info(f"  context_summary length: {len(prompt_input['context_summary'])} chars")
            logger.info(f"  curated_tables_text length: {len(prompt_input['curated_tables_text'])} chars")
            logger.info(f"  relations_summary length: {len(prompt_input['relations_summary'])} chars")
            logger.info("=" * 80)
            
            result = await chain.ainvoke(prompt_input)
            
            # Log full LLM response without truncation
            logger.info("=" * 80)
            logger.info("MDLContextualPlannerNode: Full LLM Response (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
            logger.info("=" * 80)
            
            # Extract and validate table edges - must be a list of dicts
            table_edges_raw = result.get("table_edges", [])
            reasoning = result.get("reasoning", "")
            
            # Validate table_edges - ensure it's a list of dicts, not dict keys or characters
            table_edges = []
            if isinstance(table_edges_raw, list):
                for item in table_edges_raw:
                    if isinstance(item, dict):
                        # Valid edge dict
                        table_edges.append(item)
                    elif isinstance(item, str):
                        # Skip dictionary keys and single characters
                        if len(item) > 1 and item not in ["table_name", "edge_type", "target_entity_type", 
                                                          "target_entity_id", "relevance_score", "reasoning", 
                                                          "search_query", "metadata_filters"]:
                            logger.warning(f"MDLContextualPlannerNode: Skipping string in table_edges: '{item[:50]}...' (expected dict)")
            elif isinstance(table_edges_raw, dict):
                # If a dict was returned, it might be a single edge or the response structure is wrong
                logger.warning("MDLContextualPlannerNode: table_edges was a dict, expected list. Checking if it's a single edge...")
                # Check if it has edge-like keys
                if "edge_type" in table_edges_raw or "table_name" in table_edges_raw:
                    table_edges = [table_edges_raw]
                else:
                    logger.warning("MDLContextualPlannerNode: table_edges dict doesn't look like an edge, using empty list")
            else:
                logger.warning(f"MDLContextualPlannerNode: table_edges was unexpected type {type(table_edges_raw)}, using empty list")
            
            # Update state with contextual planning results
            state["contextual_plan"] = {
                "user_question": user_question,
                "table_edges": table_edges,
                "reasoning": reasoning,
                "curated_tables_count": len(curated_tables_info),
                "discovered_relations": discovered_relations  # Store discovered relations for reference
            }
            state["edges_discovered"] = table_edges  # Store identified edges (validated list of dicts)
            state["current_step"] = "contextual_planning"
            state["status"] = "processing"
            
            logger.info(f"MDLContextualPlannerNode: Created edge plan with {len(table_edges)} edges for {len(curated_tables_info)} curated tables")
            if table_edges:
                # Group edges by table
                edges_by_table = {}
                for edge in table_edges:
                    table_name = edge.get("table_name", "Unknown")
                    if table_name not in edges_by_table:
                        edges_by_table[table_name] = []
                    edges_by_table[table_name].append(edge)
                
                logger.info(f"MDLContextualPlannerNode: Edges per table:")
                for table_name, edges in list(edges_by_table.items())[:10]:
                    logger.info(f"  {table_name}: {len(edges)} edges")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLContextualPlannerNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Contextual planning failed: {str(e)}"
            return state


class MDLEdgeBasedRetrievalNode:
    """Node that retrieves data based on edges identified by contextual planner"""
    
    def __init__(
        self,
        retriever: MDLSemanticRetriever,
        contextual_graph_storage: ContextualGraphStorage
    ):
        self.retriever = retriever
        self.contextual_graph_storage = contextual_graph_storage
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Retrieve data based on edges from contextual planning"""
        logger.info("MDLEdgeBasedRetrievalNode: Starting execution")
        
        contextual_plan = state.get("contextual_plan", {})
        table_edges = contextual_plan.get("table_edges", []) or state.get("edges_discovered", [])
        product_name = state.get("product_name", "Snyk")
        
        if not table_edges:
            logger.warning("MDLEdgeBasedRetrievalNode: No edges from contextual planning, skipping edge-based retrieval")
            state["current_step"] = "edge_retrieval"
            return state
        
        try:
            contexts_retrieved = []
            edges_retrieved = []
            related_entities = []
            
            # Process each edge to retrieve relevant data
            for edge in table_edges:
                if not isinstance(edge, dict):
                    continue
                    
                edge_type = edge.get("edge_type", "")
                target_entity_type = edge.get("target_entity_type", "")
                target_entity_id = edge.get("target_entity_id", "")
                search_query = edge.get("search_query", "")
                metadata_filters = edge.get("metadata_filters", {})
                table_name = edge.get("table_name", "")
                
                logger.info(f"MDLEdgeBasedRetrievalNode: Processing edge: {edge_type} -> {target_entity_type} ({target_entity_id})")
                
                # Retrieve based on edge type and target entity type
                # Map target entity types to entity store names
                # Note: policy_documents and risk_controls are handled specially in retrieve_by_entity()
                # - policy_documents routes to domain_knowledge/entities/evidence/fields with type="policy"
                # - risk_controls routes to domain_knowledge/controls with type="risk"
                entity_store_map = {
                    "compliance_control": "compliance_controls",
                    "compliance_controls": "compliance_controls",
                    "policy_document": "policy_documents",  # Routes to domain_knowledge/entities/evidence/fields with type="policy"
                    "policy_entity": "policy_entities",  # Routes to entities with type="policy"
                    "policy_evidence": "policy_evidence",  # Routes to evidence with type="policy"
                    "policy_field": "policy_fields",  # Routes to fields with type="policy"
                    "risk_control": "risk_controls",  # Routes to domain_knowledge/controls with type="risk"
                    "risk_entity": "risk_entities",  # Routes to entities with type="risk_entities"
                    "risk_evidence": "risk_evidence",  # Routes to evidence with type="risk_evidence"
                    "risk_field": "risk_fields",  # Routes to fields with type="risk_fields"
                    "product": "product_descriptions",
                    "product_description": "product_descriptions",
                    "product_knowledge": "product_descriptions",
                    "product_entity": "product_descriptions"
                }
                
                entity_store = entity_store_map.get(target_entity_type)
                
                if entity_store:
                    # Retrieve from entity store
                    try:
                        results = await self.retriever.retrieve_by_entity(
                            entity=entity_store,
                            query=search_query or f"Information related to {table_name}",
                            filters=metadata_filters,
                            top_k=10
                        )
                        if results:
                            logger.info(f"MDLEdgeBasedRetrievalNode: Retrieved {len(results)} results from {entity_store} for {table_name}")
                            for result in results:
                                if isinstance(result, dict):
                                    contexts_retrieved.append({
                                        "context_id": result.get("metadata", {}).get("id", "") or result.get("metadata", {}).get("control_id", "") or result.get("metadata", {}).get("policy_id", "") or result.get("metadata", {}).get("risk_id", ""),
                                        "entity_type": target_entity_type,
                                        "metadata": result.get("metadata", {}),
                                        "content": result.get("content", "")[:500],
                                        "source": entity_store,
                                        "related_table": table_name,
                                        "edge_type": edge_type
                                    })
                        else:
                            logger.info(f"MDLEdgeBasedRetrievalNode: No results from {entity_store} for {table_name} (collection may be empty or not exist)")
                    except Exception as e:
                        logger.warning(f"MDLEdgeBasedRetrievalNode: Error retrieving from {entity_store}: {e}")
                        # Continue processing other edges even if one fails
                
                elif target_entity_type == "table":
                    # Retrieve table relationships
                    try:
                        edges = await self.retriever.retrieve_edges(
                            query=search_query or f"Table relationships for {table_name}",
                            filters=metadata_filters,
                            top_k=10
                        )
                        for edge_obj in edges:
                            edges_retrieved.append({
                                "edge_id": edge_obj.edge_id,
                                "edge_type": edge_obj.edge_type,
                                "source_entity_id": edge_obj.source_entity_id,
                                "target_entity_id": edge_obj.target_entity_id,
                                "source_entity_type": edge_obj.source_entity_type,
                                "target_entity_type": edge_obj.target_entity_type,
                                "relevance_score": edge_obj.relevance_score,
                                "related_table": table_name
                            })
                    except Exception as e:
                        logger.warning(f"MDLEdgeBasedRetrievalNode: Error retrieving table edges: {e}")
                else:
                    logger.warning(f"MDLEdgeBasedRetrievalNode: Unknown target_entity_type: {target_entity_type}")
            
            # Validate edges_retrieved - ensure it's a list of dicts
            validated_edges_retrieved = []
            if isinstance(edges_retrieved, list):
                for item in edges_retrieved:
                    if isinstance(item, dict):
                        validated_edges_retrieved.append(item)
                    elif isinstance(item, str):
                        # Skip dictionary keys and single characters
                        if len(item) > 1 and item not in ["edge_id", "edge_type", "source_entity_id", 
                                                          "target_entity_id", "source_entity_type", 
                                                          "target_entity_type", "document", "relevance_score",
                                                          "related_table"]:
                            logger.warning(f"MDLEdgeBasedRetrievalNode: Skipping string in edges_retrieved: '{item[:50]}...'")
            elif isinstance(edges_retrieved, dict):
                validated_edges_retrieved = [edges_retrieved]
                logger.warning("MDLEdgeBasedRetrievalNode: edges_retrieved was a dict, wrapping in list")
            else:
                logger.warning(f"MDLEdgeBasedRetrievalNode: edges_retrieved was unexpected type {type(edges_retrieved)}, using empty list")
            
            # Validate contexts_retrieved - ensure it's a list of dicts
            validated_contexts_retrieved = []
            if isinstance(contexts_retrieved, list):
                for item in contexts_retrieved:
                    if isinstance(item, dict):
                        validated_contexts_retrieved.append(item)
                    elif isinstance(item, str) and len(item) > 1:
                        logger.warning(f"MDLEdgeBasedRetrievalNode: Skipping string in contexts_retrieved: '{item[:50]}...'")
            elif isinstance(contexts_retrieved, dict):
                validated_contexts_retrieved = [contexts_retrieved]
                logger.warning("MDLEdgeBasedRetrievalNode: contexts_retrieved was a dict, wrapping in list")
            
            # Update state with validated data
            state["contexts_retrieved"] = validated_contexts_retrieved
            state["edges_discovered"] = validated_edges_retrieved
            state["current_step"] = "edge_retrieval"
            state["status"] = "processing"
            
            logger.info(f"MDLEdgeBasedRetrievalNode: Retrieved {len(contexts_retrieved)} contexts, {len(edges_retrieved)} edges based on {len(table_edges)} planned edges")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLEdgeBasedRetrievalNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Edge-based retrieval failed: {str(e)}"
            return state


class MDLSummaryNode:
    """Node that creates a summary of all collected data"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        retriever: Optional[MDLSemanticRetriever] = None,
        retrieval_helper: Optional[Any] = None
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        self.retriever = retriever
        self.retrieval_helper = retrieval_helper
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Create summary of all collected data"""
        logger.info("MDLSummaryNode: Starting execution")
        
        user_question = state.get("user_question", "")
        product_name = state.get("product_name", "Snyk")
        project_id = state.get("project_id")
        actor = state.get("actor")  # Actor making the request (optional)
        curated_tables_info_raw = state.get("tables_found", [])
        contextual_plan = state.get("contextual_plan", {})
        contexts_retrieved = state.get("contexts_retrieved", [])
        edges_discovered = state.get("edges_discovered", [])
        
        # Normalize curated_tables_info - filter to ensure all entries are dicts
        curated_tables_info = []
        for item in curated_tables_info_raw:
            if isinstance(item, dict):
                curated_tables_info.append(item)
            elif isinstance(item, str):
                logger.warning(f"MDLSummaryNode: Skipping string table_info: '{item[:50]}...'")
            else:
                logger.warning(f"MDLSummaryNode: Skipping non-dict table_info: {type(item)}")
        
        # Also try to get curated tables from context_breakdown if tables_found is empty
        if not curated_tables_info:
            context_breakdown = state.get("context_breakdown", {})
            curated_tables_from_breakdown = context_breakdown.get("curated_tables_info", [])
            if curated_tables_from_breakdown:
                logger.info(f"MDLSummaryNode: Using curated_tables_info from context_breakdown ({len(curated_tables_from_breakdown)} tables)")
                for item in curated_tables_from_breakdown:
                    if isinstance(item, dict):
                        curated_tables_info.append(item)
        
        try:
            # Log what we have
            logger.info(f"MDLSummaryNode: Found {len(curated_tables_info)} curated tables from tables_found")
            if not curated_tables_info:
                logger.warning("MDLSummaryNode: No curated tables found in tables_found, checking context_breakdown")
            
            # Prepare summary data
            curated_tables_summary = []
            for table_info in curated_tables_info[:20]:
                if isinstance(table_info, dict):
                    curated_tables_summary.append({
                        "table_name": table_info.get("table_name", "Unknown"),
                        "relevance_score": table_info.get("relevance_score", 0.0),
                        "description": table_info.get("description", "")[:200]
                    })
                else:
                    logger.warning(f"MDLSummaryNode: Skipping non-dict table_info in summary: {type(table_info)}")
            
            table_edges = contextual_plan.get("table_edges", [])
            edges_summary = []
            for edge in table_edges[:20]:
                if isinstance(edge, dict):
                    edges_summary.append({
                        "table_name": edge.get("table_name", "Unknown"),
                        "edge_type": edge.get("edge_type", ""),
                        "target_entity_type": edge.get("target_entity_type", ""),
                        "relevance_score": edge.get("relevance_score", 0.0)
                    })
            
            contexts_summary = []
            for context in contexts_retrieved[:20]:
                if isinstance(context, dict):
                    contexts_summary.append({
                        "context_id": context.get("context_id", ""),
                        "entity_type": context.get("entity_type", ""),
                        "source": context.get("source", ""),
                        "related_table": context.get("related_table", "")
                    })
            
            # Retrieve metrics from retrieval helper if available
            metrics_retrieved = []
            if self.retrieval_helper:
                try:
                    logger.info(f"MDLSummaryNode: Retrieving metrics for query: {user_question[:100]}...")
                    # Get table names for metrics retrieval
                    table_names = [t.get("table_name", "") for t in curated_tables_info[:10] if isinstance(t, dict) and t.get("table_name")]
                    
                    if table_names:
                        # Use retrieval_helper.get_metrics if available
                        if hasattr(self.retrieval_helper, 'get_metrics') and project_id:
                            metrics_result = await self.retrieval_helper.get_metrics(
                                query=user_question,
                                project_id=project_id
                            )
                            if metrics_result:
                                metrics_retrieved = metrics_result if isinstance(metrics_result, list) else [metrics_result]
                                logger.info(f"MDLSummaryNode: Retrieved {len(metrics_retrieved)} metrics from retrieval_helper")
                        elif self.retriever:
                            # Fallback: try to retrieve metrics using retriever
                            try:
                                metrics = await self.retriever.retrieve_by_entity(
                                    entity="metrics",
                                    query=f"{user_question} {' '.join(table_names[:3])}",
                                    filters={"product_name": product_name} if product_name else None,
                                    top_k=10
                                )
                                for metric in metrics:
                                    if isinstance(metric, dict):
                                        metrics_retrieved.append({
                                            "metric_name": metric.get("metadata", {}).get("metric_name") or metric.get("metadata", {}).get("name", ""),
                                            "description": metric.get("content", "")[:300],
                                            "metadata": metric.get("metadata", {}),
                                            "source": "mdl_summary",
                                            "retrieval_method": "retrieve_by_entity"
                                        })
                                logger.info(f"MDLSummaryNode: Retrieved {len(metrics_retrieved)} metrics from retriever")
                            except Exception as e:
                                logger.warning(f"MDLSummaryNode: Error retrieving metrics from retriever: {e}")
                except Exception as e:
                    logger.warning(f"MDLSummaryNode: Error retrieving metrics: {e}")
            
            metrics_summary = []
            for metric in metrics_retrieved[:10]:
                if isinstance(metric, dict):
                    metrics_summary.append({
                        "metric_name": metric.get("metric_name") or metric.get("name", ""),
                        "description": metric.get("description", "")[:200],
                        "source": metric.get("source", "")
                    })
            
            # Generate summary using LLM
            # Build actor context for prompt
            actor_instruction = ""
            if actor:
                actor_instruction = f"\n\nIMPORTANT: Write the summary as if you are addressing {actor} directly. Use appropriate tone and language for {actor}. The answer should be written in a way that {actor} would find useful and actionable."
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at summarizing data schema analysis results and providing actionable compliance monitoring guidance.

Given a user question and all collected data (curated tables, edges, contexts, metrics), create a comprehensive summary in MARKDOWN format with natural language explanations.
{actor_instruction}

IMPORTANT GUIDANCE ON METRICS AND MONITORING:
- When discussing metrics, consider what key indicators can be derived from the table schemas (counts, rates, distributions, anomalies, trends over time)
- For compliance monitoring, suggest observable patterns in the data that indicate health or risk (e.g., orphaned access requests, unreviewed logs, permission escalations)
- Provide monitoring guidance that is implementation-agnostic - focus on WHAT to monitor rather than HOW or which specific tool to use
- Think about leading indicators (proactive) vs lagging indicators (reactive)
- Consider both operational metrics (system health) and compliance metrics (control effectiveness)

As a deep knowledge compliance expert, you should:
- Use an elaborate description of what could be done, with sources from the inputs
- Use the contextual edges to understand table relationships and build richer context
- Write in natural language with clear explanations
- Provide concrete examples based on the actual table schemas provided

REQUIRED MARKDOWN STRUCTURE:

# Summary

[Write a comprehensive answer to the user's question, explaining which tables are relevant and why]

## Key Tables

[For each relevant table, provide:
- **Table Name**: Brief description of what this table contains and its role
- Include any notable schema details that are relevant]

## Table Relationships

[Explain how the tables relate to each other, using the contextual edges provided. Describe the data flow and dependencies in natural language.]

## Compliance Context

[Explain how these tables relate to compliance requirements (SOC2, policies, risk management, etc.). Reference specific contexts from the input data.]

## Suggested Metrics & KPIs

[For each important metric, provide:
- **Metric Name**: Natural language explanation of what to measure, why it matters, and how it relates to the table schemas
- Be specific about what data fields would be used
- Explain the business/compliance value]

## Monitoring Strategies

[Provide practical, implementation-agnostic monitoring approaches:
- What patterns to look for in the data
- What anomalies or thresholds indicate issues
- How to proactively identify risks
- Use bullet points for clarity]

## Insights & Recommendations

[Provide actionable insights based on the analysis:
- Key takeaways about the data model
- Recommendations for improving compliance monitoring
- Gaps or opportunities identified]

"""),
                ("human", """Create a comprehensive markdown summary for this MDL query:

**User Question:** {user_question}
**Product:** {product_name}
{actor_line}

**Curated Tables ({tables_count}):**
{tables_summary}

**Identified Edges ({edges_count}):**
{edges_summary}

**Retrieved Contexts ({contexts_count}):**
{contexts_summary}

**Retrieved Metrics ({metrics_count}):**
{metrics_summary}

Return a well-structured markdown document following the required format above.""")
            ])
            
            # Use StrOutputParser for markdown output instead of json_parser
            from langchain_core.output_parsers import StrOutputParser
            chain = prompt | self.llm | StrOutputParser()
            
            prompt_input = {
                "user_question": user_question,
                "product_name": product_name,
                "actor_line": f"Actor: {actor}" if actor else "",
                "tables_count": len(curated_tables_summary),
                "tables_summary": json.dumps(curated_tables_summary, indent=2),
                "edges_count": len(edges_summary),
                "edges_summary": json.dumps(edges_summary, indent=2),
                "contexts_count": len(contexts_summary),
                "contexts_summary": json.dumps(contexts_summary, indent=2),
                "metrics_count": len(metrics_summary),
                "metrics_summary": json.dumps(metrics_summary, indent=2) if metrics_summary else "[]"
            }
            
            # Log full prompt
            logger.info("=" * 80)
            logger.info("MDLSummaryNode: Full LLM Prompt (NO TRUNCATION)")
            logger.info("=" * 80)
            try:
                formatted_messages = prompt.format_messages(**prompt_input)
                logger.info(f"System Prompt:\n{formatted_messages[0].content}")
                logger.info(f"Human Prompt:\n{formatted_messages[1].content}")
            except Exception as e:
                logger.warning(f"Could not format prompt for logging: {e}")
            logger.info("=" * 80)
            
            markdown_result = await chain.ainvoke(prompt_input)
            
            # Log full response
            logger.info("=" * 80)
            logger.info("MDLSummaryNode: Full LLM Response (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Full Response Markdown:\n{markdown_result}")
            logger.info("=" * 80)
            
            # Create a structured result with markdown content
            result = {
                "summary_markdown": markdown_result,
                "curated_tables": curated_tables_info,
                "edges": edges_summary,
                "contexts": contexts_summary,
                "metrics": metrics_summary
            }
            
            # Log summary generation completion
            logger.info(f"MDLSummaryNode: Generated markdown summary ({len(markdown_result)} chars)")
            
            # Update state with summary
            state["summary"] = result
            
            # Normalize state values before creating final_result to ensure no character arrays
            normalized_identified_entities = normalize_string_list(
                state.get("identified_entities", []), 
                "identified_entities"
            )
            normalized_search_questions = state.get("search_questions", [])
            # For search_questions, filter out character arrays but keep valid dicts
            if isinstance(normalized_search_questions, list):
                normalized_search_questions = [
                    item for item in normalized_search_questions 
                    if isinstance(item, dict) or (isinstance(item, str) and len(item.strip()) > 1)
                ]
            normalized_mdl_queries = normalize_string_list(
                state.get("mdl_queries", []), 
                "mdl_queries"
            )
            normalized_relevant_tables = normalize_string_list(
                state.get("relevant_tables", []), 
                "relevant_tables"
            )
            
            state["final_result"] = {
                "user_question": user_question,
                "product_name": product_name,
                "actor": actor,
                "curated_tables": curated_tables_info,
                "contextual_plan": contextual_plan,
                "contexts_retrieved": contexts_retrieved,
                "edges_discovered": edges_discovered,
                "metrics_retrieved": metrics_retrieved,
                "summary": result,
                "identified_entities": normalized_identified_entities,
                "search_questions": normalized_search_questions,
                "mdl_queries": normalized_mdl_queries,
                "relevant_tables": normalized_relevant_tables
            }
            state["current_step"] = "summary"
            state["status"] = "completed"
            
            logger.info(f"MDLSummaryNode: Generated summary with {len(result.get('key_tables', []))} key tables")
            
            return state
            
        except Exception as e:
            logger.error(f"MDLSummaryNode: Error: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = f"Summary generation failed: {str(e)}"
            return state


class MDLPlanningNode:
    """Node that creates reasoning plan for product, controls, risks, metrics (DEPRECATED - kept for backward compatibility)"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: MDLReasoningState) -> MDLReasoningState:
        """Create reasoning plan - DEPRECATED: Planning logic removed, this is now a pass-through"""
        logger.info("MDLPlanningNode: Starting execution (DEPRECATED - planning logic removed)")
        
        # Just pass through - planning logic has been removed
        state["current_step"] = "planning"
        state["status"] = "completed"
        
        # Create minimal final result
        state["final_result"] = {
            "user_question": state.get("user_question", ""),
            "product_name": state.get("product_name"),
            "tables_found": state.get("tables_found", []),
            "edges_discovered": state.get("edges_discovered", []),
            "contextual_plan": state.get("contextual_plan", {})
        }
        
        logger.info("MDLPlanningNode: Pass-through completed (planning logic removed)")
        
        return state


# ============================================================================
# Graph Builder
# ============================================================================

class MDLReasoningGraphBuilder:
    """
    Builder for MDL reasoning and planning graph.
    
    Creates a graph workflow:
    1. Context Breakdown - Breaks down user question
    2. Entity Identification - Identifies tables and entities
    3. Context Retrieval - Retrieves contexts and edges
    4. Planning - Creates reasoning plan
    """
    
    def __init__(
        self,
        contextual_graph_storage: ContextualGraphStorage,
        collection_factory: CollectionFactory,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        retrieval_helper: Optional[Any] = None
    ):
        """
        Initialize the MDL reasoning graph builder.
        
        Args:
            contextual_graph_storage: ContextualGraphStorage instance
            collection_factory: CollectionFactory instance
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.contextual_graph_storage = contextual_graph_storage
        self.collection_factory = collection_factory
        
        # Initialize agents and services
        self.context_breakdown_service = ContextBreakdownService(
            llm=llm,
            model_name=model_name
        )
        
        self.retriever = MDLSemanticRetriever(
            contextual_graph_storage=contextual_graph_storage,
            collection_factory=collection_factory,
            retrieval_helper=retrieval_helper  # Pass retrieval_helper to use standardized methods
        )
        
        self.mdl_semantic_layer_service = MDLSemanticLayerService(
            contextual_graph_storage=contextual_graph_storage,
            collection_factory=collection_factory,
            llm=llm,
            model_name=model_name
        )
        
        # Initialize table retrieval agent
        self.table_retrieval_agent = MDLTableRetrievalAgent(
            llm=llm,
            model_name=model_name
        )
        
        # Initialize nodes
        self.generic_breakdown_node = GenericContextBreakdownNode(
            context_breakdown_service=self.context_breakdown_service,
            llm=llm,
            model_name=model_name
        )
        self.mdl_curation_node = MDLTableCurationNode(
            retriever=self.retriever,
            llm=llm,
            model_name=model_name,
            retrieval_helper=retrieval_helper
        )
        
        self.contextual_planner_node = MDLContextualPlannerNode(
            retriever=self.retriever,
            llm=llm,
            model_name=model_name
        )
        
        self.edge_based_retrieval_node = MDLEdgeBasedRetrievalNode(
            retriever=self.retriever,
            contextual_graph_storage=contextual_graph_storage
        )
        
        self.summary_node = MDLSummaryNode(
            llm=llm,
            model_name=model_name,
            retriever=self.retriever,
            retrieval_helper=retrieval_helper
        )
        
        # Keep these for backward compatibility but they won't be used in the new workflow
        self.entity_identification_node = MDLEntityIdentificationNode(
            retriever=self.retriever,
            llm=llm,
            model_name=model_name
        )
        
        self.table_retrieval_node = MDLTableRetrievalNode(
            table_retrieval_agent=self.table_retrieval_agent,
            retriever=self.retriever
        )
        
        self.table_pruning_node = MDLTablePruningNode(
            retriever=self.retriever,
            llm=llm,
            model_name=model_name
        )
        
        self.context_retrieval_node = MDLContextRetrievalNode(
            mdl_semantic_layer_service=self.mdl_semantic_layer_service
        )
        
        self.planning_node = MDLPlanningNode(
            llm=llm,
            model_name=model_name
        )
        
        logger.info("Initialized MDL Reasoning Graph Builder")
    
    def build_graph(self, use_checkpointing: bool = False) -> StateGraph:
        """
        Build the MDL reasoning and planning graph.
        
        Args:
            use_checkpointing: Whether to use checkpointing for state persistence
            
        Returns:
            Compiled StateGraph
        """
        from langgraph.checkpoint.memory import MemorySaver
        
        # Create graph
        workflow = StateGraph(MDLReasoningState)
        
        # Add nodes (use different names to avoid conflicts with state keys)
        workflow.add_node("generic_breakdown_step", self.generic_breakdown_node)
        workflow.add_node("mdl_curation_step", self.mdl_curation_node)
        workflow.add_node("contextual_planning_step", self.contextual_planner_node)
        workflow.add_node("edge_retrieval_step", self.edge_based_retrieval_node)
        workflow.add_node("summary_step", self.summary_node)
        
        # Set entry point
        workflow.set_entry_point("generic_breakdown_step")
        
        # Define workflow edges - streamlined workflow
        # 1. Generic breakdown (identifies data sources and query type)
        workflow.add_edge("generic_breakdown_step", "mdl_curation_step")
        # 2. MDL table curation (only if query_type is mdl, otherwise passes through)
        workflow.add_edge("mdl_curation_step", "contextual_planning_step")
        # 3. Contextual planning (identifies relevant edges for curated tables)
        workflow.add_edge("contextual_planning_step", "edge_retrieval_step")
        # 4. Edge-based retrieval (retrieves data based on identified edges)
        workflow.add_edge("edge_retrieval_step", "summary_step")
        # 5. Summary (final summary of all collected data)
        workflow.add_edge("summary_step", END)
        
        # Compile graph
        if use_checkpointing:
            checkpointer = MemorySaver()
            return workflow.compile(checkpointer=checkpointer)
        else:
            return workflow.compile()
    
    def create_graph(self, use_checkpointing: bool = False) -> Any:
        """
        Create and return the compiled graph.
        
        Args:
            use_checkpointing: Whether to use checkpointing
            
        Returns:
            Compiled graph
        """
        return self.build_graph(use_checkpointing=use_checkpointing)


def create_mdl_reasoning_graph(
    contextual_graph_storage: ContextualGraphStorage,
    collection_factory: CollectionFactory,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o-mini",
    use_checkpointing: bool = False,
    retrieval_helper: Optional[Any] = None
) -> StateGraph:
    """
    Factory function to create MDL reasoning graph.
    
    Args:
        contextual_graph_storage: ContextualGraphStorage instance
        collection_factory: CollectionFactory instance
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        use_checkpointing: Whether to use checkpointing
        retrieval_helper: Optional RetrievalHelper instance for retrieving table DDL with columns
        
    Returns:
        Compiled StateGraph
    """
    builder = MDLReasoningGraphBuilder(
        contextual_graph_storage=contextual_graph_storage,
        collection_factory=collection_factory,
        llm=llm,
        model_name=model_name,
        retrieval_helper=retrieval_helper
    )
    return builder.build_graph(use_checkpointing=use_checkpointing)

