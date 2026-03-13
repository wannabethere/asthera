"""
Base Agent Adapter Interface

Defines the abstract interface that all agent frameworks must implement.
Adapters are stateless - all state is in the ComposedContext.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel
from datetime import datetime


class EventType(str, Enum):
    """Agent event types following the protocol from agent_adapter.md"""
    # Core streaming
    TOKEN = "token"                    # streaming LLM token
    TOOL_START = "tool_start"          # agent invoking a tool
    TOOL_END = "tool_end"              # tool finished
    
    # Lifecycle
    STEP_START = "step_start"          # one plan step beginning
    STEP_FINAL = "step_final"          # one plan step complete
    STEP_ERROR = "step_error"          # one step failed (others may continue)
    FINAL = "final"                    # entire run complete
    
    # Orchestration
    PLAN = "plan"                      # gateway emits plan before execution
    PLAN_MODIFIED = "plan_modified"    # plan changed due to auth limits
    SYNTHESIS_START = "synthesis_start" # synthesizer beginning to merge
    ERROR = "error"                    # fatal error


class AgentEvent(BaseModel):
    """
    Standardized agent event following the protocol from agent_adapter.md
    """
    type: EventType
    agent_id: str
    run_id: str
    step_id: str
    tenant_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = {}
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Events format"""
        return f"data: {self.model_dump_json()}\n\n"
    
    class Config:
        use_enum_values = True


class ComposedContext(BaseModel):
    """
    Context composed by the gateway and delivered to agents.
    Never stored by agents - gateway owns all state.
    """
    system: Dict[str, Any]              # System context (static, from registry)
    session: Dict[str, Any]            # Session context (dynamic, budget-constrained)
    turn: Dict[str, Any]                # Turn context (last N raw messages + current input)
    memory: Optional[Dict[str, Any]] = None  # Long-term memory (if available)
    
    class Config:
        arbitrary_types_allowed = True


class AgentAdapter(ABC):
    """
    Abstract interface for all agent frameworks.
    
    Adapters are stateless - all state is in the ComposedContext.
    Framework-specific implementations (LangGraph, Claude SDK, etc.) 
    implement this interface.
    """
    
    @abstractmethod
    async def stream(
        self,
        payload: Dict[str, Any],
        context: ComposedContext,
        config: Dict[str, Any]
    ) -> AsyncIterator[AgentEvent]:
        """
        Stream agent execution events.
        
        Args:
            payload: Agent invocation payload (~1-2KB) containing:
                - input: User query or agent-specific input
                - thread_id: Thread identifier
                - run_id: Unique run identifier
                - step_id: Plan step identifier
                - ctx_token: Signed token to fetch full context (optional, if using reference)
                - data_scope: Data scoping filters
            context: Pre-composed context (if ctx_token not used)
            config: Additional configuration (timeouts, model params, etc.)
        
        Yields:
            AgentEvent: Standardized events following the protocol
        """
        ...
    
    @abstractmethod
    def normalize_event(self, raw_event: Any) -> Optional[AgentEvent]:
        """
        Map framework-native event shapes to AgentEvent protocol.
        
        Args:
            raw_event: Framework-specific event object
        
        Returns:
            AgentEvent or None if event should be filtered
        """
        ...
