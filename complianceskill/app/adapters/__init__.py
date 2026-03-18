"""
Agent Adapter Layer

Framework-agnostic adapters for different agent implementations.
All agents implement the AgentAdapter interface for unified invocation.
"""

from app.adapters.base import AgentAdapter, AgentEvent, EventType
from app.adapters.registry import AgentRegistry, AgentMeta, get_agent_registry
from app.adapters.langgraph_adapter import LangGraphAdapter  # Backward compatibility
from app.adapters.base_langgraph_adapter import BaseLangGraphAdapter
from app.adapters.csod_langgraph_adapter import CSODLangGraphAdapter

__all__ = [
    "AgentAdapter",
    "AgentEvent",
    "EventType",
    "AgentRegistry",
    "AgentMeta",
    "get_agent_registry",
    "LangGraphAdapter",  # Backward compatibility
    "BaseLangGraphAdapter",
    "CSODLangGraphAdapter",
]
