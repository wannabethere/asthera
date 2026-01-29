"""
Graph Streaming Module for LangGraph execution with SSE

This module provides:
- SSE event streaming for LangGraph execution
- Graph registry for managing multiple graphs per assistant
- FastAPI router for streaming endpoints
- Event models for structured streaming
"""

from app.streams.events import (
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

from app.streams.graph_registry import (
    GraphRegistry,
    GraphConfig,
    AssistantConfig,
    get_registry
)

from app.streams.streaming_service import GraphStreamingService

from app.streams.unified_streaming import (
    UnifiedStreamingService,
    get_streaming_service
)

from app.streams.common_events import (
    BaseEvent,
    StartedEvent,
    CompletedEvent,
    ErrorEvent,
    ProgressEvent as CommonProgressEvent,
    KeepAliveEvent as CommonKeepAliveEvent,
    ResultEvent as CommonResultEvent,
    DataEvent,
    StatusUpdateEvent,
    PipelineStartedEvent,
    PipelineCompletedEvent,
    PipelineErrorEvent,
    PipelineProgressEvent,
    GraphStartedEvent as CommonGraphStartedEvent,
    GraphCompletedEvent as CommonGraphCompletedEvent,
    GraphErrorEvent as CommonGraphErrorEvent,
    ServiceStartedEvent,
    ServiceCompletedEvent,
    format_sse_event as format_common_sse_event
)

from app.streams.models import (
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
    # Unified streaming
    "UnifiedStreamingService",
    "get_streaming_service",
    # Common events
    "BaseEvent",
    "StartedEvent",
    "CompletedEvent",
    "ErrorEvent",
    "CommonProgressEvent",
    "CommonKeepAliveEvent",
    "CommonResultEvent",
    "DataEvent",
    "StatusUpdateEvent",
    "PipelineStartedEvent",
    "PipelineCompletedEvent",
    "PipelineErrorEvent",
    "PipelineProgressEvent",
    "CommonGraphStartedEvent",
    "CommonGraphCompletedEvent",
    "CommonGraphErrorEvent",
    "ServiceStartedEvent",
    "ServiceCompletedEvent",
    "format_common_sse_event",
    # Router - now in app.routers.streaming
    # "router"  # Deprecated - use app.routers.streaming.router instead
]

