"""
Compliance Edge Pruning Agent
Specialized agent for pruning compliance/risk-related edges.
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

from .base_edge_pruning_agent import BaseEdgePruningAgent
from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class ComplianceEdgePruningAgent(BaseEdgePruningAgent):
    """
    Agent that prunes compliance and risk-related edges.
    
    Specializes in:
    - Control and requirement edges (HAS_REQUIREMENT_IN_CONTEXT)
    - Evidence edges (PROVED_BY)
    - Policy edges (RELATED_TO_IN_CONTEXT)
    - Risk edges (MITIGATED_BY)
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the compliance edge pruning agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        super().__init__(llm, model_name)
        
        # Define compliance edge type priorities
        self.compliance_edge_priorities = {
            "HAS_REQUIREMENT_IN_CONTEXT": "high",
            "PROVED_BY": "high",
            "RELEVANT_TO_CONTROL": "high",
            "MITIGATED_BY": "medium",
            "RELATED_TO_IN_CONTEXT": "medium",
            "HAS_EVIDENCE": "medium",
            "APPLIES_TO": "low"
        }
    
    def _get_domain_context(self, edge: ContextualEdge) -> Dict[str, Any]:
        """
        Get compliance-specific context for an edge.
        
        Args:
            edge: Edge to get context for
            
        Returns:
            Dictionary with compliance-specific context
        """
        context = {}
        
        # Check if this is a compliance edge
        compliance_edge_types = list(self.compliance_edge_priorities.keys())
        is_compliance_edge = edge.edge_type in compliance_edge_types
        context["is_compliance_edge"] = is_compliance_edge
        
        if is_compliance_edge:
            priority = self.compliance_edge_priorities.get(edge.edge_type, "low")
            context["compliance_priority"] = priority
            
            # Extract framework info if available
            if hasattr(edge, 'metadata') and edge.metadata:
                if "framework" in edge.metadata:
                    context["framework"] = edge.metadata["framework"]
        
        return context
    
    def get_compliance_edge_type_priority(self, edge_type: str) -> float:
        """
        Get priority score for compliance edge type.
        
        Args:
            edge_type: Edge type (e.g., "HAS_REQUIREMENT_IN_CONTEXT")
            
        Returns:
            Priority score (0.0-1.0)
        """
        priority_str = self.compliance_edge_priorities.get(edge_type, "low")
        
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
        Prune discovered compliance edges using LLM.
        
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
                # No pruning needed, but still apply compliance-aware scoring
                return self._apply_domain_scoring(discovered_edges, user_question, context_breakdown)
            
            # Prepare edge summaries with compliance context
            edge_summaries = [
                self._create_edge_summary(edge, i, include_domain_context=True)
                for i, edge in enumerate(discovered_edges)
            ]
            
            # Count compliance edges
            compliance_edges_count = sum(1 for e in discovered_edges if e.edge_type in self.compliance_edge_priorities)
            
            # Build context breakdown context
            context_info = ""
            if context_breakdown:
                context_info = f"""
Context Breakdown:
- Compliance Context: {context_breakdown.get('compliance_context', 'N/A')}
- Action Context: {context_breakdown.get('action_context', 'N/A')}
- User Intent: {context_breakdown.get('user_intent', 'N/A')}
- Frameworks: {', '.join(context_breakdown.get('frameworks', []))}
"""
            
            # Build compliance-aware prompt
            compliance_edge_types_info = "\n".join([
                f"- {edge_type}: priority {priority}"
                for edge_type, priority in self.compliance_edge_priorities.items()
            ])
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at selecting the most relevant compliance and risk management edges.

Compliance Edge Type Priorities:
{compliance_edge_types_info}

Consider:
1. How well the edge relates to the user's compliance/risk question
2. The edge type priority (high priority edges are typically more important)
3. Framework relevance (if user mentions specific framework)
4. Control and requirement edges are typically high priority
5. Evidence edges are important for audit-related queries
6. The edge document content

Return a JSON object with:
- selected_edge_indices: List of indices (0-based) of selected edges
- reasoning: Brief explanation of why these edges were selected
- edge_priorities: List of priority scores (0-1) for each selected edge
"""),
                ("human", """Select the best compliance edges for this query:

User Question: {user_question}
{context_info}

Discovered Edges ({total_edges} total, {compliance_edges_count} compliance edges):
{edge_summaries}

Select the top {max_edges} edges. Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "context_info": context_info,
                "total_edges": len(discovered_edges),
                "compliance_edges_count": compliance_edges_count,
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
            
            logger.info(f"Pruned {len(discovered_edges)} compliance edges to {len(pruned_edges)} edges")
            return pruned_edges[:max_edges]
            
        except Exception as e:
            logger.error(f"Error pruning compliance edges: {str(e)}", exc_info=True)
            # Fallback: apply compliance scoring and return top edges
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
        Apply compliance-aware scoring to edges (non-LLM fallback).
        
        Args:
            edges: List of edges to score
            user_question: User question
            context_breakdown: Optional context breakdown
            
        Returns:
            List of edges with updated relevance scores
        """
        question_lower = user_question.lower()
        
        for edge in edges:
            # Check if this is a compliance edge
            if edge.edge_type in self.compliance_edge_priorities:
                # Get edge type priority
                edge_type_priority = self.get_compliance_edge_type_priority(edge.edge_type)
                
                # Boost based on query type
                if "control" in question_lower or "requirement" in question_lower:
                    if edge.edge_type in ["HAS_REQUIREMENT_IN_CONTEXT", "RELEVANT_TO_CONTROL"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "evidence" in question_lower or "proof" in question_lower:
                    if edge.edge_type in ["PROVED_BY", "HAS_EVIDENCE"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "risk" in question_lower:
                    if edge.edge_type == "MITIGATED_BY":
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                # Apply edge type priority
                edge.relevance_score = max(edge.relevance_score, edge_type_priority * 0.2)
        
        return edges
