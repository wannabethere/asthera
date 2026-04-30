"""
Preview — Drill-Down
====================

POST /preview/charts/drill-down

Passthrough router for drilling into a preview card to get a sub-level view.

• FAKE_PREVIEW_MODE=True  → proxy to ComplianceSkill /workflow/preview/drill_down
• FAKE_PREVIEW_MODE=False → call sql_helper_service.generate_sql_expansion()
  then re-render the result as a preview card

Request mirrors SQLExpansionRequest so callers use the same payload
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

class PreviewDrillDownRequest(BaseModel):
    """
    Mirrors SQLExpansionRequest fields, extended with preview card context.
    query           — drill NL question (or re-use nl_question if same).
    sql             — parent SQL (empty in fake mode).
    original_query  — parent card's NL question.
    name            — parent card display name.
    item_type       — metric | kpi | table.
    drill_dimension — column/field to drill into.
    drill_value     — specific value to filter on.
    parent_result_data — {columns, rows} from the parent preview card.
    project_ids     — optional list to scope across multiple projects.
    """
    query: str
    sql: str = ""
    original_query: Optional[str] = None
    original_reasoning: Optional[str] = None
    name: str = "Drill-down"
    item_type: str = "metric"
    nl_question: Optional[str] = None
    drill_dimension: Optional[str] = None
    drill_value: Optional[str] = None
    parent_result_data: Optional[Dict[str, Any]] = None
    source_tables: Optional[List[str]] = None
    project_id: Optional[str] = None
    project_ids: Optional[List[str]] = None
    index: int = 0


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/drill-down")
async def drill_down_preview(request: PreviewDrillDownRequest) -> Dict[str, Any]:
    """
    Drill into an existing preview card to get a sub-level view.

    Returns a full preview card dict (same shape as /workflow/preview_item):
      {name, item_type, nl_question, sql, summary, insights, chart_type,
       vega_lite_spec, result_data, ...}
    """
    from app.settings import get_settings
    settings = get_settings()

    if settings.FAKE_PREVIEW_MODE:
        return await _fake_drill_down(request, settings)

    return await _real_drill_down(request)


async def _fake_drill_down(request: PreviewDrillDownRequest, settings: Any) -> Dict[str, Any]:
    """Proxy to ComplianceSkill fake endpoint."""
    url = f"{settings.COMPLIANCE_SKILL_BASE_URL.rstrip('/')}/workflow/preview/drill_down"
    payload = {
        "name": request.name,
        "item_type": request.item_type,
        "nl_question": request.nl_question or request.query,
        "query": request.query,
        "sql": request.sql,
        "drill_dimension": request.drill_dimension or "",
        "drill_value": request.drill_value or "",
        "parent_result_data": request.parent_result_data,
        "source_tables": request.source_tables,
        "project_id": request.project_id or "",
        "project_ids": request.project_ids,
        "index": request.index,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.COMPLIANCE_SKILL_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("ComplianceSkill drill_down error %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail=f"ComplianceSkill error: {exc.response.text}")
    except Exception as exc:
        logger.error("ComplianceSkill drill_down unreachable: %s", exc)
        raise HTTPException(status_code=502, detail=f"ComplianceSkill unreachable: {exc}")


async def _real_drill_down(request: PreviewDrillDownRequest) -> Dict[str, Any]:
    """Call sql_helper_service.generate_sql_expansion() and wrap result as a preview card."""
    from app.services.service_container import SQLServiceContainer

    service = SQLServiceContainer.get_instance().get_service("sql_helper_service")
    query_id = str(uuid.uuid4())

    result = await service.generate_sql_expansion(
        query_id=query_id,
        query=request.query,
        sql=request.sql,
        original_query=request.original_query or request.query,
        original_reasoning=request.original_reasoning or "",
        project_id=request.project_id or "",
        configuration=None,
        schema_context=None,
    )

    expansion_data = result.get("data", {})
    expanded_sql = expansion_data.get("expanded_sql") or expansion_data.get("sql", request.sql)

    sub_name = (
        f"{request.name} — {request.drill_dimension}={request.drill_value}"
        if request.drill_value else f"{request.name} (drill-down)"
    )
    return {
        "name": sub_name,
        "item_type": request.item_type,
        "description": f"Drill-down view of {request.name}",
        "nl_question": request.query,
        "sql": expanded_sql,
        "summary": expansion_data.get("summary", f"Detailed breakdown of {request.name}."),
        "explanation": expansion_data.get("explanation", ""),
        "insights": expansion_data.get("insights", []),
        "chart_type": "bar",
        "trend_direction": "stable",
        "vega_lite_spec": expansion_data.get("vega_lite_spec", {}),
        "result_data": expansion_data.get("result_data", {}),
        "source_schemas": request.source_tables or [],
        "focus_area": "",
        "source": "drill_down_real",
    }
