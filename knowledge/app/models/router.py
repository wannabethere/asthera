"""
Router Request/Response Models
Models for API router endpoints (from routers/context_breakdown.py, etc.)
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ContextBreakdownRequest(BaseModel):
    """Request for context breakdown"""
    question: str = Field(..., description="User question to analyze")
    domain: Optional[str] = Field(None, description="Domain hint: 'mdl', 'compliance', or 'auto' (default)")
    product_name: Optional[str] = Field(None, description="Product name (for MDL queries)")
    frameworks: Optional[List[str]] = Field(None, description="Frameworks (for compliance queries)")
    available_products: Optional[List[str]] = Field(None, description="Available products")
    available_actors: Optional[List[str]] = Field(None, description="Available actor types")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    

class SearchQuestion(BaseModel):
    """Individual search question"""
    entity: str
    question: str
    metadata_filters: Dict[str, Any] = Field(default_factory=dict)
    response_type: Optional[str] = None


class ContextBreakdownResponse(BaseModel):
    """Response from context breakdown"""
    session_id: str
    query_type: str
    domains_involved: List[str]
    product_context: Optional[str] = None
    compliance_context: Optional[str] = None
    identified_entities: List[str] = Field(default_factory=list)
    entity_types: List[str] = Field(default_factory=list)
    edge_types: List[str] = Field(default_factory=list)
    search_questions: List[SearchQuestion] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    evidence_gathering_required: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextBreakdownSummary(BaseModel):
    """Summary response"""
    session_id: str
    query_type: str
    domains_involved: List[str]
    total_entities: int
    total_search_questions: int
    collections_to_query: List[str]
    summary: str
