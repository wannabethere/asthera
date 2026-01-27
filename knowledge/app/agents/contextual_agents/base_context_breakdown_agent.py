"""
Base Context Breakdown Agent
Abstract base class for breaking down user queries into context components.
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
import json

logger = logging.getLogger(__name__)


@dataclass
class ContextBreakdown:
    """
    Generic context breakdown structure that works for both MDL and compliance queries.
    
    Attributes:
        user_question: Original user question
        query_type: Type of query (mdl, compliance, policy, risk, product, etc.)
        identified_entities: List of entity names relevant to the query
        entity_types: List of entity types (control, requirement, evidence, entity, field, schema, etc.)
        entity_sub_types: List of sub-types for identified entities
        search_questions: List of search question objects for entity retrieval
        edge_types: List of edge types relevant to the query
        query_keywords: Key terms for vector search
        
        # Context-specific fields
        compliance_context: Compliance framework/context (for compliance queries)
        action_context: Action user is trying to perform
        product_context: Product context (Snyk, Okta, etc.)
        user_intent: What user is trying to accomplish
        frameworks: List of framework names mentioned
        
        # Evidence gathering planning (for deep research integration)
        evidence_gathering_required: Whether evidence gathering is needed
        evidence_types_needed: List of evidence types needed
        data_retrieval_plan: List of data retrieval plan objects
        metrics_kpis_needed: List of metric/KPI objects needed
        
        # Additional metadata
        metadata: Additional metadata specific to query type
    """
    user_question: str
    query_type: str = "unknown"
    identified_entities: List[str] = field(default_factory=list)
    entity_types: List[str] = field(default_factory=list)
    entity_sub_types: List[str] = field(default_factory=list)
    search_questions: List[Dict[str, Any]] = field(default_factory=list)
    edge_types: List[str] = field(default_factory=list)
    query_keywords: List[str] = field(default_factory=list)
    
    # Context-specific fields
    compliance_context: Optional[str] = None
    action_context: Optional[str] = None
    product_context: Optional[str] = None
    user_intent: Optional[str] = None
    frameworks: List[str] = field(default_factory=list)
    
    # Evidence gathering planning
    evidence_gathering_required: bool = False
    evidence_types_needed: List[str] = field(default_factory=list)
    data_retrieval_plan: List[Dict[str, Any]] = field(default_factory=list)
    metrics_kpis_needed: List[Dict[str, Any]] = field(default_factory=list)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_search_query(self) -> str:
        """Convert breakdown to a search query for edge discovery"""
        parts = []
        if self.compliance_context:
            parts.append(self.compliance_context)
        if self.action_context:
            parts.append(self.action_context)
        if self.product_context:
            parts.append(self.product_context)
        if self.user_intent:
            parts.append(self.user_intent)
        parts.extend(self.query_keywords)
        return " ".join(parts)
    
    def to_metadata_filters(self) -> Dict[str, Any]:
        """Convert breakdown to metadata filters for edge search"""
        filters = {}
        if self.frameworks:
            filters["framework"] = self.frameworks[0]
        if self.entity_types:
            filters["source_entity_type"] = self.entity_types[0]
        if self.edge_types:
            filters["edge_type"] = self.edge_types[0]
        if self.product_context:
            filters["product_name"] = self.product_context
        return filters
    
    def get_entity_queries(self, prompts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate entity queries based on identified entities and vector_store_prompts.json.
        
        Args:
            prompts_data: Loaded vector_store_prompts.json data
            
        Returns:
            List of entity query dictionaries with store_name, metadata_filters, and query
        """
        entity_queries = []
        entities = prompts_data.get("entities", {})
        
        for entity_name in self.identified_entities:
            if entity_name in entities:
                entity_info = entities[entity_name]
                store_name = entity_info.get("store_name", "")
                
                # Get sub-type if specified
                sub_type = None
                for sub_type_name in self.entity_sub_types:
                    if sub_type_name in entity_info.get("sub_types", {}):
                        sub_type = entity_info["sub_types"][sub_type_name]
                        break
                
                # Build metadata filters
                metadata_filters = {}
                if sub_type:
                    metadata_filters.update(sub_type.get("metadata_filter", {}))
                else:
                    # Use default metadata filters from entity
                    metadata_filters_info = entity_info.get("metadata_filters", {})
                    # Apply framework filter if available
                    if self.frameworks:
                        if "framework" in metadata_filters_info:
                            metadata_filters["framework"] = self.frameworks[0]
                
                # Build query from keywords and context
                query_parts = []
                if self.compliance_context:
                    query_parts.append(self.compliance_context)
                if self.action_context:
                    query_parts.append(self.action_context)
                query_parts.extend(self.query_keywords)
                query = " ".join(query_parts) if query_parts else self.user_question
                
                entity_queries.append({
                    "entity_name": entity_name,
                    "store_name": store_name,
                    "metadata_filters": metadata_filters,
                    "query": query,
                    "sub_type": sub_type.get("description", "") if sub_type else None
                })
        
        return entity_queries


class BaseContextBreakdownAgent(ABC):
    """
    Abstract base class for context breakdown agents.
    
    Provides common functionality for:
    - Loading prompts
    - LLM interaction
    - Query type detection
    
    Subclasses implement:
    - breakdown_question(): Main method to break down user question
    - _detect_query_type(): Detect specific query type
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the base context breakdown agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
        # Load prompts file
        if prompts_file is None:
            base_path = Path(__file__).parent.parent.parent
            prompts_file = base_path / "indexing" / "vector_store_prompts.json"
        
        self.prompts_file = Path(prompts_file)
        self.prompts_data = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load vector_store_prompts.json"""
        try:
            if self.prompts_file.exists():
                with open(self.prompts_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Prompts file not found: {self.prompts_file}")
                return {}
        except Exception as e:
            logger.error(f"Error loading prompts file: {str(e)}")
            return {}
    
    def _get_planning_instructions(self) -> str:
        """Get planning instructions from prompts"""
        planning = self.prompts_data.get("planning_instructions", {})
        steps = planning.get("steps", [])
        entity_identification = planning.get("entity_identification", "")
        parallel_fetching = planning.get("parallel_fetching", "")
        result_combination = planning.get("result_combination", "")
        
        return f"""
Planning Instructions:
{chr(10).join(steps)}

Entity Identification: {entity_identification}
Parallel Fetching: {parallel_fetching}
Result Combination: {result_combination}
"""
    
    def _get_question_decomposition(self) -> str:
        """Get question decomposition strategy from prompts"""
        decomposition = self.prompts_data.get("instructions", {}).get("question_decomposition", {})
        return decomposition.get("content", "")
    
    def _get_entity_definitions(self) -> Dict[str, Any]:
        """Get entity definitions from prompts"""
        return self.prompts_data.get("entities", {})
    
    @abstractmethod
    async def breakdown_question(
        self,
        user_question: str,
        **kwargs
    ) -> ContextBreakdown:
        """
        Break down a user question into context components.
        
        Args:
            user_question: User's question or query
            **kwargs: Additional context-specific parameters
            
        Returns:
            ContextBreakdown object with extracted context information
        """
        pass
    
    @abstractmethod
    async def _detect_query_type(self, user_question: str) -> Dict[str, Any]:
        """
        Detect the type of query from user question.
        
        Args:
            user_question: User's question
            
        Returns:
            Dictionary with query type information
        """
        pass
