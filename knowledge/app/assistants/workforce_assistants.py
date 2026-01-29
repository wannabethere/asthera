"""
Workforce Assistants
Generic assistant implementation for Product, Compliance, and Domain Knowledge.

Key Features:
- Uses contextual breakdown agents for query analysis
- Configurable via workforce_config.py
- Web search integration
- Multiple data source support
- Category-based filtering
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
import json

from app.agents.contextual_agents import (
    ProductContextBreakdownAgent,
    ComplianceContextBreakdownAgent,
    DomainKnowledgeContextBreakdownAgent,
    ProductEdgePruningAgent,
    ComplianceEdgePruningAgent,
    DomainKnowledgeEdgePruningAgent,
    ContextBreakdown
)
from app.config.workforce_config import (
    AssistantType,
    AssistantConfig,
    get_assistant_config,
    DataSourceConfig
)

logger = logging.getLogger(__name__)


class WorkforceAssistant:
    """
    Generic workforce assistant that can be configured for different domains.
    
    Supports:
    - Product documentation queries
    - Compliance and risk management queries
    - Domain knowledge and best practices queries
    
    Uses:
    - Context breakdown agents for query analysis
    - Edge pruning agents for result filtering
    - Web search for external documentation
    - Multiple data sources with category filtering
    """
    
    def __init__(
        self,
        assistant_type: AssistantType,
        config: Optional[AssistantConfig] = None,
        llm: Optional[ChatOpenAI] = None
    ):
        """
        Initialize a workforce assistant.
        
        Args:
            assistant_type: Type of assistant
            config: Optional custom configuration (uses default if not provided)
            llm: Optional LLM instance
        """
        self.assistant_type = assistant_type
        self.config = config or get_assistant_config(assistant_type)
        self.llm = llm or ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.temperature
        )
        
        # Initialize context breakdown agent based on type
        if assistant_type == AssistantType.PRODUCT:
            self.context_agent = ProductContextBreakdownAgent(llm=self.llm)
            self.pruning_agent = ProductEdgePruningAgent(llm=self.llm)
        elif assistant_type == AssistantType.COMPLIANCE:
            self.context_agent = ComplianceContextBreakdownAgent(llm=self.llm)
            self.pruning_agent = ComplianceEdgePruningAgent(llm=self.llm)
        elif assistant_type == AssistantType.DOMAIN_KNOWLEDGE:
            self.context_agent = DomainKnowledgeContextBreakdownAgent(llm=self.llm)
            self.pruning_agent = DomainKnowledgeEdgePruningAgent(llm=self.llm)
        else:
            raise ValueError(f"Unknown assistant type: {assistant_type}")
        
        self.json_parser = JsonOutputParser()
        self.str_parser = StrOutputParser()
        
        logger.info(f"Initialized {assistant_type.value} assistant with model {self.config.model_name}")
    
    async def process_query(
        self,
        user_question: str,
        available_products: Optional[List[str]] = None,
        available_frameworks: Optional[List[str]] = None,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        available_actions: Optional[List[str]] = None,
        available_concepts: Optional[List[str]] = None,
        output_format: str = "summary",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a user query using the workforce assistant.
        
        Args:
            user_question: User's question
            available_products: Optional list of available products
            available_frameworks: Optional list of available frameworks
            available_actors: Optional list of available actors
            available_domains: Optional list of available domains
            available_actions: Optional list of available user actions
            available_concepts: Optional list of available concepts
            output_format: Output format ("summary" or "json")
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with:
            - breakdown: Context breakdown
            - retrieved_docs: Retrieved documents
            - response: Final response (summary or JSON)
            - web_search_results: Web search results (if enabled)
        """
        try:
            # Step 1: Break down the question using context agent
            logger.info(f"Breaking down {self.assistant_type.value} query: {user_question[:100]}")
            
            breakdown_kwargs = {
                "user_question": user_question,
                "web_search_enabled": self.config.web_search_enabled
            }
            
            # Add type-specific parameters
            if self.assistant_type == AssistantType.PRODUCT:
                breakdown_kwargs.update({
                    "available_products": available_products,
                    "available_actions": available_actions,
                    "available_domains": available_domains
                })
            elif self.assistant_type == AssistantType.COMPLIANCE:
                breakdown_kwargs.update({
                    "available_frameworks": available_frameworks,
                    "available_products": available_products,
                    "available_actors": available_actors,
                    "available_domains": available_domains
                })
            elif self.assistant_type == AssistantType.DOMAIN_KNOWLEDGE:
                breakdown_kwargs.update({
                    "available_domains": available_domains,
                    "available_concepts": available_concepts,
                    "available_products": available_products,
                    "available_frameworks": available_frameworks
                })
            
            breakdown = await self.context_agent.breakdown_question(**breakdown_kwargs)
            
            logger.info(f"Context breakdown complete: {breakdown.query_type}")
            
            # Step 2: Retrieve documents from data sources
            retrieved_docs = await self._retrieve_from_data_sources(breakdown, kwargs)
            
            logger.info(f"Retrieved {len(retrieved_docs)} documents")
            
            # Step 3: Perform web search if enabled
            web_search_results = []
            if self.config.web_search_enabled and breakdown.metadata.get("web_search_queries"):
                web_search_results = await self._perform_web_search(
                    breakdown.metadata["web_search_queries"]
                )
                logger.info(f"Web search returned {len(web_search_results)} results")
            
            # Step 4: Compose final response
            response = await self._compose_response(
                user_question=user_question,
                breakdown=breakdown,
                retrieved_docs=retrieved_docs,
                web_search_results=web_search_results,
                output_format=output_format,
                available_products=available_products,
                available_frameworks=available_frameworks,
                available_actors=available_actors,
                available_domains=available_domains,
                available_actions=available_actions,
                available_concepts=available_concepts
            )
            
            return {
                "breakdown": breakdown,
                "retrieved_docs": retrieved_docs,
                "web_search_results": web_search_results,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Error processing {self.assistant_type.value} query: {str(e)}", exc_info=True)
            return {
                "breakdown": None,
                "retrieved_docs": [],
                "web_search_results": [],
                "response": f"Error processing query: {str(e)}",
                "error": str(e)
            }
    
    async def _retrieve_from_data_sources(
        self,
        breakdown: ContextBreakdown,
        kwargs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents from configured data sources.
        
        Args:
            breakdown: Context breakdown
            kwargs: Additional parameters (may include custom retrieval functions)
            
        Returns:
            List of retrieved documents
        """
        retrieved_docs = []
        
        # Sort data sources by priority (descending)
        sorted_sources = sorted(
            self.config.data_sources,
            key=lambda s: s.priority,
            reverse=True
        )
        
        for source_config in sorted_sources:
            if not source_config.enabled:
                continue
            
            try:
                # Check if custom retrieval function is provided
                retrieval_fn_key = f"{source_config.source_name}_retrieval_fn"
                if retrieval_fn_key in kwargs:
                    retrieval_fn = kwargs[retrieval_fn_key]
                    docs = await retrieval_fn(breakdown, source_config)
                    retrieved_docs.extend(docs)
                    logger.info(f"Retrieved {len(docs)} docs from {source_config.source_name} (custom)")
                else:
                    # Use default retrieval logic
                    docs = await self._default_retrieval(breakdown, source_config)
                    retrieved_docs.extend(docs)
                    logger.info(f"Retrieved {len(docs)} docs from {source_config.source_name} (default)")
            
            except Exception as e:
                logger.error(f"Error retrieving from {source_config.source_name}: {str(e)}")
                continue
        
        return retrieved_docs
    
    async def _default_retrieval(
        self,
        breakdown: ContextBreakdown,
        source_config: DataSourceConfig
    ) -> List[Dict[str, Any]]:
        """
        Default retrieval logic (placeholder).
        
        In production, this would:
        - Query Chroma vector stores
        - Query PostgreSQL tables
        - Use hybrid search
        - Apply category filters
        
        Args:
            breakdown: Context breakdown
            source_config: Data source configuration
            
        Returns:
            List of retrieved documents
        """
        # Placeholder - in production, implement actual retrieval
        logger.info(f"Default retrieval for {source_config.source_name} (placeholder)")
        return []
    
    async def _perform_web_search(
        self,
        search_queries: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Perform web search using LLM-based information retrieval.
        
        Args:
            search_queries: List of search queries
            
        Returns:
            List of web search results
        """
        if not search_queries:
            return []
        
        try:
            logger.info(f"LLM-based web search for {len(search_queries)} queries")
            
            # Use LLM to generate information based on queries
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a knowledgeable assistant that provides accurate information based on search queries.
For each query, provide relevant information that would typically be found through web search.

Return a JSON array with objects containing:
- query: The search query
- title: A relevant title for the information
- summary: A concise summary (2-3 sentences)
- url: A placeholder URL (e.g., "https://docs.example.com/...")
- relevance_score: A score from 0.0 to 1.0"""),
                ("human", """Search queries:
{queries}

Provide accurate, helpful information for each query as a JSON array.""")
            ])
            
            chain = prompt | self.llm | JsonOutputParser()
            
            results = await chain.ainvoke({
                "queries": "\n".join(f"{i+1}. {q}" for i, q in enumerate(search_queries))
            })
            
            logger.info(f"LLM web search returned {len(results)} results")
            return results if isinstance(results, list) else []
            
        except Exception as e:
            logger.error(f"Error in LLM web search: {str(e)}", exc_info=True)
            return []
    
    async def _compose_response(
        self,
        user_question: str,
        breakdown: ContextBreakdown,
        retrieved_docs: List[Dict[str, Any]],
        web_search_results: List[Dict[str, Any]],
        output_format: str,
        available_products: Optional[List[str]] = None,
        available_frameworks: Optional[List[str]] = None,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        available_actions: Optional[List[str]] = None,
        available_concepts: Optional[List[str]] = None
    ) -> str:
        """
        Compose final response using LLM.
        
        Args:
            user_question: Original user question
            breakdown: Context breakdown
            retrieved_docs: Retrieved documents
            web_search_results: Web search results
            output_format: Output format ("summary" or "json")
            available_products: Available products
            available_frameworks: Available frameworks
            available_actors: Available actors
            available_domains: Available domains
            available_actions: Available actions
            available_concepts: Available concepts
            
        Returns:
            Final response string
        """
        try:
            # Build context breakdown string
            context_breakdown_str = json.dumps({
                "query_type": breakdown.query_type,
                "user_intent": breakdown.user_intent,
                "identified_entities": breakdown.identified_entities,
                "query_keywords": breakdown.query_keywords,
                "metadata": breakdown.metadata
            }, indent=2)
            
            # Build retrieved docs string
            retrieved_docs_str = json.dumps(retrieved_docs[:10], indent=2) if retrieved_docs else "No documents retrieved"
            
            # Build web search results string
            web_search_str = json.dumps(web_search_results[:5], indent=2) if web_search_results else "No web search results"
            
            # Build human prompt
            human_prompt_vars = {
                "user_question": user_question,
                "available_products": ", ".join(available_products or []) or "N/A",
                "available_frameworks": ", ".join(available_frameworks or []) or "N/A",
                "available_actors": ", ".join(available_actors or []) or "N/A",
                "available_domains": ", ".join(available_domains or []) or "N/A",
                "available_actions": ", ".join(available_actions or []) or "N/A",
                "available_concepts": ", ".join(available_concepts or []) or "N/A",
                "context_breakdown": context_breakdown_str,
                "output_format": output_format
            }
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.config.system_prompt_template + f"""

Retrieved Documents:
{retrieved_docs_str}

Web Search Results:
{web_search_str}
"""),
                ("human", self.config.human_prompt_template)
            ])
            
            # Choose parser based on output format
            parser = self.str_parser if output_format == "summary" else self.json_parser
            
            chain = prompt | self.llm | parser
            
            response = await chain.ainvoke(human_prompt_vars)
            
            return response
            
        except Exception as e:
            logger.error(f"Error composing response: {str(e)}", exc_info=True)
            return f"Error composing response: {str(e)}"


# ============================================================================
# CONVENIENCE FACTORY FUNCTIONS
# ============================================================================

def create_product_assistant(
    config: Optional[AssistantConfig] = None,
    llm: Optional[ChatOpenAI] = None
) -> WorkforceAssistant:
    """
    Create a Product Assistant.
    
    Args:
        config: Optional custom configuration
        llm: Optional LLM instance
        
    Returns:
        WorkforceAssistant configured for product queries
    """
    return WorkforceAssistant(AssistantType.PRODUCT, config, llm)


def create_compliance_assistant(
    config: Optional[AssistantConfig] = None,
    llm: Optional[ChatOpenAI] = None
) -> WorkforceAssistant:
    """
    Create a Compliance Assistant.
    
    Args:
        config: Optional custom configuration
        llm: Optional LLM instance
        
    Returns:
        WorkforceAssistant configured for compliance queries
    """
    return WorkforceAssistant(AssistantType.COMPLIANCE, config, llm)


def create_domain_knowledge_assistant(
    config: Optional[AssistantConfig] = None,
    llm: Optional[ChatOpenAI] = None
) -> WorkforceAssistant:
    """
    Create a Domain Knowledge Assistant.
    
    Args:
        config: Optional custom configuration
        llm: Optional LLM instance
        
    Returns:
        WorkforceAssistant configured for domain knowledge queries
    """
    return WorkforceAssistant(AssistantType.DOMAIN_KNOWLEDGE, config, llm)
