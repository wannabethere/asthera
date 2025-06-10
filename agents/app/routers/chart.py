from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List

from app.services.sql.models import (
    ChartRequest,
    ChartResultRequest,
    ChartResultResponse,
    StopChartRequest
)
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/chart", tags=["chart"])

def get_chart_service():
    """Get the ChartService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("chart_service")

@router.post("/generate")
async def generate_chart(request: ChartRequest) -> ChartResultResponse:
    """Generate a chart based on the provided data and configuration."""
    service = get_chart_service()
    return await service.process_request(request)

@router.post("/result")
def get_chart_result(request: ChartResultRequest) -> ChartResultResponse:
    """Get the result of a chart generation request."""
    service = get_chart_service()
    return service.get_chart_result(request)

@router.post("/stop")
def stop_chart(request: StopChartRequest):
    """Stop an ongoing chart generation process."""
    service = get_chart_service()
    service.stop_chart(request) 