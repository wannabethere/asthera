"""
Common Streaming Events

Standardized event types for SSE streaming across graphs, pipelines, and services.
"""
from typing import Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime
import json


# Event types
EventType = Literal[
    # Lifecycle events
    "started",
    "completed",
    "error",
    "cancelled",
    "timeout",
    
    # Progress events
    "progress",
    "status_update",
    
    # Resource-specific events
    "pipeline_started",
    "pipeline_completed",
    "pipeline_error",
    "pipeline_progress",
    
    "graph_started",
    "graph_completed",
    "graph_error",
    "graph_progress",
    
    "service_started",
    "service_completed",
    "service_error",
    "service_progress",
    
    # Generic events
    "keepalive",
    "result",
    "data",
    "metadata"
]


class BaseEvent(BaseModel):
    """Base event for all SSE streams"""
    event: str = Field(..., description="Event type")
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp(), description="Event timestamp")
    
    def to_sse_format(self) -> str:
        """Format event as SSE message"""
        data = self.dict()
        event_type = data.pop("event", "message")
        
        # Format as SSE
        sse_lines = []
        sse_lines.append(f"event: {event_type}")
        sse_lines.append(f"data: {json.dumps(data, default=str)}")
        sse_lines.append("")  # Empty line to end event
        
        return "\n".join(sse_lines) + "\n"


class StartedEvent(BaseEvent):
    """Resource execution started"""
    event: Literal["started"] = "started"
    resource_type: str = Field(..., description="Type of resource (pipeline, graph, service)")
    resource_id: str = Field(..., description="Resource identifier")
    inputs: Optional[Dict[str, Any]] = Field(default=None, description="Input data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class CompletedEvent(BaseEvent):
    """Resource execution completed"""
    event: Literal["completed"] = "completed"
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="Resource identifier")
    success: bool = Field(default=True, description="Whether execution succeeded")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Result data")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class ErrorEvent(BaseEvent):
    """Resource execution error"""
    event: Literal["error"] = "error"
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="Resource identifier")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type")
    duration_seconds: Optional[float] = Field(default=None, description="Duration before error")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class ProgressEvent(BaseEvent):
    """Resource execution progress"""
    event: Literal["progress"] = "progress"
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="Resource identifier")
    status: str = Field(..., description="Current status")
    progress: Optional[float] = Field(default=None, description="Progress percentage (0-100)")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Progress data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class KeepAliveEvent(BaseEvent):
    """Keep-alive event"""
    event: Literal["keepalive"] = "keepalive"
    stream_id: Optional[str] = Field(default=None, description="Stream identifier")


class ResultEvent(BaseEvent):
    """Result data event"""
    event: Literal["result"] = "result"
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="Resource identifier")
    data: Dict[str, Any] = Field(..., description="Result data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class DataEvent(BaseEvent):
    """Generic data event"""
    event: Literal["data"] = "data"
    data: Dict[str, Any] = Field(..., description="Data payload")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


class StatusUpdateEvent(BaseEvent):
    """Status update event"""
    event: Literal["status_update"] = "status_update"
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="Resource identifier")
    status: str = Field(..., description="Current status")
    message: Optional[str] = Field(default=None, description="Status message")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")


# Pipeline-specific events
class PipelineStartedEvent(StartedEvent):
    """Pipeline execution started"""
    event: Literal["pipeline_started"] = "pipeline_started"
    resource_type: Literal["pipeline"] = "pipeline"
    pipeline_id: str = Field(..., description="Pipeline ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "pipeline_id" in data:
            data["resource_id"] = data["pipeline_id"]
        super().__init__(**data)


class PipelineCompletedEvent(CompletedEvent):
    """Pipeline execution completed"""
    event: Literal["pipeline_completed"] = "pipeline_completed"
    resource_type: Literal["pipeline"] = "pipeline"
    pipeline_id: str = Field(..., description="Pipeline ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "pipeline_id" in data:
            data["resource_id"] = data["pipeline_id"]
        super().__init__(**data)


class PipelineErrorEvent(ErrorEvent):
    """Pipeline execution error"""
    event: Literal["pipeline_error"] = "pipeline_error"
    resource_type: Literal["pipeline"] = "pipeline"
    pipeline_id: str = Field(..., description="Pipeline ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "pipeline_id" in data:
            data["resource_id"] = data["pipeline_id"]
        super().__init__(**data)


class PipelineProgressEvent(ProgressEvent):
    """Pipeline execution progress"""
    event: Literal["pipeline_progress"] = "pipeline_progress"
    resource_type: Literal["pipeline"] = "pipeline"
    pipeline_id: str = Field(..., description="Pipeline ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "pipeline_id" in data:
            data["resource_id"] = data["pipeline_id"]
        super().__init__(**data)


# Graph-specific events
class GraphStartedEvent(StartedEvent):
    """Graph execution started"""
    event: Literal["graph_started"] = "graph_started"
    resource_type: Literal["graph"] = "graph"
    graph_id: str = Field(..., description="Graph ID")
    assistant_id: Optional[str] = Field(default=None, description="Assistant ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "graph_id" in data:
            data["resource_id"] = data["graph_id"]
        super().__init__(**data)


class GraphCompletedEvent(CompletedEvent):
    """Graph execution completed"""
    event: Literal["graph_completed"] = "graph_completed"
    resource_type: Literal["graph"] = "graph"
    graph_id: str = Field(..., description="Graph ID")
    assistant_id: Optional[str] = Field(default=None, description="Assistant ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "graph_id" in data:
            data["resource_id"] = data["graph_id"]
        super().__init__(**data)


class GraphErrorEvent(ErrorEvent):
    """Graph execution error"""
    event: Literal["graph_error"] = "graph_error"
    resource_type: Literal["graph"] = "graph"
    graph_id: str = Field(..., description="Graph ID")
    assistant_id: Optional[str] = Field(default=None, description="Assistant ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    
    def __init__(self, **data):
        if "resource_id" not in data and "graph_id" in data:
            data["resource_id"] = data["graph_id"]
        super().__init__(**data)


# Service-specific events
class ServiceStartedEvent(StartedEvent):
    """Service execution started"""
    event: Literal["service_started"] = "service_started"
    resource_type: Literal["service"] = "service"
    service_name: str = Field(..., description="Service name")
    method_name: Optional[str] = Field(default=None, description="Method name")
    
    def __init__(self, **data):
        if "resource_id" not in data and "service_name" in data:
            data["resource_id"] = data["service_name"]
        super().__init__(**data)


class ServiceCompletedEvent(CompletedEvent):
    """Service execution completed"""
    event: Literal["service_completed"] = "service_completed"
    resource_type: Literal["service"] = "service"
    service_name: str = Field(..., description="Service name")
    method_name: Optional[str] = Field(default=None, description="Method name")
    
    def __init__(self, **data):
        if "resource_id" not in data and "service_name" in data:
            data["resource_id"] = data["service_name"]
        super().__init__(**data)


def format_sse_event(event: Union[BaseEvent, Dict[str, Any]]) -> str:
    """
    Format event as SSE message
    
    Args:
        event: Event object or dictionary
        
    Returns:
        SSE-formatted string
    """
    if isinstance(event, BaseEvent):
        return event.to_sse_format()
    elif isinstance(event, dict):
        # Convert dict to SSE format
        event_type = event.pop("event", "message")
        
        sse_lines = []
        sse_lines.append(f"event: {event_type}")
        sse_lines.append(f"data: {json.dumps(event, default=str)}")
        sse_lines.append("")
        
        return "\n".join(sse_lines) + "\n"
    else:
        raise ValueError(f"Invalid event type: {type(event)}")
