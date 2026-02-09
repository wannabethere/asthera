"""
Context Breakdown Service
Wrapper service that uses the generic contextual agents for context breakdown.

This service delegates to the ContextBreakdownPlanner which intelligently routes
queries to the appropriate domain-specific agent (Compliance, MDL, Product, Domain Knowledge).

Location of contextual agents: app/agents/contextual_agents/
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI

from app.agents.contextual_agents import (
    ContextBreakdownPlanner,
    ContextBreakdown
)

logger = logging.getLogger(__name__)

# Re-export ContextBreakdown for backward compatibility
__all__ = ["ContextBreakdown", "ContextBreakdownService"]


class ContextBreakdownService:
    """
    Service that breaks down user questions into context components using generic contextual agents.
    
    Delegates to ContextBreakdownPlanner which intelligently routes queries to:
    - ComplianceContextBreakdownAgent - For compliance/risk queries
    - MDLContextBreakdownAgent - For database/schema queries
    - ProductContextBreakdownAgent - For product feature queries
    - DomainKnowledgeContextBreakdownAgent - For domain concept queries
    
    Location of agents: app/agents/contextual_agents/
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the context breakdown service.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json (passed to agents)
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        
        # Use the generic ContextBreakdownPlanner which routes to appropriate agents
        self.planner = ContextBreakdownPlanner(llm=self.llm, prompts_file=prompts_file)
        
        logger.info("ContextBreakdownService initialized with generic contextual agents")
    
    async def breakdown_question(
        self,
        user_question: str,
        available_frameworks: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None
    ) -> ContextBreakdown:
        """
        Break down a user question into context components using the planner.
        
        The planner will automatically route to the appropriate domain-specific agent.
        
        Args:
            user_question: User's question or query
            available_frameworks: Optional list of available frameworks
            available_products: Optional list of available products
            available_actors: Optional list of available actor types
            available_domains: Optional list of available domains
            
        Returns:
            ContextBreakdown object with extracted context information
        """
        try:
            # Delegate to the planner which will route to the appropriate agent
            result = await self.planner.breakdown_question(
                user_question=user_question,
                available_frameworks=available_frameworks,
                available_products=available_products,
                available_actors=available_actors,
                available_domains=available_domains
            )
            
            # Extract the combined breakdown from the result
            breakdown = result.get("combined_breakdown")
            
            if breakdown is None:
                logger.warning("Planner returned no breakdown, creating minimal breakdown")
                breakdown = ContextBreakdown(
                    user_question=user_question,
                    query_type="unknown",
                    identified_entities=[]
                )
            
            logger.info(f"Context breakdown complete via planner: query_type={breakdown.query_type}, "
                       f"compliance={breakdown.compliance_context}, product={breakdown.product_context}")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down question via planner: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            return ContextBreakdown(
                user_question=user_question,
                query_type="unknown",
                identified_entities=[]
            )
