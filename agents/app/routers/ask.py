from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.services.sql.models import (
    AskRequest,
    StopAskRequest,
    AskResultRequest,
    AskResultResponse,
    AskFeedbackRequest,
    StopAskFeedbackRequest,
    AskFeedbackResultRequest,
    AskFeedbackResultResponse,
)
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/ask", tags=["ask"])

def get_ask_service():
    """Get the AskService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("ask_service")

@router.post("/query")
async def ask_query(request: AskRequest) -> AskResultResponse:
    """Process an ask query request."""
    service = get_ask_service()
    return await service.process_request(request)

@router.post("/stop")
def stop_ask(request: StopAskRequest):
    """Stop an ongoing ask query."""
    service = get_ask_service()
    service.stop_ask(request)

@router.post("/result")
def get_ask_result(request: AskResultRequest) -> AskResultResponse:
    """Get the result of an ask query."""
    service = get_ask_service()
    return service.get_ask_result(request)

@router.get("/stream/{query_id}")
async def get_ask_streaming_result(query_id: str):
    """Get streaming results for an ask query."""
    service = get_ask_service()
    return await service.get_ask_streaming_result(query_id)

@router.post("/feedback")
async def ask_feedback(request: AskFeedbackRequest):
    """Process feedback for an ask query."""
    service = get_ask_service()
    return await service.ask_feedback(request)

@router.post("/feedback/stop")
def stop_ask_feedback(request: StopAskFeedbackRequest):
    """Stop an ongoing ask feedback process."""
    service = get_ask_service()
    service.stop_ask_feedback(request)

@router.post("/feedback/result")
def get_ask_feedback_result(request: AskFeedbackResultRequest) -> AskFeedbackResultResponse:
    """Get the result of an ask feedback process."""
    service = get_ask_service()
    return service.get_ask_feedback_result(request) 