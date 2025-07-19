import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import asyncio
import json
import sys
import logging

from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Configuration via ENV ─────────────────────────────────────────────────────
AIRBYTE_API_URL = os.getenv("AIRBYTE_API_URL", "https://airbyte.app.tellius.com")
AIRBYTE_API_TOKEN = os.getenv("AIRBYTE_API_TOKEN", None)
AIRBYTE_WORKSPACE_ID = os.getenv("AIRBYTE_WORKSPACE_ID", "5c99e616-3f0c-458a-89f5-f074ab3f5d7b")

# Source Definition IDs
SOURCE_DEFINITIONS = {
    "gong": "32382e40-3b49-4b99-9c5c-4076501914e7",
    "s3": "69589781-7828-43c5-9f63-8925b1c1ccc2",
    "google_drive": "9f8dda77-1048-4368-815b-269bf54ee9b8",
    "salesforce": "b117307c-14b6-41aa-9422-947e34922962"
}

# ── FastAPI Setup ─────────────────────────────────────────────────────────────
app = FastAPI(title="Connector Sync Service")

# ── Request / Response DTOs ───────────────────────────────────────────────────
class SyncConnectionRequest(BaseModel):
    connector_name: str
    connector_type: str
    description: Optional[str] = None
    config: Dict[str, Any]

class SyncConnectionResponse(BaseModel):
    connector_name: str
    connector_type: str
    description: Optional[str] = None
    config: Dict[str, Any]
    source_id: str

class CheckConnectionRequest(BaseModel):
    source_id: str

class CheckConnectionResponse(BaseModel):
    status: str
    job_info: Optional[Dict[str, Any]] = None

async def check_connection(request: CheckConnectionRequest):
    """Check the status of a connection in Airbyte"""
    try:
        logger.info(f"Starting connection check for source_id: {request.source_id}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": AIRBYTE_API_URL,
                "Referer": f"{AIRBYTE_API_URL}/workspaces/{AIRBYTE_WORKSPACE_ID}/source",
                "x-airbyte-analytic-source": "webapp"
            }
            if AIRBYTE_API_TOKEN:
                headers["Authorization"] = f"Bearer {AIRBYTE_API_TOKEN}"
                logger.info("Using authentication token")
            else:
                logger.warning("No authentication token provided")
            
            logger.info(f"Making request to {AIRBYTE_API_URL}/api/v1/sources/check_connection")
            # Call Airbyte API to check connection
            try:
                response = await client.post(
                    f"{AIRBYTE_API_URL}/api/v1/sources/check_connection",
                    headers=headers,
                    json={"sourceId": request.source_id},
                    timeout=30.0
                )
                
                logger.info(f"Received response with status code: {response.status_code}")
                
                if response.status_code != 200:
                    error_detail = f"Failed to check connection status: {response.text}"
                    logger.error(error_detail)
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )
                
                result = response.json()
                logger.info(f"Connection check result: {result.get('status')}")
                
                return CheckConnectionResponse(
                    status=result.get("status"),
                    job_info=result.get("jobInfo")
                )
            except httpx.RequestError as e:
                error_msg = f"HTTP request error when checking connection: {str(e)}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        error_msg = f"Unexpected error checking connection: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

async def create_sync_connection(request: SyncConnectionRequest):
    """Create a new sync connection in Airbyte"""
    try:
        # Create source in Airbyte
        async with httpx.AsyncClient() as client:
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": AIRBYTE_API_URL,
                "Referer": f"{AIRBYTE_API_URL}/workspaces/{AIRBYTE_WORKSPACE_ID}/source/new-source/{SOURCE_DEFINITIONS.get(request.connector_type.lower())}",
                "x-airbyte-analytic-source": "webapp"
            }
            if AIRBYTE_API_TOKEN:
                headers["Authorization"] = f"Bearer {AIRBYTE_API_TOKEN}"
            
            # Get source definition ID
            source_def_id = SOURCE_DEFINITIONS.get(request.connector_type.lower())
            if not source_def_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source definition ID not found for connector type: {request.connector_type}. Supported types: {list(SOURCE_DEFINITIONS.keys())}"
                )
            
            # Transform config keys if needed
            config = {}
            if request.connector_type.lower() == "gong":
                # Handle Gong config
                config = {
                    "access_key": request.config.get("gong_access_key", request.config.get("access_key")),
                    "access_key_secret": request.config.get("gong_access_key_secret", request.config.get("access_key_secret"))
                }
                if "start_date" in request.config:
                    config["start_date"] = request.config["start_date"]
                
                logger.info(f"Transformed Gong config: {json.dumps(config, indent=2)}")
                
            elif request.connector_type.lower() == "s3":
                # Handle S3 config
                config = {
                    "sourceType": request.config.get("sourceType", "s3"),
                    "streams": request.config["streams"],
                    "bucket": request.config["bucket"],
                    "aws_access_key_id": request.config["aws_access_key_id"],
                    "aws_secret_access_key": request.config["aws_secret_access_key"],
                    "region_name": request.config["region_name"]
                }
                # Add optional fields
                if "role_arn" in request.config:
                    config["role_arn"] = request.config["role_arn"]
                if "endpoint" in request.config:
                    config["endpoint"] = request.config["endpoint"]
                    
                logger.info(f"Transformed S3 config: {json.dumps(config, indent=2)}")
                
            elif request.connector_type.lower() == "google_drive":
                # Handle Google Drive config

                credentials = request.config.get("credentials", {})
                service_account_info_raw = credentials.get("service_account_info")

                try:
                    if isinstance(service_account_info_raw, dict):
                        service_account_info = json.dumps(service_account_info_raw)
                        logger.info("Converted service_account_info dict to JSON string.")
                    elif isinstance(service_account_info_raw, str):
                        service_account_info = service_account_info_raw  # Assume it's already valid
                        logger.info("Using pre-validated stringified service_account_info.")
                    else:
                        raise ValueError("service_account_info must be a dict or a valid JSON string.")
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid service_account_info format: {str(e)}"
                    )

                # Prepare streams configuration
                streams = request.config.get("streams", [])

                config = {
                    "streams": streams,
                    "credentials": {
                        "auth_type": credentials.get("auth_type", "Service"),
                        "service_account_info": service_account_info
                    },
                    "folder_url": request.config.get("folder_url")
                }

                # Add optional delivery method if present
                if "delivery_method" in request.config:
                    config["delivery_method"] = request.config["delivery_method"]

                logger.info(f"Transformed Google Drive config: {json.dumps({**config, 'credentials': {'auth_type': 'Service', 'service_account_info': '***REDACTED***'}}, indent=2)}")
                
            elif request.connector_type.lower() == "salesforce":
                # Handle Salesforce config
                config = {
                    "client_id": request.config["client_id"],
                    "client_secret": request.config["client_secret"],
                    "refresh_token": request.config["refresh_token"]
                }
                # Add optional fields
                if "start_date" in request.config:
                    config["start_date"] = request.config["start_date"]
                if "streams_criteria" in request.config:
                    config["streams_criteria"] = request.config["streams_criteria"]
                    
                logger.info(f"Transformed Salesforce config: {json.dumps(config, indent=2)}")
                
            else:
                config = request.config
            
            # Create source directly with known source definition ID
            source_response = await client.post(
                f"{AIRBYTE_API_URL}/api/v1/sources/create",
                headers=headers,
                json={
                    "name": request.connector_name,
                    "sourceDefinitionId": source_def_id,
                    "workspaceId": AIRBYTE_WORKSPACE_ID,
                    "connectionConfiguration": config
                }
            )
            
            print(f"Response status: {source_response.status_code}")
            print(f"Response headers: {source_response.headers}")
            print(f"Response text: {source_response.text[:500]}...")
            
            if source_response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create Airbyte source: {source_response.text}"
                )
            
            source_data = source_response.json()
            logger.info(f"Created Airbyte source: {source_data}")
            
            return SyncConnectionResponse(
                connector_name=request.connector_name,
                connector_type=request.connector_type,
                description=request.description,
                config=config,
                source_id=source_data["sourceId"]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete a source from Airbyte"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": AIRBYTE_API_URL,
                "Referer": f"{AIRBYTE_API_URL}/workspaces/{AIRBYTE_WORKSPACE_ID}/source/{source_id}",
                "x-airbyte-analytic-source": "webapp"
            }
            if AIRBYTE_API_TOKEN:
                headers["Authorization"] = f"Bearer {AIRBYTE_API_TOKEN}"
            
            response = await client.post(
                f"{AIRBYTE_API_URL}/api/v1/sources/delete",
                headers=headers,
                json={"sourceId": source_id}
            )
            
            if response.status_code == 404 or (
                response.status_code == 500 
                and "Could not find configuration for SOURCE_CONNECTION" in response.text
            ):
                # Source doesn't exist in Airbyte - consider this a success
                logger.warning(f"Source {source_id} not found in Airbyte, considering delete successful")
                return {"message": f"Source {source_id} no longer exists"}
            elif response.status_code != 204:
                logger.error(f"Failed to delete source {source_id}. Status: {response.status_code}, Response: {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete Airbyte source: {response.text}"
                )
            
            logger.info(f"Successfully deleted source {source_id}")
            return {"message": f"Source {source_id} deleted successfully"}
            
    except Exception as e:
        logger.error(f"Error deleting source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def test_create_source(input_json: Dict[str, Any]):
    """Test function to create a source using input JSON"""
    try:
        # Create request object from input JSON
        test_request = SyncConnectionRequest(**input_json)
        
        response = await create_sync_connection(test_request)
        print("\nSuccessfully created source:")
        print(f"Name: {response.connector_name}")
        print(f"Type: {response.connector_type}")
        print(f"Description: {response.description}")
        print(f"Config: {json.dumps(response.config, indent=2)}")
    except HTTPException as e:
        print(f"\nError creating source: {e.detail}")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")

def print_usage():
    print("\nUsage:")
    print("python airbyte_sync_service.py '<json_input>'")
    print("\nExample:")
    print('''python airbyte_sync_service.py '{
    "connector_name": "Gong Integration",
    "connector_type": "gong",
    "description": "Test Gong connection",
    "config": {
        "access_key": "your_key",
        "access_key_secret": "your_secret"
    }
}'
    ''')

if __name__ == "__main__":
    # Check if JSON input is provided
    if len(sys.argv) < 2:
        print("\nError: Please provide the JSON input as a command line argument")
        print_usage()
        exit(1)
        
    try:
        # Parse JSON input
        input_json = json.loads(sys.argv[1])
        
        print(f"\nUsing Airbyte API URL: {AIRBYTE_API_URL}")
        print(f"Using Workspace ID: {AIRBYTE_WORKSPACE_ID}")
        print("Authentication: " + ("Enabled" if AIRBYTE_API_TOKEN else "Disabled"))
        print(f"\nCreating source with input:\n{json.dumps(input_json, indent=2)}")
        
        # Run the test
        asyncio.run(test_create_source(input_json))
    except json.JSONDecodeError as e:
        print(f"\nError: Invalid JSON input - {str(e)}")
        print_usage()
        exit(1)