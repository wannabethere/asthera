from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DocumentInfo(BaseModel):
    """Information about a retrieved document."""
    page_content: str
    metadata: Dict[str, Any]

class DocumentGrade(TypedDict):
    relevance_score: float
    reasoning: str

class RecommendedQuestion(TypedDict):
    text: str
    score: Optional[float]
    explanation: Optional[str]
    category: str
    relevant_functions: Optional[List[str]]
    key_matches: Optional[List[str]]


class ReportState(TypedDict):
    """State for the Report workflow."""
    report: str
    metric_questions: List[Dict[str, Any]] = Field(default_factory=list)
    insights_questions: List[Dict[str, Any]] = Field(default_factory=list)
    eda_questions: List[Dict[str, Any]] = Field(default_factory=list)
    selected_insight: List[Dict[str, Any]] = Field(default_factory=list)

class InsightManagerState(TypedDict):
    """State for the Insight workflow."""
    question: str
    goal: str
    context: str
    dataset_path: str
    sample: str
    schema: str
    top_values: str
    business_question: str = Field(default="")
    description: str = Field(default="")
    actor_type: str = Field(default="data_scientist")
    domain: str = Field(default="General")
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    graded_documents: List[Dict[str, Any]] = Field(default_factory=list)
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    selected_insight: List[Dict[str, Any]] = Field(default_factory=list)

class VisualizationConfig(TypedDict):
    """Configuration for the Visualization workflow."""
    charting_package_library: str
    destination_name: str
    model_name: str
    model_version: str
    


class VisualizationState(TypedDict):
    """State for the Visualization workflow."""
    question: str
    goal: str
    context: str
    dataset_path: str
    sample: str
    config: Optional[VisualizationConfig] = None