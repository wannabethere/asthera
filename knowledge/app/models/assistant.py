"""
Assistant and Streaming Models
Includes:
- Graph streaming API models (from streams/models.py)
- Workforce assistant configuration models (from config/workforce_config.py)
"""
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.storage.query.collection_factory import CollectionFactory


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


# ============================================================================
# WORKFORCE ASSISTANT MODELS (from config/workforce_config.py)
# ============================================================================

class AssistantType(Enum):
    """Types of workforce assistants"""
    PRODUCT = "product"
    COMPLIANCE = "compliance"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


@dataclass
class DataSourceConfig:
    """
    Configuration for a data source used by an assistant.
    
    Attributes:
        source_name: Name of the data source (e.g., "chroma", "web", "postgres")
        enabled: Whether this data source is enabled
        categories: List of categories to filter by (if applicable)
        metadata_filters: Additional metadata filters for this source
        priority: Priority of this source (1-10, higher = more important)
    """
    source_name: str
    enabled: bool = True
    categories: List[str] = field(default_factory=list)
    metadata_filters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5


@dataclass
class AssistantConfig:
    """
    Configuration for a workforce assistant.
    
    Attributes:
        assistant_type: Type of assistant
        model_name: LLM model to use
        temperature: Model temperature
        system_prompt_template: System prompt template
        human_prompt_template: Human prompt template
        data_sources: List of data source configurations
        web_search_enabled: Whether web search is enabled
        max_edges: Maximum number of edges to retrieve
        enable_evidence_gathering: Whether to enable evidence gathering
    """
    assistant_type: AssistantType
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.2
    system_prompt_template: str = ""
    human_prompt_template: str = ""
    data_sources: List[DataSourceConfig] = field(default_factory=list)
    web_search_enabled: bool = False
    max_edges: int = 10
    enable_evidence_gathering: bool = False

