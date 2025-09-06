from app.routers.ask import router as ask_router
from app.routers.question_recommendation import router as question_recommendation_router
from app.routers.chart import router as chart_router
from app.routers.chart_adjustment import router as chart_adjustment_router
from app.routers.instructions import router as instructions_router
from app.routers.sql_helper import router as sql_helper_router
from app.routers.dashboard import router as dashboard_router
from app.routers.report import router as report_router
from app.routers.alert_router import router as alert_router

__all__ = [
    "ask_router",
    "question_recommendation_router",
    "chart_router",
    "chart_adjustment_router",
    "instructions_router",
    "sql_helper_router",
    "dashboard_router",
    "report_router",
    "alert_router"
]
