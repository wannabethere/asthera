from fastapi import APIRouter, HTTPException, status, Query, Path, Body
from typing import List, Dict, Any, Optional, Union
from httpx import AsyncClient, HTTPStatusError, ConnectError, RequestError
from app.schemas.thread import RequestType
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
workflow_api_router = APIRouter()

# Constants
BASE_URL = "http://ec2-18-204-196-65.compute-1.amazonaws.com:8045"
MAX_RETRIES = 3
RETRY_DELAY = 1.0
DEFAULT_USER_ID = "1e0cba86-110a-4d45-a205-182963880d75"

@asynccontextmanager
async def get_http_client():
    """Context manager for HTTP client with SSL verification disabled."""
    client = None
    try:
        client = AsyncClient(
            verify=False,  # Disable SSL verification
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
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=json_data, params=params)
                elif method.upper() == "PATCH":
                    response = await client.patch(url, headers=headers, json=json_data, params=params)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Try to parse JSON response
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
    
    # This should never be reached, but just in case
    if last_exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Request failed after {max_retries + 1} attempts"
        )

# ========================================
# HEALTH CHECK ENDPOINT
# ========================================

@workflow_api_router.get("/")
async def health_check() -> Dict[str, Any]:
    """Health Check to confirm API is up and running."""
    url = f"{BASE_URL}/"
    return await make_request_with_retry("GET", url)

# ========================================
# DASHBOARD ENDPOINTS
# ========================================


@workflow_api_router.post("/api/v1/workflows/dashboard")
async def create_dashboard_workflow(
    name: str = Query(..., description="Dashboard name"),
    description: str = Query(..., description="Dashboard description"),
    project_id: Optional[str] = Query(None, description="Project ID"),
    workspace_id: Optional[str] = Query(None, description="Workspace ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    metadata: Optional[Dict[str, Any]] = Body(None, description="Additional metadata")
) :
    """Create a new dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/dashboard"
    params = {
        "name": name,
        "description": description,
        "user_id": user_id
    }
    if project_id:
        params["project_id"] = project_id
    if workspace_id:
        params["workspace_id"] = workspace_id
    
    return await make_request_with_retry("POST", url, metadata, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/dashboard/add-component")
async def add_dashboard_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    thread_message_id: Optional[Union[str, List[str]]] = Query(None, description="Thread message ID(s)"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    components: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(..., description="Components to add")
) :
    """Add thread components to the dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/add-component"
    params = {"user_id": user_id}
    
    if thread_message_id:
        params["thread_message_id"] = thread_message_id
    
    return await make_request_with_retry("POST", url, components, params)

@workflow_api_router.patch("/api/v1/workflows/{workflow_id}/dashboard/configure-component/{component_id}")
async def configure_dashboard_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    configuration: Dict[str, Any] = Body(..., description="Component configuration")
) :
    """Configure a specific dashboard component."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/configure-component/{component_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("PATCH", url, configuration, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/dashboard/share")
async def configure_dashboard_sharing(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    share_config: Dict[str, Any] = Body(..., description="Share configuration")
) :
    """Configure sharing for the dashboard."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/share"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, share_config, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/dashboard/schedule")
async def schedule_dashboard(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    schedule_config: Dict[str, Any] = Body(..., description="Schedule configuration")
) :
    """Configure scheduling for the dashboard."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/schedule"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, schedule_config, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/dashboard/integrations")
async def configure_dashboard_integrations(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    integrations: List[Dict[str, Any]] = Body(..., description="Integration configurations")
) :
    """Configure integrations for publishing the dashboard."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/integrations"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, integrations, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/dashboard/publish")
async def publish_dashboard(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Publish the dashboard to all configured integrations."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/publish"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.get("/api/v1/workflows/workflow/getAllDashboards")
async def get_all_dashboards(
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    limit: int = Query(20, le=100, description="Limit number of results")
) :
    """Get all dashboards for the current user."""
    url = f"{BASE_URL}/api/v1/workflows/workflow/getAllDashboards"
    params = {"user_id": user_id, "limit": limit}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/workflow/getDashboardById")
async def get_dashboard_by_id(
    dashboard_id: Optional[str] = Query(None, description="Dashboard ID"),
    workflow_id: Optional[str] = Query(None, description="Workflow ID"),
    dashboard_type: str = Query("dashboard", regex="^(dashboard|report)$", description="Dashboard type"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get a specific dashboard or report by ID with all details including sharing, scheduling, and integrations."""
    url = f"{BASE_URL}/api/v1/workflows/workflow/getDashboardById"
    params = {"dashboard_type": dashboard_type, "user_id": user_id}
    if dashboard_id:
        params["dashboard_id"] = dashboard_id
    if workflow_id:
        params["workflow_id"] = workflow_id
    
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.patch("/api/v1/workflows/{workflow_id}/dashboard/edit")
async def edit_dashboard(
    workflow_id: str = Path(..., description="Workflow ID"),
    name: Optional[str] = Query(None, description="Dashboard name"),
    description: Optional[str] = Query(None, description="Dashboard description"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    dashboard_data: Optional[Dict[str, Any]] = Body(None, description="Dashboard content and metadata")
) :
    """Edit dashboard basic information - creates draft version."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/edit"
    params = {"user_id": user_id}
    if name:
        params["name"] = name
    if description:
        params["description"] = description
    
    return await make_request_with_retry("PATCH", url, dashboard_data, params)

@workflow_api_router.patch("/api/v1/workflows/{workflow_id}/dashboard/components/{component_id}")
async def update_dashboard_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    update_data: Dict[str, Any] = Body(..., description="Component update data")
) :
    """Update a dashboard thread component."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/components/{component_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("PATCH", url, update_data, params)

@workflow_api_router.delete("/api/v1/workflows/{workflow_id}/dashboard/components/{component_id}")
async def remove_dashboard_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Remove a dashboard thread component."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/components/{component_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("DELETE", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/dashboard/draft-changes")
async def get_dashboard_draft_changes(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get current draft changes for a dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/draft-changes"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/dashboard/discard-draft")
async def discard_dashboard_draft_changes(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Discard all draft changes for a dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/discard-draft"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/dashboard/preview")
async def get_dashboard_preview(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get dashboard preview with draft changes applied."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/dashboard/preview"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)


#=========================================
# REPORT ENDPOINTS
#=========================================

@workflow_api_router.post("/api/v1/workflows/report")
async def create_report_workflow(
    name: str = Query(..., description="Report name"),
    description: str = Query(..., description="Report description"),
    template: str = Query("standard", description="Report template"),
    project_id: Optional[str] = Query(None, description="Project ID"),
    workspace_id: Optional[str] = Query(None, description="Workspace ID"),
    workflow_id: Optional[str] = Query(None, description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Create a new report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/report"
    params = {
        "name": name,
        "description": description,
        "template": template,
        "user_id": user_id
    }
    if project_id:
        params["project_id"] = project_id
    if workspace_id:
        params["workspace_id"] = workspace_id
    if workflow_id:
        params["workflow_id"] = workflow_id
    
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/report/add-section")
async def add_report_section(
    workflow_id: str = Path(..., description="Workflow ID"),
    section_type: Optional[str] = Query(None, description="Section type"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    section_config: Dict[str, Any] = Body(..., description="Section configuration")
) :
    """Add a section to the report."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/add-section"
    params = {
        "section_type": section_type,
        "user_id": user_id
    }
    return await make_request_with_retry("POST", url, section_config, params)

@workflow_api_router.get("/api/v1/workflows/workflow/getAllReports")
async def get_all_reports(
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    limit: Optional[int] = Query(20, description="Limit number of reports")
) :
    """Get all reports."""
    url = f"{BASE_URL}/api/v1/workflows/workflow/getAllReports"
    params = {"user_id": user_id}
    if limit:
        params["limit"] = limit
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/workflow/getReportById")
async def get_report_by_id(
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    report_id: str = Query(..., description="Report ID"),
    workflow_id: Optional[str] = Query(None, description="Workflow ID")
) :
    """Get a report by ID."""
    url = f"{BASE_URL}/api/v1/workflows/workflow/getReportById"
    params = {
        "user_id": user_id,
        "report_id": report_id
    }
    if workflow_id:
        params["workflow_id"] = workflow_id
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/report/data-sources")
async def configure_report_data_sources(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    data_sources: List[Dict[str, Any]] = Body(..., description="Data sources configuration")
) :
    """Configure data sources for the report."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/data-sources"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, data_sources, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/report/share")
async def configure_report_sharing(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    share_config: Dict[str, Any] = Body(..., description="Report share configuration")
) :
    """Configure sharing for the report."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/share"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, share_config, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/report/schedule")
async def schedule_report(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    schedule_config: Dict[str, Any] = Body(..., description="Schedule configuration")
) :
    """Configure scheduling for the report."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/schedule"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, schedule_config, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/report/publish")
async def publish_report(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Publish the report to all configured integrations."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/publish"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/report/preview-draft")
async def get_report_preview_draft(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get report preview with draft changes applied."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/preview-draft"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.patch("/api/v1/workflows/{workflow_id}/report/edit")
async def edit_report(
    workflow_id: str = Path(..., description="Workflow ID"),
    name: Optional[str] = Query(None, description="Report name"),
    description: Optional[str] = Query(None, description="Report description"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    report_data: Optional[Dict[str, Any]] = Body(None, description="Report content and metadata")
) :
    """Edit report basic information - creates draft version."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/edit"
    params = {"user_id": user_id}
    if name:
        params["name"] = name
    if description:
        params["description"] = description
    
    return await make_request_with_retry("PATCH", url, report_data, params)

@workflow_api_router.patch("/api/v1/workflows/{workflow_id}/report/sections/{section_id}")
async def update_report_section(
    workflow_id: str = Path(..., description="Workflow ID"),
    section_id: str = Path(..., description="Section ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    section_config: Dict[str, Any] = Body(..., description="Section configuration")
) :
    """Update a report section in draft mode."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/sections/{section_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("PATCH", url, section_config, params)

@workflow_api_router.delete("/api/v1/workflows/{workflow_id}/report/sections/{section_id}")
async def remove_report_section(
    workflow_id: str = Path(..., description="Workflow ID"),
    section_id: str = Path(..., description="Section ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Remove a report section from draft."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/sections/{section_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("DELETE", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/report/draft-changes")
async def get_report_draft_changes(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get current draft changes for a report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/draft-changes"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/report/discard-draft")
async def discard_report_draft_changes(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Discard all draft changes for a report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/discard-draft"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/report/preview-draft")
async def get_report_preview_draft(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get report preview with draft changes applied."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/preview-draft"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/report/preview")
async def preview_report(
    workflow_id: str = Path(..., description="Workflow ID"),
    format_type: str = Query("html", regex="^(html|pdf)$", description="Format type"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Generate a preview of the report."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/report/preview"
    params = {"format_type": format_type, "user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/share/{shareType}/getAllShares/{entityid}")
async def get_all_shares(
    shareType: RequestType,
    entityid: str,
    user_id: str = "1e0cba86-110a-4d45-a205-182963880d75",
) :
    """Get all shares for the current user"""
    url = f"{BASE_URL}/api/v1/workflows/share/{shareType.value}/getAllShares/{entityid}"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)


#=========================================
# WORKFLOWS ENDPOINTS
#=========================================

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/batch")
async def execute_batch_steps(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    steps: List[Dict[str, Any]] = Body(..., description="Batch steps to execute")
) :
    """Execute multiple workflow steps in sequence."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/batch"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, steps, params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/status")
async def get_workflow_status(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get the current status and progress of a workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/status"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/list")
async def list_workflows(
    workflow_type: Optional[str] = Query(None, description="Workflow type filter"),
    state: Optional[str] = Query(None, description="Workflow state filter"),
    limit: int = Query(20, le=100, description="Limit number of results"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """List all workflows for the current user."""
    url = f"{BASE_URL}/api/v1/workflows/list"
    params = {"limit": limit, "user_id": user_id}
    if workflow_type:
        params["workflow_type"] = workflow_type
    if state:
        params["state"] = state
    
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.delete("/api/v1/workflows/{workflow_id}")
async def cancel_workflow(
    workflow_id: str = Path(..., description="Workflow ID"),
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Cancel an active workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}"
    params = {"user_id": user_id}
    if reason:
        params["reason"] = reason
    
    return await make_request_with_retry("DELETE", url, params=params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Resume a paused or failed workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/resume"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.post("/api/v1/workflows/example/complete-dashboard-workflow")
async def example_complete_dashboard_workflow(
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Example endpoint showing a complete dashboard workflow from start to finish."""
    url = f"{BASE_URL}/api/v1/workflows/example/complete-dashboard-workflow"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.post("/api/v1/workflows/scheduled/run")
async def run_scheduled_workflows() :
    """Trigger execution of all due scheduled workflows."""
    url = f"{BASE_URL}/api/v1/workflows/scheduled/run"
    return await make_request_with_retry("POST", url)



# ========================================
# N8N WORKFLOW MANAGEMENT ENDPOINTS
# ========================================

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/n8n/create")
async def create_n8n_workflow(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Manually create n8n workflow for an existing active dashboard."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/n8n/create"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, params=params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/n8n/status")
async def get_n8n_workflow_status(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get the status of n8n workflow for a dashboard."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/n8n/status"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/n8n/workflows")
async def list_all_n8n_workflows(
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """List all generated n8n workflow files."""
    url = f"{BASE_URL}/api/v1/workflows/n8n/workflows"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.delete("/api/v1/workflows/{workflow_id}/n8n/delete")
async def delete_n8n_workflow(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Delete n8n workflow file for a dashboard."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/n8n/delete"
    params = {"user_id": user_id}
    return await make_request_with_retry("DELETE", url, params=params)

# ========================================
# ALERT MANAGEMENT - WORKFLOW ENDPOINTS
# ========================================

@workflow_api_router.post("/api/v1/workflows/alert")
async def create_alert_workflow(
    name:str = Query(..., description="Workflow name"),
    description:str = Query(..., description="Workflow description"),
    project_id:Optional[str] = Query(None, description="Project ID"),
    workspace_id:Optional[str] = Query(None, description="Workspace ID"),
    user_id:str = Query(DEFAULT_USER_ID, description="User ID"),
    alert_config:Dict[str, Any] = Body(..., description="Alert configuration")
) :
    """Create an alert workflow."""
    url = f"{BASE_URL}/api/v1/workflows/alert"
    params = {"user_id": user_id,"name":name,"description":description}
    if project_id:
        params["project_id"] = project_id
    if workspace_id:
        params["workspace_id"] = workspace_id
    return await make_request_with_retry("POST", url,alert_config, params)

@workflow_api_router.get("/api/v1/workflows/alert/all")
async def get_all_alert_workflows(
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get all alert workflows."""
    url = f"{BASE_URL}/api/v1/workflows/alert/all"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.get("/api/v1/workflows/alert/{alert_id}")
async def get_alert_workflow(
    alert_id: str = Path(..., description="Alert ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get a specific alert workflow."""
    url = f"{BASE_URL}/api/v1/workflows/alert/{alert_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

# ========================================
# ALERT MANAGEMENT - REPORT ENDPOINTS
# ========================================

@workflow_api_router.post("/api/v1/workflows/reports/{workflow_id}/alerts")
async def add_report_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    alert_config: Dict[str, Any] = Body(..., description="Alert configuration")
) :
    """Add an alert as a thread message component to a report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/reports/{workflow_id}/alerts"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, alert_config, params)

@workflow_api_router.get("/api/v1/workflows/reports/{workflow_id}/alerts")
async def get_report_alert_thread_components(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get all alert thread components for a report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/reports/{workflow_id}/alerts"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.patch("/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}")
async def update_report_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    alert_id: str = Path(..., description="Alert ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    alert_update: Dict[str, Any] = Body(..., description="Alert update data")
) :
    """Update an existing alert thread component in a report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("PATCH", url, alert_update, params)

@workflow_api_router.delete("/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}")
async def delete_report_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    alert_id: str = Path(..., description="Alert ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Delete an alert thread component from a report workflow."""
    url = f"{BASE_URL}/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("DELETE", url, params=params)

@workflow_api_router.post("/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}/test")
async def test_report_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    alert_id: str = Path(..., description="Alert ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    test_data: Optional[Dict[str, Any]] = Body(None, description="Test data")
) :
    """Test an alert thread component in a report workflow with sample data."""
    url = f"{BASE_URL}/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}/test"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, test_data, params)

@workflow_api_router.post("/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}/trigger")
async def trigger_report_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    alert_id: str = Path(..., description="Alert ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    trigger_data: Optional[Dict[str, Any]] = Body(None, description="Trigger data")
) :
    """Manually trigger an alert thread component in a report workflow for testing."""
    url = f"{BASE_URL}/api/v1/workflows/reports/{workflow_id}/alerts/{alert_id}/trigger"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, trigger_data, params)



# ========================================
# ALERT MANAGEMENT - DASHBOARD ENDPOINTS
# ========================================

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/alerts")
async def add_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    alert_config: Dict[str, Any] = Body(..., description="Alert configuration")
) :
    """Add an alert as a thread message component to the dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/alerts"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, alert_config, params)

@workflow_api_router.get("/api/v1/workflows/{workflow_id}/alerts")
async def get_alert_thread_components(
    workflow_id: str = Path(..., description="Workflow ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Get all alert thread components for a dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/alerts"
    params = {"user_id": user_id}
    return await make_request_with_retry("GET", url, params=params)

@workflow_api_router.patch("/api/v1/workflows/{workflow_id}/alerts/{component_id}")
async def update_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    alert_update: Dict[str, Any] = Body(..., description="Alert update data")
) :
    """Update an existing alert thread component."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/alerts/{component_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("PATCH", url, alert_update, params)

@workflow_api_router.delete("/api/v1/workflows/{workflow_id}/alerts/{component_id}")
async def delete_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID")
) :
    """Delete an alert thread component from a dashboard workflow."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/alerts/{component_id}"
    params = {"user_id": user_id}
    return await make_request_with_retry("DELETE", url, params=params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/alerts/{component_id}/test")
async def test_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    test_data: Optional[Dict[str, Any]] = Body(None, description="Test data")
) :
    """Test an alert thread component with sample data."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/alerts/{component_id}/test"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, test_data, params)

@workflow_api_router.post("/api/v1/workflows/{workflow_id}/alerts/{component_id}/trigger")
async def trigger_alert_thread_component(
    workflow_id: str = Path(..., description="Workflow ID"),
    component_id: str = Path(..., description="Component ID"),
    user_id: str = Query(DEFAULT_USER_ID, description="User ID"),
    trigger_data: Optional[Dict[str, Any]] = Body(None, description="Trigger data")
) :
    """Manually trigger an alert thread component for testing."""
    url = f"{BASE_URL}/api/v1/workflows/{workflow_id}/alerts/{component_id}/trigger"
    params = {"user_id": user_id}
    return await make_request_with_retry("POST", url, trigger_data, params)
