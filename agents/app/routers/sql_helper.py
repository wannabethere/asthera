from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
import json
import uuid
from datetime import datetime
from pydantic import BaseModel

from app.services.sql.models import (
    AskRequest,
    AskResultResponse,
)
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/sql-helper", tags=["sql-helper"])

def get_sql_helper_service():
    """Get the SQLHelperService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("sql_helper_service")

# Request models for SQL helper endpoints
class SQLSummaryRequest(BaseModel):
    """Request model for SQL summary and visualization generation."""
    sql: str
    query: str
    project_id: str
    data_description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None

class SQLStreamingRequest(BaseModel):
    """Request model for SQL streaming summary and visualization."""
    sql: str
    query: str
    project_id: str
    data_description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None

class QueryRequirementsRequest(BaseModel):
    """Request model for query requirements analysis."""
    query: str
    project_id: str
    configuration: Optional[Dict[str, Any]] = None
    schema_context: Optional[Dict[str, Any]] = None

class SQLVisualizationRequest(BaseModel):
    """Request model for SQL visualization generation."""
    query: str
    sql_result: Dict[str, Any]
    project_id: str
    chart_config: Optional[Dict[str, Any]] = None
    streaming: bool = False

@router.post("/summary")
async def generate_sql_summary_and_visualization(request: SQLSummaryRequest):
    """Generate SQL summary and visualization using DataSummarizationPipeline."""
    try:
        service = get_sql_helper_service()
        
        # Generate a unique query ID
        query_id = str(uuid.uuid4())
        
        # Call the service method
        result = await service.generate_sql_summary_and_visualization(
            query_id=query_id,
            sql=request.sql,
            query=request.query,
            project_id=request.project_id,
            data_description=request.data_description,
            configuration=request.configuration
        )
        
        return {
            "query_id": query_id,
            "success": result.get("success", False),
            "data": result.get("data", {}),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating SQL summary: {str(e)}")

@router.post("/summary/stream")
async def stream_sql_summary_and_visualization(request: SQLStreamingRequest):
    """Stream SQL summary and visualization using DataSummarizationPipeline with callbacks."""
    try:
        service = get_sql_helper_service()
        
        # Generate a unique query ID
        query_id = str(uuid.uuid4())
        
        async def generate_stream():
            """Generate streaming response."""
            try:
                async for update in service.stream_sql_summary_and_visualization(
                    query_id=query_id,
                    sql=request.sql,
                    query=request.query,
                    project_id=request.project_id,
                    data_description=request.data_description,
                    configuration=request.configuration
                ):
                    # Convert update to JSON string with newline for SSE format
                    yield f"data: {json.dumps(update)}\n\n"
                    
            except Exception as e:
                error_update = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {json.dumps(error_update)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error streaming SQL summary: {str(e)}")

@router.post("/analyze-requirements")
async def analyze_query_requirements(request: QueryRequirementsRequest):
    """Analyze query requirements using SQL expansion and correction pipelines."""
    try:
        service = get_sql_helper_service()
        
        # Generate a unique query ID
        query_id = str(uuid.uuid4())
        
        # Call the service method
        result = await service.analyze_query_requirements(
            query_id=query_id,
            query=request.query,
            project_id=request.project_id,
            configuration=request.configuration,
            schema_context=request.schema_context
        )
        
        return {
            "query_id": query_id,
            "success": result.get("success", False),
            "data": result.get("data", {}),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing query requirements: {str(e)}")

@router.post("/visualization")
async def generate_sql_visualization(request: SQLVisualizationRequest):
    """Generate SQL visualization with data, summary and chart generation."""
    try:
        service = get_sql_helper_service()
        
        # Generate a unique query ID
        query_id = str(uuid.uuid4())
        
        # Create a mock AskRequest for compatibility
        mock_request = AskRequest(
            query=request.query,
            project_id=request.project_id,
            language="English",
            histories=[],
            configuration={}
        )
        
        # Call the service method
        result = await service.generate_sql_visualization(
            query_id=query_id,
            query=request.query,
            sql_result=request.sql_result,
            request=mock_request,
            chart_config=request.chart_config,
            streaming=request.streaming
        )
        
        return {
            "query_id": query_id,
            "success": result.get("success", False),
            "data": result.get("data", {}),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating SQL visualization: {str(e)}")

@router.post("/stop/{query_id}")
def stop_query(query_id: str):
    """Stop an ongoing query process."""
    try:
        service = get_sql_helper_service()
        service.stop_query(query_id)
        return {"success": True, "message": f"Query {query_id} stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping query: {str(e)}")

@router.get("/status/{query_id}")
def get_query_status(query_id: str):
    """Get the status of a query."""
    try:
        service = get_sql_helper_service()
        status = service.get_query_status(query_id)
        return {"query_id": query_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting query status: {str(e)}") 