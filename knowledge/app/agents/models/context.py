"""
Context Breakdown Models
Models for context breakdown agents (from agents/contextual_agents/base_context_breakdown_agent.py)
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


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
        if not parts:
            return self.user_question
        return " ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "user_question": self.user_question,
            "query_type": self.query_type,
            "identified_entities": self.identified_entities,
            "entity_types": self.entity_types,
            "entity_sub_types": self.entity_sub_types,
            "search_questions": self.search_questions,
            "edge_types": self.edge_types,
            "query_keywords": self.query_keywords,
            "compliance_context": self.compliance_context,
            "action_context": self.action_context,
            "product_context": self.product_context,
            "user_intent": self.user_intent,
            "frameworks": self.frameworks,
            "evidence_gathering_required": self.evidence_gathering_required,
            "evidence_types_needed": self.evidence_types_needed,
            "data_retrieval_plan": self.data_retrieval_plan,
            "metrics_kpis_needed": self.metrics_kpis_needed,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextBreakdown":
        """Create from dictionary"""
        return cls(**data)
