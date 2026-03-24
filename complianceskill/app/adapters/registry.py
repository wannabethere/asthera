"""
Agent Registry

Maintains catalog of available agents with metadata and adapters.
Resolves agents by ID and filters by JWT claims.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from app.adapters.base import AgentAdapter

logger = logging.getLogger(__name__)


@dataclass
class AgentMeta:
    """
    Metadata for an agent following the schema from agent_adapter.md.
    Design-style (agent_gateway_updates.md): planner_description and routing_tags
    align with manifest routing_triggers / planner_description.
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
    # Design-style: planner-facing description (optional; defaults to display_name in manifest)
    planner_description: Optional[str] = None

    def to_catalog_entry(self) -> Dict:
        """Stripped version sent to planner LLM (backward compatible)."""
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
    Design-style (agent_gateway_updates.md): optional manifest storage and
    build_planner_catalog() for planner-facing catalog; existing register() unchanged.
    """
    
    def __init__(self):
        self._adapters: Dict[str, AgentAdapter] = {}
        self._meta: Dict[str, AgentMeta] = {}
        self._manifests: Dict[str, Any] = {}  # agent_id -> AgentManifest (optional)
        self._describe_contexts: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent_describe context (prompt + tools)

    def register(self, meta: AgentMeta, adapter: AgentAdapter):
        """
        Register an agent with its metadata and adapter.
        Also derives and stores a design-style manifest for catalog/describe,
        and builds agent_describe context (prompt + tools) for the proxy layer.
        
        Args:
            meta: Agent metadata
            adapter: Agent adapter implementation
        """
        self._adapters[meta.agent_id] = adapter
        self._meta[meta.agent_id] = meta
        try:
            from app.adapters.manifest import manifest_from_meta
            manifest = manifest_from_meta(meta)
            self._manifests[meta.agent_id] = manifest
            adapter._manifest = manifest
        except Exception as e:
            logger.debug(f"Manifest derivation skipped for {meta.agent_id}: {e}")
        try:
            from app.services.agent_describe_context import build_agent_describe_context
            self._describe_contexts[meta.agent_id] = build_agent_describe_context(meta.agent_id)
        except Exception as e:
            logger.debug(f"Agent describe context skipped for {meta.agent_id}: {e}")
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

    def build_planner_catalog(self, claims: Dict) -> List[Dict[str, Any]]:
        """
        Build planner-facing catalog (design-style agent_gateway_updates.md §10.7).
        Uses manifest.to_catalog_entry() when manifest exists, else meta.to_catalog_entry().
        Existing agents_for_claims() filtering applies.
        """
        accessible = self.agents_for_claims(claims)
        out = []
        for meta in accessible:
            if meta.agent_id in self._manifests:
                out.append(self._manifests[meta.agent_id].to_catalog_entry())
            else:
                out.append(meta.to_catalog_entry())
        return out

    def get_describe_context(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent_describe context (prompt summary + tools) for the proxy layer.
        Built at registration; if missing, builds on demand.
        """
        if agent_id in self._describe_contexts:
            return self._describe_contexts[agent_id]
        try:
            from app.services.agent_describe_context import build_agent_describe_context
            ctx = build_agent_describe_context(agent_id)
            self._describe_contexts[agent_id] = ctx
            return ctx
        except Exception as e:
            logger.debug(f"Agent describe context build failed for {agent_id}: {e}")
            return {
                "prompt_summary": "",
                "prompt_excerpts": [],
                "tools": [],
                "description": f"Agent {agent_id}.",
            }


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
