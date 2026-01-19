"""
SSE Event Models for Graph Streaming
"""
from enum import Enum
from typing import Any, Dict, Optional, List, Union
from pydantic import BaseModel, Field
from datetime import datetime


class EventType(str, Enum):
    """Types of events that can be streamed"""
    # Graph lifecycle events
    GRAPH_STARTED = "graph_started"
    GRAPH_COMPLETED = "graph_completed"
    GRAPH_ERROR = "graph_error"
    
    # Node execution events
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_ERROR = "node_error"
    
    # State update events
    STATE_UPDATE = "state_update"
    
    # Progress events
    PROGRESS = "progress"
    
    # Final result
    RESULT = "result"
    
    # Keep-alive
    KEEP_ALIVE = "keep_alive"


class GraphEvent(BaseModel):
    """Base event model for SSE streaming"""
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    session_id: str = Field(..., description="Session/thread ID")
    assistant_id: Optional[str] = Field(None, description="Assistant ID")
    graph_id: Optional[str] = Field(None, description="Graph ID")
    
    class Config:
        use_enum_values = True


class GraphStartedEvent(GraphEvent):
    """Event emitted when graph execution starts"""
    event_type: EventType = EventType.GRAPH_STARTED
    query: str = Field(..., description="User query/input")
    config: Optional[Dict[str, Any]] = Field(None, description="Graph configuration")


class GraphCompletedEvent(GraphEvent):
    """Event emitted when graph execution completes"""
    event_type: EventType = EventType.GRAPH_COMPLETED
    final_state: Optional[Dict[str, Any]] = Field(None, description="Final graph state")
    duration_ms: Optional[float] = Field(None, description="Execution duration in milliseconds")


class GraphErrorEvent(GraphEvent):
    """Event emitted when graph execution fails"""
    event_type: EventType = EventType.GRAPH_ERROR
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Error type/class name")
    traceback: Optional[str] = Field(None, description="Error traceback")


class NodeStartedEvent(GraphEvent):
    """Event emitted when a node starts execution"""
    event_type: EventType = EventType.NODE_STARTED
    node_name: str = Field(..., description="Name of the node")
    input_state: Optional[Dict[str, Any]] = Field(None, description="Input state snapshot")


class NodeCompletedEvent(GraphEvent):
    """Event emitted when a node completes execution"""
    event_type: EventType = EventType.NODE_COMPLETED
    node_name: str = Field(..., description="Name of the node")
    output_state: Optional[Dict[str, Any]] = Field(None, description="Output state snapshot")
    duration_ms: Optional[float] = Field(None, description="Node execution duration")


class NodeErrorEvent(GraphEvent):
    """Event emitted when a node execution fails"""
    event_type: EventType = EventType.NODE_ERROR
    node_name: str = Field(..., description="Name of the node")
    error: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")


class StateUpdateEvent(GraphEvent):
    """Event emitted when state is updated"""
    event_type: EventType = EventType.STATE_UPDATE
    state_snapshot: Dict[str, Any] = Field(..., description="Current state snapshot")
    changed_keys: List[str] = Field(default_factory=list, description="Keys that changed")


class ProgressEvent(GraphEvent):
    """Event for progress updates"""
    event_type: EventType = EventType.PROGRESS
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress (0.0 to 1.0)")
    message: Optional[str] = Field(None, description="Progress message")
    current_step: Optional[str] = Field(None, description="Current step name")
    total_steps: Optional[int] = Field(None, description="Total number of steps")


class ResultEvent(GraphEvent):
    """Event containing final result"""
    event_type: EventType = EventType.RESULT
    result: Dict[str, Any] = Field(..., description="Final result data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Result metadata")


class KeepAliveEvent(GraphEvent):
    """Keep-alive event to maintain connection"""
    event_type: EventType = EventType.KEEP_ALIVE


# Union type for all events (using Union for Python < 3.10 compatibility)
GraphStreamEvent = Union[
    GraphStartedEvent,
    GraphCompletedEvent,
    GraphErrorEvent,
    NodeStartedEvent,
    NodeCompletedEvent,
    NodeErrorEvent,
    StateUpdateEvent,
    ProgressEvent,
    ResultEvent,
    KeepAliveEvent
]


def serialize_event(event: GraphStreamEvent) -> str:
    """Serialize event to SSE format"""
    event_dict = event.model_dump(mode="json", exclude_none=True)
    # Convert datetime to ISO format string (if not already a string)
    if "timestamp" in event_dict:
        timestamp = event_dict["timestamp"]
        # If it's already a string, keep it; otherwise convert datetime to ISO format
        if isinstance(timestamp, str):
            # Already a string, no conversion needed
            pass
        elif isinstance(timestamp, datetime):
            event_dict["timestamp"] = timestamp.isoformat()
        else:
            # Fallback: convert to string
            event_dict["timestamp"] = str(timestamp)
    
    import json
    return json.dumps(event_dict)


def format_sse_event(event: GraphStreamEvent, event_id: Optional[int] = None) -> str:
    """Format event as SSE message"""
    event_data = serialize_event(event)
    lines = [f"event: {event.event_type.value}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {event_data}")
    lines.append("")  # Empty line to end SSE message
    return "\n".join(lines)

