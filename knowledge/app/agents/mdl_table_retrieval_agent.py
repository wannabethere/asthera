"""
MDL Table Retrieval Agent
LLM-based agent that generates retrieval queries for table/entity discovery.
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

logger = logging.getLogger(__name__)


class MDLTableRetrievalAgent:
    """
    Agent that uses LLM to generate retrieval queries for table/entity discovery.
    
    This is an AGENT (uses LLM) that:
    - Takes user question and context breakdown
    - Generates specific retrieval queries for tables, entities, and contexts
    - Returns structured retrieval plan with queries and filters
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the MDL table retrieval agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def generate_retrieval_queries(
        self,
        user_question: str,
        context_breakdown: Optional[Dict[str, Any]] = None,
        product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate retrieval queries using LLM based on user question and breakdown.
        
        This is the main AGENT method that uses LLM to:
        1. Analyze the question and breakdown
        2. Generate specific retrieval queries for tables, entities, contexts
        3. Return structured retrieval plan
        
        Args:
            user_question: Original user question
            context_breakdown: Optional context breakdown from previous step
            product_name: Optional product name
            
        Returns:
            Dictionary with retrieval queries for different entity types
        """
        try:
            # Get query type from context breakdown
            query_type = context_breakdown.get("query_type", "unknown") if context_breakdown else "unknown"
            is_mdl_query = query_type == "mdl"
            
            # Build prompt
            breakdown_info = ""
            mdl_instructions = ""
            if context_breakdown:
                identified_entities = context_breakdown.get("identified_entities", [])
                search_questions = context_breakdown.get("search_questions", [])
                breakdown_info = f"""
Context Breakdown Available:
- Query Type: {query_type}
- Identified Entities: {', '.join(identified_entities) if identified_entities else 'None'}
- Search Questions: {len(search_questions)} questions
- Product Context: {context_breakdown.get('product_context', 'N/A')}
"""
                
                # Add MDL-specific instructions only if query type is MDL
                if is_mdl_query:
                    mdl_instructions = """
Generate retrieval queries for MDL semantic layer:
1. table_definitions - Table structure definitions
2. table_descriptions - Table descriptions with business context (includes schema categories from project_reader.py)
3. context_definitions - Table entity contexts
4. contextual_edges - Table relationships

For MDL queries, use categories filters for discovery, avoid specific table_name or context_id filters in first retrieval.
"""
                else:
                    mdl_instructions = f"""
Generate retrieval queries based on the query type ({query_type}) and identified entities.
"""
            
            # Build system prompt based on query type
            if is_mdl_query:
                system_prompt = """You are an expert at generating retrieval queries for MDL semantic layer queries.

Given a user question and context breakdown (query_type: mdl), generate specific MDL retrieval queries that will find:
1. Tables and their definitions/descriptions
2. Table relationships and edges
3. Schema categories and organization
4. Context definitions for tables
5. Related entities

For each entity type, generate:
- A natural language query that will retrieve relevant documents
- Metadata filters that should be applied (following MDL rules)
- The expected response type

MDL-SPECIFIC RULES:
- Use the original user question to generate queries (don't just repeat the breakdown)
- Be specific about table names, categories, and relationships mentioned
- Note: schema_descriptions are now handled by project_reader.py via table_description component - use table_descriptions instead
- For contextual_edges queries, specify edge types as a list when multiple are relevant: ["BELONGS_TO_TABLE", "HAS_MANY_TABLES"]
- For table_definitions/table_descriptions, use product_name filter (NOT table_name in first retrieval)
- CRITICAL: Use "categories" filter to narrow down table search based on semantic categories:
  * Available categories: "access requests", "assets", "projects", "vulnerabilities", "integrations", 
    "configuration", "audit logs", "risk management", "deployment", "groups", "organizations", 
    "memberships and roles", "issues", "artifacts", "application data", "user management", "security"
  * Example: For "user access" questions, use {{"categories": ["access requests", "user management"]}}
  * Example: For "asset" questions, use {{"categories": ["assets"]}}
  * Example: For "vulnerability" questions, use {{"categories": ["vulnerabilities", "issues"]}}
  * Categories are NOW INDEXED in all table/column stores and should be used for filtering
- For filters with multiple values, simply provide a list: {{"edge_type": ["BELONGS_TO_TABLE", "HAS_MANY_TABLES"]}}
- The system will automatically convert lists to the appropriate filter format for the vector store backend
- Do NOT use vector store-specific operators (like $in, $and, etc.) - just provide the values and condition types
- Table entity IDs follow format: entity_{{product_name}}_{{table_name}} (use context_id filter ONLY after tables are discovered)
- For relationship queries, use edge_type filters but avoid specific source_entity_id in first retrieval"""
            else:
                system_prompt = """You are an expert at generating retrieval queries.

Given a user question and context breakdown (query_type: {query_type}), generate specific retrieval queries that will find relevant information.

For each entity type, generate:
- A natural language query that will retrieve relevant documents
- Metadata filters that should be applied
- The expected response type

IMPORTANT:
- Use the original user question to generate queries (don't just repeat the breakdown)
- Be specific about what information is needed
- For filters with multiple values, simply provide a list
- The system will automatically convert lists to the appropriate filter format for the vector store backend
- Do NOT use vector store-specific operators (like $in, $and, etc.) - just provide the values and condition types""".format(query_type=query_type)
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", """Generate retrieval queries for this query:

User Question: {user_question}
Product: {product_name}
Query Type: {query_type}
{breakdown_info}

{mdl_instructions}

For each entity type, provide:
- query: Natural language query string
- metadata_filters: Dictionary of filters with simple key-value pairs or lists for multiple values
  * For single values: {{"product_name": "Snyk"}}
  * For multiple values: {{"edge_type": ["BELONGS_TO_TABLE", "HAS_MANY_TABLES"]}}
  * The system will handle filter format conversion automatically
- response_type: What type of information should be retrieved

Return JSON with:
- retrieval_queries: List of query objects, each with entity, query, metadata_filters, response_type
- priority: Priority order for retrieval (1 = highest priority)
""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            # Prepare input for logging
            prompt_input = {
                "user_question": user_question,
                "product_name": product_name or "Unknown",
                "query_type": query_type,
                "breakdown_info": breakdown_info or "No context breakdown available",
                "mdl_instructions": mdl_instructions
            }
            
            # Log full prompt without truncation
            logger.info("=" * 80)
            logger.info("MDLTableRetrievalAgent: Full LLM Prompt (NO TRUNCATION)")
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
            logger.info("MDLTableRetrievalAgent: Full LLM Response (NO TRUNCATION)")
            logger.info("=" * 80)
            logger.info(f"Full Response JSON:\n{json.dumps(result, indent=2)}")
            logger.info("=" * 80)
            
            retrieval_queries = result.get("retrieval_queries", [])
            
            logger.info(f"MDLTableRetrievalAgent: Generated {len(retrieval_queries)} retrieval queries")
            
            return {
                "retrieval_queries": retrieval_queries,
                "user_question": user_question,
                "product_name": product_name
            }
            
        except Exception as e:
            logger.error(f"Error generating retrieval queries: {str(e)}", exc_info=True)
            return {
                "retrieval_queries": [],
                "user_question": user_question,
                "product_name": product_name,
                "error": str(e)
            }
