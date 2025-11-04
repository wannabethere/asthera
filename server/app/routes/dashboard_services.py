from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Body
)
from typing import Dict, Any, Optional
import logging
import traceback
from httpx import AsyncClient, HTTPStatusError, ConnectError, RequestError
import httpx
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio
from contextlib import asynccontextmanager

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router and Security Initialization ---
dashboard_router = APIRouter()
enhanced_rag_router = APIRouter()
security = HTTPBearer()

# --- Constants ---
# Note: This is a new BASE_URL for these specific services
ANALYTICS_BASE_URL = "http://ec2-18-204-196-65.compute-1.amazonaws.com:8025"
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# --- Helper Functions (Reused from previous examples) ---

def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Extracts and validates the bearer token from the request's Authorization header.
    """
    if not credentials or not credentials.credentials:
        logger.warning("Authentication attempt with missing or invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

@asynccontextmanager
async def get_http_client():
    """
    Provides an asynchronous HTTP client within a context manager for safe handling.
    """
    async with AsyncClient(
        verify=False, 
        timeout=None,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        yield client

async def make_request_with_retry_enhanced(
    method: str,
    url: str,
    token: Optional[str] = None,
    json_data: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Makes an HTTP request with exponential backoff retry logic and handles common errors.
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if json_data:
        headers["Content-Type"] = "application/json"
        
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with get_http_client() as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=json_data,
                    data=data,
                    files=files,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except (HTTPStatusError, ConnectError, RequestError, ValueError) as e:
            # Simplified error handling for brevity, can be expanded like previous examples
            if attempt >= MAX_RETRIES:
                logger.error(f"Request failed after all retries for {url}: {e}")
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Upstream service error: {e}")
            await asyncio.sleep(RETRY_DELAY * (2 ** attempt))


@dashboard_router.post("/dashboard/generate")
async def generate_dashboard(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to generate a new dashboard."""
    url = f"{ANALYTICS_BASE_URL}/dashboard/generate"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@dashboard_router.post("/dashboard/generate-from-workflow")
async def generate_dashboard_from_workflow(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to generate a dashboard from an existing workflow."""
    url = f"{ANALYTICS_BASE_URL}/dashboard/generate-from-workflow"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@dashboard_router.post("/dashboard/render-from-workflow")
async def render_dashboard_from_workflow(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to render a dashboard from an existing workflow."""
    url = f"{ANALYTICS_BASE_URL}/dashboard/render-from-workflow"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@dashboard_router.post("/dashboard/execute-only")
async def execute_dashboard_only(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to execute the logic of a dashboard without rendering."""
    url = f"{ANALYTICS_BASE_URL}/dashboard/execute-only"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@dashboard_router.post("/report/render-from-workflow")
async def render_report_from_workflow(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to render a report from an existing workflow."""
    url = f"{ANALYTICS_BASE_URL}/report/render-from-workflow"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@enhanced_rag_router.post("/enhanced-rag/ask")
async def enhanced_rag_ask(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to ask a single question to the Enhanced RAG service."""
    url = f"{ANALYTICS_BASE_URL}/enhanced-rag/ask"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@enhanced_rag_router.post("/enhanced-rag/chat")
async def enhanced_rag_chat(
    payload: Dict[str, Any] = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Proxy to engage in a conversational chat with the Enhanced RAG service."""
    url = f"{ANALYTICS_BASE_URL}/enhanced-rag/chat"
    return await make_request_with_retry_enhanced("POST", url, token, json_data=payload)

@enhanced_rag_router.get("/enhanced-rag/capabilities")
async def get_enhanced_rag_capabilities(token: str = Depends(get_token)) -> Dict[str, Any]:
    """Proxy to get the capabilities of the Enhanced RAG service."""
    url = f"{ANALYTICS_BASE_URL}/enhanced-rag/capabilities"
    return await make_request_with_retry_enhanced("GET", url, token)

@enhanced_rag_router.get("/enhanced-rag/examples")
async def get_enhanced_rag_examples(token: str = Depends(get_token)) -> Dict[str, Any]:
    """Proxy to get example use cases for the Enhanced RAG service."""
    url = f"{ANALYTICS_BASE_URL}/enhanced-rag/examples"
    return await make_request_with_retry_enhanced("GET", url, token)
