"""
Graph Streaming Module for LangGraph execution with SSE

This module provides:
- SSE event streaming for LangGraph execution
- Graph registry for managing multiple graphs per assistant
- FastAPI router for streaming endpoints
- Event models for structured streaming
"""

from .events import (
    EventType,
    GraphEvent,
    GraphStartedEvent,
    GraphCompletedEvent,
    GraphErrorEvent,
    NodeStartedEvent,
    NodeCompletedEvent,
    NodeErrorEvent,
    StateUpdateEvent,
    ProgressEvent,
    ResultEvent,
    KeepAliveEvent,
    serialize_event,
    format_sse_event
)

from .graph_registry import (
    GraphRegistry,
    GraphConfig,
    AssistantConfig,
    get_registry
)

from .streaming_service import GraphStreamingService

from .models import (
    GraphInvokeRequest,
    AssistantCreateRequest,
    GraphRegisterRequest,
    AssistantInfo,
    GraphInfo,
    AssistantListResponse,
    GraphListResponse
)

# Router is now in app/routers/streaming.py
# from .router import router  # Deprecated - use app.routers.streaming.router instead

__all__ = [
    # Events
    "EventType",
    "GraphEvent",
    "GraphStartedEvent",
    "GraphCompletedEvent",
    "GraphErrorEvent",
    "NodeStartedEvent",
    "NodeCompletedEvent",
    "NodeErrorEvent",
    "StateUpdateEvent",
    "ProgressEvent",
    "ResultEvent",
    "KeepAliveEvent",
    "serialize_event",
    "format_sse_event",
    # Registry
    "GraphRegistry",
    "GraphConfig",
    "AssistantConfig",
    "get_registry",
    # Service
    "GraphStreamingService",
    # Models
    "GraphInvokeRequest",
    "AssistantCreateRequest",
    "GraphRegisterRequest",
    "AssistantInfo",
    "GraphInfo",
    "AssistantListResponse",
    "GraphListResponse",
    # Router - now in app.routers.streaming
    # "router"  # Deprecated - use app.routers.streaming.router instead
]

