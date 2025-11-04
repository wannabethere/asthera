from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Query, Body, File, UploadFile, Form, FastAPI
)
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel
import logging
import traceback
from httpx import AsyncClient, HTTPStatusError, ConnectError, RequestError
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router and Security Initialization ---
document_upload_router = APIRouter()
security = HTTPBearer()

# --- Constants ---
BASE_URL = "http://ec2-18-204-196-65.compute-1.amazonaws.com:8035"
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# --- Allowed Document Types ---
DocumentTypeLiteral = Literal[
    "gong_transcript", "slack_conversation", "contract", "generic",
    "extensive_call", "docs_documentation", "financial_report",
    "business_document", "pdf_document", "text_document",
    "json_document", "word_document", "google_document", "wiki_document"
]

# --- Pydantic Models for Request Bodies ---
class DocumentSearchPayload(BaseModel):
    """Defines the expected data structure for a document search request."""
    query: str
    document_type: DocumentTypeLiteral = "generic"
    source_type: str = "string"
    domain_id: str = "default_domain"
    limit: int = 10
    use_tfidf: bool = True

# --- Helper Functions ---
def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extracts and validates the bearer token."""
    if not credentials or not credentials.credentials:
        logger.warning("Missing or invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

@asynccontextmanager
async def get_http_client():
    """Provides an async HTTP client with limits and no timeout."""
    async with AsyncClient(
        verify=False,
        timeout=None,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    ) as client:
        yield client

async def make_request_with_retry(
    method: str,
    url: str,
    token: Optional[str] = None,
    json_data: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Makes an HTTP request with retry logic and proper error handling."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_data:
        headers["Content-Type"] = "application/json"

    last_exception = None
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
                    params=params
                )
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError:
                    logger.error(f"Invalid JSON response from {url}")
                    return {"message": "Invalid JSON response from server", "status_code": response.status_code}
        except HTTPStatusError as e:
            last_exception = e
            status_code = e.response.status_code
            if status_code in [401, 403, 404] or status_code < 500:
                logger.error(f"Client-side HTTP error {status_code} for {url}: {e.response.text}")
                raise HTTPException(status_code=status_code, detail=f"Upstream service error: {e.response.text}")
            logger.warning(f"Server error {status_code} for {url}, attempt {attempt + 1}/{MAX_RETRIES + 1}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
            else:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream service temporarily unavailable")
        except (ConnectError, RequestError) as e:
            last_exception = e
            logger.warning(f"Network error for {url}, attempt {attempt + 1}/{MAX_RETRIES + 1}: {str(e)}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
            else:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to connect to upstream service")
        except Exception as e:
            last_exception = e
            logger.error(f"Unexpected error for {url}: {traceback.format_exc()}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Request failed after all retries")

# --- Document Endpoints ---
@document_upload_router.post("/documents/")
async def upload_document(
    token: str = Depends(get_token),
    file: UploadFile = File(...),
    document_type: DocumentTypeLiteral = Form(...),
    test_mode: str = Form("disabled"),
    user_context: str = Form("string"),
    questions: str = Form("string"),
    domain_id: str = Form("default_domain"),
    created_by: str = Form("api_user")
) -> Dict[str, Any]:
    """Uploads a document with streaming to avoid memory issues."""
    url = f"{BASE_URL}/documents/"
    form_data = {
        "document_type": document_type,
        "test_mode": test_mode,
        "user_context": user_context,
        "questions": questions,
        "domain_id": domain_id,
        "created_by": created_by,
    }
    # Stream the file directly
    files = {"file": (file.filename, file.file, file.content_type)}
    return await make_request_with_retry("POST", url, token=token, data=form_data, files=files)

@document_upload_router.get("/documents/{document_type}/all")
async def get_all_documents_by_type(
    document_type: DocumentTypeLiteral,
    token: str = Depends(get_token)
) -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/documents/{document_type}/all"
    return await make_request_with_retry("GET", url, token=token)

@document_upload_router.get("/documents/{document_type}/schemas")
async def get_document_schemas(
    document_type: DocumentTypeLiteral,
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    url = f"{BASE_URL}/documents/{document_type}/schemas"
    return await make_request_with_retry("GET", url, token=token)

@document_upload_router.get("/documents/{document_type}/{document_id}")
async def get_document_by_id(
    document_type: DocumentTypeLiteral,
    document_id: str,
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    url = f"{BASE_URL}/documents/{document_type}/{document_id}"
    return await make_request_with_retry("GET", url, token=token)

@document_upload_router.delete("/documents/{document_type}/{document_id}")
async def delete_document(
    document_type: DocumentTypeLiteral,
    document_id: str,
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    url = f"{BASE_URL}/documents/{document_type}/{document_id}"
    return await make_request_with_retry("DELETE", url, token=token)

@document_upload_router.post("/documents/search")
async def search_documents(
    payload: DocumentSearchPayload = Body(...),
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    """Search documents with JSON payload (safe for API)."""
    url = f"{BASE_URL}/documents/search"
    search_data = payload.model_dump()  # JSON-safe
    return await make_request_with_retry("POST", url, token=token, json_data=search_data)

@document_upload_router.get("/documents/insights/{document_id}")
async def get_document_insights(
    document_id: str,
    token: str = Depends(get_token)
) -> Dict[str, Any]:
    url = f"{BASE_URL}/documents/insights/{document_id}"
    return await make_request_with_retry("GET", url, token=token)
