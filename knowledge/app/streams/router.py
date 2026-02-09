"""
FastAPI router for graph streaming endpoints
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig

from app.streams.streaming_service import GraphStreamingService
from app.streams.graph_registry import GraphRegistry, get_registry
from app.streams.models import (
    GraphInvokeRequest,
    AssistantCreateRequest,
    GraphRegisterRequest,
    AssistantListResponse,
    GraphListResponse,
    AssistantInfo,
    GraphInfo
)

router = APIRouter(prefix="/streams", tags=["Graph Streaming"])


def get_streaming_service() -> GraphStreamingService:
    """Dependency to get streaming service"""
    registry = get_registry()
    return GraphStreamingService(registry=registry)


def get_registry_dep() -> GraphRegistry:
    """Dependency to get graph registry"""
    return get_registry()


@router.post("/invoke")
async def invoke_graph_stream(
    request: GraphInvokeRequest,
    service: GraphStreamingService = Depends(get_streaming_service)
):
    """
    Invoke a graph and stream execution events via SSE
    
    This endpoint streams real-time updates as the graph executes,
    including node starts/completions, state updates, and final results.
    """
    # Generate session_id if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    # Prepare input data
    input_data = request.input_data or {}
    if "query" not in input_data:
        input_data["query"] = request.query
    
    # Prepare config
    config: Optional[RunnableConfig] = None
    if request.config:
        config = request.config
    
    async def event_stream():
        try:
            async for event in service.stream_with_keepalive(
                assistant_id=request.assistant_id,
                graph_id=request.graph_id,
                input_data=input_data,
                session_id=session_id,
                config=config,
                keepalive_interval=30.0
            ):
                yield event
        except Exception as e:
            # Send error event
            from .events import GraphErrorEvent, format_sse_event
            error_event = GraphErrorEvent(
                session_id=session_id,
                assistant_id=request.assistant_id,
                graph_id=request.graph_id,
                error=str(e),
                error_type=type(e).__name__
            )
            yield format_sse_event(error_event)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/assistants", response_model=AssistantInfo)
async def create_assistant(
    request: AssistantCreateRequest,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """Create a new assistant"""
    try:
        assistant = registry.register_assistant(
            assistant_id=request.assistant_id,
            name=request.name,
            description=request.description,
            metadata=request.metadata
        )
        return AssistantInfo(
            assistant_id=assistant.assistant_id,
            name=assistant.name,
            description=assistant.description,
            graph_count=len(assistant.graphs),
            default_graph_id=assistant.default_graph_id,
            metadata=assistant.metadata
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/assistants", response_model=AssistantListResponse)
async def list_assistants(
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """List all assistants"""
    assistants_data = registry.list_assistants()
    assistants = [
        AssistantInfo(**data) for data in assistants_data
    ]
    return AssistantListResponse(assistants=assistants)


@router.get("/assistants/{assistant_id}", response_model=AssistantInfo)
async def get_assistant(
    assistant_id: str,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """Get assistant information"""
    assistant = registry.get_assistant(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")
    
    return AssistantInfo(
        assistant_id=assistant.assistant_id,
        name=assistant.name,
        description=assistant.description,
        graph_count=len(assistant.graphs),
        default_graph_id=assistant.default_graph_id,
        metadata=assistant.metadata
    )


@router.get("/assistants/{assistant_id}/graphs", response_model=GraphListResponse)
async def list_assistant_graphs(
    assistant_id: str,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """List all graphs for an assistant"""
    graphs_data = registry.list_assistant_graphs(assistant_id)
    if graphs_data is None:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")
    
    graphs = [GraphInfo(**data) for data in graphs_data]
    return GraphListResponse(assistant_id=assistant_id, graphs=graphs)


@router.delete("/assistants/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """Delete an assistant and all its graphs"""
    success = registry.unregister_assistant(assistant_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")
    return {"message": f"Assistant {assistant_id} deleted"}


@router.delete("/assistants/{assistant_id}/graphs/{graph_id}")
async def delete_graph(
    assistant_id: str,
    graph_id: str,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """Delete a graph from an assistant"""
    success = registry.unregister_graph(assistant_id, graph_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Graph {graph_id} not found for assistant {assistant_id}"
        )
    return {"message": f"Graph {graph_id} deleted from assistant {assistant_id}"}


# Note: Graph registration should be done programmatically via the registry
# since we can't serialize LangGraph objects over HTTP
# This endpoint is for metadata updates only
@router.patch("/assistants/{assistant_id}/graphs/{graph_id}")
async def update_graph_metadata(
    assistant_id: str,
    graph_id: str,
    request: GraphRegisterRequest,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """Update graph metadata (graph object itself must be registered programmatically)"""
    graph_config = registry.get_assistant_graph(assistant_id, graph_id)
    if not graph_config:
        raise HTTPException(
            status_code=404,
            detail=f"Graph {graph_id} not found for assistant {assistant_id}"
        )
    
    # Update metadata
    if request.name:
        graph_config.name = request.name
    if request.description is not None:
        graph_config.description = request.description
    if request.metadata:
        graph_config.metadata.update(request.metadata)
    if request.set_as_default:
        assistant = registry.get_assistant(assistant_id)
        if assistant:
            assistant.default_graph_id = graph_id
    
    return {"message": f"Graph {graph_id} metadata updated"}

