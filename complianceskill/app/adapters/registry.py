"""
Agent Registry

Maintains catalog of available agents with metadata and adapters.
Resolves agents by ID and filters by JWT claims.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

from app.adapters.base import AgentAdapter

logger = logging.getLogger(__name__)


@dataclass
class AgentMeta:
    """
    Metadata for an agent following the schema from agent_adapter.md
    """
    agent_id: str
    display_name: str
    framework: str                     # "langgraph" | "claude-sdk" | "a2a"
    capabilities: List[str]             # ["streaming", "tool_use", "multi_step"]
    context_window_tokens: int = 8000
    system_ctx_tokens: int = 1500
    session_ctx_tokens: int = 3000
    turn_ctx_tokens: int = 2000
    response_reserve_tokens: int = 1500
    requires_memory: bool = False
    requires_memory_keys: List[str] = field(default_factory=list)
    required_role: str = "viewer"
    feature_flag: Optional[str] = None
    routing_tags: List[str] = field(default_factory=list)
    tenant_scoped: bool = True
    use_conversation_phase0: bool = False  # If True, run conversation engine before agent execution
    conversation_vertical: Optional[str] = None  # Vertical ID for conversation config (e.g., "lms", "dt")
    
    def to_catalog_entry(self) -> Dict:
        """Stripped version sent to planner LLM"""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "routing_tags": self.routing_tags,
        }


class AgentRegistry:
    """
    Registry for agent adapters and metadata.
    Resolves agents by ID and filters by claims.
    """
    
    def __init__(self):
        self._adapters: Dict[str, AgentAdapter] = {}
        self._meta: Dict[str, AgentMeta] = {}
    
    def register(self, meta: AgentMeta, adapter: AgentAdapter):
        """
        Register an agent with its metadata and adapter.
        
        Args:
            meta: Agent metadata
            adapter: Agent adapter implementation
        """
        self._adapters[meta.agent_id] = adapter
        self._meta[meta.agent_id] = meta
        logger.info(f"Registered agent: {meta.agent_id} ({meta.framework})")
    
    def get_adapter(self, agent_id: str) -> AgentAdapter:
        """
        Get adapter for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            AgentAdapter instance
        
        Raises:
            AgentNotFoundError: If agent not registered
        """
        if agent_id not in self._adapters:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")
        return self._adapters[agent_id]
    
    def get_meta(self, agent_id: str) -> AgentMeta:
        """
        Get metadata for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            AgentMeta instance
        
        Raises:
            AgentNotFoundError: If agent not registered
        """
        if agent_id not in self._meta:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")
        return self._meta[agent_id]
    
    def agents_for_claims(self, claims: Dict) -> List[AgentMeta]:
        """
        Filter agents by JWT claims (agent_access, roles, feature_flags).
        
        Args:
            claims: Resolved JWT claims dict with:
                - agent_access: List of allowed agent IDs
                - roles: List of user roles
                - feature_flags: Dict of feature flags
        
        Returns:
            List of AgentMeta for accessible agents
        """
        agent_access = claims.get("agent_access", [])
        roles = claims.get("roles", [])
        feature_flags = claims.get("feature_flags", {})
        
        accessible = []
        for meta in self._meta.values():
            # Check agent access
            # Empty list means access to all agents (permissive for testing)
            if agent_access and len(agent_access) > 0 and meta.agent_id not in agent_access:
                continue
            
            # Check role requirement (simplified - can be enhanced)
            # For now, if required_role is specified, user must have matching role
            if meta.required_role and meta.required_role != "viewer":
                if meta.required_role not in roles:
                    continue
            
            # Check feature flag
            if meta.feature_flag:
                if not feature_flags.get(meta.feature_flag, False):
                    continue
            
            accessible.append(meta)
        
        return accessible
    
    def list_agents(self) -> List[str]:
        """List all registered agent IDs"""
        return list(self._adapters.keys())


class AgentNotFoundError(Exception):
    """Raised when an agent is not found in the registry"""
    pass


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry():
    """
    Get the global agent registry instance.
    
    Note: Return type annotation removed to avoid FastAPI validation issues.
    Returns AgentRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
