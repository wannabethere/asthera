"""
Edge Pruning Service
Uses LLM to select the best edges from discovered edges based on user question
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class EdgePruningService:
    """
    Service that prunes discovered edges using LLM to select the most relevant ones.
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
        self.json_parser = JsonOutputParser()
    
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
        try:
            if not discovered_edges:
                return []
            
            if len(discovered_edges) <= max_edges:
                # No pruning needed
                return discovered_edges
            
            # Prepare edge summaries for LLM
            edge_summaries = []
            for i, edge in enumerate(discovered_edges):
                summary = {
                    "index": i,
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type,
                    "source_entity_type": edge.source_entity_type,
                    "target_entity_type": edge.target_entity_type,
                    "document": edge.document[:200],  # Truncate for prompt
                    "relevance_score": edge.relevance_score
                }
                edge_summaries.append(summary)
            
            # Build context breakdown context
            context_info = ""
            if context_breakdown:
                context_info = f"""
Context Breakdown:
- Compliance Context: {context_breakdown.get('compliance_context', 'N/A')}
- Action Context: {context_breakdown.get('action_context', 'N/A')}
- Product Context: {context_breakdown.get('product_context', 'N/A')}
- User Intent: {context_breakdown.get('user_intent', 'N/A')}
- Frameworks: {', '.join(context_breakdown.get('frameworks', []))}
"""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at selecting the most relevant knowledge graph edges for answering user questions.

Given a user question and a list of discovered edges, select the {max_edges} most relevant edges that will help answer the question.

Consider:
1. How well the edge relates to the user's question
2. The edge type and entity types (are they relevant to the question?)
3. The edge document content (does it address the question?)
4. The context breakdown (compliance, action, product, intent)
5. Edge relevance scores (higher is generally better)

Return a JSON object with:
- selected_edge_indices: List of indices (0-based) of selected edges
- reasoning: Brief explanation of why these edges were selected
- edge_priorities: List of priority scores (0-1) for each selected edge, in same order as indices
"""),
                ("human", """Select the best edges for this question:

User Question: {user_question}
{context_info}

Discovered Edges ({total_edges} total):
{edge_summaries}

Select the top {max_edges} edges. Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "context_info": context_info,
                "total_edges": len(discovered_edges),
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
            
            # Select edges and update relevance scores with priorities
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
            
            logger.info(f"Pruned {len(discovered_edges)} edges to {len(pruned_edges)} edges")
            return pruned_edges[:max_edges]
            
        except Exception as e:
            logger.error(f"Error pruning edges: {str(e)}", exc_info=True)
            # Fallback: return top edges by relevance score
            sorted_edges = sorted(discovered_edges, key=lambda e: e.relevance_score, reverse=True)
            return sorted_edges[:max_edges]
    
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
            
            # Use LLM to score each edge
            edge_summaries = []
            for i, edge in enumerate(edges):
                summary = {
                    "index": i,
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type,
                    "document": edge.document[:200]
                }
                edge_summaries.append(summary)
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at ranking knowledge graph edges by relevance to user questions.

Given a user question and edges, assign a relevance score (0.0-1.0) to each edge.

Return a JSON object with:
- edge_scores: List of objects with "index" and "relevance_score" (0.0-1.0)
"""),
                ("human", """Rank edges by relevance to:

User Question: {user_question}

Edges:
{edge_summaries}

Return scores as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "edge_summaries": json.dumps(edge_summaries, indent=2)
            })
            
            # Update edge relevance scores
            scores = result.get("edge_scores", [])
            score_map = {s["index"]: s["relevance_score"] for s in scores}
            
            for i, edge in enumerate(edges):
                if i in score_map:
                    edge.relevance_score = score_map[i]
            
            # Sort by relevance score
            sorted_edges = sorted(edges, key=lambda e: e.relevance_score, reverse=True)
            
            return sorted_edges
            
        except Exception as e:
            logger.error(f"Error ranking edges: {str(e)}", exc_info=True)
            # Fallback: return edges sorted by existing relevance score
            return sorted(edges, key=lambda e: e.relevance_score, reverse=True)

