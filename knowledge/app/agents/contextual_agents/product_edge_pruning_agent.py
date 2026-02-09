"""
Product Edge Pruning Agent
Specialized agent for pruning product-related edges.
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

from app.agents.contextual_agents.base_edge_pruning_agent import BaseEdgePruningAgent
from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class ProductEdgePruningAgent(BaseEdgePruningAgent):
    """
    Agent that prunes product-related edges.
    
    Specializes in:
    - Product feature edges (HAS_FEATURE, SUPPORTS)
    - API documentation edges (HAS_ENDPOINT, DOCUMENTED_IN)
    - User action edges (REQUIRES_ACTION, ENABLES)
    - Integration edges (INTEGRATES_WITH)
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the product edge pruning agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        super().__init__(llm, model_name)
        
        # Define product edge type priorities
        self.product_edge_priorities = {
            "HAS_FEATURE": "high",
            "HAS_ENDPOINT": "high",
            "DOCUMENTED_IN": "high",
            "REQUIRES_ACTION": "medium",
            "INTEGRATES_WITH": "medium",
            "SUPPORTS": "medium",
            "ENABLES": "medium",
            "CONFIGURED_BY": "medium",
            "RELATED_TO_IN_CONTEXT": "low"
        }
    
    def _get_domain_context(self, edge: ContextualEdge) -> Dict[str, Any]:
        """
        Get product-specific context for an edge.
        
        Args:
            edge: Edge to get context for
            
        Returns:
            Dictionary with product-specific context
        """
        context = {}
        
        # Check if this is a product edge
        product_edge_types = list(self.product_edge_priorities.keys())
        is_product_edge = edge.edge_type in product_edge_types
        context["is_product_edge"] = is_product_edge
        
        if is_product_edge:
            priority = self.product_edge_priorities.get(edge.edge_type, "low")
            context["product_priority"] = priority
            
            # Extract product info if available
            if hasattr(edge, 'metadata') and edge.metadata:
                if "product_name" in edge.metadata:
                    context["product_name"] = edge.metadata["product_name"]
                if "feature_name" in edge.metadata:
                    context["feature_name"] = edge.metadata["feature_name"]
        
        return context
    
    def get_product_edge_type_priority(self, edge_type: str) -> float:
        """
        Get priority score for product edge type.
        
        Args:
            edge_type: Edge type (e.g., "HAS_FEATURE")
            
        Returns:
            Priority score (0.0-1.0)
        """
        priority_str = self.product_edge_priorities.get(edge_type, "low")
        
        priority_map = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4
        }
        
        return priority_map.get(priority_str, 0.5)
    
    async def prune_edges(
        self,
        user_question: str,
        discovered_edges: List[ContextualEdge],
        max_edges: int = 10,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Prune discovered product edges using LLM.
        
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
                # No pruning needed, but still apply product-aware scoring
                return self._apply_domain_scoring(discovered_edges, user_question, context_breakdown)
            
            # Prepare edge summaries with product context
            edge_summaries = [
                self._create_edge_summary(edge, i, include_domain_context=True)
                for i, edge in enumerate(discovered_edges)
            ]
            
            # Count product edges
            product_edges_count = sum(1 for e in discovered_edges if e.edge_type in self.product_edge_priorities)
            
            # Build context breakdown context
            context_info = ""
            if context_breakdown:
                context_info = f"""
Context Breakdown:
- Product Context: {context_breakdown.get('product_context', 'N/A')}
- Action Context: {context_breakdown.get('action_context', 'N/A')}
- User Intent: {context_breakdown.get('user_intent', 'N/A')}
- Products: {', '.join(context_breakdown.get('metadata', {}).get('products', []))}
- Feature Context: {context_breakdown.get('metadata', {}).get('feature_context', 'N/A')}
"""
            
            # Build product-aware prompt
            product_edge_types_info = "\n".join([
                f"- {edge_type}: priority {priority}"
                for edge_type, priority in self.product_edge_priorities.items()
            ])
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at selecting the most relevant product-related edges.

Product Edge Type Priorities:
{product_edge_types_info}

Consider:
1. How well the edge relates to the user's product question
2. The edge type priority (high priority edges are typically more important)
3. Product relevance (if user mentions specific product)
4. Feature edges are important for feature-related queries
5. API/endpoint edges are important for API documentation queries
6. User action edges are important for configuration/workflow queries
7. The edge document content

Return a JSON object with:
- selected_edge_indices: List of indices (0-based) of selected edges
- reasoning: Brief explanation of why these edges were selected
- edge_priorities: List of priority scores (0-1) for each selected edge
"""),
                ("human", """Select the best product edges for this query:

User Question: {user_question}
{context_info}

Discovered Edges ({total_edges} total, {product_edges_count} product edges):
{edge_summaries}

Select the top {max_edges} edges. Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "context_info": context_info,
                "total_edges": len(discovered_edges),
                "product_edges_count": product_edges_count,
                "edge_summaries": json.dumps(edge_summaries, indent=2),
                "max_edges": max_edges
            })
            
            # Extract selected edges
            selected_indices = result.get("selected_edge_indices", [])
            priorities = result.get("edge_priorities", [])
            
            # Build priority map
            priority_map = {}
            for idx, priority in zip(selected_indices, priorities):
                if 0 <= idx < len(discovered_edges):
                    priority_map[idx] = priority
            
            # Select edges and update relevance scores
            pruned_edges = []
            for idx in selected_indices:
                if 0 <= idx < len(discovered_edges):
                    edge = discovered_edges[idx]
                    # Update relevance score with LLM priority if available
                    if idx in priority_map:
                        edge.relevance_score = priority_map[idx]
                    pruned_edges.append(edge)
            
            # Sort by relevance score (descending)
            pruned_edges.sort(key=lambda e: e.relevance_score, reverse=True)
            
            logger.info(f"Pruned {len(discovered_edges)} product edges to {len(pruned_edges)} edges")
            return pruned_edges[:max_edges]
            
        except Exception as e:
            logger.error(f"Error pruning product edges: {str(e)}", exc_info=True)
            # Fallback: apply product scoring and return top edges
            scored_edges = self._apply_domain_scoring(discovered_edges, user_question, context_breakdown)
            sorted_edges = sorted(scored_edges, key=lambda e: e.relevance_score, reverse=True)
            return sorted_edges[:max_edges]
    
    def _apply_domain_scoring(
        self,
        edges: List[ContextualEdge],
        user_question: str,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Apply product-aware scoring to edges (non-LLM fallback).
        
        Args:
            edges: List of edges to score
            user_question: User question
            context_breakdown: Optional context breakdown
            
        Returns:
            List of edges with updated relevance scores
        """
        question_lower = user_question.lower()
        
        for edge in edges:
            # Check if this is a product edge
            if edge.edge_type in self.product_edge_priorities:
                # Get edge type priority
                edge_type_priority = self.get_product_edge_type_priority(edge.edge_type)
                
                # Boost based on query type
                if "feature" in question_lower or "capability" in question_lower:
                    if edge.edge_type in ["HAS_FEATURE", "SUPPORTS", "ENABLES"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "api" in question_lower or "endpoint" in question_lower:
                    if edge.edge_type in ["HAS_ENDPOINT", "DOCUMENTED_IN"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "configure" in question_lower or "setup" in question_lower:
                    if edge.edge_type in ["REQUIRES_ACTION", "CONFIGURED_BY"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "integrate" in question_lower or "integration" in question_lower:
                    if edge.edge_type == "INTEGRATES_WITH":
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                # Apply edge type priority
                edge.relevance_score = max(edge.relevance_score, edge_type_priority * 0.2)
        
        return edges
