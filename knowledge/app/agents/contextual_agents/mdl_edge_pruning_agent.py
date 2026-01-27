"""
MDL Edge Pruning Agent
Specialized agent for pruning MDL (Metadata Definition Language) semantic layer edges.

Handles MDL edge types:
- Schema/table/column hierarchy (BELONGS_TO_TABLE, HAS_MANY_TABLES, HAS_COLUMN)
- Table relationships (RELATES_TO_TABLE, DERIVED_FROM)
- Category groupings (CATEGORY_CONTAINS_TABLE, TABLE_IN_CATEGORY)
- Feature relationships (TABLE_HAS_FEATURE, COLUMN_SUPPORTS_FEATURE)
- Compliance mappings (FEATURE_SUPPORTS_CONTROL, TABLE_PROVIDES_EVIDENCE)
- Metrics and KPIs (METRIC_FROM_TABLE, KPI_FROM_METRIC)
- Examples and patterns (EXAMPLE_USES_TABLE, QUESTION_ANSWERED_BY_TABLE)
- Product instructions (INSTRUCTION_APPLIES_TO_PRODUCT, INSTRUCTION_APPLIES_TO_TABLE)
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

from .base_edge_pruning_agent import BaseEdgePruningAgent
from app.services.contextual_graph_storage import ContextualEdge
from app.utils.mdl_edge_types import (
    get_mdl_edge_type_semantics,
    get_edge_type_priority,
    MDLEdgeType,
    get_mdl_categories
)

logger = logging.getLogger(__name__)


class MDLEdgePruningAgent(BaseEdgePruningAgent):
    """
    Agent that prunes MDL semantic layer edges.
    
    Specializes in:
    - Schema and table structure edges
    - Relationship edges between tables
    - Category and classification edges
    - Feature and capability edges
    - Metric and KPI edges
    - Example and instruction edges
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
        super().__init__(llm, model_name)
        
        # Load MDL edge type semantics
        self.mdl_edge_semantics = get_mdl_edge_type_semantics()
        
        # Define MDL edge type priority groups
        self.mdl_edge_priority_groups = {
            # Critical structure edges
            "critical": [
                MDLEdgeType.BELONGS_TO_TABLE.value,
                MDLEdgeType.HAS_COLUMN.value,
                MDLEdgeType.QUESTION_ANSWERED_BY_TABLE.value,
                MDLEdgeType.FEATURE_SUPPORTS_CONTROL.value
            ],
            # High priority edges
            "high": [
                MDLEdgeType.HAS_MANY_TABLES.value,
                MDLEdgeType.RELATES_TO_TABLE.value,
                MDLEdgeType.TABLE_HAS_FEATURE.value,
                MDLEdgeType.TABLE_PROVIDES_EVIDENCE.value,
                MDLEdgeType.EXAMPLE_USES_TABLE.value,
                MDLEdgeType.QUESTION_ANSWERED_BY_COLUMN.value
            ],
            # Medium priority edges
            "medium": [
                MDLEdgeType.CATEGORY_CONTAINS_TABLE.value,
                MDLEdgeType.TABLE_IN_CATEGORY.value,
                MDLEdgeType.METRIC_FROM_TABLE.value,
                MDLEdgeType.COLUMN_PROVIDES_EVIDENCE.value,
                MDLEdgeType.INSTRUCTION_APPLIES_TO_TABLE.value,
                MDLEdgeType.PATTERN_USES_TABLE.value
            ],
            # Lower priority edges
            "low": [
                MDLEdgeType.DERIVED_FROM.value,
                MDLEdgeType.COLUMN_SUPPORTS_FEATURE.value,
                MDLEdgeType.METRIC_FROM_COLUMN.value,
                MDLEdgeType.EXAMPLE_USES_COLUMN.value,
                MDLEdgeType.INSTRUCTION_APPLIES_TO_CATEGORY.value,
                MDLEdgeType.PRODUCT_HAS_CATEGORY.value,
                MDLEdgeType.KPI_FROM_METRIC.value,
                MDLEdgeType.FEATURE_DEPENDS_ON_FEATURE.value,
                MDLEdgeType.INSTRUCTION_APPLIES_TO_PRODUCT.value,
                MDLEdgeType.PATTERN_USES_RELATIONSHIP.value
            ]
        }
        
        # Reverse mapping for quick lookup
        self.edge_type_to_priority = {}
        for priority, edge_types in self.mdl_edge_priority_groups.items():
            for edge_type in edge_types:
                self.edge_type_to_priority[edge_type] = priority
    
    def _get_domain_context(self, edge: ContextualEdge) -> Dict[str, Any]:
        """
        Get MDL-specific context for an edge.
        
        Args:
            edge: Edge to get context for
            
        Returns:
            Dictionary with MDL-specific context
        """
        context = {}
        
        # Check if this is an MDL edge
        is_mdl_edge = edge.edge_type in self.mdl_edge_semantics
        context["is_mdl_edge"] = is_mdl_edge
        
        if is_mdl_edge:
            # Get priority group
            priority_group = self.edge_type_to_priority.get(edge.edge_type, "low")
            context["mdl_priority_group"] = priority_group
            
            # Get semantic info
            semantics = self.mdl_edge_semantics.get(edge.edge_type, {})
            context["edge_description"] = semantics.get("description", "")
            context["edge_priority_score"] = semantics.get("priority", 0.5)
            
            # Extract product/category info if available
            if hasattr(edge, 'metadata') and edge.metadata:
                if "product_name" in edge.metadata:
                    context["product"] = edge.metadata["product_name"]
                if "category_name" in edge.metadata:
                    context["category"] = edge.metadata["category_name"]
                if "table_name" in edge.metadata:
                    context["table"] = edge.metadata["table_name"]
                if "column_name" in edge.metadata:
                    context["column"] = edge.metadata["column_name"]
        
        return context
    
    def get_mdl_edge_type_priority_score(self, edge_type: str) -> float:
        """
        Get priority score for MDL edge type.
        
        Args:
            edge_type: Edge type (e.g., "BELONGS_TO_TABLE")
            
        Returns:
            Priority score (0.0-1.0)
        """
        priority_group = self.edge_type_to_priority.get(edge_type, "low")
        
        priority_map = {
            "critical": 1.0,
            "high": 0.85,
            "medium": 0.7,
            "low": 0.5
        }
        
        return priority_map.get(priority_group, 0.5)
    
    async def prune_edges(
        self,
        user_question: str,
        discovered_edges: List[ContextualEdge],
        max_edges: int = 10,
        context_breakdown: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Prune discovered MDL edges using LLM.
        
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
                return self._apply_domain_scoring(discovered_edges, user_question, context_breakdown)
            
            # Prepare edge summaries with MDL context
            edge_summaries = [
                self._create_edge_summary(edge, i, include_domain_context=True)
                for i, edge in enumerate(discovered_edges)
            ]
            
            # Count edges by priority group
            edge_counts_by_priority = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            }
            for edge in discovered_edges:
                priority_group = self.edge_type_to_priority.get(edge.edge_type, "low")
                edge_counts_by_priority[priority_group] += 1
            
            # Build context breakdown context
            context_info = ""
            if context_breakdown:
                # Extract relevant info from context breakdown
                query_type = context_breakdown.get('query_type', 'mdl')
                identified_entities = context_breakdown.get('identified_entities', [])
                product_context = context_breakdown.get('product_context', 'N/A')
                
                context_info = f"""
Context Breakdown:
- Query Type: {query_type}
- Product Context: {product_context}
- Identified Entities: {', '.join(identified_entities) if identified_entities else 'N/A'}
"""
                
                # Add MDL detection if available
                mdl_detection = context_breakdown.get('metadata', {}).get('mdl_detection', {})
                if mdl_detection:
                    query_type_flags = mdl_detection.get('query_type', {})
                    context_info += f"""
MDL Query Detection:
- Is table query: {query_type_flags.get('is_table_query', False)}
- Is relationship query: {query_type_flags.get('is_relationship_query', False)}
- Is column query: {query_type_flags.get('is_column_query', False)}
- Is category query: {query_type_flags.get('is_category_query', False)}
- Potential tables: {', '.join(mdl_detection.get('potential_tables', [])) or 'None'}
- Potential categories: {', '.join(mdl_detection.get('potential_categories', [])) or 'None'}
"""
            
            # Build MDL-aware prompt
            mdl_categories = get_mdl_categories()
            mdl_categories_text = ", ".join(mdl_categories)
            
            edge_priority_info = "\n".join([
                f"- {priority.upper()} priority: {count} edges"
                for priority, count in edge_counts_by_priority.items()
                if count > 0
            ])
            
            # Build edge type semantics summary
            edge_types_in_results = set(edge.edge_type for edge in discovered_edges)
            edge_type_semantics_text = "\n".join([
                f"- {edge_type}: {self.mdl_edge_semantics[edge_type]['description']} "
                f"(priority: {self.mdl_edge_semantics[edge_type]['priority']:.2f})"
                for edge_type in edge_types_in_results
                if edge_type in self.mdl_edge_semantics
            ])
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at selecting the most relevant MDL (Metadata Definition Language) semantic layer edges.

MDL Edge Types and Priorities:
{edge_type_semantics_text}

MDL Categories: {mdl_categories_text}

Priority Guidelines:
1. CRITICAL edges (1.0): Essential structure and question-answering edges
   - BELONGS_TO_TABLE, HAS_COLUMN: Core schema structure
   - QUESTION_ANSWERED_BY_TABLE: Direct question-to-table mappings
   - FEATURE_SUPPORTS_CONTROL: Critical compliance mappings

2. HIGH priority edges (0.85): Important relationships and features
   - RELATES_TO_TABLE: Table joins and relationships
   - TABLE_HAS_FEATURE: Feature capabilities
   - EXAMPLE_USES_TABLE: Query examples
   - TABLE_PROVIDES_EVIDENCE: Compliance evidence

3. MEDIUM priority edges (0.7): Supporting information
   - CATEGORY_CONTAINS_TABLE: Category groupings
   - METRIC_FROM_TABLE: Metrics and KPIs
   - INSTRUCTION_APPLIES_TO_TABLE: Usage instructions

4. LOW priority edges (0.5): Supplementary details
   - DERIVED_FROM: Column derivations
   - COLUMN-level edges: Granular column information
   - Product-level edges: General product info

Selection Strategy:
1. Prioritize edges that DIRECTLY answer the user's question
2. For table queries: Favor BELONGS_TO_TABLE, HAS_COLUMN, TABLE_IN_CATEGORY
3. For relationship queries: Favor RELATES_TO_TABLE, DERIVED_FROM
4. For example/how-to queries: Favor EXAMPLE_USES_TABLE, INSTRUCTION_APPLIES_TO_TABLE
5. For compliance queries: Favor FEATURE_SUPPORTS_CONTROL, TABLE_PROVIDES_EVIDENCE
6. For metric queries: Favor METRIC_FROM_TABLE, KPI_FROM_METRIC
7. For natural questions: Favor QUESTION_ANSWERED_BY_TABLE
8. Consider product and category context from the question
9. Balance edge types - include diverse edge types when relevant
10. Include high-priority edges even if slightly less relevant than low-priority edges

Return a JSON object with:
- selected_edge_indices: List of indices (0-based) of selected edges
- reasoning: Brief explanation of why these edges were selected
- edge_priorities: List of priority scores (0-1) for each selected edge
"""),
                ("human", """Select the best MDL edges for this query:

User Question: {user_question}
{context_info}

Edge Distribution:
{edge_priority_info}

Discovered Edges ({total_edges} total):
{edge_summaries}

Select the top {max_edges} edges that best answer the question. Return as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "context_info": context_info,
                "edge_priority_info": edge_priority_info,
                "total_edges": len(discovered_edges),
                "edge_summaries": json.dumps(edge_summaries, indent=2),
                "max_edges": max_edges
            })
            
            # Extract selected edges
            selected_indices = result.get("selected_edge_indices", [])
            priorities = result.get("edge_priorities", [])
            reasoning = result.get("reasoning", "")
            
            logger.info(f"MDL edge pruning reasoning: {reasoning}")
            
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
            
            logger.info(
                f"Pruned {len(discovered_edges)} MDL edges to {len(pruned_edges)} edges. "
                f"Edge type distribution: {dict((e.edge_type, 1) for e in pruned_edges)}"
            )
            return pruned_edges[:max_edges]
            
        except Exception as e:
            logger.error(f"Error pruning MDL edges: {str(e)}", exc_info=True)
            # Fallback: apply MDL scoring and return top edges
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
        Apply MDL-aware scoring to edges (non-LLM fallback).
        
        Args:
            edges: List of edges to score
            user_question: User question
            context_breakdown: Optional context breakdown
            
        Returns:
            List of edges with updated relevance scores
        """
        question_lower = user_question.lower()
        
        # Extract query type hints from question
        is_table_query = any(kw in question_lower for kw in ["table", "tables", "schema", "model"])
        is_relationship_query = any(kw in question_lower for kw in ["related", "relationship", "join", "link"])
        is_column_query = any(kw in question_lower for kw in ["column", "field", "attribute"])
        is_category_query = any(kw in question_lower for kw in ["category", "group", "type"])
        is_example_query = any(kw in question_lower for kw in ["example", "how to", "how do i", "sample"])
        is_compliance_query = any(kw in question_lower for kw in ["compliance", "control", "evidence"])
        is_metric_query = any(kw in question_lower for kw in ["metric", "kpi", "measure"])
        
        for edge in edges:
            # Base score from edge type priority
            edge_type_priority = self.get_mdl_edge_type_priority_score(edge.edge_type)
            base_score = edge.relevance_score if edge.relevance_score > 0 else edge_type_priority
            
            # Apply query-type specific boosts
            boost = 0.0
            
            # Table query boosts
            if is_table_query:
                if edge.edge_type in [
                    MDLEdgeType.BELONGS_TO_TABLE.value,
                    MDLEdgeType.HAS_COLUMN.value,
                    MDLEdgeType.HAS_MANY_TABLES.value,
                    MDLEdgeType.QUESTION_ANSWERED_BY_TABLE.value
                ]:
                    boost += 0.2
            
            # Relationship query boosts
            if is_relationship_query:
                if edge.edge_type in [
                    MDLEdgeType.RELATES_TO_TABLE.value,
                    MDLEdgeType.DERIVED_FROM.value
                ]:
                    boost += 0.25
            
            # Column query boosts
            if is_column_query:
                if edge.edge_type in [
                    MDLEdgeType.BELONGS_TO_TABLE.value,
                    MDLEdgeType.HAS_COLUMN.value,
                    MDLEdgeType.QUESTION_ANSWERED_BY_COLUMN.value
                ]:
                    boost += 0.2
            
            # Category query boosts
            if is_category_query:
                if edge.edge_type in [
                    MDLEdgeType.CATEGORY_CONTAINS_TABLE.value,
                    MDLEdgeType.TABLE_IN_CATEGORY.value,
                    MDLEdgeType.PRODUCT_HAS_CATEGORY.value
                ]:
                    boost += 0.2
            
            # Example query boosts
            if is_example_query:
                if edge.edge_type in [
                    MDLEdgeType.EXAMPLE_USES_TABLE.value,
                    MDLEdgeType.INSTRUCTION_APPLIES_TO_TABLE.value,
                    MDLEdgeType.PATTERN_USES_TABLE.value
                ]:
                    boost += 0.25
            
            # Compliance query boosts
            if is_compliance_query:
                if edge.edge_type in [
                    MDLEdgeType.FEATURE_SUPPORTS_CONTROL.value,
                    MDLEdgeType.TABLE_PROVIDES_EVIDENCE.value,
                    MDLEdgeType.COLUMN_PROVIDES_EVIDENCE.value
                ]:
                    boost += 0.25
            
            # Metric query boosts
            if is_metric_query:
                if edge.edge_type in [
                    MDLEdgeType.METRIC_FROM_TABLE.value,
                    MDLEdgeType.METRIC_FROM_COLUMN.value,
                    MDLEdgeType.KPI_FROM_METRIC.value
                ]:
                    boost += 0.2
            
            # Apply boost
            edge.relevance_score = min(1.0, base_score + boost)
        
        return edges
