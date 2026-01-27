"""
Streaming Router for Graph Execution

This router provides SSE (Server-Sent Events) endpoints for streaming
LangGraph execution with real-time updates.
"""
import uuid
import logging
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
    GraphInfo,
    AskRequest,
    AskResponse,
    MCPRequest,
    MCPResponse,
    MCPError
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/streams", tags=["Graph Streaming"])


@router.get("/health")
async def streaming_health():
    """Health check endpoint for streaming router"""
    try:
        registry = get_registry()
        assistant_count = len(registry.list_assistants()) if registry else 0
        return {
            "status": "ok",
            "router": "streaming",
            "assistants_count": assistant_count,
            "registry_available": registry is not None
        }
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {
            "status": "error",
            "router": "streaming",
            "error": str(e)
        }


def get_streaming_service() -> GraphStreamingService:
    """Dependency to get streaming service"""
    registry = get_registry()
    return GraphStreamingService(registry=registry)


def get_registry_dep(request: Request) -> GraphRegistry:
    """Dependency to get graph registry from app state or global"""
    try:
        # Try to get from app state first (preferred)
        if hasattr(request.app.state, 'graph_registry') and request.app.state.graph_registry:
            logger.debug("Using registry from app.state")
            return request.app.state.graph_registry
        
        # Fallback to global registry
        registry = get_registry()
        if registry is None:
            logger.warning("Registry is None, creating new instance")
            from app.streams.graph_registry import GraphRegistry
            return GraphRegistry()
        return registry
    except Exception as e:
        logger.error(f"Error getting registry: {e}", exc_info=True)
        # Return a new empty registry as fallback
        from app.streams.graph_registry import GraphRegistry
        return GraphRegistry()


@router.post("/invoke")
async def invoke_graph_stream(
    request: GraphInvokeRequest,
    service: GraphStreamingService = Depends(get_streaming_service),
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """
    Invoke a graph and stream execution events via SSE
    
    This endpoint streams real-time updates as the graph executes,
    including node starts/completions, state updates, and final results.
    
    **Request Body:**
    - `assistant_id`: ID of the assistant (required)
    - `graph_id`: ID of the graph (optional, uses default if not provided)
    - `query`: User query/input (required)
    - `session_id`: Session/thread ID (optional, auto-generated if not provided)
    - `input_data`: Additional input data (optional)
    - `config`: LangGraph config overrides (optional)
    
    **Response:**
    Server-Sent Events stream with the following event types:
    - `graph_started`: Graph execution begins
    - `node_started`: A node begins execution
    - `node_completed`: A node completes execution
    - `state_update`: Graph state is updated
    - `progress`: Progress update (0.0 to 1.0)
    - `result`: Final result data
    - `graph_completed`: Graph execution completes
    - `graph_error`: Graph execution fails
    - `node_error`: Node execution fails
    - `keep_alive`: Keep-alive ping (every 30 seconds)
    """
    logger.info(f"Received invoke request: assistant_id={request.assistant_id}, graph_id={request.graph_id}, query_length={len(request.query) if request.query else 0}")
    
    # Validate assistant exists before starting stream
    assistant = registry.get_assistant(request.assistant_id)
    if not assistant:
        logger.error(f"Assistant not found: {request.assistant_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Assistant '{request.assistant_id}' not found. Available assistants: {[a['assistant_id'] for a in registry.list_assistants()]}"
        )
    
    # Validate graph exists (if specified) or default graph exists
    graph_id = request.graph_id or assistant.default_graph_id
    if not graph_id:
        logger.error(f"No graph_id available for assistant: {request.assistant_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Assistant '{request.assistant_id}' has no graphs and no graph_id was specified"
        )
    
    logger.info(f"Using graph_id={graph_id} for assistant_id={request.assistant_id}")
    
    graph_config = registry.get_assistant_graph(request.assistant_id, graph_id)
    if not graph_config:
        available_graphs = [g["graph_id"] for g in (registry.list_assistant_graphs(request.assistant_id) or [])]
        logger.error(f"Graph not found: assistant_id={request.assistant_id}, graph_id={graph_id}, available={available_graphs}")
        raise HTTPException(
            status_code=404,
            detail=f"Graph '{graph_id}' not found for assistant '{request.assistant_id}'. Available graphs: {available_graphs}"
        )
    
    if not graph_config.graph:
        logger.error(f"Graph not initialized: assistant_id={request.assistant_id}, graph_id={graph_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Graph '{graph_id}' for assistant '{request.assistant_id}' is not properly initialized"
        )
    
    # Generate session_id if not provided
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Starting stream for session_id={session_id}")
    
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
            logger.info(f"Starting event stream for session_id={session_id}")
            async for event in service.stream_with_keepalive(
                assistant_id=request.assistant_id,
                graph_id=graph_id,  # Use resolved graph_id instead of request.graph_id
                input_data=input_data,
                session_id=session_id,
                config=config,
                keepalive_interval=30.0
            ):
                yield event
        except Exception as e:
            logger.error(f"Error in event stream for session_id={session_id}: {e}", exc_info=True)
            # Send error event
            from app.streams.events import GraphErrorEvent, format_sse_event
            error_event = GraphErrorEvent(
                session_id=session_id,
                assistant_id=request.assistant_id,
                graph_id=graph_id,
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
    """
    Create a new assistant
    
    An assistant can have multiple graphs configured to it.
    Each assistant has a default graph that is used when no graph_id is specified.
    """
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
    """
    List all registered assistants
    
    Returns a list of all assistants with their metadata and graph counts.
    """
    try:
        logger.info("Listing assistants...")
        if not registry:
            logger.warning("Registry is None, returning empty list")
            return AssistantListResponse(assistants=[])
        
        assistants_data = registry.list_assistants()
        logger.info(f"Found {len(assistants_data)} assistants")
        
        assistants = []
        for data in assistants_data:
            try:
                assistant_info = AssistantInfo(**data)
                assistants.append(assistant_info)
            except Exception as e:
                logger.error(f"Error creating AssistantInfo from data {data}: {e}")
                # Skip invalid assistant data but continue
                continue
        
        logger.info(f"Returning {len(assistants)} valid assistants")
        return AssistantListResponse(assistants=assistants)
    except Exception as e:
        logger.error(f"Error listing assistants: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listing assistants: {str(e)}"
        )


@router.get("/assistants/{assistant_id}", response_model=AssistantInfo)
async def get_assistant(
    assistant_id: str,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """
    Get assistant information by ID
    
    Returns detailed information about a specific assistant including
    its graphs and configuration.
    """
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
    """
    List all graphs configured for an assistant
    
    Returns a list of all graphs registered to the specified assistant,
    including which one is the default.
    """
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
    """
    Delete an assistant and all its graphs
    
    This permanently removes the assistant and all graphs associated with it.
    """
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
    """
    Delete a graph from an assistant
    
    Removes a specific graph from an assistant. If it was the default graph,
    another graph will be selected as default (if available).
    """
    success = registry.unregister_graph(assistant_id, graph_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Graph {graph_id} not found for assistant {assistant_id}"
        )
    return {"message": f"Graph {graph_id} deleted from assistant {assistant_id}"}


@router.patch("/assistants/{assistant_id}/graphs/{graph_id}")
async def update_graph_metadata(
    assistant_id: str,
    graph_id: str,
    request: GraphRegisterRequest,
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """
    Update graph metadata
    
    Updates the metadata for a graph (name, description, etc.).
    Note: The graph object itself must be registered programmatically,
    as LangGraph objects cannot be serialized over HTTP.
    """
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


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    service: GraphStreamingService = Depends(get_streaming_service),
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """
    Ask a question using an assistant agent with a dataset
    
    This endpoint provides a simple question-answer interface that:
    - Accepts a question, dataset identifier, and optional agent
    - Executes the assistant graph with the provided context
    - Returns the final answer (non-streaming)
    
    **Request Body:**
    - `question`: The question to ask (required)
    - `dataset`: Dataset identifier - ID, name, or metadata (required)
    - `agent`: Assistant ID (optional, uses default assistant if not provided)
    - `session_id`: Session/thread ID (optional, auto-generated if not provided)
    - `dataset_metadata`: Additional dataset metadata (optional)
    
    **Response:**
    - `answer`: The answer from the assistant
    - `agent_used`: The assistant ID that was used
    - `session_id`: Session ID for this conversation
    - `metadata`: Additional metadata (sources, confidence, etc.)
    """
    logger.info(f"Received ask request: question_length={len(request.question)}, dataset={request.dataset}, agent={request.agent}")
    
    # Determine which assistant to use
    assistant_id = request.agent
    if not assistant_id:
        # Use default assistant - get first available assistant
        assistants = registry.list_assistants()
        if not assistants:
            raise HTTPException(
                status_code=404,
                detail="No assistants available. Please specify an agent or register an assistant first."
            )
        # Use the first operational assistant
        assistant_id = assistants[0]["assistant_id"]
        logger.info(f"No agent specified, using default assistant: {assistant_id}")
    
    # Validate assistant exists
    assistant = registry.get_assistant(assistant_id)
    if not assistant:
        available_assistants = [a["assistant_id"] for a in registry.list_assistants()]
        logger.error(f"Assistant not found: {assistant_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Assistant '{assistant_id}' not found. Available assistants: {available_assistants}"
        )
    
    # Get default graph for assistant
    graph_id = assistant.default_graph_id
    if not graph_id:
        raise HTTPException(
            status_code=400,
            detail=f"Assistant '{assistant_id}' has no default graph configured"
        )
    
    # Generate session_id if not provided
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Using assistant={assistant_id}, graph={graph_id}, session_id={session_id}")
    
    # Prepare input data with question and dataset
    input_data = {
        "query": request.question,
        "dataset": request.dataset,
        "dataset_metadata": request.dataset_metadata or {}
    }
    
    # Execute graph and collect final result
    try:
        final_answer = None
        final_state = {}
        metadata = {}
        
        # Stream execution and collect final result
        async for event_str in service.stream_graph_execution(
            assistant_id=assistant_id,
            graph_id=graph_id,
            input_data=input_data,
            session_id=session_id,
            config=None
        ):
            # Parse SSE event to extract result
            if "event: result" in event_str or '"event_type":"result"' in event_str:
                try:
                    # Extract data from SSE format
                    import json
                    lines = event_str.strip().split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            data_str = line[6:]  # Remove 'data: ' prefix
                            event_data = json.loads(data_str)
                            if event_data.get("event_type") == "result":
                                result_data = event_data.get("result", {})
                                final_answer = result_data.get("final_answer") or result_data.get("answer") or str(result_data)
                                metadata = event_data.get("metadata", {})
                                break
                except Exception as e:
                    logger.debug(f"Could not parse result event: {e}")
            
            # Also check for graph_completed event for final state
            if '"event_type":"graph_completed"' in event_str:
                try:
                    import json
                    lines = event_str.strip().split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            data_str = line[6:]
                            event_data = json.loads(data_str)
                            if event_data.get("event_type") == "graph_completed":
                                final_state = event_data.get("final_state", {})
                                if not final_answer:
                                    final_answer = final_state.get("final_answer") or final_state.get("answer") or ""
                                break
                except Exception as e:
                    logger.debug(f"Could not parse completion event: {e}")
        
        # If we didn't get an answer from events, try to get final state directly
        if not final_answer:
            try:
                graph_config = registry.get_assistant_graph(assistant_id, graph_id)
                if graph_config and graph_config.graph:
                    state_obj = graph_config.graph.get_state(config={"configurable": {"thread_id": session_id}})
                    final_state = state_obj.values if hasattr(state_obj, "values") else {}
                    if callable(final_state):
                        final_state = final_state()
                    if not isinstance(final_state, dict):
                        final_state = state_obj.model_dump() if hasattr(state_obj, "model_dump") else {}
                    final_answer = final_state.get("final_answer") or final_state.get("answer") or ""
            except Exception as e:
                logger.warning(f"Could not retrieve final state: {e}")
        
        # If still no answer, provide a default
        if not final_answer:
            final_answer = "I processed your question but couldn't generate a complete answer. Please check the metadata for details."
            metadata["warning"] = "Answer extraction may have failed"
        
        return AskResponse(
            answer=final_answer,
            agent_used=assistant_id,
            session_id=session_id,
            metadata={
                "dataset": request.dataset,
                "graph_id": graph_id,
                "assistant_name": assistant.name,
                **metadata
            }
        )
        
    except Exception as e:
        logger.error(f"Error executing ask request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing question: {str(e)}"
        )


@router.post("/mcp", response_model=MCPResponse)
async def mcp_endpoint(
    request: MCPRequest,
    service: GraphStreamingService = Depends(get_streaming_service),
    registry: GraphRegistry = Depends(get_registry_dep)
):
    """
    MCP (Model Context Protocol) server endpoint
    
    This endpoint implements the JSON-RPC 2.0 protocol for MCP clients.
    It supports the following methods:
    - `ask_question`: Ask a question using an assistant agent with a dataset
    
    **Request Format (JSON-RPC 2.0):**
    ```json
    {
      "jsonrpc": "2.0",
      "method": "ask_question",
      "params": {
        "question": "string",
        "dataset": "string",
        "agent": "string (optional)"
      },
      "id": "request_id"
    }
    ```
    
    **Response Format:**
    ```json
    {
      "jsonrpc": "2.0",
      "result": {
        "answer": "string",
        "agent_used": "string",
        "session_id": "string",
        "metadata": {}
      },
      "id": "request_id"
    }
    ```
    
    **Error Response:**
    ```json
    {
      "jsonrpc": "2.0",
      "error": {
        "code": -32600,
        "message": "Invalid Request"
      },
      "id": "request_id"
    }
    ```
    """
    logger.info(f"Received MCP request: method={request.method}, id={request.id}")
    
    # Validate JSON-RPC version
    if request.jsonrpc != "2.0":
        return MCPResponse(
            jsonrpc="2.0",
            error={
                "code": -32600,
                "message": "Invalid Request",
                "data": "jsonrpc version must be '2.0'"
            },
            id=request.id
        )
    
    # Handle different methods
    if request.method == "ask_question":
        try:
            params = request.params
            question = params.get("question")
            dataset = params.get("dataset")
            agent = params.get("agent")
            session_id = params.get("session_id")
            dataset_metadata = params.get("dataset_metadata")
            
            if not question:
                return MCPResponse(
                    jsonrpc="2.0",
                    error={
                        "code": -32602,
                        "message": "Invalid params",
                        "data": "question parameter is required"
                    },
                    id=request.id
                )
            
            if not dataset:
                return MCPResponse(
                    jsonrpc="2.0",
                    error={
                        "code": -32602,
                        "message": "Invalid params",
                        "data": "dataset parameter is required"
                    },
                    id=request.id
                )
            
            # Create AskRequest and process
            ask_request = AskRequest(
                question=question,
                dataset=dataset,
                agent=agent,
                session_id=session_id,
                dataset_metadata=dataset_metadata
            )
            
            # Process the request using the ask endpoint logic
            ask_response = await ask_question(ask_request, service, registry)
            
            # Return MCP response
            return MCPResponse(
                jsonrpc="2.0",
                result={
                    "answer": ask_response.answer,
                    "agent_used": ask_response.agent_used,
                    "session_id": ask_response.session_id,
                    "metadata": ask_response.metadata
                },
                id=request.id
            )
            
        except HTTPException as e:
            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": e.status_code,
                    "message": e.detail,
                    "data": {"status_code": e.status_code}
                },
                id=request.id
            )
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}", exc_info=True)
            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                id=request.id
            )
    
    elif request.method == "list_assistants":
        # List available assistants
        try:
            assistants_data = registry.list_assistants()
            assistants = [
                {
                    "assistant_id": a["assistant_id"],
                    "name": a["name"],
                    "description": a.get("description", ""),
                    "graph_count": a["graph_count"],
                    "default_graph_id": a.get("default_graph_id")
                }
                for a in assistants_data
            ]
            return MCPResponse(
                jsonrpc="2.0",
                result={"assistants": assistants},
                id=request.id
            )
        except Exception as e:
            logger.error(f"Error listing assistants: {e}", exc_info=True)
            return MCPResponse(
                jsonrpc="2.0",
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                id=request.id
            )
    
    else:
        # Method not found
        return MCPResponse(
            jsonrpc="2.0",
            error={
                "code": -32601,
                "message": "Method not found",
                "data": f"Method '{request.method}' is not supported. Available methods: ask_question, list_assistants"
            },
            id=request.id
        )

