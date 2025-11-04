from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import List, Dict, Any, Optional
from httpx import AsyncClient, HTTPStatusError, ConnectError, RequestError
import httpx
import logging
import traceback
from pydantic import BaseModel, Field, ValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio
from contextlib import asynccontextmanager
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class connection_details(BaseModel):
    name: str = Field(..., description="Name of the connection")
    database_type: str = Field(..., description="Type of the database")
    database_details: dict = Field(..., description="Details of the database")

    class Config:
        extra = "forbid"  # Prevent extra fields

dataservice_router = APIRouter()
security = HTTPBearer()

# Constants
BASE_URL = "http://ec2-18-204-196-65.compute-1.amazonaws.com:8035"
MAX_RETRIES = 3
RETRY_DELAY = 1.0

def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract and validate the bearer token from request headers."""
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
    """Context manager for HTTP client with proper error handling."""
    client = None
    try:
        client = AsyncClient(
            verify=False,
            timeout=None,  # No timeout - wait indefinitely
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        yield client
    except Exception as e:
        print("=========== Error Started here================")
        traceback.print_exc()
        print("=========== Error ended here=================")
        logger.error(f"Failed to create HTTP client: {str(e)}")
        raise
    finally:
        if client:
            await client.aclose()

async def make_request_with_retry(
    method: str,
    url: str,
    token: Optional[str] = None,
    json_data: Optional[Dict[str, Any]] = None,
    max_retries: int = MAX_RETRIES,
    params:  Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Make HTTP request with retry logic and comprehensive error handling."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            async with get_http_client() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers,params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=json_data, params=params)
                elif method.upper() == "PATCH":
                    response = await client.patch(url, headers=headers, json=json_data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
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

# Datasources Endpoints

@dataservice_router.get("/datasources/datasources")
async def get_datasources(token: str = Depends(get_token)) -> List[Dict[str, Any]]:
    """Get all datasources."""
    url = f"{BASE_URL}/datasources/datasources"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.get("/datasources/connections/getAllConnections")
async def get_all_connections(token: str = Depends(get_token)) ->List[Dict[str, Any]]:
    """Get all database connections."""
    url = f"{BASE_URL}/datasources/connections/getAllConnections"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.post("/datasources/connections/createConnections")
async def create_connection(
    connection_details: connection_details,
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Create a new database connection."""
    try:
        connection_data = connection_details.model_dump()
        url = f"{BASE_URL}/datasources/connections/createConnections"
        return await make_request_with_retry("POST", url, token, connection_data)
    except ValidationError as e:
        logger.error(f"Validation error in create_connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid connection details: {str(e)}"
        )

@dataservice_router.get("/datasources/connections/{connectionId}/ERD")
async def get_erd(connectionId: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Get Entity Relationship Diagram for a connection."""
    if not connectionId or not connectionId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection ID cannot be empty"
        )
    
    url = f"{BASE_URL}/datasources/connections/{connectionId}/ERD"
    return await make_request_with_retry("GET", url, token)

# Domains Endpoints

@dataservice_router.post("/projects/workflow/workflow/domain")
async def create_domain(
    domain_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Create a new domain."""
    if not domain_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain details cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/domain"
    return await make_request_with_retry("POST", url, token, domain_details)

@dataservice_router.get("/projects/workflow/workflow/dataset/domain/all")
async def get_all_domains_for_datasets(token: str = Depends(get_token)) -> List[Dict[str, Any]]:
    """Get all domains for datasets which are not associated to any datasets."""
    url = f"{BASE_URL}/projects/workflow/workflow/dataset/domain/all"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.get("/projects/workflow/workflow/global/domain/all")
async def get_all_global_domains(token: str = Depends(get_token)) -> List[Dict[str, Any]]:
    """Get all global domains."""
    url = f"{BASE_URL}/projects/workflow/workflow/global/domain/all"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.post("/projects/workflow/workflow/dataset")
async def create_dataset(
    dataset_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Create a new dataset."""
    if not dataset_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset details cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/dataset"
    return await make_request_with_retry("POST", url, token, dataset_details)

@dataservice_router.get("/projects/workflow/workflow/dataset/all")
async def get_all_datasets(token: str = Depends(get_token)) -> Dict[str, Any]:
    """Get all datasets."""
    url = f"{BASE_URL}/projects/workflow/workflow/dataset/all"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.get("/projects/workflow/workflow/dataset/{datasetId}")
async def get_dataset(datasetId: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Get a specific dataset by ID."""
    if not datasetId or not datasetId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset ID cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/dataset/{datasetId}"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.post("/projects/workflow/workflow/table")
async def create_table(
    table_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Create a new table."""
    if not table_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table details cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/table"
    return await make_request_with_retry("POST", url, token, table_details)

@dataservice_router.post("/projects/workflow/workflow/commit")
async def commit(token: str = Depends(get_token)) -> Dict[str, Any]:
    """Commit workflow changes."""
    url = f"{BASE_URL}/projects/workflow/workflow/commit"
    return await make_request_with_retry("POST", url, token)

@dataservice_router.get("/projects/workflow/workflow/{domain_id}/sharing-permissions")
async def get_sharing_permissions(domain_id: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Get sharing permissions for a domain."""
    if not domain_id or not domain_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain ID cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/{domain_id}/sharing-permissions"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.post("/projects/workflow/workflow/metric")
async def create_metric(
    metric_details: Dict[str, Any],
    token: str = Depends(get_token),
    table_id: str = Query(...)
) -> Dict[str, Any]:
    """Create a new metric."""
    if not metric_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric details cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/metric"
    
    # Create a dictionary for the query parameters
    params = {"table_id": table_id}
    
    return await make_request_with_retry(
        "POST", url, token, json_data=metric_details, params=params
    )

@dataservice_router.post("/projects/workflow/workflow/calculated-column")
async def create_calculated_column(
    calculated_column_details: Dict[str, Any],
    token: str = Depends(get_token),
    table_id: str = Query(...)
) -> Dict[str, Any]:
    """Create a new calculated column."""
    if not calculated_column_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculated column details cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/calculated-column"    
    params = {"table_id": table_id}    
    return await make_request_with_retry( "POST", url, token, json_data=calculated_column_details, params=params)
    
@dataservice_router.post("/projects/workflow/workflow/view")    
async def create_view(
    view_details: Dict[str, Any],
    token: str = Depends(get_token),
    table_id: str = Query(...) 
) -> Dict[str, Any]:
    """Create a new view."""
    if not view_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="View details cannot be empty"
        )
    
    url = f"{BASE_URL}/projects/workflow/workflow/view"
    params = {"table_id": table_id}
    return await make_request_with_retry("POST", url, token, json_data=view_details, params=params)

@dataservice_router.get("/projects/workflow/workflow/table/{table_id}/metrics")
async def get_metrics(table_id,token: str = Depends(get_token)):
    url = f"{BASE_URL}/projects/workflow/workflow/table/{table_id}/metrics"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.get("/projects/workflow/workflow/table/{table_id}/views")
async def get_views(table_id,token: str = Depends(get_token)):
    url = f"{BASE_URL}/projects/workflow/workflow/table/{table_id}/views"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.get("/projects/workflow/workflow/table/{table_id}/calculated-columns")
async def get_calculated_columns(table_id,token: str = Depends(get_token)):
    url = f"{BASE_URL}/projects/workflow/workflow/table/{table_id}/calculated-columns"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.get("/projects/workflow/workflow/table/{table_id}/enhanced-columns")
async def get_enhanced_columns(table_id,token: str = Depends(get_token)):
    url = f"{BASE_URL}/projects/workflow/workflow/table/{table_id}/enhanced-columns"
    return await make_request_with_retry("GET", url, token)

    
# Instructions Endpoints

@dataservice_router.post("/instructions/instructions/")
async def create_instructions(
    instructions_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Create new instructions."""
    if not instructions_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instructions details cannot be empty"
        )
    
    url = f"{BASE_URL}/instructions/instructions/"
    return await make_request_with_retry("POST", url, token, instructions_details)

@dataservice_router.get("/instructions/instructions/")
async def get_all_instructions(domain_id:Optional[str]=None,token: str = Depends(get_token)) -> List[Dict[str, Any]]:
    """Get all instructions."""
    url = f"{BASE_URL}/instructions/instructions/"
    if domain_id:
        params={"domain_id":domain_id}
    else:
        params=None
    return await make_request_with_retry("GET", url, token, params=params)

@dataservice_router.get("/instructions/instructions/{instructionId}")
async def get_instruction(instructionId: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Get a specific instruction by ID."""
    if not instructionId or not instructionId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instruction ID cannot be empty"
        )
    
    url = f"{BASE_URL}/instructions/instructions/{instructionId}"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.delete("/instructions/instructions/{instruction_id}")
async def delete_instruction(instruction_id: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Delete a specific instruction."""
    if not instruction_id or not instruction_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instruction ID cannot be empty"
        )
    
    url = f"{BASE_URL}/instructions/instructions/{instruction_id}"
    return await make_request_with_retry("DELETE", url, token)

@dataservice_router.patch("/instructions/instructions/{instruction_id}")
async def update_instruction(
    instruction_id: str,
    instructions_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Update a specific instruction."""
    if not instruction_id or not instruction_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instruction ID cannot be empty"
        )
    
    if not instructions_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instructions details cannot be empty"
        )
    
    url = f"{BASE_URL}/instructions/instructions/{instruction_id}"
    return await make_request_with_retry("PATCH", url, token, instructions_details)

# Examples Endpoints

@dataservice_router.post("/examples/examples/")
async def create_examples(
    examples_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Create new examples."""
    if not examples_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Examples details cannot be empty"
        )
    
    url = f"{BASE_URL}/examples/examples/"
    return await make_request_with_retry("POST", url, token, examples_details)

@dataservice_router.get("/examples/examples/")
async def get_all_examples(domain_id:Optional[str]=None,token: str = Depends(get_token)) -> List[Dict[str, Any]]:
    """Get all examples."""
    url = f"{BASE_URL}/examples/examples/"
    if domain_id:
        params={"domain_id":domain_id}
    else:
        params=None
    return await make_request_with_retry("GET", url, token, params=params)

@dataservice_router.get("/examples/examples/{example_id}")
async def get_example(example_id: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Get a specific example by ID."""
    if not example_id or not example_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Example ID cannot be empty"
        )
    
    url = f"{BASE_URL}/examples/examples/{example_id}"
    return await make_request_with_retry("GET", url, token)

@dataservice_router.delete("/examples/examples/{example_id}")
async def delete_example(example_id: str, token: str = Depends(get_token)) -> Dict[str, Any]:
    """Delete a specific example."""
    if not example_id or not example_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Example ID cannot be empty"
        )
    
    url = f"{BASE_URL}/examples/examples/{example_id}"
    return await make_request_with_retry("DELETE", url, token)

@dataservice_router.patch("/examples/examples/{example_id}")
async def update_example(
    example_id: str,
    examples_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Update a specific example."""
    if not example_id or not example_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Example ID cannot be empty"
        )
    
    if not examples_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Examples details cannot be empty"
        )
    
    url = f"{BASE_URL}/examples/examples/{example_id}"
    return await make_request_with_retry("PATCH", url, token, examples_details)

# Semantics Endpoints

@dataservice_router.post("/semantics/semantics/describe-table")
async def describe_table(
    table_details: Dict[str, Any],
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Describe a table using semantic analysis."""
    if not table_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table details cannot be empty"
        )
    
    url = f"{BASE_URL}/semantics/semantics/describe-table"
    return await make_request_with_retry("POST", url, token, table_details)

@dataservice_router.get("/projects/workflow/workflow/dataset/samples/getTablesData")
async def get_sample_data(dataset_id:str,token: str = Depends(get_token)):
    """Get all instructions."""
    url = f"{BASE_URL}/projects/workflow/workflow/dataset/samples/getTablesData"
    params = {"dataset_id":dataset_id}
    return await make_request_with_retry("GET", url, token, params=params)


@dataservice_router.get("/time-columns/time-columns")
async def get_all_time_columns(token: str = Depends(get_token)):
    """Get all time columns."""
    url = f"{BASE_URL}/time-columns/time-columns"
    return await make_request_with_retry("GET", url, token)
 
@dataservice_router.get("/time-columns/time-columns/{time_column_id}")
async def get_time_column(time_column_id: str, token: str = Depends(get_token)):
    """Get a specific time column."""
    url = f"{BASE_URL}/time-columns/time-columns/{time_column_id}"
    return await make_request_with_retry("GET", url, token)
 
@dataservice_router.delete("/time-columns/time-columns/{time_column_id}")
async def delete_time_column(time_column_id: str, token: str = Depends(get_token)):
    """Delete a specific time column."""
    if not time_column_id or not time_column_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time column ID cannot be empty"
        )
   
    url = f"{BASE_URL}/time-columns/time-columns/{time_column_id}"
    return await make_request_with_retry("DELETE", url, token)
 
 
@dataservice_router.patch("/time-columns/time-columns/{time_column_id}")
async def update_time_column(
    time_column_id: str,
    time_column_details: Dict[str, Any],
    token: str = Depends(get_token)
):
    """Update a specific time column."""
    if not time_column_id or not time_column_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time column ID cannot be empty"
        )
   
    if not time_column_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time column details cannot be empty"
        )
   
    url = f"{BASE_URL}/time-columns/time-columns/{time_column_id}"
    return await make_request_with_retry("PATCH", url, token, time_column_details)
 
 
 
@dataservice_router.post("/time-columns/time-columns")
async def create_time_column(
    time_column_details: List[Dict[str, Any]],
    token: str = Depends(get_token)
):
    """Create new time columns by proxying to the time-column service."""
    try:
        url = f"{BASE_URL}/time-columns/time-columns"

        return await make_request_with_retry(
            method="POST",
            url=url,
            token=token,
            json_data=time_column_details
        )
    except ValidationError as e:
        logger.error(f"Validation error in create_time_column: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid time column details: {str(e)}"
        )
 