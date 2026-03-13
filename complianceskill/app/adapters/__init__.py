"""
Agent Adapter Layer

Framework-agnostic adapters for different agent implementations.
All agents implement the AgentAdapter interface for unified invocation.
"""

from app.adapters.base import AgentAdapter, AgentEvent, EventType
from app.adapters.registry import AgentRegistry, AgentMeta, get_agent_registry
from app.adapters.langgraph_adapter import LangGraphAdapter

__all__ = [
    "AgentAdapter",
    "AgentEvent",
    "EventType",
    "AgentRegistry",
    "AgentMeta",
    "get_agent_registry",
    "LangGraphAdapter",
]
