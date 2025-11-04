from fastapi import APIRouter, Body, Request, Depends, HTTPException, status
from typing import Dict, Any, Optional
import httpx
import asyncio
import traceback
import logging

logger = logging.getLogger(__name__)

ALERTS_API_BASE_URL = "http://172.191.171.71:8010/api"
MAX_RETRIES = 3
RETRY_DELAY = 1.0

alerts_router = APIRouter()


from contextlib import asynccontextmanager
from httpx import AsyncClient, ConnectError, RequestError, HTTPStatusError

@asynccontextmanager
async def get_http_client():
    """Context manager for a shared HTTP client."""
    async with AsyncClient(verify=False, timeout=30.0) as client:
        yield client

async def make_request_with_retry(
    method: str,
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = MAX_RETRIES
) -> Dict[str, Any]:
    """Make an HTTP request with retry logic for the alerts API."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            async with get_http_client() as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    json=json_data,
                    params=params
                )
                response.raise_for_status()
                # Handle cases where the response might be empty
                if not response.content:
                    return {"status": "success", "message": "Operation successful with no content."}
                return response.json()
        except (ConnectError, RequestError, HTTPStatusError) as e:
            logger.warning(f"Request to {url} failed on attempt {attempt + 1}: {e}")
            last_exception = e
            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
        except Exception as e:
            logger.error(f"An unexpected error occurred while requesting {url}: {e}")
            raise HTTPException(status_code=500, detail="An internal error occurred.")
    
    # If all retries fail
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unable to connect to the alerts service at {url} after {max_retries} attempts. Last error: {last_exception}"
    )



@alerts_router.get("/alerts", summary="Get all alerts")
async def proxy_get_alerts():
    """Alerts Node API: Get all alerts."""
    url = f"{ALERTS_API_BASE_URL}/alerts"
    return await make_request_with_retry("GET", url)

@alerts_router.get("/alerts/{alert_id}", summary="Get a specific alert")
async def proxy_get_alert_by_id(alert_id: str):
    """Alerts Node API: Get a specific alert by ID."""
    url = f"{ALERTS_API_BASE_URL}/alerts/{alert_id}"
    return await make_request_with_retry("GET", url)

@alerts_router.post("/alerts/{alert_id}/ticket", summary="Create a ticket for an alert")
async def proxy_create_ticket(alert_id: str, payload: Dict[str, Any] = Body(...)):
    """Alerts Node API: Create a ticket for an alert."""
    url = f"{ALERTS_API_BASE_URL}/alerts/{alert_id}/ticket"
    return await make_request_with_retry("POST", url, json_data=payload)

@alerts_router.post("/alerts/{alert_id}/escalate", summary="Escalate an alert")
async def proxy_escalate_alert(alert_id: str, payload: Dict[str, Any] = Body(...)):
    """Alerts Node API: Escalate an alert."""
    url = f"{ALERTS_API_BASE_URL}/alerts/{alert_id}/escalate"
    return await make_request_with_retry("POST", url, json_data=payload)

@alerts_router.post("/alerts/{alert_id}/annotate", summary="Annotate an alert")
async def proxy_annotate_alert(alert_id: str, payload: Dict[str, Any] = Body(...)):
    """Alerts Node API: Add an annotation to an alert."""
    url = f"{ALERTS_API_BASE_URL}/alerts/{alert_id}/annotate"
    return await make_request_with_retry("POST", url, json_data=payload)

@alerts_router.post("/alerts/{alert_id}/mute", summary="Mute an alert")
async def proxy_mute_alert(alert_id: str, payload: Dict[str, Any] = Body(...)):
    """Alerts Node API: Mute an alert."""
    url = f"{ALERTS_API_BASE_URL}/alerts/{alert_id}/mute"
    return await make_request_with_retry("POST", url, json_data=payload)

@alerts_router.delete("/alerts/{alert_id}/mute", summary="Unmute an alert")
async def proxy_unmute_alert(alert_id: str, payload: Dict[str, Any] = Body(...)):
    """Alerts Node API: Unmute an alert."""
    url = f"{ALERTS_API_BASE_URL}/alerts/{alert_id}/mute"
    return await make_request_with_retry("DELETE", url, json_data=payload)

@alerts_router.get("/context/links", summary="Get context links for UI")
async def proxy_get_context_links(request: Request):
    """Alerts Node API: Get context data for UI dropdowns (with query params)."""
    alert_id = request.query_params.get('alertId')
    url = f"{ALERTS_API_BASE_URL}/context/links"
    params = {"alertId": alert_id} if alert_id else None
    return await make_request_with_retry("GET", url, params=params)

@alerts_router.post("/alerts/service/create-single", summary="Create a single alert")
async def proxy_create_single_alert(payload: Dict[str, Any] = Body(...)):
    """Alerts Node API: Create a single alert."""
    url = "http://ec2-44-202-8-38.compute-1.amazonaws.com:8025/alerts/service/create-single"
    return await make_request_with_retry("POST", url, json_data=payload)

