"""
Preview — Chart Adjust
======================

POST /preview/charts/adjust

Passthrough router for adjusting the chart type / axes of a preview card.

• FAKE_PREVIEW_MODE=True  → proxy to ComplianceSkill /workflow/preview/chart_adjust
  (uses dummy data; no warehouse required)
• FAKE_PREVIEW_MODE=False → call chart_adjustment_service directly
  (real ChartAdjustmentRequest pipeline)

Request mirrors ChartAdjustmentRequest so callers use the same payload
regardless of mode.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview/charts", tags=["preview-charts"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PreviewAdjustmentOption(BaseModel):
    chart_type: str
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    x_offset: Optional[str] = None
    color: Optional[str] = None
    theta: Optional[str] = None


class PreviewChartAdjustRequest(BaseModel):
    """
    Mirrors ChartAdjustmentRequest.
    chart_schema   — current vega-lite spec from the preview card.
    result_data    — {columns, rows, row_count} from the preview card (used in fake mode).
    project_ids    — optional list to scope across multiple projects.
    """
    query: str
    sql: str = ""
    chart_schema: Dict[str, Any]
    adjustment_option: PreviewAdjustmentOption
    result_data: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = None
    project_ids: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/adjust")
async def adjust_preview_chart(request: PreviewChartAdjustRequest) -> Dict[str, Any]:
    """
    Adjust chart type / axes for an existing preview card.

    Returns ChartAdjustmentResultResponse shape:
      {status, response: {reasoning, chart_type, chart_schema}, error, trace_id}
    """
    from app.settings import get_settings
    settings = get_settings()

    if settings.FAKE_PREVIEW_MODE:
        return await _fake_adjust(request, settings)

    return await _real_adjust(request)


async def _fake_adjust(request: PreviewChartAdjustRequest, settings: Any) -> Dict[str, Any]:
    """Proxy to ComplianceSkill fake endpoint."""
    url = f"{settings.COMPLIANCE_SKILL_BASE_URL.rstrip('/')}/workflow/preview/chart_adjust"
    payload = {
        "query": request.query,
        "sql": request.sql,
        "chart_schema": request.chart_schema,
        "adjustment_option": request.adjustment_option.dict(),
        "result_data": request.result_data,
        "project_id": request.project_id or "",
        "project_ids": request.project_ids,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.COMPLIANCE_SKILL_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("ComplianceSkill chart_adjust error %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail=f"ComplianceSkill error: {exc.response.text}")
    except Exception as exc:
        logger.error("ComplianceSkill chart_adjust unreachable: %s", exc)
        raise HTTPException(status_code=502, detail=f"ComplianceSkill unreachable: {exc}")


async def _real_adjust(request: PreviewChartAdjustRequest) -> Dict[str, Any]:
    """Call the real chart_adjustment_service."""
    from app.services.service_container import SQLServiceContainer
    from app.services.sql.models import ChartAdjustmentRequest, ChartAdjustmentOption

    service = SQLServiceContainer.get_instance().get_service("chart_adjustment_service")
    adj_request = ChartAdjustmentRequest(
        query=request.query,
        sql=request.sql,
        chart_schema=request.chart_schema,
        adjustment_option=ChartAdjustmentOption(
            chart_type=request.adjustment_option.chart_type,
            x_axis=request.adjustment_option.x_axis,
            y_axis=request.adjustment_option.y_axis,
            x_offset=request.adjustment_option.x_offset,
            color=request.adjustment_option.color,
            theta=request.adjustment_option.theta,
        ),
        project_id=request.project_id,
    )
    adj_request.query_id = str(uuid.uuid4())
    result = await service.process_request(adj_request)
    return result.dict() if hasattr(result, "dict") else result
