from fastapi import APIRouter, HTTPException, status, Query, Path, Body
from typing import List, Dict, Any, Optional, Union
from httpx import AsyncClient, HTTPStatusError, ConnectError, RequestError
import httpx
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router setup
sql_helper_api_router = APIRouter()

# Constants
BASE_URL = "http://ec2-18-204-196-65.compute-1.amazonaws.com:8025"
MAX_RETRIES = 3
RETRY_DELAY = 1.0

@asynccontextmanager
async def get_http_client():
    """Context manager for HTTP client."""
    client = None
    try:
        client = AsyncClient(
            timeout=None,  # No timeout - wait indefinitely
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        yield client
    except Exception as e:
        logger.error(f"Failed to create HTTP client: {str(e)}")
        raise
    finally:
        if client:
            await client.aclose()

async def make_request_with_retry(
    method: str,
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = MAX_RETRIES
):
    """Make HTTP request with retry logic and comprehensive error handling."""
    headers = {"Content-Type": "application/json"}
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            async with get_http_client() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=json_data, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                try:
                    result = response.json()
                    logger.info(f"Successfully completed {method} request to {url}")
                    return result
                except ValueError as json_err:
                    logger.error(f"Invalid JSON response from {url}: {str(json_err)}")
                    return {"message": "Invalid JSON response from server", "status_code": response.status_code}
                
        except HTTPStatusError as e:
            last_exception = e
            status_code = e.response.status_code
            
            if status_code == 401:
                logger.error(f"Authentication failed for {url}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed with upstream service"
                )
            elif status_code == 403:
                logger.error(f"Authorization failed for {url}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions for this operation"
                )
            elif status_code == 404:
                logger.error(f"Resource not found: {url}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Requested resource not found"
                )
            elif status_code >= 500:
                logger.warning(f"Server error {status_code} for {url}, attempt {attempt + 1}/{max_retries + 1}")
                if attempt < max_retries:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Upstream service temporarily unavailable"
                    )
            else:
                logger.error(f"HTTP error {status_code} for {url}: {e.response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Upstream service error: HTTP {status_code}"
                )
                
        except (ConnectError, RequestError) as e:
            last_exception = e
            logger.warning(f"Network error for {url}, attempt {attempt + 1}/{max_retries + 1}: {str(e)}")
            
            if attempt < max_retries:
                await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                continue
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Unable to connect to upstream service"
                )
            
        except Exception as e:
            last_exception = e
            logger.error(f"Unexpected error for {url}: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )
    
    if last_exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Request failed after {max_retries + 1} attempts"
        )

# ========================================
# SQL HELPER ENDPOINTS
# ========================================

@sql_helper_api_router.post("/sql-helper/summary")
async def get_sql_summary(
    payload: Dict[str, Any] = Body(..., description="Payload for SQL summary")
):
    """Get a summary for the given SQL query."""
    url = f"{BASE_URL}/sql-helper/summary"
    return await make_request_with_retry("POST", url, json_data=payload)

@sql_helper_api_router.post("/sql-helper/summary/stream")
async def get_sql_summary_stream(
    payload: Dict[str, Any] = Body(..., description="Payload for SQL summary stream")
):
    """Get a streaming summary for the given SQL query."""
    url = f"{BASE_URL}/sql-helper/summary/stream"
    return await make_request_with_retry("POST", url, json_data=payload)

@sql_helper_api_router.post("/sql-helper/analyze-requirements")
async def analyze_sql_requirements(
    payload: Dict[str, Any] = Body(..., description="Payload for analyzing SQL requirements")
):
    """Analyze the requirements for a SQL query."""
    url = f"{BASE_URL}/sql-helper/analyze-requirements"
    return await make_request_with_retry("POST", url, json_data=payload)

@sql_helper_api_router.post("/sql-helper/visualization")
async def get_sql_visualization(
    payload: Dict[str, Any] = Body(..., description="Payload for SQL visualization")
):
    """Get a visualization for the given SQL query."""
    url = f"{BASE_URL}/sql-helper/visualization"
    return await make_request_with_retry("POST", url, json_data=payload)

@sql_helper_api_router.post("/sql-helper/stop/{query_id}")
async def stop_sql_query(
    query_id: str = Path(..., description="The ID of the query to stop")
):
    """Stop a running SQL query."""
    url = f"{BASE_URL}/sql-helper/stop/{query_id}"
    return await make_request_with_retry("POST", url)

@sql_helper_api_router.get("/sql-helper/status/{query_id}")
async def get_sql_query_status(
    query_id: str = Path(..., description="The ID of the query to get the status of")
):
    """Get the status of a SQL query."""
    url = f"{BASE_URL}/sql-helper/status/{query_id}"
    return await make_request_with_retry("GET", url)

@sql_helper_api_router.post("/sql-helper/data-assistance")
async def get_data_assistance(
    payload: Dict[str, Any] = Body(..., description="Payload for data assistance")
):
    """Get data assistance for a SQL query."""
    url = f"{BASE_URL}/sql-helper/data-assistance"
    return await make_request_with_retry("POST", url, json_data=payload)

@sql_helper_api_router.post("/sql-helper/sql-expansion")
async def expand_sql_query(
    payload: Dict[str, Any] = Body(..., description="Payload for SQL expansion")
):
    """Expand a SQL query."""
    url = f"{BASE_URL}/sql-helper/sql-expansion"
    return await make_request_with_retry("POST", url, json_data=payload)

@sql_helper_api_router.post("/sql-helper/data-generation")
async def generate_data(
    payload: Dict[str, Any] = Body(..., description="Payload for data generation")
):
    """Generate data based on a SQL query."""
    url = f"{BASE_URL}/sql-helper/data-generation"
    return await make_request_with_retry("POST", url, json_data=payload)