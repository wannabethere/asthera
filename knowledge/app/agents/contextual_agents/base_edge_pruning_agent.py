"""
Base Edge Pruning Agent
Abstract base class for pruning discovered edges using LLM.
"""
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class BaseEdgePruningAgent(ABC):
    """
    Abstract base class for edge pruning agents.
    
    Provides common functionality for:
    - LLM interaction
    - Edge summarization
    - Edge selection
    
    Subclasses implement:
    - prune_edges(): Main method to prune edges
    - _apply_domain_scoring(): Domain-specific scoring logic
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the base edge pruning agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    def _create_edge_summary(
        self,
        edge: ContextualEdge,
        index: int,
        include_domain_context: bool = True
    ) -> Dict[str, Any]:
        """
        Create a summary of an edge for LLM processing.
        
        Args:
            edge: Edge to summarize
            index: Index of the edge
            include_domain_context: Whether to include domain-specific context
            
        Returns:
            Dictionary with edge summary
        """
        summary = {
            "index": index,
            "edge_id": edge.edge_id,
            "edge_type": edge.edge_type,
            "source_entity_type": edge.source_entity_type,
            "target_entity_type": edge.target_entity_type,
            "source_entity_id": edge.source_entity_id,
            "target_entity_id": edge.target_entity_id,
            "document": edge.document[:200],  # Truncate for prompt
            "relevance_score": edge.relevance_score
        }
        
        if include_domain_context:
            summary.update(self._get_domain_context(edge))
        
        return summary
    
    @abstractmethod
    def _get_domain_context(self, edge: ContextualEdge) -> Dict[str, Any]:
        """
        Get domain-specific context for an edge.
        
        Args:
            edge: Edge to get context for
            
        Returns:
            Dictionary with domain-specific context
        """
        pass
    
    @abstractmethod
    async def prune_edges(
        self,
        user_question: str,
        discovered_edges: List[ContextualEdge],
        max_edges: int = 10,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Prune discovered edges to select the most relevant ones.
        
        Args:
            user_question: Original user question
            discovered_edges: List of discovered edges
            max_edges: Maximum number of edges to return
            context_breakdown: Optional context breakdown information
            
        Returns:
            List of pruned (selected) edges
        """
        pass
    
    def _apply_domain_scoring(
        self,
        edges: List[ContextualEdge],
        user_question: str,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Apply domain-specific scoring to edges (non-LLM fallback).
        
        Args:
            edges: List of edges to score
            user_question: User question
            context_breakdown: Optional context breakdown
            
        Returns:
            List of edges with updated relevance scores
        """
        # Default implementation - subclasses can override
        return edges
    
    async def rank_edges_by_relevance(
        self,
        user_question: str,
        edges: List[ContextualEdge]
    ) -> List[ContextualEdge]:
        """
        Rank edges by relevance to user question (without pruning).
        
        Args:
            user_question: User question
            edges: List of edges to rank
            
        Returns:
            List of edges sorted by relevance
        """
        try:
            if not edges:
                return []
            
            # Create edge summaries
            edge_summaries = [
                self._create_edge_summary(edge, i, include_domain_context=True)
                for i, edge in enumerate(edges)
            ]
            
            # Use LLM to score each edge (implemented by subclass or generic)
            # For now, sort by existing relevance score
            sorted_edges = sorted(edges, key=lambda e: e.relevance_score, reverse=True)
            
            return sorted_edges
            
        except Exception as e:
            logger.error(f"Error ranking edges: {str(e)}", exc_info=True)
            # Fallback: return edges sorted by existing relevance score
            return sorted(edges, key=lambda e: e.relevance_score, reverse=True)
