from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List

from app.services.sql.models import (
    ChartRequest,
    ChartResultRequest,
    ChartResultResponse,
    StopChartRequest
)
from app.services.service_container import SQLServiceContainer

router = APIRouter(prefix="/chart", tags=["chart"])

def get_chart_service():
    """Get the ChartService instance from the service container."""
    container = SQLServiceContainer.get_instance()
    return container.get_service("chart_service")

@router.post("/generate")
async def generate_chart(request: ChartRequest) -> ChartResultResponse:
    """Generate a chart based on the provided data and configuration."""
    service = get_chart_service()
    return await service.process_request(request)

@router.post("/execute")
async def execute_chart_with_sql(
    query: str,
    sql: str,
    project_id: str,
    configuration: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute a chart with SQL data using ChartExecutionPipeline."""
    try:
        service = get_chart_service()
        
        # Get the chart execution pipeline from the service
        chart_execution_pipeline = getattr(service, 'chart_execution_pipeline', None)
        
        if not chart_execution_pipeline:
            raise HTTPException(
                status_code=500,
                detail="Chart execution pipeline not available in service"
            )
        
        # Execute the chart
        result = await chart_execution_pipeline.run(
            query=query,
            sql=sql,
            project_id=project_id,
            configuration=configuration
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing chart: {str(e)}"
        )

@router.post("/result")
def get_chart_result(request: ChartResultRequest) -> ChartResultResponse:
    """Get the result of a chart generation request."""
    service = get_chart_service()
    return service.get_chart_result(request)

@router.post("/stop")
def stop_chart(request: StopChartRequest):
    """Stop an ongoing chart generation process."""
    service = get_chart_service()
    service.stop_chart(request)

@router.post("/render")
async def render_visualization(
    query: str,
    sql: str,
    project_id: str,
    query_id: str,
    configuration: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Render visualization by generating chart schema and executing it with full data."""
    try:
        # Get the SQL helper service from the service container
        container = SQLServiceContainer.get_instance()
        sql_helper_service = container.get_service("sql_helper_service")
        
        if not sql_helper_service:
            raise HTTPException(
                status_code=500,
                detail="SQL helper service not available"
            )
        
        # Render the visualization
        result = await sql_helper_service.render_visualization(
            query_id=query_id,
            query=query,
            sql=sql,
            project_id=project_id,
            configuration=configuration
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error rendering visualization: {str(e)}"
        )

@router.post("/render/stream")
async def stream_visualization_rendering(
    query: str,
    sql: str,
    project_id: str,
    query_id: str,
    configuration: Optional[Dict[str, Any]] = None
):
    """Stream visualization rendering process with real-time updates."""
    try:
        # Get the SQL helper service from the service container
        container = SQLServiceContainer.get_instance()
        sql_helper_service = container.get_service("sql_helper_service")
        
        if not sql_helper_service:
            raise HTTPException(
                status_code=500,
                detail="SQL helper service not available"
            )
        
        # Import StreamingResponse for async streaming
        from fastapi.responses import StreamingResponse
        import json
        
        async def generate_stream():
            """Generate streaming response"""
            async for update in sql_helper_service.stream_visualization_rendering(
                query_id=query_id,
                query=query,
                sql=sql,
                project_id=project_id,
                configuration=configuration
            ):
                yield f"data: {json.dumps(update)}\n\n"
        
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
        raise HTTPException(
            status_code=500,
            detail=f"Error streaming visualization rendering: {str(e)}"
        ) 