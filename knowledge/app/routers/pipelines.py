"""
Pipeline Router

Provides REST and SSE API endpoints for accessing and using async pipelines.
Follows unified architecture: Routers -> Services -> Pipelines
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging

from app.services.pipeline_service import get_pipeline_service
from app.streams.unified_streaming import get_streaming_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pipelines",
    tags=["pipelines"]
)


class PipelineQueryRequest(BaseModel):
    """Request model for pipeline query execution"""
    query: str = Field(..., description="Query to process")
    context: Dict[str, Any] = Field(default_factory=dict, description="Query context")
    options: Dict[str, Any] = Field(default_factory=dict, description="Processing options")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Data filters")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PipelineQueryResponse(BaseModel):
    """Response model for pipeline query execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    pipeline_id: str
    processing_time: Optional[float] = None


@router.get("/")
async def list_pipelines(
    request: Request,
    category: Optional[str] = None,
    active_only: bool = True
):
    """
    List available pipelines
    
    Args:
        category: Optional category filter
        active_only: Only return active pipelines
        
    Returns:
        List of available pipelines
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            raise HTTPException(
                status_code=503,
                detail="Pipeline registry not initialized"
            )
        
        registry = request.app.state.pipeline_registry
        pipelines = registry.list_pipelines(category=category, active_only=active_only)
        
        return {
            "success": True,
            "pipelines": pipelines,
            "count": len(pipelines)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing pipelines: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_categories(request: Request):
    """
    List pipeline categories
    
    Returns:
        List of pipeline categories
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            raise HTTPException(
                status_code=503,
                detail="Pipeline registry not initialized"
            )
        
        registry = request.app.state.pipeline_registry
        categories = registry.list_categories()
        
        return {
            "success": True,
            "categories": categories,
            "count": len(categories)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing categories: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pipeline_id}")
async def get_pipeline_info(
    request: Request,
    pipeline_id: str
):
    """
    Get information about a specific pipeline
    
    Args:
        pipeline_id: Pipeline ID
        
    Returns:
        Pipeline configuration and metadata
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            raise HTTPException(
                status_code=503,
                detail="Pipeline registry not initialized"
            )
        
        registry = request.app.state.pipeline_registry
        config = registry.get_pipeline_config(pipeline_id)
        
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline '{pipeline_id}' not found"
            )
        
        return {
            "success": True,
            "pipeline": {
                "pipeline_id": config.pipeline_id,
                "name": config.name,
                "description": config.description,
                "category": config.category,
                "version": config.version,
                "is_active": config.is_active,
                "metadata": config.metadata,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pipeline_id}/execute")
async def execute_pipeline(
    request: Request,
    pipeline_id: str,
    query_request: PipelineQueryRequest
) -> PipelineQueryResponse:
    """
    Execute a pipeline with the given query
    
    Args:
        pipeline_id: Pipeline ID to execute
        query_request: Query request with query, context, options, etc.
        
    Returns:
        Pipeline execution results
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            raise HTTPException(
                status_code=503,
                detail="Pipeline registry not initialized"
            )
        
        registry = request.app.state.pipeline_registry
        pipeline = registry.get_pipeline(pipeline_id)
        
        if not pipeline:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline '{pipeline_id}' not found or inactive"
            )
        
        # Execute pipeline
        logger.info(f"Executing pipeline '{pipeline_id}' with query: {query_request.query[:100]}")
        
        result = await pipeline.run(
            inputs={
                "query": query_request.query,
                "context": query_request.context,
                "options": query_request.options,
                "filters": query_request.filters,
                "metadata": query_request.metadata
            }
        )
        
        return PipelineQueryResponse(
            success=result.get("success", False),
            data=result.get("data"),
            error=result.get("error"),
            metadata=result.get("metadata"),
            pipeline_id=pipeline_id,
            processing_time=result.get("metadata", {}).get("processing_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing pipeline: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/category/{category}/execute")
async def execute_category_pipeline(
    request: Request,
    category: str,
    query_request: PipelineQueryRequest,
    pipeline_id: Optional[str] = None
) -> PipelineQueryResponse:
    """
    Execute a pipeline from a category (uses default if pipeline_id not provided)
    
    Args:
        category: Pipeline category
        query_request: Query request with query, context, options, etc.
        pipeline_id: Optional specific pipeline ID
        
    Returns:
        Pipeline execution results
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            raise HTTPException(
                status_code=503,
                detail="Pipeline registry not initialized"
            )
        
        registry = request.app.state.pipeline_registry
        pipeline = registry.get_category_pipeline(category, pipeline_id)
        
        if not pipeline:
            raise HTTPException(
                status_code=404,
                detail=f"No active pipeline found for category '{category}'"
            )
        
        # Get pipeline_id for response
        if not pipeline_id:
            category_config = registry._categories.get(category)
            pipeline_id = category_config.default_pipeline_id if category_config else "unknown"
        
        # Execute pipeline
        logger.info(f"Executing category '{category}' pipeline '{pipeline_id}' with query: {query_request.query[:100]}")
        
        result = await pipeline.run(
            inputs={
                "query": query_request.query,
                "context": query_request.context,
                "options": query_request.options,
                "filters": query_request.filters,
                "metadata": query_request.metadata
            }
        )
        
        return PipelineQueryResponse(
            success=result.get("success", False),
            data=result.get("data"),
            error=result.get("error"),
            metadata=result.get("metadata"),
            pipeline_id=pipeline_id,
            processing_time=result.get("metadata", {}).get("processing_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing category pipeline: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/status")
async def pipeline_health_status(request: Request):
    """
    Get health status of pipeline registry
    
    Returns:
        Health status information
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            return {
                "success": False,
                "status": "not_initialized",
                "message": "Pipeline registry not initialized"
            }
        
        registry = request.app.state.pipeline_registry
        
        # Get statistics
        all_pipelines = registry.list_pipelines(active_only=False)
        active_pipelines = registry.list_pipelines(active_only=True)
        categories = registry.list_categories()
        
        # Get initialization results if available
        init_results = {}
        if hasattr(request.app.state, "pipeline_initialization_results"):
            init_results = request.app.state.pipeline_initialization_results
        
        return {
            "success": True,
            "status": "operational",
            "statistics": {
                "total_pipelines": len(all_pipelines),
                "active_pipelines": len(active_pipelines),
                "inactive_pipelines": len(all_pipelines) - len(active_pipelines),
                "categories": len(categories)
            },
            "initialization": init_results,
            "categories": [
                {
                    "category": cat["category_id"],
                    "name": cat["name"],
                    "pipeline_count": cat["pipeline_count"],
                    "default_pipeline": cat["default_pipeline_id"]
                }
                for cat in categories
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting pipeline health status: {str(e)}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# SSE Streaming Endpoints (unified architecture)
# ============================================================================

@router.post("/{pipeline_id}/stream")
async def stream_pipeline_execution(
    request: Request,
    pipeline_id: str,
    query_request: PipelineQueryRequest
):
    """
    Stream pipeline execution with SSE
    
    Args:
        pipeline_id: Pipeline ID to execute
        query_request: Query request with query, context, options, etc.
        
    Returns:
        SSE stream of execution events
    """
    try:
        # Get services
        pipeline_service = get_pipeline_service()
        streaming_service = get_streaming_service()
        
        logger.info(f"Starting SSE stream for pipeline: {pipeline_id}")
        
        # Create event generator
        async def event_generator():
            """Generate SSE events from pipeline execution"""
            async for event in streaming_service.stream_pipeline_execution(
                pipeline_service=pipeline_service,
                pipeline_id=pipeline_id,
                inputs={
                    "query": query_request.query,
                    "context": query_request.context,
                    "options": query_request.options,
                    "filters": query_request.filters,
                    "metadata": query_request.metadata
                }
            ):
                yield event
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting pipeline stream: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/category/{category}/stream")
async def stream_category_pipeline(
    request: Request,
    category: str,
    query_request: PipelineQueryRequest,
    pipeline_id: Optional[str] = None
):
    """
    Stream pipeline execution from category with SSE
    
    Args:
        category: Pipeline category
        query_request: Query request with query, context, options, etc.
        pipeline_id: Optional specific pipeline ID
        
    Returns:
        SSE stream of execution events
    """
    try:
        if not hasattr(request.app.state, "pipeline_registry"):
            raise HTTPException(
                status_code=503,
                detail="Pipeline registry not initialized"
            )
        
        registry = request.app.state.pipeline_registry
        pipeline = registry.get_category_pipeline(category, pipeline_id)
        
        if not pipeline:
            raise HTTPException(
                status_code=404,
                detail=f"No pipeline found for category '{category}'"
            )
        
        # Get actual pipeline ID
        actual_pipeline_id = None
        for pid, config in registry._pipelines.items():
            if config.pipeline == pipeline:
                actual_pipeline_id = pid
                break
        
        if not actual_pipeline_id:
            actual_pipeline_id = category
        
        logger.info(f"Starting SSE stream for category: {category} -> {actual_pipeline_id}")
        
        # Get services
        pipeline_service = get_pipeline_service()
        streaming_service = get_streaming_service()
        
        # Create event generator
        async def event_generator():
            """Generate SSE events from pipeline execution"""
            async for event in streaming_service.stream_pipeline_execution(
                pipeline_service=pipeline_service,
                pipeline_id=actual_pipeline_id,
                inputs={
                    "query": query_request.query,
                    "context": query_request.context,
                    "options": query_request.options,
                    "filters": query_request.filters,
                    "metadata": {**query_request.metadata, "category": category}
                }
            ):
                yield event
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting category pipeline stream: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
