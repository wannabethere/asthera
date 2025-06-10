from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional

from app.services.sql.models import Configuration
from app.services.sql.question_recommendation import QuestionRecommendation
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/question-recommendation", tags=["question-recommendation"])

def get_question_recommendation_service():
    """Get the QuestionRecommendation service instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("question_recommendation")

@router.post("/recommend")
async def recommend_questions(
    event_id: str,
    mdl: str,
    user_question: str,
    project_id: str,
    configuration: Optional[Configuration] = None,
    previous_questions: List[str] = [],
    max_questions: int = 5,
    max_categories: int = 3,
    regenerate: bool = False
):
    """Generate question recommendations based on the user's question and context."""
    service = get_question_recommendation_service()
    
    request = QuestionRecommendation.Request(
        event_id=event_id,
        mdl=mdl,
        user_question=user_question,
        project_id=project_id,
        configuration=configuration,
        previous_questions=previous_questions,
        max_questions=max_questions,
        max_categories=max_categories,
        regenerate=regenerate
    )
    
    return await service.recommend(request) 