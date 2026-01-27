"""
MDL Edge Pruning Agent
LLM-based agent that prunes discovered edges using MDL-aware semantic understanding.
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

from app.services.contextual_graph_storage import ContextualEdge
from app.utils.mdl_prompt_generator import get_mdl_edge_type_semantics

logger = logging.getLogger(__name__)


class MDLEdgePruningAgent:
    """
    Agent that uses LLM to prune discovered edges with MDL-aware understanding.
    
    This is an AGENT (uses LLM) that:
    - Analyzes edge relevance to MDL queries
    - Understands MDL edge type semantics
    - Prioritizes edges based on MDL query type
    - Selects top N most relevant edges
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the MDL edge pruning agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
        # Load MDL edge type semantics
        self.mdl_edge_semantics = get_mdl_edge_type_semantics()
    
    def _is_mdl_edge(self, edge: ContextualEdge) -> bool:
        """Check if edge is an MDL-related edge."""
        mdl_edge_types = [
            "BELONGS_TO_TABLE",
            "HAS_MANY_TABLES",
            "REFERENCES_TABLE",
            "MANY_TO_MANY_TABLE",
            "LINKED_TO_TABLE",
            "RELATED_TO_TABLE",
            "HAS_FIELD"
        ]
        return edge.edge_type in mdl_edge_types
    
    def _is_table_entity(self, entity_type: str, entity_id: str) -> bool:
        """Check if entity is a table entity."""
        return entity_type == "entity" and entity_id.startswith("entity_")
    
    def _extract_table_info(self, entity_id: str) -> Dict[str, str]:
        """
        Extract product and table name from entity ID.
        
        Args:
            entity_id: Entity ID (format: entity_{product}_{table})
            
        Returns:
            Dictionary with product_name and table_name
        """
        if not entity_id or not entity_id.startswith("entity_"):
            return {"product_name": None, "table_name": None}
        
        parts = entity_id.replace("entity_", "").split("_", 1)
        if len(parts) >= 2:
            return {
                "product_name": parts[0],
                "table_name": "_".join(parts[1:])
            }
        return {"product_name": None, "table_name": None}
    
    async def prune_edges(
        self,
        user_question: str,
        discovered_edges: List[ContextualEdge],
        max_edges: int = 10,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Prune discovered edges using LLM with MDL-aware understanding.
        
        This is the main AGENT method that uses LLM to:
        1. Analyze edge relevance to MDL queries
        2. Understand MDL edge type semantics
        3. Prioritize edges based on query type
        4. Select top N most relevant edges
        
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
                # No pruning needed, but still apply MDL-aware scoring
                return self._apply_mdl_scoring(discovered_edges, user_question, context_breakdown)
            
            # Separate MDL edges from other edges
            mdl_edges = [e for e in discovered_edges if self._is_mdl_edge(e)]
            other_edges = [e for e in discovered_edges if not self._is_mdl_edge(e)]
            
            logger.info(f"Pruning {len(discovered_edges)} edges: {len(mdl_edges)} MDL edges, {len(other_edges)} other edges")
            
            # Prepare edge summaries with MDL context
            edge_summaries = []
            for i, edge in enumerate(discovered_edges):
                summary = {
                    "index": i,
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type,
                    "source_entity_type": edge.source_entity_type,
                    "target_entity_type": edge.target_entity_type,
                    "source_entity_id": edge.source_entity_id,
                    "target_entity_id": edge.target_entity_id,
                    "document": edge.document[:300],  # Longer for MDL context
                    "relevance_score": edge.relevance_score,
                    "is_mdl_edge": self._is_mdl_edge(edge)
                }
                
                # Add MDL-specific context
                if self._is_mdl_edge(edge):
                    edge_semantics = self.mdl_edge_semantics.get(edge.edge_type, {})
                    summary["mdl_semantics"] = {
                        "description": edge_semantics.get("description", ""),
                        "cardinality": edge_semantics.get("cardinality", ""),
                        "query_priority": edge_semantics.get("query_priority", "medium")
                    }
                    
                    # Extract table info if applicable
                    if self._is_table_entity(edge.source_entity_type, edge.source_entity_id):
                        summary["source_table_info"] = self._extract_table_info(edge.source_entity_id)
                    if self._is_table_entity(edge.target_entity_type, edge.target_entity_id):
                        summary["target_table_info"] = self._extract_table_info(edge.target_entity_id)
                
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
- Identified Entities: {', '.join(context_breakdown.get('identified_entities', []))}
"""
                
                # Add MDL detection if available
                if hasattr(context_breakdown, 'mdl_detection') or 'mdl_detection' in context_breakdown:
                    mdl_detection = context_breakdown.get('mdl_detection', {})
                    query_type = mdl_detection.get('query_type', {})
                    context_info += f"""
MDL Query Type:
- Is table query: {query_type.get('is_table_query', False)}
- Is relationship query: {query_type.get('is_relationship_query', False)}
- Is column query: {query_type.get('is_column_query', False)}
- Is category query: {query_type.get('is_category_query', False)}
- Detected products: {', '.join(mdl_detection.get('detected_products', []))}
"""
            
            # Build MDL-aware prompt
            mdl_edge_types_info = "\n".join([
                f"- {edge_type}: {semantics.get('description', '')} (priority: {semantics.get('query_priority', 'medium')})"
                for edge_type, semantics in self.mdl_edge_semantics.items()
            ])
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at selecting the most relevant knowledge graph edges for answering MDL semantic layer queries.

Given a user question and a list of discovered edges, select the {max_edges} most relevant edges that will help answer the question.

MDL Edge Type Semantics:
{mdl_edge_types_info}

Consider:
1. How well the edge relates to the user's question
2. The edge type and entity types (are they relevant to the question?)
3. For MDL edges, consider the edge type semantics and priority
4. Table relationship hierarchy (BELONGS_TO_TABLE and HAS_MANY_TABLES are high priority for relationship queries)
5. The edge document content (does it address the question?)
6. The context breakdown (compliance, action, product, intent, MDL query type)
7. Edge relevance scores (higher is generally better)
8. For table queries, prioritize table relationship edges
9. For column queries, prioritize HAS_FIELD edges
10. For compliance queries, prioritize RELEVANT_TO_CONTROL edges

Return a JSON object with:
- selected_edge_indices: List of indices (0-based) of selected edges
- reasoning: Brief explanation of why these edges were selected, especially MDL edges
- edge_priorities: List of priority scores (0-1) for each selected edge, in same order as indices
"""),
                ("human", """Select the best edges for this MDL query:

User Question: {user_question}
{context_info}

Discovered Edges ({total_edges} total, {mdl_edges_count} MDL edges):
{edge_summaries}

Select the top {max_edges} edges. Pay special attention to MDL edges and their semantics.
Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "context_info": context_info,
                "total_edges": len(discovered_edges),
                "mdl_edges_count": len(mdl_edges),
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
                    # Apply MDL edge type priority boost
                    if self._is_mdl_edge(edge):
                        edge_type_priority = self.get_mdl_edge_type_priority(edge.edge_type)
                        edge.relevance_score = max(edge.relevance_score, edge_type_priority * 0.3)  # 30% boost
                    pruned_edges.append(edge)
            
            # Sort by relevance score (descending)
            pruned_edges.sort(key=lambda e: e.relevance_score, reverse=True)
            
            logger.info(f"Pruned {len(discovered_edges)} edges to {len(pruned_edges)} edges ({len([e for e in pruned_edges if self._is_mdl_edge(e)])} MDL edges)")
            return pruned_edges[:max_edges]
            
        except Exception as e:
            logger.error(f"Error pruning MDL edges: {str(e)}", exc_info=True)
            # Fallback: apply MDL scoring and return top edges
            scored_edges = self._apply_mdl_scoring(discovered_edges, user_question, context_breakdown)
            sorted_edges = sorted(scored_edges, key=lambda e: e.relevance_score, reverse=True)
            return sorted_edges[:max_edges]
    
    def _apply_mdl_scoring(
        self,
        edges: List[ContextualEdge],
        user_question: str,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Apply MDL-aware scoring to edges (non-LLM fallback).
        
        Args:
            edges: List of edges to score
            user_question: User question
            context_breakdown: Optional context breakdown
            
        Returns:
            List of edges with updated relevance scores
        """
        question_lower = user_question.lower()
        
        for edge in edges:
            if self._is_mdl_edge(edge):
                # Get edge type priority
                edge_type_priority = self.get_mdl_edge_type_priority(edge.edge_type)
                
                # Boost based on query type
                if "relationship" in question_lower or "related" in question_lower:
                    if edge.edge_type in ["BELONGS_TO_TABLE", "HAS_MANY_TABLES", "REFERENCES_TABLE"]:
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "column" in question_lower or "field" in question_lower:
                    if edge.edge_type == "HAS_FIELD":
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                if "compliance" in question_lower or "control" in question_lower:
                    if edge.edge_type == "RELEVANT_TO_CONTROL":
                        edge.relevance_score = min(1.0, edge.relevance_score + 0.2)
                
                # Apply edge type priority
                edge.relevance_score = max(edge.relevance_score, edge_type_priority * 0.2)
        
        return edges
    
    def get_mdl_edge_type_priority(self, edge_type: str) -> float:
        """
        Get priority score for MDL edge type based on semantic importance.
        
        Args:
            edge_type: Edge type (e.g., "BELONGS_TO_TABLE", "RELEVANT_TO_CONTROL")
            
        Returns:
            Priority score (0.0-1.0)
        """
        semantics = self.mdl_edge_semantics.get(edge_type, {})
        priority_str = semantics.get("query_priority", "low")
        
        priority_map = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4
        }
        
        return priority_map.get(priority_str, 0.5)

