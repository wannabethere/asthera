from datetime import datetime
from typing import Annotated, Any, Dict, List, Tuple, TypedDict, Optional
from pydantic import BaseModel, Field

class ValidationResult(BaseModel):
    """Model for validation results of RAG responses."""
    is_valid: bool = Field(
        description="Whether the response is valid and accurate"
    )
    confidence_score: float = Field(
        description="Confidence score between 0 and 1",
        ge=0.0,
        le=1.0
    )
    feedback: str = Field(
        description="Feedback about what might be wrong or needs improvement"
    )

class QueryMetrics(BaseModel):
    """Model for tracking query performance metrics."""
    question: str = Field(description="The original question asked")
    attempts: int = Field(description="Number of attempts made to answer")
    final_confidence: float = Field(
        description="Final confidence score achieved",
        ge=0.0,
        le=1.0
    )
    total_time: float = Field(description="Total processing time in seconds")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the query was processed"
    )

class RAGResponse(BaseModel):
    """Model for the final RAG response including metadata."""
    question: str = Field(description="Original question asked")
    response: str = Field(description="Final generated response")
    validation: ValidationResult = Field(description="Validation results")
    metrics: QueryMetrics = Field(description="Query performance metrics")
    context_used: List[str] = Field(
        description="Relevant context chunks used for the response"
    )


class RetrievalState(TypedDict):
    """State for document retrieval and grading."""
    question: str
    retrieved_documents: List[Dict[str, Any]]
    graded_documents: List[Dict[str, float]]
    filtered_documents: List[Dict[str, Any]]
    current_answer: Optional[str]
    reflection: Optional[str]
    final_answer: Optional[str]
    should_retry: bool
    attempts: int

class DocumentInfo(BaseModel):
    """Information about a retrieved document."""
    content: str
    metadata: Dict[str, Any]


class DocumentGrade(BaseModel):
    """Model for document relevance grading."""
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(...)

class CRAGConfig(BaseModel):
    """Configuration for CRAG."""
    max_documents: int = Field(default=4)
    relevance_threshold: float = Field(default=0.7)
    max_attempts: int = Field(default=2)
    model_name: str = Field(default="gpt-4-turbo-preview")
    temperature: float = Field(default=0.0)

class CRAGState(BaseModel):
    """State for the CRAG workflow."""
    question: str
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    graded_documents: List[Dict[str, Any]] = Field(default_factory=list)
    filtered_documents: List[Dict[str, Any]] = Field(default_factory=list)
    current_answer: str = ""
    reflection: str = ""
    final_answer: str = ""
    should_retry: bool = True
    attempts: int = 0

