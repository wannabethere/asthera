"""
Domain Knowledge Edge Pruning Agent
Specialized agent for pruning domain knowledge edges.
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

from app.agents.contextual_agents.base_edge_pruning_agent import BaseEdgePruningAgent
from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class DomainKnowledgeEdgePruningAgent(BaseEdgePruningAgent):
    """
    Agent that prunes domain knowledge edges.
    
    Specializes in:
    - Concept edges (DEFINES, IS_TYPE_OF, RELATED_CONCEPT)
    - Best practice edges (RECOMMENDS, BEST_PRACTICE_FOR)
    - Pattern edges (IMPLEMENTS_PATTERN, USES_PATTERN)
    - Relationship edges (DEPENDS_ON, RELATES_TO, PART_OF)
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the domain knowledge edge pruning agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        super().__init__(llm, model_name)
        
        # Define domain knowledge edge type priorities
        self.domain_edge_priorities = {
            "DEFINES": "high",
            "IS_TYPE_OF": "high",
            "RELATED_CONCEPT": "high",
            "BEST_PRACTICE_FOR": "high",
            "RECOMMENDS": "medium",
            "IMPLEMENTS_PATTERN": "medium",
            "USES_PATTERN": "medium",
            "DEPENDS_ON": "medium",
            "RELATES_TO": "medium",
            "PART_OF": "medium",
            "RELATED_TO_IN_CONTEXT": "low",
            "MENTIONED_IN": "low"
        }
    
    def _get_domain_context(self, edge: ContextualEdge) -> Dict[str, Any]:
        """
        Get domain knowledge-specific context for an edge.
        
        Args:
            edge: Edge to get context for
            
        Returns:
            Dictionary with domain knowledge-specific context
        """
        context = {}
        
        # Check if this is a domain knowledge edge
        domain_edge_types = list(self.domain_edge_priorities.keys())
        is_domain_edge = edge.edge_type in domain_edge_types
        context["is_domain_edge"] = is_domain_edge
        
        if is_domain_edge:
            priority = self.domain_edge_priorities.get(edge.edge_type, "low")
            context["domain_priority"] = priority
            
            # Extract domain info if available
            if hasattr(edge, 'metadata') and edge.metadata:
                if "domain" in edge.metadata:
                    context["domain"] = edge.metadata["domain"]
                if "concept" in edge.metadata:
                    context["concept"] = edge.metadata["concept"]
        
        return context
    
    def get_domain_edge_type_priority(self, edge_type: str) -> float:
        """
        Get priority score for domain knowledge edge type.
        
        Args:
            edge_type: Edge type (e.g., "DEFINES")
            
        Returns:
            Priority score (0.0-1.0)
        """
        priority_str = self.domain_edge_priorities.get(edge_type, "low")
        
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
        Prune discovered domain knowledge edges using LLM.
        
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
                # No pruning needed, but still apply domain-aware scoring
                return self._apply_domain_scoring(discovered_edges, user_question, context_breakdown)
            
            # Prepare edge summaries with domain context
            edge_summaries = [
                self._create_edge_summary(edge, i, include_domain_context=True)
                for i, edge in enumerate(discovered_edges)
            ]
            
            # Count domain edges
            domain_edges_count = sum(1 for e in discovered_edges if e.edge_type in self.domain_edge_priorities)
            
            # Build context breakdown context
            context_info = ""
            if context_breakdown:
                context_info = f"""
Context Breakdown:
- Domain Context: {context_breakdown.get('metadata', {}).get('domain_context', 'N/A')}
- Concept Context: {context_breakdown.get('metadata', {}).get('concept_context', 'N/A')}
- Action Context: {context_breakdown.get('action_context', 'N/A')}
- User Intent: {context_breakdown.get('user_intent', 'N/A')}
- Domains: {', '.join(context_breakdown.get('metadata', {}).get('domains', []))}
- Concepts: {', '.join(context_breakdown.get('metadata', {}).get('concepts', []))}
"""
            
            # Build domain-aware prompt
            domain_edge_types_info = "\n".join([
                f"- {edge_type}: priority {priority}"
                for edge_type, priority in self.domain_edge_priorities.items()
            ])
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at selecting the most relevant domain knowledge edges.

Domain Knowledge Edge Type Priorities:
{domain_edge_types_info}

Consider:
1. How well the edge relates to the user's domain knowledge question
2. The edge type priority (high priority edges are typically more important)
3. Domain relevance (if user mentions specific domain like Security, Privacy, etc.)
4. Definition edges are important for concept queries
5. Best practice edges are important for guideline queries
6. Pattern edges are important for implementation queries
7. Relationship edges are important for understanding connections
8. The edge document content

Return a JSON object with:
- selected_edge_indices: List of indices (0-based) of selected edges
- reasoning: Brief explanation of why these edges were selected
- edge_priorities: List of priority scores (0-1) for each selected edge
"""),
                ("human", """Select the best domain knowledge edges for this query:

User Question: {user_question}
{context_info}

Discovered Edges ({total_edges} total, {domain_edges_count} domain knowledge edges):
{edge_summaries}

Select the top {max_edges} edges. Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "context_info": context_info,
                "total_edges": len(discovered_edges),
                "domain_edges_count": domain_edges_count,
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
            
            logger.info(f"Pruned {len(discovered_edges)} domain knowledge edges to {len(pruned_edges)} edges")
            return pruned_edges[:max_edges]
            
        except Exception as e:
            logger.error(f"Error pruning domain knowledge edges: {str(e)}", exc_info=True)
            # Fallback: apply domain scoring and return top edges
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
        Apply domain knowledge-aware scoring to edges (non-LLM fallback).
        
        Args:
            edges: List of edges to score
            user_question: User question
            context_breakdown: Optional context breakdown
            
        Returns:
            List of edges with updated relevance scores
        """
        question_lower = user_question.lower()
        
        for edge in edges:
            # Check if this is a domain knowledge edge
            if edge.edge_type in self.domain_edge_priorities:
                # Get edge type priority
                edge_type_priority = self.get_domain_edge_type_priority(edge.edge_type)
                
                # Boost based on query type
                if "what is" in question_lower or "define" in question_lower or "definition" in question_lower:
                    if edge.edge_type in ["DEFINES", "IS_TYPE_OF", "RELATED_CONCEPT"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "best practice" in question_lower or "recommended" in question_lower:
                    if edge.edge_type in ["BEST_PRACTICE_FOR", "RECOMMENDS"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "how to" in question_lower or "how does" in question_lower or "implement" in question_lower:
                    if edge.edge_type in ["IMPLEMENTS_PATTERN", "USES_PATTERN"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "relate" in question_lower or "relationship" in question_lower or "connection" in question_lower:
                    if edge.edge_type in ["DEPENDS_ON", "RELATES_TO", "PART_OF"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                # Apply edge type priority
                edge.relevance_score = max(edge.relevance_score, edge_type_priority * 0.2)
        
        return edges
