"""
Edge Pruning Service
Wrapper service that uses the generic edge pruning agents from contextual_agents.

This service delegates to domain-specific pruning agents that understand
edge priorities and relevance for different domains.

Location of pruning agents: app/agents/contextual_agents/
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI

from app.services.contextual_graph_storage import ContextualEdge
from app.agents.contextual_agents import (
    ComplianceEdgePruningAgent,
    MDLEdgePruningAgent
)

logger = logging.getLogger(__name__)


class EdgePruningService:
    """
    Service that prunes discovered edges using domain-specific pruning agents.
    
    Delegates to:
    - ComplianceEdgePruningAgent - For compliance-related edges
    - MDLEdgePruningAgent - For MDL/schema-related edges
    
    Location of agents: app/agents/contextual_agents/
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the edge pruning service.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        
        # Initialize domain-specific pruning agents
        self.compliance_agent = ComplianceEdgePruningAgent(llm=self.llm)
        self.mdl_agent = MDLEdgePruningAgent(llm=self.llm)
        
        logger.info("EdgePruningService initialized with generic pruning agents")
    
    async def prune_edges(
        self,
        user_question: str,
        discovered_edges: List[ContextualEdge],
        max_edges: int = 10,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Prune discovered edges using the appropriate domain agent.
        
        Args:
            user_question: Original user question
            discovered_edges: List of discovered edges
            max_edges: Maximum number of edges to return
            context_breakdown: Optional context breakdown information
            
        Returns:
            List of pruned (selected) edges
        """
        try:
            if not discovered_edges:
                return []
            
            if len(discovered_edges) <= max_edges:
                # No pruning needed
                return discovered_edges
            
            # Determine which agent to use based on query type or edge types
            query_type = context_breakdown.get("query_type", "unknown") if context_breakdown else "unknown"
            
            # Check if edges are predominantly MDL or compliance
            mdl_edge_types = {"TABLE_HAS_FEATURE", "METRIC_FROM_TABLE", "EXAMPLE_USES_TABLE", 
                            "TABLE_BELONGS_TO_CATEGORY", "COLUMN_BELONGS_TO_TABLE"}
            compliance_edge_types = {"HAS_REQUIREMENT_IN_CONTEXT", "PROVED_BY", "RELEVANT_TO_CONTROL",
                                    "MITIGATED_BY"}
            
            edge_types = {edge.edge_type for edge in discovered_edges}
            mdl_count = len(edge_types & mdl_edge_types)
            compliance_count = len(edge_types & compliance_edge_types)
            
            # Select appropriate agent
            if query_type == "mdl" or mdl_count > compliance_count:
                logger.info(f"Using MDL edge pruning agent (mdl_count={mdl_count})")
                pruned_edges = await self.mdl_agent.prune_edges(
                    user_question=user_question,
                    discovered_edges=discovered_edges,
                    max_edges=max_edges,
                    context_breakdown=context_breakdown
                )
            else:
                logger.info(f"Using Compliance edge pruning agent (compliance_count={compliance_count})")
                pruned_edges = await self.compliance_agent.prune_edges(
                    user_question=user_question,
                    discovered_edges=discovered_edges,
                    max_edges=max_edges,
                    context_breakdown=context_breakdown
                )
            
            logger.info(f"Pruned {len(discovered_edges)} edges to {len(pruned_edges)} edges")
            return pruned_edges
            
        except Exception as e:
            logger.error(f"Error pruning edges: {str(e)}", exc_info=True)
            # Fallback: return top edges by relevance score
            sorted_edges = sorted(discovered_edges, key=lambda e: e.relevance_score, reverse=True)
            return sorted_edges[:max_edges]
