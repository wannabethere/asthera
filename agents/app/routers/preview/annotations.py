"""
Preview — Annotations
=====================

POST /preview/charts/annotate

Passthrough router for injecting annotations into a preview card's
vega-lite spec.

• FAKE_PREVIEW_MODE=True  → proxy to ComplianceSkill /workflow/preview/annotate
• FAKE_PREVIEW_MODE=False → proxy to ComplianceSkill /workflow/preview/annotate
  (annotation injection is always handled by ComplianceSkill — there is no
  warehouse dependency, so both modes use the same implementation)

The real upgrade path is to replace the ComplianceSkill call with an
LLM-backed annotation generator once one is wired up in astherabackend.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview/charts", tags=["preview-charts"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PreviewAnnotateRequest(BaseModel):
    """
    Request for adding an annotation to an existing chart spec.
    annotation_type: "text" | "rule" | "point"
    x_value / y_value: data-space coordinates (optional; median row used if omitted).
    """
    vega_lite_spec: Dict[str, Any]
    annotation_text: str
    annotation_type: str = "text"
    x_value: Optional[Any] = None
    y_value: Optional[Any] = None
    color: str = "#ff9800"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/annotate")
async def annotate_preview_chart(request: PreviewAnnotateRequest) -> Dict[str, Any]:
    """
    Inject an annotation layer into an existing preview card's vega-lite spec.

    Returns:
      {
        "vega_lite_spec": <updated spec with annotation layer>,
        "annotations": [{"text", "x_value", "y_value", "type", "color"}]
      }
    """
    from app.settings import get_settings
    settings = get_settings()
    return await _proxy_annotate(request, settings)


async def _proxy_annotate(request: PreviewAnnotateRequest, settings: Any) -> Dict[str, Any]:
    """
    Always proxies to ComplianceSkill — annotation injection has no
    warehouse dependency so fake/real modes behave identically here.
    """
    url = f"{settings.COMPLIANCE_SKILL_BASE_URL.rstrip('/')}/workflow/preview/annotate"
    payload = {
        "vega_lite_spec": request.vega_lite_spec,
        "annotation_text": request.annotation_text,
        "annotation_type": request.annotation_type,
        "x_value": request.x_value,
        "y_value": request.y_value,
        "color": request.color,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.COMPLIANCE_SKILL_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("ComplianceSkill annotate error %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail=f"ComplianceSkill error: {exc.response.text}")
    except Exception as exc:
        logger.error("ComplianceSkill annotate unreachable: %s", exc)
        raise HTTPException(status_code=502, detail=f"ComplianceSkill unreachable: {exc}")
