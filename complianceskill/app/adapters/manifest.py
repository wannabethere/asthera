"""
Agent Manifest — design-style self-description (agent_gateway_updates.md v3.0).

Minimal implementation so existing agents (csod_workflow, csod_metric_advisor,
dt_workflow, compliance_workflow, dashboard_agent) can be described without
breaking current registration. CCE and full fleet fields are optional defaults.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ContextKeySpec:
    """Declares a context key this agent produces (design-style)."""
    key_name: str
    schema_version: str = "v1"
    supported_versions: List[str] = field(default_factory=lambda: ["v1"])
    description: str = ""
    ttl_seconds: int = 14400
    invalidated_by: List[str] = field(default_factory=list)


@dataclass
class CapabilitySpec:
    """Declares a capability this agent provides (design-style)."""
    name: str
    description: str = ""
    satisfaction_flag_ttl: int = 86400


@dataclass
class IntermediateEventSpec:
    """Declares an intermediate event type (design-style, e.g. CCE)."""
    event_type: str
    description: str = ""
    timing_hint: str = ""
    recipient_hint: str = ""
    payload_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentManifest:
    """
    Self-description for an agent (agent_gateway_updates.md §10.2, §17).
    Existing agents get a manifest derived from AgentMeta via manifest_from_meta().
    """
    # Identity
    agent_id: str
    display_name: str
    version: str = "1.0.0"
    framework: str = "langgraph"

    # Planner-facing (used by catalog)
    routing_triggers: List[str] = field(default_factory=list)
    planner_description: str = ""
    required_role: str = "viewer"
    feature_flag: Optional[str] = None
    phase: int = 1
    gateway_resident: bool = False
    requires_phase2: Optional[str] = None
    orchestrates: List[str] = field(default_factory=list)
    writes_to_thread_state: bool = False
    influences_future_plans: bool = False

    # Dependencies (optional for existing agents)
    depends_on_capabilities: List[str] = field(default_factory=list)
    produces_context_keys: List[ContextKeySpec] = field(default_factory=list)
    consumes_context_keys: List[str] = field(default_factory=list)
    provides_capabilities: List[CapabilitySpec] = field(default_factory=list)
    intermediate_events: List[IntermediateEventSpec] = field(default_factory=list)
    emits_intermediate_events: bool = False

    # Context window (from AgentMeta)
    context_window_tokens: int = 8000
    system_ctx_tokens: int = 1500
    session_ctx_tokens: int = 3000
    turn_ctx_tokens: int = 2000
    response_reserve_tokens: int = 1500
    requires_memory: bool = False
    requires_memory_keys: List[str] = field(default_factory=list)

    # JWT / scope
    jwt_claims_required: List[str] = field(default_factory=list)
    data_scope_requirements: Dict[str, str] = field(default_factory=dict)
    tenant_scoped: bool = True

    # Infrastructure (for remote agents)
    health_check_path: str = "/health"
    describe_path: str = "/describe"

    def to_catalog_entry(self) -> Dict[str, Any]:
        """Planner-facing catalog entry (design §10.2)."""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "planner_description": self.planner_description or self.display_name,
            "routing_triggers": self.routing_triggers,
            "depends_on_capabilities": self.depends_on_capabilities,
            "provides_capabilities": [c.name for c in self.provides_capabilities],
            "produces_context_keys": [k.key_name for k in self.produces_context_keys],
            "consumes_context_keys": self.consumes_context_keys,
            "orchestrates": self.orchestrates,
            "requires_phase2": self.requires_phase2,
            "phase": self.phase,
            "capabilities": [],  # backward compat key
            "routing_tags": self.routing_triggers,  # backward compat
        }


def manifest_from_meta(meta: "AgentMeta") -> AgentManifest:
    """
    Build a design-style AgentManifest from existing AgentMeta.
    Keeps existing registration flow unchanged; manifest is used for catalog/describe.
    """
    return AgentManifest(
        agent_id=meta.agent_id,
        display_name=meta.display_name,
        version="1.0.0",
        framework=meta.framework,
        routing_triggers=getattr(meta, "routing_tags", []) or [],
        planner_description=getattr(meta, "planner_description", None) or meta.display_name,
        required_role=meta.required_role,
        feature_flag=meta.feature_flag,
        phase=1,
        gateway_resident=False,
        context_window_tokens=meta.context_window_tokens,
        system_ctx_tokens=meta.system_ctx_tokens,
        session_ctx_tokens=meta.session_ctx_tokens,
        turn_ctx_tokens=meta.turn_ctx_tokens,
        response_reserve_tokens=meta.response_reserve_tokens,
        requires_memory=meta.requires_memory,
        requires_memory_keys=meta.requires_memory_keys or [],
        tenant_scoped=meta.tenant_scoped,
    )
