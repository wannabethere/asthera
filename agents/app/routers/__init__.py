from app.routers.ask import router as ask_router
from app.routers.question_recommendation import router as question_recommendation_router
from app.routers.chart import router as chart_router
from app.routers.chart_adjustment import router as chart_adjustment_router
from app.routers.instructions import router as instructions_router

__all__ = [
    "ask_router",
    "question_recommendation_router",
    "chart_router",
    "chart_adjustment_router",
    "instructions_router"
]
