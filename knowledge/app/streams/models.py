"""
Request/Response models for graph streaming API
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class GraphInvokeRequest(BaseModel):
    """Request to invoke a graph"""
    query: str = Field(..., description="User query/input")
    assistant_id: str = Field(..., description="Assistant ID")
    graph_id: Optional[str] = Field(None, description="Graph ID (uses default if not provided)")
    session_id: Optional[str] = Field(None, description="Session/thread ID (auto-generated if not provided)")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Additional input data")
    config: Optional[Dict[str, Any]] = Field(None, description="LangGraph config overrides")


class AssistantCreateRequest(BaseModel):
    """Request to create an assistant"""
    assistant_id: str = Field(..., description="Assistant ID")
    name: str = Field(..., description="Assistant name")
    description: Optional[str] = Field(None, description="Assistant description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class GraphRegisterRequest(BaseModel):
    """Request to register a graph"""
    assistant_id: str = Field(..., description="Assistant ID")
    graph_id: str = Field(..., description="Graph ID")
    name: Optional[str] = Field(None, description="Graph name")
    description: Optional[str] = Field(None, description="Graph description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    set_as_default: bool = Field(False, description="Set as default graph for assistant")
    # Note: The actual graph object should be registered via the service, not via API


class AssistantInfo(BaseModel):
    """Assistant information"""
    assistant_id: str
    name: str
    description: Optional[str] = None
    graph_count: int
    default_graph_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphInfo(BaseModel):
    """Graph information"""
    graph_id: str
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class AssistantListResponse(BaseModel):
    """Response listing assistants"""
    assistants: List[AssistantInfo]


class GraphListResponse(BaseModel):
    """Response listing graphs for an assistant"""
    assistant_id: str
    graphs: List[GraphInfo]


class AskRequest(BaseModel):
    """Request to ask a question using an assistant agent"""
    question: str = Field(..., description="The question to ask")
    dataset: str = Field(..., description="Dataset identifier (ID, name, or metadata)")
    agent: Optional[str] = Field(None, description="Assistant ID (optional, uses default if not provided)")
    session_id: Optional[str] = Field(None, description="Session/thread ID (auto-generated if not provided)")
    dataset_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional dataset metadata")


class AskResponse(BaseModel):
    """Response from asking a question"""
    answer: str = Field(..., description="The answer from the assistant")
    agent_used: str = Field(..., description="The assistant ID that was used")
    session_id: str = Field(..., description="Session ID for this conversation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (sources, confidence, etc.)")


class MCPRequest(BaseModel):
    """MCP JSON-RPC request"""
    jsonrpc: str = Field("2.0", description="JSON-RPC version")
    method: str = Field(..., description="Method name (e.g., 'ask_question')")
    params: Dict[str, Any] = Field(..., description="Method parameters")
    id: Optional[Any] = Field(None, description="Request ID for correlation")


class MCPResponse(BaseModel):
    """MCP JSON-RPC response"""
    jsonrpc: str = Field("2.0", description="JSON-RPC version")
    result: Optional[Dict[str, Any]] = Field(None, description="Result data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information if request failed")
    id: Optional[Any] = Field(None, description="Request ID from original request")


class MCPError(BaseModel):
    """MCP error object"""
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional error data")

