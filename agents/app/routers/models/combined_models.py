from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.services.sql.models import AskResult, AskError, QualityScoring

class CombinedAskRequest(BaseModel):
    """Request model for combined ask and question recommendation"""
    query_id: str
    query: str
    project_id: str
    histories: List[Dict] = []
    configurations: Optional[Configuration] = None
    enable_scoring: bool = True
    previous_questions: List[str] = []
    max_questions: int = 5
    max_categories: int = 3
    regenerate: bool = False

class QuestionRecommendation(BaseModel):
    """Model for question recommendation data"""
    question: str
    category: str
    sql: Optional[str] = None

class QuestionCategory(BaseModel):
    """Model for question category with its questions"""
    name: str
    questions: List[QuestionRecommendation]

class CombinedAskResponse(BaseModel):
    """Response model for combined ask and question recommendation"""
    status: str
    type: str = "TEXT_TO_SQL"
    response: Optional[List[AskResult]] = None
    error: Optional[AskError] = None
    retrieved_tables: Optional[List[str]] = None
    sql_generation_reasoning: Optional[str] = None
    is_followup: bool = False
    quality_scoring: Optional[QualityScoring] = None
    invalid_sql: Optional[str] = None
    
    # Question recommendation fields
    questions: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    categories: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None 