from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional

from app.services.sql.models import (
    ChartAdjustmentRequest,
    ChartAdjustmentResultRequest,
    ChartAdjustmentResultResponse,
    StopChartAdjustmentRequest
)
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/chart-adjustment", tags=["chart-adjustment"])

def get_chart_adjustment_service():
    """Get the ChartAdjustmentService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("chart_adjustment_service")

@router.post("/adjust")
async def adjust_chart(request: ChartAdjustmentRequest) -> ChartAdjustmentResultResponse:
    """Adjust an existing chart based on the provided adjustment options."""
    service = get_chart_adjustment_service()
    return await service.process_request(request)

@router.post("/result")
def get_chart_adjustment_result(request: ChartAdjustmentResultRequest) -> ChartAdjustmentResultResponse:
    """Get the result of a chart adjustment request."""
    service = get_chart_adjustment_service()
    return service.get_chart_adjustment_result(request)

@router.post("/stop")
def stop_chart_adjustment(request: StopChartAdjustmentRequest):
    """Stop an ongoing chart adjustment process."""
    service = get_chart_adjustment_service()
    service.stop_chart_adjustment(request) 