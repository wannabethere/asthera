"""
Product Context Breakdown Agent
Specialized agent for breaking down product-related queries.

Handles:
- Product documentation (Snyk, Okta, Jira, etc.)
- API documentation and endpoints
- Product features and capabilities
- User actions within products
- Product-specific keywords, concepts, and workflows
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
import json

from app.agents.contextual_agents.base_context_breakdown_agent import BaseContextBreakdownAgent, ContextBreakdown

logger = logging.getLogger(__name__)


class ProductContextBreakdownAgent(BaseContextBreakdownAgent):
    """
    Agent that breaks down product-related queries using LLM.
    
    Specializes in:
    - Product feature queries (Snyk vulnerabilities, Okta authentication, etc.)
    - API documentation queries
    - User action queries (how to configure X, how to use Y)
    - Product integration queries
    - Product workflow queries
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the product context breakdown agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json
        """
        super().__init__(llm, model_name, prompts_file)
    
    async def _detect_query_type(self, user_question: str) -> Dict[str, Any]:
        """
        Detect the type of product query from user question.
        
        Returns:
            Dictionary with query_type and detected entities
        """
        question_lower = user_question.lower()
        
        query_type = {
            "is_feature_query": any(keyword in question_lower for keyword in [
                "feature", "capability", "function", "what does", "how does"
            ]),
            "is_api_query": any(keyword in question_lower for keyword in [
                "api", "endpoint", "rest", "graphql", "webhook"
            ]),
            "is_configuration_query": any(keyword in question_lower for keyword in [
                "configure", "setup", "install", "enable", "disable", "settings"
            ]),
            "is_integration_query": any(keyword in question_lower for keyword in [
                "integrate", "integration", "connect", "sync"
            ]),
            "is_workflow_query": any(keyword in question_lower for keyword in [
                "workflow", "process", "how to", "steps", "procedure"
            ]),
            "is_troubleshooting_query": any(keyword in question_lower for keyword in [
                "error", "issue", "problem", "not working", "troubleshoot", "fix"
            ])
        }
        
        # Detect products mentioned
        detected_products = []
        product_keywords = {
            "Snyk": ["snyk"],
            "Okta": ["okta"],
            "Jira": ["jira"],
            "GitHub": ["github"],
            "GitLab": ["gitlab"],
            "ServiceNow": ["servicenow"],
            "Slack": ["slack"],
            "PagerDuty": ["pagerduty"],
            "Datadog": ["datadog"]
        }
        for product, keywords in product_keywords.items():
            if any(kw in question_lower for kw in keywords):
                detected_products.append(product)
        
        # Detect user actions mentioned
        detected_actions = []
        action_keywords = {
            "Configure": ["configure", "setup", "set up"],
            "Query": ["query", "search", "find", "get"],
            "Create": ["create", "add", "new"],
            "Update": ["update", "modify", "change", "edit"],
            "Delete": ["delete", "remove"],
            "Integrate": ["integrate", "connect", "link"],
            "Monitor": ["monitor", "track", "watch"],
            "Analyze": ["analyze", "review", "assess"]
        }
        for action, keywords in action_keywords.items():
            if any(kw in question_lower for kw in keywords):
                detected_actions.append(action)
        
        return {
            "query_type": query_type,
            "detected_products": detected_products,
            "detected_actions": detected_actions
        }
    
    async def breakdown_question(
        self,
        user_question: str,
        available_products: Optional[List[str]] = None,
        available_actions: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        web_search_enabled: bool = True,
        **kwargs
    ) -> ContextBreakdown:
        """
        Break down a product-related query using LLM.
        
        Args:
            user_question: User's question about product
            available_products: Optional list of available products
            available_actions: Optional list of available user actions
            available_domains: Optional list of available domains
            web_search_enabled: Whether web search is enabled for this query
            **kwargs: Additional parameters
            
        Returns:
            ContextBreakdown object with product-aware context information
        """
        try:
            # Detect product query type
            product_detection = await self._detect_query_type(user_question)
            
            # Build context for prompt
            products_context = ""
            if available_products:
                products_context = f"\n\nAvailable products: {', '.join(available_products)}"
            
            actions_context = ""
            if available_actions:
                actions_context = f"\n\nAvailable user actions: {', '.join(available_actions)}"
            
            domains_context = ""
            if available_domains:
                domains_context = f"\n\nAvailable domains: {', '.join(available_domains)}"
            
            # Get prompts from vector_store_prompts.json
            planning_instructions = self._get_planning_instructions()
            question_decomposition = self._get_question_decomposition()
            entity_definitions = self._get_entity_definitions()
            
            # Build entity list for prompt
            entity_list = "\n".join([
                f"- {name}: {info.get('description', '')[:100]}"
                for name, info in list(entity_definitions.items())[:20]
            ])
            
            # Add product detection results
            product_context_info = f"""
Product Query Detection:
- Is feature query: {product_detection['query_type']['is_feature_query']}
- Is API query: {product_detection['query_type']['is_api_query']}
- Is configuration query: {product_detection['query_type']['is_configuration_query']}
- Is integration query: {product_detection['query_type']['is_integration_query']}
- Is workflow query: {product_detection['query_type']['is_workflow_query']}
- Is troubleshooting query: {product_detection['query_type']['is_troubleshooting_query']}
- Detected products: {', '.join(product_detection['detected_products']) if product_detection['detected_products'] else 'None'}
- Detected actions: {', '.join(product_detection['detected_actions']) if product_detection['detected_actions'] else 'None'}
- Web search enabled: {web_search_enabled}
"""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at analyzing product-related questions to extract context information.

{planning_instructions}

{question_decomposition}

Available Entities:
{entity_list}

Break down the user question into:
1. Product context: Which product(s) are mentioned or implied?
2. Action context: What action is the user trying to perform?
3. Feature context: Which product features are relevant?
4. User intent: What is the user trying to accomplish?
5. Identified entities: Which entities from the available entities list are relevant?
6. Entity sub-types: Specific sub-types for identified entities
7. Edge types: Which edge types might be relevant?
8. Query keywords: Key terms that should be used for vector search
9. Web search queries: Suggested web search queries if web search is enabled

Return a JSON object with:
- query_type: Type of query (product_feature, api_docs, configuration, integration, workflow, troubleshooting)
- product_context: String describing product context
- action_context: String describing the action
- feature_context: String describing feature context (if any)
- user_intent: String describing user intent
- products: List of product names mentioned
- identified_entities: List of entity names from available entities
- entity_sub_types: List of specific sub-types
- entity_types: List of entity types that might be relevant
- edge_types: List of edge types that might be relevant
- query_keywords: List of key terms for search
- search_questions: List of search question objects for entity retrieval
- web_search_queries: List of suggested web search queries (if web_search_enabled)

If a context is not present, set it to null."""),
                ("human", """Analyze this product query:

{user_question}
{product_context_info}
{products_context}
{actions_context}
{domains_context}

Provide the context breakdown as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "product_context_info": product_context_info,
                "products_context": products_context,
                "actions_context": actions_context,
                "domains_context": domains_context
            })
            
            # Log result
            logger.info(f"Product context breakdown result: {json.dumps(result, indent=2)[:500]}")
            
            # Build ContextBreakdown from result
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type=result.get("query_type", "product"),
                product_context=result.get("product_context"),
                action_context=result.get("action_context"),
                user_intent=result.get("user_intent"),
                entity_types=result.get("entity_types", []),
                edge_types=result.get("edge_types", []),
                query_keywords=result.get("query_keywords", []),
                identified_entities=result.get("identified_entities", []),
                entity_sub_types=result.get("entity_sub_types", [])
            )
            
            # Store product-specific data in metadata
            breakdown.metadata["product_detection"] = product_detection
            breakdown.metadata["products"] = result.get("products", [])
            breakdown.metadata["feature_context"] = result.get("feature_context")
            breakdown.metadata["web_search_queries"] = result.get("web_search_queries", [])
            breakdown.metadata["web_search_enabled"] = web_search_enabled
            breakdown.search_questions = result.get("search_questions", [])
            
            logger.info(f"Product context breakdown: {len(breakdown.identified_entities)} entities, "
                       f"{len(breakdown.search_questions)} search questions, "
                       f"{len(breakdown.metadata.get('web_search_queries', []))} web search queries")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down product question: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type="product",
                identified_entities=[]
            )
            breakdown.search_questions = []
            breakdown.metadata["web_search_enabled"] = web_search_enabled
            breakdown.metadata["web_search_queries"] = []
            return breakdown
