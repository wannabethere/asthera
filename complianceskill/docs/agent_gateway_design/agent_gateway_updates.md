# Agent Gateway — Architecture Design Document

**Version:** 3.0
**Status:** Draft
**Author:** Comatrix Labs
**Changes from v2.0:** Sections 1, 2, 5, 9, 10, 11, 12, 14 updated. Sections 16–20 added.
- Self-description pattern: `describe()` mandatory on every adapter; `AgentManifest` replaces static `AgentMeta` registration
- Full agent fleet: workflow planner, MDL services, metrics recommender, Cornerstone analysis, alert analysis, CCE causal analysis, CCE narration orchestrator
- Registry bootstrap: startup discovery phase replaces hardcoded `registry_setup.py`
- Dependency-aware planner: catalog built from live manifests; dependency graph resolves at plan time
- Context key handoff protocol: structured state passing between agents via declared `produces`/`consumes` keys
- Health dependency graph: partial degradation propagation across agent dependencies
- Agent server implementation pattern: what every agent on the server must implement to follow this contract

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Request Source Configuration](#3-request-source-configuration)
4. [JWT & Privilege Model](#4-jwt--privilege-model)
5. [Intent & Planning Layer](#5-intent--planning-layer)
6. [Thread Management](#6-thread-management)
7. [History & Memory Model](#7-history--memory-model)
8. [Context Composition](#8-context-composition)
9. [Redis Caching Architecture](#9-redis-caching-architecture)
10. [Agent Adapter Layer](#10-agent-adapter-layer)
11. [Event Protocol](#11-event-protocol)
12. [Multi-Agent Orchestration](#12-multi-agent-orchestration)
13. [Observability](#13-observability)
14. [Failure Handling](#14-failure-handling)
15. [CCE Hybrid Narration Orchestrator](#15-cce-hybrid-narration-orchestrator)
16. [Registry Bootstrap — Startup Self-Description](#16-registry-bootstrap--startup-self-description) ← NEW
17. [Full Fleet Manifests](#17-full-fleet-manifests) ← NEW
18. [Agent Server Implementation Pattern](#18-agent-server-implementation-pattern) ← NEW
19. [Context Key Handoff Protocol](#19-context-key-handoff-protocol) ← NEW
20. [Health Dependency Graph](#20-health-dependency-graph) ← NEW

---

## 1. Overview

The Agent Gateway is a framework-agnostic orchestration layer that sits between a frontend
chat application and a fleet of heterogeneous AI agents. It is responsible for authentication,
intent planning, context composition, agent fan-out, stream multiplexing, and memory write-back.

### 1.1 Core Design Principles

- **Framework agnostic** — agent frameworks are implementation details behind an adapter
  interface. Swapping LangGraph for Claude SDK requires only a new adapter, not a protocol change.
- **Gateway owns all state** — agents are stateless. Thread history, memory, and context
  are composed by the gateway and delivered to agents, never stored by them.
- **Reference over hydration** — large context is passed by reference (Redis token) not by
  value. Agents pull only what they need.
- **Streaming first** — the entire pipeline is designed around SSE. Every layer is non-blocking.
- **JWT as capability manifest** — JWT claims control authentication, agent access, data
  scoping, feature flags, and parallel execution limits.
- **Agents are the authority on themselves** — the proxy contains no hardcoded knowledge of
  any agent's capabilities, dependencies, or routing triggers. Every agent declares its own
  manifest via a mandatory `describe()` method. The proxy builds all routing, planning, event
  interception, and health logic from live manifest data at startup.
- **Reactive narration for CCE** — a gateway-resident narration orchestrator listens to
  Agent Server SSE events as they arrive and drives narration agents as direct LLM calls.

### 1.2 Fleet Overview

The Lexy AI agent fleet is organised into three tiers. The tiers reflect dependency direction —
lower tiers must exist before upper tiers can operate usefully.

```
TIER 3 — Workflow Orchestration
  workflow_planner          Decomposes multi-session analytical workflows into
                            cross-agent step sequences. Writes workflow context
                            that constrains future gateway planner decisions.

TIER 2 — Interpretation & Analysis
  cce_causal_analysis       LangGraph causal risk graph — decision tree routing,
                            LR risk scoring per R-node, Shapley attribution.
                            Emits intermediate events consumed by narration orchestrator.
  alert_analysis            Alert classification, triage routing, compound alert
                            detection. Internally orchestrates CCE for high-confidence alerts.
  metrics_recommender       Causal-aware metric recommendation. Reads causal knowledge
                            base to recommend safe metrics and flag colliders.
  cornerstone_analysis      CSOD-specific data analysis. Interrogates silver/gold
                            CSOD tables. Depends on MDL services gold layer.

TIER 1 — Data Foundation
  mdl_services              Medallion architecture builder. Produces silver and gold
                            layer tables from bronze ingest. Generates dbt models
                            and Cube.js schemas. Writes context keys consumed by Tier 2.

TIER 0 — Gateway-Resident (not on Agent Server)
  cce_narration_orchestrator Reactive narration engine. Listens to CCE intermediate
                             events and drives WHAT/WHY/INSIGHT/GAP/FOLLOWUP narration
                             as direct LLM calls. Zero network round-trips.
  gateway_planner            Existing routing planner — now dependency-aware and
                             catalog-driven from live manifests.
```

---

## 2. System Architecture

### 2.1 Full Fleet Architecture

-- All metadata apis will go via genimel
Genimel -

-- All agent related actions will go through this architecture

APIs 
-- Metadata APIs - CRUD
-- Actionable APIs via agents 
Browser
|

Node JS Proxy -- For your SSL Termination

|
Proxy to either apps depending on the request
Its going to be rest apis
-- CRUD APis -- Genimel, Workflows, Dashboards
or
its going to be Streaming
-- Agent interactions
  -- API Gateway 
    
New Conversations, thread chat storage, 

  

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Request Sources                                     │
│   Web App      Mobile App      CLI / API      Internal Services             │
└──────┬─────────────┬──────────────┬───────────────────┬──────────────────┘
       │             │              │                   │
       ▼             ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       API Gateway (FastAPI)                                  │
│                                                                             │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  ┌────────────────┐ │
│  │Source Config │  │  JWT Auth   │  │ OTel+Prometheus│  │Registry Health │ │
│  │Middleware    │  │  Middleware  │  │ Middleware     │  │Poll (30s)      │ │
│  └──────────────┘  └─────────────┘  └───────────────┘  └────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   REGISTRY (built from manifests at startup)        │   │
│  │  capability_index | event_routing_table | context_key_registry      │   │
│  │  health_dep_graph | planner_catalog     | protocol_version_matrix   │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│  ┌────────────────────────────▼───────────────────────────────────────┐    │
│  │              Dependency-Aware Planner Agent                        │    │
│  │  manifest-driven catalog → dependency resolution → ExecutionPlan  │    │
│  │  workflow_context check → capability satisfaction check           │    │
│  └────────────────────────────┬──────────────────────────────────────┘    │
│                               │                                             │
│  ┌────────────────────────────▼──────────────────────────────────────┐     │
│  │                  Orchestration Engine                             │     │
│  │  SINGLE | PARALLEL | SEQUENTIAL | CONDITIONAL | TWO_PHASE        │     │
│  │  Context key handoff between steps                                │     │
│  │  Phase1 event interception → CCE narration orchestrator           │     │
│  └──────┬──────────────────────┬──────────────────────────┬─────────┘     │
│         │                      │                          │                │
│  ┌──────▼──────┐  ┌────────────▼────────┐  ┌────────────▼────────────┐   │
│  │Context      │  │Thread Manager       │  │CCE Narration            │   │
│  │Composer     │  │(Postgres + Redis)   │  │Orchestrator             │   │
│  │(budget-aware│  │                     │  │(gateway-resident)       │   │
│  │+ ctx-key    │  │workflow_context     │  │                         │   │
│  │ injection)  │  │per-thread           │  │                         │   │
│  └─────────────┘  └─────────────────────┘  └─────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │  ctx_token + slim payload (~1–2KB)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Agent Server (separate host)                           │
│                                                                             │
│  EVERY AGENT EXPOSES:  GET /describe  GET /health  POST /invoke (SSE)      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TIER 3 — Workflow Orchestration                                    │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │  workflow_planner  (LangGraph)                                  │ │   │
│  │  │  Writes: workflow_context to thread long-term memory            │ │   │
│  │  │  Orchestrates: all other agents via sub-plans                   │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TIER 2 — Interpretation & Analysis                                 │   │
│  │  ┌──────────────────────┐  ┌──────────────────────┐                │   │
│  │  │  cce_causal_analysis │  │  alert_analysis      │                │   │
│  │  │  (LangGraph)         │  │  (LangGraph)         │                │   │
│  │  │  Emits intermediate  │  │  Orchestrates CCE    │                │   │
│  │  │  events for narration│  │  for P0/P1 alerts    │                │   │
│  │  └──────────────────────┘  └──────────────────────┘                │   │
│  │  ┌──────────────────────┐  ┌──────────────────────┐                │   │
│  │  │  metrics_recommender │  │  cornerstone_analysis│                │   │
│  │  │  (Claude SDK)        │  │  (LangGraph)         │                │   │
│  │  │  Reads causal KB     │  │  Depends on MDL gold │                │   │
│  │  └──────────────────────┘  └──────────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TIER 1 — Data Foundation                                           │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │  mdl_services  (LangGraph)                                      │ │   │
│  │  │  Produces: gold_layer_csod, mdl_schema_current                  │ │   │
│  │  │  Writes context keys consumed by Tier 2 agents                  │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Self-Description Contract

Every agent on the Agent Server exposes three mandatory HTTP endpoints:

```
GET  /describe   → AgentManifest (JSON)
GET  /health     → HealthStatus (JSON)
POST /invoke     → SSE AgentEvent stream
```

The proxy calls `/describe` at startup for every registered URL. The proxy calls `/health`
every 30 seconds for liveness. `/invoke` is the streaming execution endpoint — unchanged
from v1.0. No agent is reachable for user traffic until `/describe` has been called
successfully and its manifest validated.

---

## 3. Request Source Configuration

*(Unchanged from v2.0 — `cce_narration` feature flag retained)*

---

## 4. JWT & Privilege Model

*(Unchanged from v2.0. Addition: `workflow_planner` feature flag added.)*

```json
"feature_flags": {
  "multi_agent": true,
  "what_if_analysis": false,
  "max_parallel_agents": 3,
  "long_term_memory": true,
  "synthesis": true,
  "cce_narration": true,
  "cce_compound_alerts": true,
  "cce_capability_risk": false,
  "workflow_planner": true,
  "mdl_rebuild": false
}
```

`mdl_rebuild: false` — only elevated roles can trigger a gold layer rebuild via
`mdl_services`. Analysts can read existing gold layer; they cannot initiate a rebuild.

---

## 5. Intent & Planning Layer

### 5.1 ExecutionPlan Schema

*(TWO_PHASE strategy and NarrationMode from v2.0 retained — additions below)*

```python
# planner/models.py

class ExecutionStrategy(str, Enum):
    SINGLE       = "single"
    PARALLEL     = "parallel"
    SEQUENTIAL   = "sequential"
    CONDITIONAL  = "conditional"
    TWO_PHASE    = "two_phase"

class NarrationMode(str, Enum):
    STANDARD     = "standard"
    COMPOUND     = "compound"
    META_ALERT   = "meta_alert"
    FOLLOWUP     = "followup"

@dataclass
class ContextKeyRef:
    key_name: str               # e.g. "mdl_gold_schema_v1"
    source_step_id: str         # which step produced it
    required: bool = True       # if required=True and missing, block this step

@dataclass
class PlanStep:
    step_id: str
    agent_id: str
    input: str
    depends_on: list[str]       # step_id dependencies
    context_keys_in: list[ContextKeyRef]   # NEW: keys this step needs
    context_keys_out: list[str]            # NEW: keys this step produces
    output_role: str
    timeout_seconds: int = 60
    optional: bool = False
    phase: int = 1
    emits_intermediate: bool = False

@dataclass
class ExecutionPlan:
    run_id: str
    strategy: ExecutionStrategy
    steps: list[PlanStep]
    synthesis_required: bool
    original_input: str
    plan_reasoning: str
    estimated_tokens: int
    narration_mode: NarrationMode = NarrationMode.STANDARD
    cce_query: bool = False
    followup_context: dict = None
    workflow_context: dict = None     # NEW: active workflow from workflow_planner
    dependency_satisfied: dict = {}   # NEW: which capability deps are pre-satisfied
```

### 5.2 Dependency-Aware Planner

The planner now receives a manifest-derived catalog that includes dependency declarations,
currently satisfied capabilities (from Redis context key flags), and agent health states.

```python
# planner/planner.py

PLANNER_SYSTEM_PROMPT = """
You are a routing planner for a security compliance and LMS analytics platform.
Given a user message and a live agent catalog, return a JSON ExecutionPlan.

AGENT CATALOG STRUCTURE:
Each agent in the catalog declares:
  - routing_triggers: phrases that signal this agent should be used
  - depends_on_capabilities: capabilities that must exist before this agent runs
  - produces_context_keys: structured outputs written to Redis after this agent runs
  - consumes_context_keys: structured inputs this agent reads from prior steps
  - requires_phase2: if set, always pair with that agent as phase 2

PLANNING RULES:
1. Only use agents the user's JWT grants access to
2. Resolve dependency chains: if agent A depends_on_capabilities ["gold_layer_csod"]
   and mdl_services produces that capability, include mdl_services first
3. Check dependency_satisfied map — if a capability is already satisfied (Redis flag
   exists from a prior session), do not re-run the producing agent
4. Never route to an agent whose health_state is "degraded" — use its fallback instead
5. If workflow_context is present, honour the current_step designation before planning
6. For TWO_PHASE plans: always pair cce_causal_analysis with cce_narration_orchestrator
7. Set context_keys_in on each step from the producing step's context_keys_out
8. Prefer parallel execution for independent agents; sequential only when
   consumes_context_keys creates an ordering requirement

FLEET TIERS (for reasoning about dependency ordering):
  Tier 1 (data foundation): mdl_services
  Tier 2 (interpretation):  cce_causal_analysis, alert_analysis,
                             metrics_recommender, cornerstone_analysis
  Tier 3 (orchestration):   workflow_planner

CCE QUERY DETECTION: (same as v2.0 — triggers TWO_PHASE)

WORKFLOW CONTEXT: If workflow_context.current_step is set, the next step is
pre-determined. Wrap it in the appropriate strategy — do not re-plan from scratch.

Return a valid ExecutionPlan JSON.
"""

class PlannerAgent:
    async def plan(
        self,
        user_input: str,
        claims: ResolvedClaims,
        registry: "AgentRegistry",
        followup_context: dict | None = None,
        workflow_context: dict | None = None
    ) -> ExecutionPlan:

        # Build live catalog from current manifests
        catalog = registry.build_planner_catalog(claims)

        # Check which dependency capabilities are pre-satisfied in Redis
        dep_satisfied = await self._check_satisfied_capabilities(
            thread_id=claims.thread_id,
            tenant_id=claims.tenant_id,
            catalog=catalog
        )

        prompt = f"""
        User message: {user_input}

        Live agent catalog:
        {json.dumps(catalog, indent=2)}

        Pre-satisfied capabilities (skip producing agents for these):
        {json.dumps(dep_satisfied, indent=2)}

        Agent health states:
        {json.dumps(registry.health_states(), indent=2)}

        JWT feature flags: {claims.feature_flags}
        JWT r_node_access: {claims.data_scope.r_node_access}
        Workflow context: {workflow_context}
        Followup context present: {followup_context is not None}

        Return a valid ExecutionPlan JSON.
        """

        raw = await self.llm.ainvoke([
            SystemMessage(PLANNER_SYSTEM_PROMPT),
            HumanMessage(prompt)
        ])

        plan = ExecutionPlan.parse_raw(raw.content)
        plan.followup_context = followup_context
        plan.workflow_context = workflow_context
        plan.dependency_satisfied = dep_satisfied
        return self.enforce_claim_limits(plan, claims)

    async def _check_satisfied_capabilities(
        self,
        thread_id: str,
        tenant_id: str,
        catalog: list[dict]
    ) -> dict[str, bool]:
        """
        For each capability declared in any agent's depends_on_capabilities,
        check whether the producing agent has written its Redis satisfaction flag.
        Returns: { capability_name: True|False }
        """
        satisfied = {}
        for entry in catalog:
            for cap in entry.get("depends_on_capabilities", []):
                key = f"capability:{tenant_id}:{cap}"
                satisfied[cap] = bool(await self.redis.exists(key))
        return satisfied
```

### 5.3 Workflow Context Pre-check

Before any planning, the gateway checks the thread's long-term memory for an active
workflow context. If present, the current step takes priority over planner re-derivation.

```python
# routes/invoke.py

async def get_workflow_context(thread_id: str, redis: Redis) -> dict | None:
    raw = await redis.get(f"workflow:{thread_id}:context")
    if not raw:
        return None
    ctx = json.loads(raw)
    if ctx.get("status") == "active":
        return ctx
    return None
```

---

## 6. Thread Management

*(Unchanged from v2.0. Additions: `workflow_context` JSONB column on `threads` table;
per-section narration rows with `narration_state` on `messages` table.)*

```sql
ALTER TABLE threads  ADD COLUMN workflow_context JSONB DEFAULT NULL;
ALTER TABLE messages ADD COLUMN narration_state  JSONB DEFAULT NULL;
ALTER TABLE messages ADD COLUMN context_keys_out JSONB DEFAULT NULL;
-- context_keys_out: keys this message's agent wrote, for downstream reuse
```

---

## 7. History & Memory Model

*(Unchanged from v2.0 — three-tier architecture retained.)*

Workflow context is Tier 3 long-term memory. The workflow planner writes and reads it
from `workflow:{thread_id}:context` in Redis and the `threads.workflow_context` column
in Postgres for persistence across Redis eviction.

---

## 8. Context Composition

*(Unchanged from v2.0. Addition: context key injection into agent payloads.)*

The `ContextComposer.compose()` method gains a `context_keys_in` parameter. For each
declared key in the step's `context_keys_in`, the composer fetches the key's value from
Redis and injects it into the ctx_token payload under `agent_context.{key_name}`. The
agent reads it from `context.agent_context` — it does not need to know about Redis keys.

```python
# context/composer.py  (addition)

async def inject_context_keys(
    self,
    context: ComposedContext,
    keys_in: list[ContextKeyRef],
    tenant_id: str,
    thread_id: str
) -> ComposedContext:
    for key_ref in keys_in:
        redis_key = f"ctxkey:{tenant_id}:{thread_id}:{key_ref.key_name}"
        value = await self.redis.get(redis_key)
        if value is None and key_ref.required:
            raise ContextKeyMissingError(key_ref.key_name, key_ref.source_step_id)
        if value:
            context.agent_context[key_ref.key_name] = json.loads(value)
    return context
```

---

## 9. Redis Caching Architecture

### Key Schema (updated — full fleet keys added)

```
# Standard thread keys (unchanged)
thread:{thread_id}:working_mem          TTL: 2h
thread:{thread_id}:summary              TTL: 24h
thread:{thread_id}:meta                 TTL: 2h
run:{run_id}:state                      TTL: 10m
ctx:{token_id}                          TTL: 5m
memory:{tenant_id}:facts                TTL: 1h
registry:agents                         TTL: none (rebuilt on re-describe)
ratelimit:{source_id}:{user_id}:rpm     TTL: 60s
source:{source_id}:config               TTL: 5m

# CCE keys (from v2.0)
cce_graph:{run_id}:{tenant_id}          TTL: 15m
cce_narration:{run_id}:routing_state    TTL: 15m
cce_collider:{run_id}                   TTL: 15m
cce_followup:{thread_id}:last           TTL: 30m
cce_graph:{run_id}:warm                 TTL: 15m

# NEW — Context Key Handoff (written by agents at STEP_FINAL)
ctxkey:{tenant_id}:{thread_id}:{key_name}     TTL: 4h
  → Structured JSON produced by one agent, consumed by subsequent agents
  → e.g. ctxkey:org_xyz:t_abc:mdl_gold_schema_v2
  → e.g. ctxkey:org_xyz:t_abc:cce_causal_subgraph_v1
  → e.g. ctxkey:org_xyz:t_abc:csod_observable_nodes_v1
  → e.g. ctxkey:org_xyz:t_abc:metrics_recommendation_v1

# NEW — Capability Satisfaction Flags (written by agents on capability completion)
capability:{tenant_id}:{capability_name}      TTL: 24h
  → "1" when the capability has been produced and is current
  → e.g. capability:org_xyz:gold_layer_csod
  → e.g. capability:org_xyz:mdl_schema_current
  → e.g. capability:org_xyz:causal_graph_seeded
  → Cleared by MDL services when a rebuild starts (prevents stale reads)

# NEW — Workflow Context (written by workflow_planner)
workflow:{thread_id}:context            TTL: 7d (long-lived — spans sessions)
  → { workflow_id, workflow_type, current_step, total_steps,
      steps_completed, steps_remaining, status, started_at }

# NEW — Agent Manifest Cache (built from /describe at startup, refreshed on re-describe)
manifest:{agent_id}                     TTL: none (cleared on re-describe)
  → Full AgentManifest JSON
manifest:{agent_id}:version             TTL: none
  → Version string for drift detection

# NEW — Health State (updated by 30s health poll)
health:{agent_id}                       TTL: 90s  (3 missed polls = expired = degraded)
  → { status: "healthy"|"degraded"|"unavailable", last_check: ISO, details: {} }

# NEW — Protocol Version Compatibility Matrix (built at startup)
protocol_compat:{producer_agent}:{consumer_agent}:{key_name}    TTL: none
  → { compatible: true, resolved_version: "v2", producer_supports: ["v1","v2"],
      consumer_supports: ["v2"] }
```

---

## 10. Agent Adapter Layer

### 10.1 Abstract Interface (updated — `describe()` is mandatory third method)

Every adapter must implement three methods. An adapter that cannot implement `describe()`
cannot be registered. This is the central contract change in v3.0.

```python
# adapters/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator

class AgentAdapter(ABC):
    """
    All agent frameworks implement this interface.
    Adapters are stateless — all state is in ComposedContext.

    THREE MANDATORY METHODS:
      describe()        — called at startup; returns AgentManifest
      stream()          — called per request; returns SSE AgentEvent stream
      normalize_event() — maps framework-native events to AgentEvent protocol
    """

    @abstractmethod
    async def describe(self) -> "AgentManifest":
        """
        Called once at startup (and periodically on re-describe cycles).
        For remote agents: makes HTTP GET /describe call.
        For gateway-resident agents: returns manifest synchronously.
        Must complete within 5 seconds or agent is marked unavailable.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        payload: dict,
        context: ComposedContext,
        config: dict
    ) -> AsyncIterator["AgentEvent"]:
        ...

    @abstractmethod
    def normalize_event(self, raw_event: any) -> "AgentEvent":
        ...
```

### 10.2 AgentManifest Schema

The `AgentManifest` is the complete self-description. It replaces `AgentMeta` as the
source of truth. `AgentMeta` is derived from `AgentManifest` after validation — nothing
else in the system changes.

```python
# adapters/manifest.py

@dataclass
class IntermediateEventSpec:
    event_type: str             # e.g. "cce_router_complete"
    description: str
    timing_hint: str            # e.g. "~80ms after invocation"
    recipient_hint: str         # agent_id of the intended consumer
    payload_schema: dict        # JSON schema of the event data field

@dataclass
class ContextKeySpec:
    key_name: str               # e.g. "mdl_gold_schema_v2"
    schema_version: str         # e.g. "v2"
    supported_versions: list[str]  # e.g. ["v1", "v2"] — for compatibility matrix
    description: str
    ttl_seconds: int = 14400    # how long this key stays valid (default 4h)
    invalidated_by: list[str] = field(default_factory=list)
    # events that should clear this key, e.g. ["mdl_rebuild_started"]

@dataclass
class CapabilitySpec:
    name: str                   # e.g. "gold_layer_csod"
    description: str
    satisfaction_flag_ttl: int = 86400  # how long the satisfaction flag lives (default 24h)

@dataclass
class AgentManifest:
    # Identity
    agent_id: str
    display_name: str
    version: str
    framework: str              # "langgraph" | "claude_sdk" | "gateway_native" | "a2a"

    # Planner-facing
    routing_triggers: list[str]
    planner_description: str    # written by agent, for planner LLM context window
    required_role: str
    feature_flag: str | None
    phase: int = 1
    gateway_resident: bool = False
    requires_phase2: str | None = None  # agent_id of required phase-2 partner
    orchestrates: list[str] = field(default_factory=list)  # agents this agent may invoke
    writes_to_thread_state: bool = False  # True for workflow_planner
    influences_future_plans: bool = False # True for workflow_planner

    # Dependency declarations
    depends_on_capabilities: list[str] = field(default_factory=list)
    # capabilities that must exist (from capability_index) before this agent runs

    # Context key contract
    produces_context_keys: list[ContextKeySpec] = field(default_factory=list)
    consumes_context_keys: list[str] = field(default_factory=list)
    # key_names this agent reads from agent_context — must be produced by prior step

    # Capabilities produced (for capability_index)
    provides_capabilities: list[CapabilitySpec] = field(default_factory=list)

    # Intermediate events (CCE pattern — generalisable)
    intermediate_events: list[IntermediateEventSpec] = field(default_factory=list)
    emits_intermediate_events: bool = False

    # Context window budget
    context_window_tokens: int = 8000
    system_ctx_tokens: int = 1500
    session_ctx_tokens: int = 3000
    turn_ctx_tokens: int = 2000
    response_reserve_tokens: int = 1500
    requires_memory: bool = False
    requires_memory_keys: list[str] = field(default_factory=list)

    # JWT requirements
    jwt_claims_required: list[str] = field(default_factory=list)
    data_scope_requirements: dict = field(default_factory=dict)

    # Infrastructure
    health_check_path: str = "/health"
    describe_path: str = "/describe"
    tenant_scoped: bool = True

    def to_agent_meta(self) -> "AgentMeta":
        """Derive AgentMeta for downstream compatibility."""
        return AgentMeta(
            agent_id=self.agent_id,
            display_name=self.display_name,
            framework=self.framework,
            capabilities=[e.event_type for e in self.intermediate_events],
            context_window_tokens=self.context_window_tokens,
            system_ctx_tokens=self.system_ctx_tokens,
            session_ctx_tokens=self.session_ctx_tokens,
            turn_ctx_tokens=self.turn_ctx_tokens,
            response_reserve_tokens=self.response_reserve_tokens,
            required_role=self.required_role,
            feature_flag=self.feature_flag,
            routing_tags=self.routing_triggers,
            tenant_scoped=self.tenant_scoped,
            phase=self.phase,
            gateway_resident=self.gateway_resident,
            emits_intermediate_events=self.emits_intermediate_events,
        )

    def to_catalog_entry(self) -> dict:
        """Stripped version sent to planner LLM."""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "planner_description": self.planner_description,
            "routing_triggers": self.routing_triggers,
            "depends_on_capabilities": self.depends_on_capabilities,
            "provides_capabilities": [c.name for c in self.provides_capabilities],
            "produces_context_keys": [k.key_name for k in self.produces_context_keys],
            "consumes_context_keys": self.consumes_context_keys,
            "orchestrates": self.orchestrates,
            "requires_phase2": self.requires_phase2,
            "phase": self.phase,
        }
```

### 10.3 Remote Agent Adapter (HTTP describe)

```python
# adapters/remote_adapter.py

class RemoteAgentAdapter(AgentAdapter):
    """
    Base adapter for all agents on the Agent Server.
    Subclasses (LangGraphAdapter, ClaudeSDKAdapter) extend this.
    describe() makes an HTTP GET /describe call.
    """

    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        self.base_url = base_url
        self.http_client = http_client

    async def describe(self) -> AgentManifest:
        try:
            resp = await self.http_client.get(
                f"{self.base_url}/describe",
                timeout=5.0
            )
            resp.raise_for_status()
            return AgentManifest.model_validate(resp.json())
        except Exception as e:
            raise AgentDescribeError(self.base_url, str(e))

    async def health(self) -> HealthStatus:
        try:
            resp = await self.http_client.get(
                f"{self.base_url}/health",
                timeout=3.0
            )
            return HealthStatus.model_validate(resp.json())
        except Exception:
            return HealthStatus(status="unavailable")
```

### 10.4 LangGraph Adapter (SSE stream — framework specific)

```python
# adapters/langgraph_adapter.py

class LangGraphAdapter(RemoteAgentAdapter):
    """
    Remote adapter for LangGraph agents on the Agent Server.
    describe() inherited from RemoteAgentAdapter (HTTP call).
    stream() sends payload and streams SSE events back.
    """

    async def stream(
        self,
        payload: dict,
        context: ComposedContext,
        config: dict
    ) -> AsyncIterator[AgentEvent]:
        async with self.http_client.stream(
            "POST",
            f"{self.base_url}/invoke",
            json=payload,
            timeout=None
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    raw = json.loads(line[6:])
                    event = self.normalize_event(raw)
                    if event:
                        yield event

    def normalize_event(self, raw: dict) -> AgentEvent | None:
        event_type = raw.get("type")
        if not event_type:
            return None
        try:
            return AgentEvent(
                type=EventType(event_type),
                agent_id=raw.get("agent_id", ""),
                run_id=raw.get("run_id", ""),
                step_id=raw.get("step_id", ""),
                tenant_id=raw.get("tenant_id", ""),
                data=raw.get("data", {}),
                metadata=raw.get("metadata", {})
            )
        except ValueError:
            return None  # unknown event type — ignore
```

### 10.5 Claude SDK Adapter (unchanged from v2.0)

```python
# adapters/claude_adapter.py

class ClaudeAgentAdapter(RemoteAgentAdapter):
    """
    For agents using the Claude SDK directly rather than LangGraph.
    describe() inherited from RemoteAgentAdapter.
    stream() uses Anthropic streaming messages API.
    """

    async def stream(self, payload, context, config) -> AsyncIterator[AgentEvent]:
        messages = to_claude_messages(context.turn.recent)
        messages.append({"role": "user", "content": payload["input"]})
        system = f"{context.system.persona}\n\nContext:\n{context.session.summary or ''}"
        system += f"\n\nAgent context:\n{json.dumps(context.agent_context)}"

        async with self.anthropic_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system,
            messages=messages
        ) as stream:
            async for raw in stream:
                event = self.normalize_event(raw)
                if event:
                    yield event

    def normalize_event(self, raw) -> AgentEvent | None:
        if raw.type == "content_block_delta":
            return AgentEvent(type=EventType.TOKEN, data={"text": raw.delta.text})
        if raw.type == "message_stop":
            return AgentEvent(type=EventType.FINAL, data={"text": ""})
        return None

    async def describe(self) -> AgentManifest:
        # Claude SDK agents still expose /describe — same HTTP call
        return await super().describe()
```

### 10.6 Gateway Narration Adapter (unchanged from v2.0, describe() added)

```python
# adapters/gateway_narration_adapter.py

class GatewayNarrationAdapter(AgentAdapter):
    """Gateway-resident. describe() returns manifest in-process."""

    def __init__(self, orchestrator: "CCENarrationOrchestrator"):
        self.orchestrator = orchestrator

    async def describe(self) -> AgentManifest:
        return self.orchestrator.get_manifest()  # in-process, no network call

    async def stream(self, payload, context, config) -> AsyncIterator[AgentEvent]:
        async for event in self.orchestrator.run(**payload):
            yield event

    def normalize_event(self, raw) -> AgentEvent | None:
        return raw
```

### 10.7 Updated Agent Registry

```python
# adapters/registry.py

class AgentRegistry:
    def __init__(self, redis: Redis):
        self._adapters: dict[str, AgentAdapter] = {}
        self._manifests: dict[str, AgentManifest] = {}
        self._health: dict[str, HealthStatus] = {}
        self.redis = redis

        # Built from manifests at startup:
        self._capability_index: dict[str, list[str]] = {}
        # { capability_name → [agent_ids that provide it] }

        self._event_routing_table: dict[str, str] = {}
        # { event_type → recipient_agent_id }

        self._context_key_registry: dict[str, list[str]] = {}
        # { key_name → [agent_ids that produce it] }

        self._health_dep_graph: dict[str, list[str]] = {}
        # { agent_id → [agent_ids it depends on for health] }

        self._protocol_compat: dict[tuple, dict] = {}
        # { (producer_id, consumer_id, key_name) → compatibility_result }

    def register_from_manifest(
        self,
        manifest: AgentManifest,
        adapter: AgentAdapter
    ):
        self._adapters[manifest.agent_id] = adapter
        self._manifests[manifest.agent_id] = manifest

        # Build capability index
        for cap in manifest.provides_capabilities:
            self._capability_index.setdefault(cap.name, []).append(manifest.agent_id)

        # Build event routing table
        for evt in manifest.intermediate_events:
            if evt.recipient_hint:
                self._event_routing_table[evt.event_type] = evt.recipient_hint

        # Build context key registry
        for key in manifest.produces_context_keys:
            self._context_key_registry.setdefault(key.key_name, []).append(manifest.agent_id)

        # Build health dependency graph
        for dep_cap in manifest.depends_on_capabilities:
            providers = self._capability_index.get(dep_cap, [])
            for provider in providers:
                self._health_dep_graph.setdefault(manifest.agent_id, []).append(provider)

        # Persist manifest to Redis
        asyncio.create_task(self.redis.set(
            f"manifest:{manifest.agent_id}",
            manifest.model_dump_json()
        ))

    def build_planner_catalog(self, claims: ResolvedClaims) -> list[dict]:
        return [
            m.to_catalog_entry()
            for m in self._manifests.values()
            if claims.can_access_agent(m.agent_id)
            and self._health.get(m.agent_id, HealthStatus()).status != "unavailable"
            and not m.gateway_resident  # narration orchestrator excluded from planner
        ]

    def get_event_recipient(self, event_type: str) -> str | None:
        return self._event_routing_table.get(event_type)

    def should_intercept_event(self, event_type: str) -> bool:
        return event_type in self._event_routing_table

    def health_states(self) -> dict[str, str]:
        return {aid: h.status for aid, h in self._health.items()}

    def update_health(self, agent_id: str, status: HealthStatus):
        self._health[agent_id] = status
        # Propagate degradation to dependents
        for dependent, deps in self._health_dep_graph.items():
            if agent_id in deps:
                if status.status in ("degraded", "unavailable"):
                    if self._health.get(dependent, HealthStatus()).status == "healthy":
                        self._health[dependent] = HealthStatus(
                            status="partially_degraded",
                            details={"degraded_dependency": agent_id}
                        )
```

---

## 11. Event Protocol

### 11.1 AgentEvent Schema (updated — fleet event types added)

```python
# protocol/events.py

class EventType(str, Enum):
    # Core streaming
    TOKEN            = "token"
    TOOL_START       = "tool_start"
    TOOL_END         = "tool_end"

    # Lifecycle
    STEP_START       = "step_start"
    STEP_FINAL       = "step_final"
    STEP_ERROR       = "step_error"
    FINAL            = "final"

    # Orchestration
    PLAN             = "plan"
    PLAN_MODIFIED    = "plan_modified"
    SYNTHESIS_START  = "synthesis_start"
    ERROR            = "error"

    # CCE intermediate (from v2.0)
    CCE_ROUTER_COMPLETE   = "cce_router_complete"
    CCE_COLLIDER_COMPLETE = "cce_collider_complete"
    CCE_LR_COMPLETE       = "cce_lr_complete"

    # CCE narration (from v2.0)
    CCE_SECTION_START     = "cce_section_start"
    CCE_SECTION_COMPLETE  = "cce_section_complete"
    CCE_FOLLOWUP_READY    = "cce_followup_ready"
    CCE_META_ALERT        = "cce_meta_alert"
    CCE_CORRECTION        = "cce_correction"

    # NEW — Context key handoff (all agents)
    CONTEXT_KEY_WRITTEN   = "context_key_written"
    # data: { "key_name": "...", "schema_version": "...", "ttl_seconds": N }
    # Emitted by any agent that produces a context key.
    # Orchestration engine intercepts and writes to Redis.
    # Not forwarded to frontend.

    CAPABILITY_SATISFIED  = "capability_satisfied"
    # data: { "capability_name": "..." }
    # Emitted when an agent completes a capability provision.
    # Orchestration engine writes capability flag to Redis.
    # Not forwarded to frontend.

    # NEW — Workflow events (workflow_planner)
    WORKFLOW_STEP_START   = "workflow_step_start"
    # data: { "workflow_id": "...", "step": N, "total": N, "step_name": "..." }
    WORKFLOW_STEP_COMPLETE = "workflow_step_complete"
    WORKFLOW_COMPLETE     = "workflow_complete"
    WORKFLOW_PAUSED       = "workflow_paused"
    # Forwarded to frontend — drives workflow progress UI.

    # NEW — MDL events (mdl_services)
    MDL_LAYER_START       = "mdl_layer_start"
    # data: { "layer": "silver"|"gold", "table_count": N }
    MDL_LAYER_COMPLETE    = "mdl_layer_complete"
    # data: { "layer": "...", "tables_built": [...], "schema_version": "..." }
    MDL_REBUILD_STARTED   = "mdl_rebuild_started"
    # Signals that existing capability flags for this tenant should be cleared.

    # NEW — Alert analysis events (alert_analysis)
    ALERT_CLASSIFIED      = "alert_classified"
    # data: { "alert_id": "...", "classification": "...", "confidence": 0.0–1.0,
    #         "routed_to": "cce_causal_analysis"|"cornerstone_analysis"|... }
    ALERT_TRIAGE_COMPLETE = "alert_triage_complete"


# Intercepted events — NOT forwarded to frontend (registry-driven, not hardcoded)
# Built from event_routing_table at startup.
# Any event whose type appears in event_routing_table is intercepted.
def is_intercepted(event_type: str, registry: AgentRegistry) -> bool:
    return registry.should_intercept_event(event_type)

# Additionally, these operational events are always intercepted:
ALWAYS_INTERCEPTED = {
    EventType.CONTEXT_KEY_WRITTEN,
    EventType.CAPABILITY_SATISFIED,
    EventType.MDL_REBUILD_STARTED,
}
```

---

## 12. Multi-Agent Orchestration

### 12.1 Orchestration Engine (updated — context key handoff integrated)

```python
# orchestration/engine.py

class OrchestrationEngine:

    async def execute(self, plan, claims, thread_id, output_queue):
        if plan.strategy == ExecutionStrategy.TWO_PHASE:
            await self.execute_two_phase(plan, claims, thread_id, output_queue)
        elif plan.strategy == ExecutionStrategy.PARALLEL:
            await self.execute_parallel(plan.steps, claims, thread_id, output_queue)
        elif plan.strategy == ExecutionStrategy.SEQUENTIAL:
            await self.execute_sequential(plan.steps, claims, thread_id, output_queue)
        else:
            await self.execute_single(plan.steps[0], claims, thread_id, output_queue)

        if plan.synthesis_required and plan.strategy != ExecutionStrategy.TWO_PHASE:
            await self.synthesize(plan, output_queue)

    async def execute_sequential(self, steps, claims, thread_id, queue):
        """
        Sequential execution with context key handoff.
        Each step receives context keys produced by prior steps.
        """
        step_results = {}
        accumulated_ctx_keys = {}  # key_name → value, built as steps complete

        for step in steps:
            # Inject context keys from prior steps
            context = await self.context_composer.compose(
                thread_id=thread_id,
                user_input=step.input,
                agent_meta=self.registry.get_meta(step.agent_id),
                claims=claims
            )
            # Inject declared consumed keys from Redis + accumulated in-session keys
            for key_ref in step.context_keys_in:
                val = accumulated_ctx_keys.get(key_ref.key_name) or \
                      await self._fetch_ctx_key(claims.tenant_id, thread_id, key_ref.key_name)
                if val is None and key_ref.required:
                    await queue.put(self._make_step_error(
                        step, f"Required context key '{key_ref.key_name}' not available"
                    ))
                    if not step.optional:
                        raise ContextKeyMissingError(key_ref.key_name)
                    continue
                context.agent_context[key_ref.key_name] = val

            ctx_token = await self.ctx_token_svc.mint(context)
            payload = self.build_payload(step, ctx_token, claims)
            adapter = self.registry.get_adapter(step.agent_id)

            final_text = ""
            async for event in adapter.stream(payload, context, {}):
                event.agent_id = step.agent_id
                event.step_id = step.step_id

                # Handle context key events
                if event.type == EventType.CONTEXT_KEY_WRITTEN:
                    key_name = event.data["key_name"]
                    # Value was written to Redis by the agent; also cache in-session
                    val = await self._fetch_ctx_key(claims.tenant_id, thread_id, key_name)
                    accumulated_ctx_keys[key_name] = val
                    continue  # Do not forward to frontend

                if event.type == EventType.CAPABILITY_SATISFIED:
                    await self._write_capability_flag(
                        claims.tenant_id, event.data["capability_name"]
                    )
                    continue

                if event.type in ALWAYS_INTERCEPTED:
                    await self._handle_operational_event(event, claims)
                    continue

                if self.registry.should_intercept_event(event.type):
                    await self._route_intercepted_event(event, claims)
                    continue

                await queue.put(event)
                if event.type == EventType.FINAL:
                    final_text = event.data.get("text", "")

            step_results[step.step_id] = final_text

    async def _write_capability_flag(self, tenant_id: str, capability_name: str):
        manifest_cap = self._find_capability_spec(capability_name)
        ttl = manifest_cap.satisfaction_flag_ttl if manifest_cap else 86400
        await self.redis.setex(f"capability:{tenant_id}:{capability_name}", ttl, "1")

    async def _fetch_ctx_key(self, tenant_id, thread_id, key_name) -> dict | None:
        raw = await self.redis.get(f"ctxkey:{tenant_id}:{thread_id}:{key_name}")
        return json.loads(raw) if raw else None

    async def _handle_operational_event(self, event: AgentEvent, claims: ResolvedClaims):
        if event.type == EventType.MDL_REBUILD_STARTED:
            # Clear all capability flags for this tenant — data is stale
            keys = await self.redis.keys(f"capability:{claims.tenant_id}:*")
            if keys:
                await self.redis.delete(*keys)
```

### 12.2 TWO_PHASE execution (unchanged from v2.0 — event routing now registry-driven)

```python
    async def execute_two_phase(self, plan, claims, thread_id, output_queue):
        # (Same structure as v2.0 but event interception uses registry)
        phase1_event_queue: asyncio.Queue = asyncio.Queue()

        async def run_phase1():
            # ... (same as v2.0) ...
            async for event in adapter.stream(payload, context, {}):
                if self.registry.should_intercept_event(event.type) or \
                   event.type in ALWAYS_INTERCEPTED:
                    # Route to narration orchestrator's queue
                    await phase1_event_queue.put(event)
                else:
                    await output_queue.put(event)
            await phase1_event_queue.put(SENTINEL_PHASE1_COMPLETE)

        async def run_phase2():
            # ... (same as v2.0) ...
            pass

        await asyncio.gather(run_phase1(), run_phase2())
```

---

## 13. Observability

*(Unchanged from v2.0, additions below.)*

**New metrics:**
- `registry.describe_latency_ms` — per-agent, at startup and re-describe
- `registry.manifest_version_drift` — when health poll returns version ≠ startup manifest version
- `context_key.write_latency_ms` — time from CONTEXT_KEY_WRITTEN event to Redis write
- `context_key.cache_miss_rate` — rate at which required context keys are missing
- `capability.satisfaction_age_seconds` — how old each capability flag is when read
- `workflow.step_completion_rate` — fraction of workflow steps completing vs abandoning
- `agent.partial_degradation_count` — agents marked partially_degraded due to dependency

---

## 14. Failure Handling

*(Base table from v2.0 retained. Fleet-specific rows added.)*

| Failure | Behavior |
|---|---|
| Agent timeout | Emit `step_error`, mark optional if plan allows, continue |
| Context token expired | Re-compose, re-mint, retry once |
| Redis unavailable | Fall back to Postgres, log degraded mode |
| Planner returns invalid plan | Fallback to single-agent via routing_tags match |
| JWT expired mid-stream | Close SSE, 401 on next request |
| Agent returns no FINAL | Gateway emits synthetic FINAL after timeout |
| Parallel step fails | optional=true: continue; optional=false: abort |
| CCE: ROUTER_COMPLETE timeout | CONTEXT_NARRATOR fires with generic framing |
| CCE: COLLIDER_COMPLETE timeout | WHY agent fires with generic collider caution |
| **NEW: /describe fails at startup** | Agent excluded from registry; proxy starts without it; `agent.describe_failed` metric emitted; background retry every 60s |
| **NEW: /describe returns invalid manifest** | Schema validation error logged; agent excluded; `manifest.validation_failed` metric |
| **NEW: manifest version drift detected** | `agent_manifest_version_drift` metric; re-describe triggered; if new manifest incompatible with current session context keys, session flagged for context key refresh |
| **NEW: required context key missing** | Step emits `step_error` with `ContextKeyMissingError`; if step is optional, plan continues with degraded context; if required, plan aborts with explanation to user: "Prerequisite data not available — [agent] needs to run first" |
| **NEW: context key version incompatible** | Registry detects at plan time via `protocol_compat` matrix; planner receives `incompatible_key_versions` in health states; planner excludes affected step pair and surfaces to user |
| **NEW: capability flag stale/missing** | Planner re-includes producing agent in plan; user sees "rebuilding [capability] before proceeding" narration |
| **NEW: mdl_services degraded** | `cornerstone_analysis` marked partially_degraded automatically via health dep graph; planner excludes cornerstone_analysis from plans; user sees "Data foundation agent is unavailable — analysis requiring CSOD gold layer is temporarily disabled" |
| **NEW: workflow_planner degraded** | Workflow context preserved in Redis/Postgres; single-turn plans continue unaffected; multi-step workflows paused until recovery; user notified |
| **NEW: alert_analysis → CCE dependency degraded** | alert_analysis demotes to classification-only mode; emits `ALERT_CLASSIFIED` without routing to CCE; user sees alert classification without causal root cause |
| **NEW: workflow step abandonment** | If user departs from workflow with a clearly off-workflow query for 3+ turns, workflow_planner marks workflow as paused; `workflow.status = paused`; resumes on next on-workflow query |

---

## 15. CCE Hybrid Narration Orchestrator

*(Unchanged from v2.0 — full implementation retained.)*
*(One update: `get_manifest()` method added for in-process describe.)*

```python
# orchestration/cce_narration_orchestrator.py (addition)

class CCENarrationOrchestrator:

    def get_manifest(self) -> AgentManifest:
        """Called by GatewayNarrationAdapter.describe() — in-process, no network."""
        return AgentManifest(
            agent_id="cce_narration_orchestrator",
            display_name="CCE Narration Orchestrator",
            version=CCE_VERSION,
            framework="gateway_native",
            phase=2,
            gateway_resident=True,
            routing_triggers=[],
            planner_description=(
                "Gateway-resident narration orchestrator. Never planned directly. "
                "Always phase 2 of a cce_causal_analysis plan. Reacts to intermediate "
                "events from phase 1 and drives narration agents as direct LLM calls."
            ),
            required_role="analyst",
            feature_flag="cce_narration",
            depends_on_agent="cce_causal_analysis",
            depends_on_phase1_events=[
                "cce_router_complete",
                "cce_collider_complete",
                "cce_lr_complete",
                "step_final"
            ],
            consumes_context_keys=["cce_graph_state_v1"],
            tenant_scoped=True,
        )
```

---

## 16. Registry Bootstrap — Startup Self-Description

This section specifies the startup sequence that replaces `registry_setup.py`. The proxy
contains zero hardcoded agent knowledge. It reads `agents.yaml` (URLs and trust config only)
and builds all routing intelligence from live `/describe` responses.

### 16.1 agents.yaml — The Only Hardcoded Config

```yaml
# config/agents.yaml
# Contains ONLY: agent URLs, trust level, and gateway_native flag.
# NO capabilities, NO routing tags, NO context keys.
# Everything else comes from /describe.

agents:

  # Tier 1 — Data Foundation
  - agent_id: mdl_services
    url: http://agent-server:8001/agents/mdl_services
    trust_level: internal
    type: remote

  # Tier 2 — Interpretation & Analysis
  - agent_id: cce_causal_analysis
    url: http://agent-server:8001/agents/cce_causal_analysis
    trust_level: internal
    type: remote

  - agent_id: alert_analysis
    url: http://agent-server:8001/agents/alert_analysis
    trust_level: internal
    type: remote

  - agent_id: metrics_recommender
    url: http://agent-server:8001/agents/metrics_recommender
    trust_level: internal
    type: remote

  - agent_id: cornerstone_analysis
    url: http://agent-server:8001/agents/cornerstone_analysis
    trust_level: internal
    type: remote

  # Tier 3 — Workflow Orchestration
  - agent_id: workflow_planner
    url: http://agent-server:8001/agents/workflow_planner
    trust_level: internal
    type: remote

  # Tier 0 — Gateway-Resident (no URL — in-process)
  - agent_id: cce_narration_orchestrator
    type: gateway_native
    class: CCENarrationOrchestrator
```

### 16.2 RegistryBootstrap

```python
# adapters/bootstrap.py

class RegistryBootstrap:
    """
    Runs at proxy startup. Discovers all agents via /describe.
    Builds registry data structures from live manifests.
    Proxy does not accept user traffic until bootstrap completes.
    """

    def __init__(
        self,
        agents_config: list[AgentConfig],
        registry: AgentRegistry,
        redis: Redis,
        http_client: httpx.AsyncClient
    ):
        self.agents_config = agents_config
        self.registry = registry
        self.redis = redis
        self.http_client = http_client

    async def run(self) -> BootstrapResult:
        result = BootstrapResult()

        # Step 1: Build adapters from config
        adapters = self._build_adapters()

        # Step 2: Describe all agents in parallel (5s timeout per agent)
        describe_results = await asyncio.gather(
            *[self._describe_agent(cfg, adapter)
              for cfg, adapter in adapters.items()],
            return_exceptions=True
        )

        # Step 3: Validate manifests and register
        for cfg, describe_result in zip(adapters.keys(), describe_results):
            if isinstance(describe_result, Exception):
                result.failed.append(cfg.agent_id)
                logger.error(
                    f"Agent {cfg.agent_id} describe failed: {describe_result}"
                )
                metrics.increment("registry.describe_failed",
                                  tags={"agent_id": cfg.agent_id})
                continue

            manifest, adapter = describe_result
            try:
                self._validate_manifest(manifest)
                self.registry.register_from_manifest(manifest, adapter)
                result.registered.append(cfg.agent_id)
                logger.info(
                    f"Registered {cfg.agent_id} v{manifest.version} "
                    f"({len(manifest.routing_triggers)} triggers, "
                    f"{len(manifest.intermediate_events)} intermediate events, "
                    f"{len(manifest.produces_context_keys)} context keys produced)"
                )
            except ManifestValidationError as e:
                result.failed.append(cfg.agent_id)
                logger.error(f"Manifest validation failed for {cfg.agent_id}: {e}")

        # Step 4: Build protocol compatibility matrix
        await self._build_protocol_compat_matrix()

        # Step 5: Validate dependency graph (no cycles, all deps resolvable)
        self._validate_dependency_graph(result)

        # Step 6: Log startup summary
        self._log_startup_summary(result)

        return result

    async def _describe_agent(
        self,
        cfg: AgentConfig,
        adapter: AgentAdapter
    ) -> tuple[AgentManifest, AgentAdapter]:
        t0 = time.time()
        manifest = await adapter.describe()
        latency_ms = int((time.time() - t0) * 1000)
        metrics.record("registry.describe_latency_ms", latency_ms,
                       tags={"agent_id": cfg.agent_id})
        # Verify agent_id matches config
        if manifest.agent_id != cfg.agent_id:
            raise ManifestValidationError(
                f"agent_id mismatch: config={cfg.agent_id}, manifest={manifest.agent_id}"
            )
        return manifest, adapter

    def _validate_manifest(self, manifest: AgentManifest):
        # Required fields
        assert manifest.agent_id, "agent_id required"
        assert manifest.version, "version required"
        assert manifest.planner_description, "planner_description required"
        assert manifest.routing_triggers is not None, "routing_triggers required"

        # Context key version format
        for key in manifest.produces_context_keys:
            assert re.match(r"^[a-z_]+_v\d+$", key.key_name), \
                f"Context key name must follow pattern 'name_vN': {key.key_name}"

        # Intermediate event recipient hints must reference registered agents
        for evt in manifest.intermediate_events:
            if evt.recipient_hint and evt.recipient_hint not in \
               [c.agent_id for c in self.agents_config]:
                raise ManifestValidationError(
                    f"Intermediate event recipient '{evt.recipient_hint}' "
                    f"not in agents.yaml"
                )

    async def _build_protocol_compat_matrix(self):
        """
        For each (producer, consumer, key_name) pair where producer produces
        a key and consumer consumes it, determine the highest compatible version.
        """
        manifests = self.registry.all_manifests()
        for producer in manifests.values():
            for key_spec in producer.produces_context_keys:
                consumers = [
                    m for m in manifests.values()
                    if key_spec.key_name.rsplit("_v", 1)[0] + "_v" in
                    " ".join(m.consumes_context_keys)
                ]
                for consumer in consumers:
                    compat = self._resolve_version_compat(
                        producer_versions=key_spec.supported_versions,
                        consumer_versions=self._consumer_supported_versions(
                            consumer, key_spec.key_name
                        )
                    )
                    key = (producer.agent_id, consumer.agent_id, key_spec.key_name)
                    self.registry._protocol_compat[key] = compat
                    if not compat["compatible"]:
                        logger.warning(
                            f"INCOMPATIBLE: {producer.agent_id} → {consumer.agent_id} "
                            f"on key {key_spec.key_name}. "
                            f"Producer: {key_spec.supported_versions}, "
                            f"Consumer: {compat['consumer_supports']}"
                        )

    def _validate_dependency_graph(self, result: BootstrapResult):
        """Detect cycles and unresolvable dependencies."""
        registered = set(result.registered)
        for agent_id in registered:
            manifest = self.registry._manifests[agent_id]
            for cap in manifest.depends_on_capabilities:
                providers = self.registry._capability_index.get(cap, [])
                if not providers:
                    logger.warning(
                        f"{agent_id} depends on capability '{cap}' "
                        f"but no registered agent provides it"
                    )
                elif not any(p in registered for p in providers):
                    logger.warning(
                        f"{agent_id} depends on capability '{cap}' "
                        f"but all providers failed registration: {providers}"
                    )

    def _log_startup_summary(self, result: BootstrapResult):
        logger.info(
            f"\n{'='*60}\n"
            f"AGENT REGISTRY BOOTSTRAP COMPLETE\n"
            f"{'='*60}\n"
            f"Registered:  {len(result.registered)} agents\n"
            f"Failed:      {len(result.failed)} agents\n"
            f"{'  FAILED: ' + ', '.join(result.failed) if result.failed else ''}\n"
            f"\nCapability index ({len(self.registry._capability_index)} capabilities):\n"
            + "\n".join(
                f"  {cap}: provided by {providers}"
                for cap, providers in self.registry._capability_index.items()
            ) +
            f"\n\nEvent routing table ({len(self.registry._event_routing_table)} events):\n"
            + "\n".join(
                f"  {evt} → {recipient}"
                for evt, recipient in self.registry._event_routing_table.items()
            ) +
            f"\n{'='*60}"
        )


### 16.3 Health Poll (30s background task)

```python
# adapters/health_monitor.py

class HealthMonitor:
    def __init__(self, registry: AgentRegistry, adapters: dict[str, RemoteAgentAdapter]):
        self.registry = registry
        self.adapters = adapters

    async def start(self):
        while True:
            await asyncio.sleep(30)
            await self._poll_all()

    async def _poll_all(self):
        results = await asyncio.gather(
            *[self._poll_one(agent_id, adapter)
              for agent_id, adapter in self.adapters.items()],
            return_exceptions=True
        )
        for agent_id, result in zip(self.adapters.keys(), results):
            if isinstance(result, Exception):
                self.registry.update_health(agent_id, HealthStatus(status="unavailable"))
                continue
            health, version = result
            # Detect manifest version drift
            current_version = self.registry._manifests[agent_id].version
            if version != current_version:
                metrics.increment("registry.manifest_version_drift",
                                  tags={"agent_id": agent_id,
                                        "old": current_version, "new": version})
                # Trigger re-describe on next startup or on-demand
                logger.warning(
                    f"Version drift on {agent_id}: "
                    f"registry={current_version}, live={version}"
                )
            self.registry.update_health(agent_id, health)

    async def _poll_one(self, agent_id: str, adapter: RemoteAgentAdapter):
        health = await adapter.health()
        version = health.details.get("version", "unknown")
        return health, version
```

---

## 17. Full Fleet Manifests

Each manifest below is what each agent's `/describe` endpoint returns. These are
authoritative — the proxy builds everything from them.

### 17.1 mdl_services

```json
{
  "agent_id": "mdl_services",
  "display_name": "MDL Services Agent",
  "version": "1.2.0",
  "framework": "langgraph",
  "phase": 1,
  "gateway_resident": false,

  "routing_triggers": [
    "build gold layer", "rebuild silver", "create dbt model",
    "medallion architecture", "csod schema", "cornerstone schema",
    "gold layer stale", "refresh data", "cube.js schema",
    "mdl", "data pipeline", "bronze to silver", "silver to gold"
  ],

  "planner_description": "Builds and maintains the medallion data architecture (Bronze → Silver → Gold) for connected data sources. Produces structured gold layer tables, dbt model definitions, and Cube.js schemas. Must run before cornerstone_analysis when gold layer is absent or stale. Declare mdl_rebuild feature flag required for rebuild operations — readers do not need it.",

  "depends_on_capabilities": [],

  "provides_capabilities": [
    {
      "name": "gold_layer_csod",
      "description": "CSOD gold layer tables are current and queryable",
      "satisfaction_flag_ttl": 86400
    },
    {
      "name": "mdl_schema_current",
      "description": "dbt and Cube.js schemas are generated and current",
      "satisfaction_flag_ttl": 86400
    },
    {
      "name": "silver_layer_csod",
      "description": "CSOD silver layer enriched and validated",
      "satisfaction_flag_ttl": 86400
    }
  ],

  "produces_context_keys": [
    {
      "key_name": "mdl_gold_schema_v2",
      "schema_version": "v2",
      "supported_versions": ["v1", "v2"],
      "description": "Gold layer table names, column definitions, row counts, and freshness timestamps per data source",
      "ttl_seconds": 14400,
      "invalidated_by": ["mdl_rebuild_started"]
    },
    {
      "key_name": "mdl_populated_tables_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "List of tables with sufficient row counts for analysis, with per-table grain and date range",
      "ttl_seconds": 14400,
      "invalidated_by": ["mdl_rebuild_started"]
    },
    {
      "key_name": "mdl_cubejs_schema_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "Generated Cube.js measures and dimensions per gold table",
      "ttl_seconds": 86400,
      "invalidated_by": ["mdl_rebuild_started"]
    }
  ],

  "consumes_context_keys": [],

  "intermediate_events": [
    {
      "event_type": "mdl_layer_start",
      "description": "A medallion layer build has begun",
      "timing_hint": "at layer build start",
      "recipient_hint": "",
      "payload_schema": { "layer": "string", "table_count": "integer" }
    },
    {
      "event_type": "mdl_layer_complete",
      "description": "A medallion layer build is complete — writes context keys",
      "timing_hint": "at layer build completion",
      "recipient_hint": "",
      "payload_schema": {
        "layer": "string",
        "tables_built": "array",
        "schema_version": "string",
        "context_key_written": "string"
      }
    },
    {
      "event_type": "mdl_rebuild_started",
      "description": "Full rebuild started — signals gateway to clear capability flags",
      "timing_hint": "immediately on rebuild trigger",
      "recipient_hint": "",
      "payload_schema": { "tenant_id": "string", "triggered_by": "string" }
    },
    {
      "event_type": "context_key_written",
      "description": "A context key has been written to Redis",
      "timing_hint": "after each layer completes",
      "recipient_hint": "",
      "payload_schema": { "key_name": "string", "schema_version": "string" }
    },
    {
      "event_type": "capability_satisfied",
      "description": "A capability has been produced and satisfaction flag should be written",
      "timing_hint": "at job completion",
      "recipient_hint": "",
      "payload_schema": { "capability_name": "string" }
    }
  ],

  "emits_intermediate_events": true,
  "writes_to_thread_state": false,
  "influences_future_plans": false,
  "orchestrates": [],

  "context_window_tokens": 12000,
  "system_ctx_tokens": 1500,
  "session_ctx_tokens": 3000,
  "turn_ctx_tokens": 2000,
  "response_reserve_tokens": 5500,
  "required_role": "analyst",
  "feature_flag": null,
  "tenant_scoped": true,
  "health_check_path": "/health",
  "describe_path": "/describe",

  "jwt_claims_required": ["tenant_id"],
  "data_scope_requirements": { "asset_groups": "optional" }
}
```

### 17.2 metrics_recommender

```json
{
  "agent_id": "metrics_recommender",
  "display_name": "Metrics Recommender",
  "version": "1.1.0",
  "framework": "claude_sdk",
  "phase": 1,

  "routing_triggers": [
    "which metrics", "recommend metrics", "what should I measure",
    "which KPIs", "leading indicator", "lagging indicator",
    "collider", "safe to use", "metric recommendation",
    "metrics for compliance", "metrics for training", "dashboard metrics",
    "what metrics matter", "avoid metrics"
  ],

  "planner_description": "Recommends which metrics to use for a given analytical goal. Reads the causal knowledge base to identify colliders (metrics to avoid), mediators (safe leading indicators), and terminal metrics (what to optimise). Provides causal rationale for each recommendation. Does not run LR models or Shapley — use cce_causal_analysis for full risk scoring. Operates in degraded heuristic mode if causal knowledge base is unreachable.",

  "depends_on_capabilities": [],

  "provides_capabilities": [],

  "produces_context_keys": [
    {
      "key_name": "metrics_recommendation_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "Recommended metric set with causal rationale, collider flags, and leading/lagging classification",
      "ttl_seconds": 3600
    }
  ],

  "consumes_context_keys": [
    "mdl_populated_tables_v1"
  ],

  "intermediate_events": [],
  "emits_intermediate_events": false,

  "orchestrates": [],
  "writes_to_thread_state": false,
  "influences_future_plans": false,

  "context_window_tokens": 8000,
  "system_ctx_tokens": 1500,
  "session_ctx_tokens": 3000,
  "turn_ctx_tokens": 2000,
  "response_reserve_tokens": 1500,
  "required_role": "viewer",
  "feature_flag": null,
  "tenant_scoped": true,
  "health_check_path": "/health",
  "describe_path": "/describe",

  "jwt_claims_required": ["tenant_id"],
  "data_scope_requirements": { "frameworks": "optional" }
}
```

### 17.3 cornerstone_analysis

```json
{
  "agent_id": "cornerstone_analysis",
  "display_name": "Cornerstone Data Analysis",
  "version": "2.0.1",
  "framework": "langgraph",
  "phase": 1,

  "routing_triggers": [
    "cornerstone", "csod", "completion rate", "compliance training",
    "learner engagement", "overdue", "certification", "ilt",
    "training completion", "lms", "learning management",
    "pass rate", "assignment", "course", "curriculum"
  ],

  "planner_description": "Analyses Cornerstone OnDemand (CSOD) training and compliance data against the silver and gold layer tables. Answers questions about completion rates, compliance gaps, learner engagement, ILT capacity, and certification compliance. Depends on mdl_services having built the CSOD gold layer — will fail gracefully if gold layer is absent and request MDL rebuild. Produces csod_observable_nodes context key consumed by cce_causal_analysis when doing CSOD causal analysis.",

  "depends_on_capabilities": [
    "gold_layer_csod",
    "mdl_schema_current"
  ],

  "provides_capabilities": [],

  "produces_context_keys": [
    {
      "key_name": "csod_observable_nodes_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "List of causal graph nodes that are observable in this org's CSOD gold layer, with current metric values and data freshness",
      "ttl_seconds": 3600,
      "invalidated_by": ["mdl_rebuild_started"]
    },
    {
      "key_name": "csod_analysis_snapshot_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "Current metric values for key CSOD nodes: completion_rate, overdue_count, compliance_rate, cert_compliance_rate, login_trend",
      "ttl_seconds": 1800
    }
  ],

  "consumes_context_keys": [
    "mdl_gold_schema_v2",
    "mdl_populated_tables_v1",
    "metrics_recommendation_v1"
  ],

  "intermediate_events": [],
  "emits_intermediate_events": false,
  "orchestrates": [],
  "writes_to_thread_state": false,
  "influences_future_plans": false,

  "context_window_tokens": 16000,
  "system_ctx_tokens": 2000,
  "session_ctx_tokens": 4000,
  "turn_ctx_tokens": 3000,
  "response_reserve_tokens": 7000,
  "required_role": "viewer",
  "feature_flag": null,
  "tenant_scoped": true,
  "health_check_path": "/health",
  "describe_path": "/describe",

  "jwt_claims_required": ["tenant_id", "data_scope.asset_groups"],
  "data_scope_requirements": { "asset_groups": "required" }
}
```

### 17.4 cce_causal_analysis

```json
{
  "agent_id": "cce_causal_analysis",
  "display_name": "CCE Causal Analysis",
  "version": "1.4.2",
  "framework": "langgraph",
  "phase": 1,
  "requires_phase2": "cce_narration_orchestrator",

  "routing_triggers": [
    "risk", "vulnerability", "mttr", "kev", "patch sla",
    "mfa failure", "credential", "identity threat",
    "mde gap", "lateral movement", "endpoint coverage",
    "detection capability", "causal", "root cause",
    "why is this risky", "what is driving", "what caused",
    "completion rate drop", "compliance drop", "why did this change",
    "causal analysis", "shapley", "attribution"
  ],

  "planner_description": "Runs full causal risk analysis for security and LMS queries. Activates decision tree routing, per-R-node logistic regression risk scoring, and Shapley attribution. Emits intermediate events consumed by cce_narration_orchestrator (phase 2). For LMS causal queries, reads csod_observable_nodes to scope which graph nodes are observable in this org. For security queries, reads r_node_access from JWT to scope which risk models run. Always paired with cce_narration_orchestrator as phase 2.",

  "depends_on_capabilities": [
    "causal_graph_seeded",
    "enum_metadata_current"
  ],

  "provides_capabilities": [
    {
      "name": "causal_analysis_complete",
      "description": "Full causal graph traversal and risk scoring completed for this session",
      "satisfaction_flag_ttl": 900
    }
  ],

  "produces_context_keys": [
    {
      "key_name": "cce_graph_state_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "Full ConversationState: activated subgraph, LR scores per R-node, Shapley ϕ values, collider warnings, gap inventory, triage scores",
      "ttl_seconds": 900,
      "invalidated_by": []
    },
    {
      "key_name": "cce_causal_subgraph_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "Assembled causal subgraph nodes and edges for this query — reusable by alert_analysis for follow-up triage",
      "ttl_seconds": 900
    }
  ],

  "consumes_context_keys": [
    "csod_observable_nodes_v1",
    "csod_analysis_snapshot_v1"
  ],

  "intermediate_events": [
    {
      "event_type": "cce_router_complete",
      "description": "Decision tree routing complete. Activated R-nodes, domain, and narration hint.",
      "timing_hint": "~80ms after invocation",
      "recipient_hint": "cce_narration_orchestrator",
      "payload_schema": {
        "activated_r_nodes": "array",
        "suppressed_r_nodes": "array",
        "domain": "string",
        "p_tree_scores": "object",
        "narration_hint": "string"
      }
    },
    {
      "event_type": "cce_collider_complete",
      "description": "Collider guard output. Structured warning list for WHY narration context.",
      "timing_hint": "~200ms after invocation",
      "recipient_hint": "cce_narration_orchestrator",
      "payload_schema": {
        "collider_warnings": "array"
      }
    },
    {
      "event_type": "cce_lr_complete",
      "description": "LR model scoring complete. Per-R-node scores and feature attributions.",
      "timing_hint": "~500ms after invocation",
      "recipient_hint": "cce_narration_orchestrator",
      "payload_schema": {
        "lr_scores": "object",
        "feature_attributions": "object"
      }
    },
    {
      "event_type": "context_key_written",
      "description": "cce_graph_state_v1 written to Redis",
      "timing_hint": "at STEP_FINAL",
      "recipient_hint": "",
      "payload_schema": { "key_name": "string", "schema_version": "string" }
    }
  ],

  "emits_intermediate_events": true,
  "orchestrates": [],
  "writes_to_thread_state": false,
  "influences_future_plans": false,

  "context_window_tokens": 16000,
  "system_ctx_tokens": 2000,
  "session_ctx_tokens": 4000,
  "turn_ctx_tokens": 2000,
  "response_reserve_tokens": 8000,
  "required_role": "analyst",
  "feature_flag": "cce_narration",
  "tenant_scoped": true,
  "health_check_path": "/health",
  "describe_path": "/describe",

  "jwt_claims_required": ["data_scope.r_node_access", "data_scope.frameworks"],
  "data_scope_requirements": { "r_node_access": "required" }
}
```

### 17.5 alert_analysis

```json
{
  "agent_id": "alert_analysis",
  "display_name": "Alert Analysis Agent",
  "version": "1.0.3",
  "framework": "langgraph",
  "phase": 1,

  "routing_triggers": [
    "alert", "fired", "threshold breached", "anomaly detected",
    "mfa failures", "spike", "unusual activity", "incident",
    "triage", "investigate", "false positive", "is this real",
    "should I be worried", "overnight alert", "alert queue"
  ],

  "planner_description": "Classifies and triages security and operational alerts. Determines alert type (metric anomaly, identity event, endpoint signal, compound), confidence level, and routes high-confidence alerts to cce_causal_analysis for root cause analysis. Operates in classification-only mode when cce_causal_analysis is degraded. Manages alert queue context across multi-turn investigation conversations.",

  "depends_on_capabilities": [],

  "provides_capabilities": [
    {
      "name": "alert_classified",
      "description": "Alert has been classified and routed",
      "satisfaction_flag_ttl": 1800
    }
  ],

  "produces_context_keys": [
    {
      "key_name": "alert_classification_v1",
      "schema_version": "v1",
      "supported_versions": ["v1"],
      "description": "Alert type, confidence, routed agent, account decompositions, compound alert flag",
      "ttl_seconds": 1800
    }
  ],

  "consumes_context_keys": [
    "cce_causal_subgraph_v1"
  ],

  "intermediate_events": [
    {
      "event_type": "alert_classified",
      "description": "Alert classification complete — routing decision made",
      "timing_hint": "~150ms after invocation",
      "recipient_hint": "",
      "payload_schema": {
        "alert_id": "string",
        "classification": "string",
        "confidence": "number",
        "routed_to": "string",
        "compound_flag": "boolean",
        "suppressed_accounts": "array"
      }
    },
    {
      "event_type": "alert_triage_complete",
      "description": "Full triage including CCE routing complete",
      "timing_hint": "after CCE sub-invocation if routed",
      "recipient_hint": "",
      "payload_schema": { "triage_level": "string", "action_items": "array" }
    }
  ],

  "emits_intermediate_events": true,
  "orchestrates": ["cce_causal_analysis", "cornerstone_analysis"],
  "writes_to_thread_state": false,
  "influences_future_plans": false,

  "context_window_tokens": 12000,
  "system_ctx_tokens": 1500,
  "session_ctx_tokens": 3000,
  "turn_ctx_tokens": 2000,
  "response_reserve_tokens": 5500,
  "required_role": "analyst",
  "feature_flag": null,
  "tenant_scoped": true,
  "health_check_path": "/health",
  "describe_path": "/describe",

  "jwt_claims_required": ["tenant_id", "data_scope.r_node_access"],
  "data_scope_requirements": { "r_node_access": "optional" }
}
```

### 17.6 workflow_planner

```json
{
  "agent_id": "workflow_planner",
  "display_name": "Workflow Planner",
  "version": "1.0.0",
  "framework": "langgraph",
  "phase": 1,

  "routing_triggers": [
    "set up workflow", "set up monitoring", "configure compliance",
    "build pipeline", "automate", "multi-step", "end-to-end setup",
    "implement", "deploy analysis", "continuous monitoring",
    "schedule", "recurring", "quarterly review setup",
    "help me set up", "walk me through"
  ],

  "planner_description": "Decomposes multi-session analytical workflows into ordered cross-agent step sequences. Writes a workflow context to thread long-term memory that persists across sessions and constrains future gateway planner decisions. Knows the full agent fleet and can plan sequences involving mdl_services → cornerstone_analysis → metrics_recommender → cce_causal_analysis in the correct dependency order. Use when the user wants to set up a sustained analytical capability, not answer a one-off question.",

  "depends_on_capabilities": [],
  "provides_capabilities": [],
  "produces_context_keys": [],
  "consumes_context_keys": [],

  "intermediate_events": [
    {
      "event_type": "workflow_step_start",
      "description": "A workflow step is beginning",
      "timing_hint": "at each step boundary",
      "recipient_hint": "",
      "payload_schema": {
        "workflow_id": "string", "step": "integer",
        "total": "integer", "step_name": "string"
      }
    },
    {
      "event_type": "workflow_step_complete",
      "description": "A workflow step is complete",
      "timing_hint": "at step completion",
      "recipient_hint": "",
      "payload_schema": { "workflow_id": "string", "step": "integer" }
    },
    {
      "event_type": "workflow_complete",
      "description": "All workflow steps done",
      "timing_hint": "at workflow completion",
      "recipient_hint": "",
      "payload_schema": { "workflow_id": "string", "summary": "string" }
    },
    {
      "event_type": "workflow_paused",
      "description": "User departed from workflow",
      "timing_hint": "on off-workflow query detection",
      "recipient_hint": "",
      "payload_schema": { "workflow_id": "string", "resume_hint": "string" }
    }
  ],

  "emits_intermediate_events": true,
  "orchestrates": [
    "mdl_services", "cornerstone_analysis",
    "metrics_recommender", "cce_causal_analysis", "alert_analysis"
  ],
  "writes_to_thread_state": true,
  "influences_future_plans": true,

  "context_window_tokens": 16000,
  "system_ctx_tokens": 2000,
  "session_ctx_tokens": 5000,
  "turn_ctx_tokens": 2000,
  "response_reserve_tokens": 7000,
  "required_role": "analyst",
  "feature_flag": "workflow_planner",
  "tenant_scoped": true,
  "health_check_path": "/health",
  "describe_path": "/describe",

  "jwt_claims_required": ["tenant_id"],
  "data_scope_requirements": {}
}
```

---

## 18. Agent Server Implementation Pattern

Every agent on the Agent Server must implement a consistent server-side pattern.
This section specifies exactly what each agent must build to participate in the
self-description protocol. The pattern is framework-independent — it works for
LangGraph agents, Claude SDK agents, and any other framework.

### 18.1 Mandatory Server Structure

Every agent on the Agent Server is an independent FastAPI application (or a router
mounted in a shared application) that exposes exactly three routes:

```python
# agent_server/agents/{agent_id}/server.py
# Template — copy and fill for each agent.

from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

# ── The three mandatory routes ─────────────────────────────────────────────

@app.get("/describe")
async def describe() -> dict:
    """
    Returns the agent's AgentManifest as JSON.
    Called by the proxy at startup and on re-describe cycles.
    Must complete in < 5 seconds.
    Must NOT make any external calls — return a static or lightly-computed manifest.
    """
    return AGENT_MANIFEST  # defined below

@app.get("/health")
async def health() -> dict:
    """
    Returns current health status and manifest version.
    Called by proxy every 30 seconds.
    Must complete in < 3 seconds.
    Must reflect actual dependency health (e.g. DB reachable, model loaded).
    """
    return {
        "status": await check_health(),     # "healthy" | "degraded" | "unavailable"
        "version": AGENT_MANIFEST["version"],
        "details": await health_details()   # e.g. { "db_reachable": true, "model_loaded": true }
    }

@app.post("/invoke")
async def invoke(request: Request) -> StreamingResponse:
    """
    Accepts the gateway payload and streams SSE AgentEvents.
    Payload structure: { input, thread_id, run_id, step_id, ctx_token, hint, data_scope }
    ctx_token is resolved against Redis via the context sidecar.
    """
    payload = await request.json()
    ctx = await resolve_context(payload["ctx_token"])
    agent_context = ctx.get("agent_context", {})  # context keys injected by gateway

    return StreamingResponse(
        run_agent(payload, ctx, agent_context),
        media_type="text/event-stream"
    )
```

### 18.2 The AGENT_MANIFEST Constant

Each agent defines its manifest as a module-level constant. This is the single source of
truth for that agent's self-description. It is returned verbatim by `/describe` and its
`version` field is included in every `/health` response.

```python
# agent_server/agents/mdl_services/manifest.py
# Example — mdl_services fills in its own values.

AGENT_MANIFEST = {
    "agent_id": "mdl_services",
    "display_name": "MDL Services Agent",
    "version": "1.2.0",           # Bumped on every release. Proxy detects drift.
    "framework": "langgraph",
    "phase": 1,
    "gateway_resident": False,

    "routing_triggers": [
        "build gold layer", "rebuild silver", "create dbt model",
        # ... full list as in Section 17.1
    ],

    "planner_description": "...",  # Written for the planner LLM, not users

    "depends_on_capabilities": [],
    "provides_capabilities": [
        {
            "name": "gold_layer_csod",
            "description": "CSOD gold layer tables are current and queryable",
            "satisfaction_flag_ttl": 86400
        }
        # ...
    ],

    "produces_context_keys": [
        {
            "key_name": "mdl_gold_schema_v2",
            "schema_version": "v2",
            "supported_versions": ["v1", "v2"],
            "description": "...",
            "ttl_seconds": 14400,
            "invalidated_by": ["mdl_rebuild_started"]
        }
        # ...
    ],

    "consumes_context_keys": [],

    "intermediate_events": [
        {
            "event_type": "mdl_layer_complete",
            "description": "...",
            "timing_hint": "at layer build completion",
            "recipient_hint": "",
            "payload_schema": { "layer": "string", "tables_built": "array" }
        },
        {
            "event_type": "context_key_written",
            "description": "Context key written to Redis",
            "timing_hint": "after each layer",
            "recipient_hint": "",
            "payload_schema": { "key_name": "string", "schema_version": "string" }
        },
        {
            "event_type": "capability_satisfied",
            "description": "Capability provision complete",
            "timing_hint": "at job completion",
            "recipient_hint": "",
            "payload_schema": { "capability_name": "string" }
        }
    ],

    "emits_intermediate_events": True,
    "orchestrates": [],
    "writes_to_thread_state": False,
    "influences_future_plans": False,

    "context_window_tokens": 12000,
    "system_ctx_tokens": 1500,
    "session_ctx_tokens": 3000,
    "turn_ctx_tokens": 2000,
    "response_reserve_tokens": 5500,

    "required_role": "analyst",
    "feature_flag": None,
    "tenant_scoped": True,
    "health_check_path": "/health",
    "describe_path": "/describe",

    "jwt_claims_required": ["tenant_id"],
    "data_scope_requirements": { "asset_groups": "optional" }
}
```

### 18.3 Context Key Writing Pattern

Every agent that produces context keys must write them to Redis before emitting the
`context_key_written` SSE event. The gateway acts on the event to cache the key
in-session, but the key must already be in Redis before the event is emitted.

```python
# agent_server/shared/context_keys.py

class ContextKeyWriter:
    """
    Shared utility for all agents that produce context keys.
    Write to Redis first, then emit the SSE event.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def write(
        self,
        key_name: str,
        value: dict,
        schema_version: str,
        tenant_id: str,
        thread_id: str,
        ttl_seconds: int,
        event_queue: asyncio.Queue
    ):
        # 1. Write to Redis FIRST
        redis_key = f"ctxkey:{tenant_id}:{thread_id}:{key_name}"
        await self.redis.setex(
            redis_key,
            ttl_seconds,
            json.dumps(value)
        )

        # 2. THEN emit the SSE event so proxy can cache in-session
        await event_queue.put({
            "type": "context_key_written",
            "data": {
                "key_name": key_name,
                "schema_version": schema_version,
                "ttl_seconds": ttl_seconds,
                "redis_key": redis_key
            }
        })

    async def satisfy_capability(
        self,
        capability_name: str,
        event_queue: asyncio.Queue
    ):
        # The proxy writes the capability flag to Redis on receiving this event.
        # The agent does NOT write it — the proxy owns capability flags.
        await event_queue.put({
            "type": "capability_satisfied",
            "data": { "capability_name": capability_name }
        })
```

### 18.4 LangGraph Agent Implementation Pattern

For agents using LangGraph, the graph nodes are responsible for emitting SSE events.
The pattern below shows how a LangGraph node emits intermediate events and context keys.

```python
# agent_server/agents/mdl_services/graph.py

from langgraph.graph import StateGraph, END
from agent_server.shared.context_keys import ContextKeyWriter
from agent_server.shared.sse import emit_event
import asyncio

class MDLState(TypedDict):
    payload: dict
    context: dict
    tenant_id: str
    thread_id: str
    run_id: str
    event_queue: asyncio.Queue
    gold_schema: dict | None
    populated_tables: list | None
    layers_built: list

def build_mdl_graph() -> StateGraph:
    graph = StateGraph(MDLState)

    graph.add_node("plan_build",   plan_build_node)
    graph.add_node("build_silver", build_silver_node)
    graph.add_node("build_gold",   build_gold_node)
    graph.add_node("write_schemas", write_schemas_node)

    graph.set_entry_point("plan_build")
    graph.add_edge("plan_build",   "build_silver")
    graph.add_edge("build_silver", "build_gold")
    graph.add_edge("build_gold",   "write_schemas")
    graph.add_edge("write_schemas", END)

    return graph.compile()


async def build_gold_node(state: MDLState) -> MDLState:
    queue = state["event_queue"]

    # Emit MDL_LAYER_START event — forwarded to frontend as progress
    await emit_event(queue, {
        "type": "mdl_layer_start",
        "data": { "layer": "gold", "table_count": 12 }
    })

    # Do the actual work
    gold_schema = await run_gold_layer_build(
        tenant_id=state["tenant_id"],
        silver_results=state.get("silver_results", {})
    )

    # Write context key to Redis, then emit context_key_written event
    ctx_writer = ContextKeyWriter(get_redis())
    await ctx_writer.write(
        key_name="mdl_gold_schema_v2",
        value=gold_schema,
        schema_version="v2",
        tenant_id=state["tenant_id"],
        thread_id=state["thread_id"],
        ttl_seconds=14400,
        event_queue=queue
    )

    # Emit MDL_LAYER_COMPLETE event
    await emit_event(queue, {
        "type": "mdl_layer_complete",
        "data": {
            "layer": "gold",
            "tables_built": list(gold_schema.keys()),
            "schema_version": "v2"
        }
    })

    return { **state, "gold_schema": gold_schema }


async def write_schemas_node(state: MDLState) -> MDLState:
    queue = state["event_queue"]
    ctx_writer = ContextKeyWriter(get_redis())

    # Write populated tables context key
    populated = await determine_populated_tables(state["tenant_id"])
    await ctx_writer.write(
        key_name="mdl_populated_tables_v1",
        value=populated,
        schema_version="v1",
        tenant_id=state["tenant_id"],
        thread_id=state["thread_id"],
        ttl_seconds=14400,
        event_queue=queue
    )

    # Emit capability_satisfied events — proxy writes the flags
    await ctx_writer.satisfy_capability("gold_layer_csod", queue)
    await ctx_writer.satisfy_capability("mdl_schema_current", queue)

    # Final token stream — the narrative response to the user
    narrative = f"Gold layer built successfully. {len(populated)} tables available."
    await emit_event(queue, {
        "type": "token",
        "data": { "text": narrative }
    })
    await emit_event(queue, {
        "type": "final",
        "data": { "text": narrative }
    })

    return state
```

### 18.5 SSE Emission Utility

All agents share the same SSE emission format. A utility function ensures consistency.

```python
# agent_server/shared/sse.py

async def emit_event(
    queue: asyncio.Queue,
    event: dict,
    agent_id: str = "",
    run_id: str = "",
    step_id: str = "",
    tenant_id: str = ""
):
    """
    Puts a normalised AgentEvent-shaped dict onto the event queue.
    The agent's /invoke route reads from this queue and yields SSE lines.
    """
    await queue.put({
        "type":      event["type"],
        "agent_id":  agent_id,
        "run_id":    run_id,
        "step_id":   step_id,
        "tenant_id": tenant_id,
        "data":      event.get("data", {}),
        "metadata":  event.get("metadata", {})
    })


async def stream_from_queue(
    queue: asyncio.Queue,
    run_id: str
) -> AsyncIterator[str]:
    """
    The /invoke route's response generator.
    Reads from event queue and yields SSE-formatted strings.
    """
    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event)}\n\n"
        if event["type"] in ("final", "step_error", "error"):
            break
```

### 18.6 Context Sidecar Pattern (unchanged from v2.0)

Every agent resolves its ctx_token against Redis via the sidecar before processing.
The resolved context includes the `agent_context` dict populated by the gateway with
the consumed context keys for this step.

```python
# agent_server/shared/context_sidecar.py

async def resolve_context(ctx_token: str) -> dict:
    """
    Resolves ctx_token to the composed context, including any
    context keys injected by the gateway's ContextComposer.
    """
    resp = await http_client.get(
        f"http://gateway-internal/internal/ctx/{ctx_token}"
    )
    if resp.status_code == 404:
        raise ContextExpiredError(ctx_token)
    return resp.json()
    # Returns: { system, session, turn, agent_context }
    # agent_context contains injected context keys:
    # e.g. agent_context["mdl_gold_schema_v2"] = { ... }
    # e.g. agent_context["csod_observable_nodes_v1"] = { ... }
```

### 18.7 Health Check Implementation Pattern

Each agent's `/health` endpoint must reflect actual dependency health, not just
"process is running". The pattern below shows what to check per agent type.

```python
# agent_server/shared/health.py

async def check_health() -> str:
    """
    Returns "healthy" | "degraded" | "unavailable".
    Each agent overrides check_dependencies() for its specific deps.
    """
    try:
        deps = await check_dependencies()
        if all(deps.values()):
            return "healthy"
        elif any(deps.values()):
            return "degraded"
        else:
            return "unavailable"
    except Exception:
        return "unavailable"


# Per-agent dependency checks:

# mdl_services:
async def check_dependencies() -> dict[str, bool]:
    return {
        "postgres_reachable": await ping_postgres(),
        "dbt_installed": check_dbt_binary(),
        "bronze_tables_exist": await check_bronze_tables()
    }

# cce_causal_analysis:
async def check_dependencies() -> dict[str, bool]:
    return {
        "postgres_reachable": await ping_postgres(),   # causal graph tables
        "qdrant_reachable": await ping_qdrant(),       # node knowledge base
        "lr_models_loaded": check_lr_model_registry(), # per-R-node models
        "enum_tables_populated": await check_enum_tables()
    }

# cornerstone_analysis:
async def check_dependencies() -> dict[str, bool]:
    return {
        "postgres_reachable": await ping_postgres(),
        "csod_gold_exists": await check_table_exists("gold_csod_assignments")
        # Note: gold existence checked here but capability flag
        # is the proxy's responsibility — the agent just checks if the
        # table physically exists, not whether it's "current"
    }

# metrics_recommender:
async def check_dependencies() -> dict[str, bool]:
    return {
        "qdrant_reachable": await ping_qdrant(),       # causal knowledge base
        # Graceful degradation: if Qdrant unreachable, agent operates in
        # heuristic mode — health = "degraded", not "unavailable"
    }

# alert_analysis:
async def check_dependencies() -> dict[str, bool]:
    return {
        "postgres_reachable": await ping_postgres(),
        # Does NOT check cce_causal_analysis health — that's the proxy's job.
        # alert_analysis degrades gracefully when CCE is unavailable.
    }

# workflow_planner:
async def check_dependencies() -> dict[str, bool]:
    return {
        "postgres_reachable": await ping_postgres(),   # workflow state
        "redis_reachable": await ping_redis()           # workflow context cache
    }
```

---

## 19. Context Key Handoff Protocol

Context keys are the structured state-passing mechanism between agents in a multi-step
plan. This section specifies the full lifecycle of a context key.

### 19.1 Lifecycle

```
AGENT A runs            AGENT A writes           GATEWAY intercepts
(e.g. mdl_services)     to Redis:                CONTEXT_KEY_WRITTEN event,
                         ctxkey:{tenant}:         caches value in-session:
                         {thread}:{key_name}      accumulated_ctx_keys[key_name]
                             │                              │
                             ▼                              ▼
                        AGENT A emits              AGENT B runs
                        context_key_written        (e.g. cornerstone_analysis)
                        SSE event                  Context key injected into
                                                   AGENT B's ctx_token payload
                                                   under agent_context.{key_name}
                                                   AGENT B reads it from
                                                   context.agent_context
```

### 19.2 Naming Convention

All context key names follow `{domain}_{type}_v{N}`:

```
mdl_gold_schema_v2              mdl_services → cornerstone_analysis, cce_causal_analysis
mdl_populated_tables_v1         mdl_services → metrics_recommender, cornerstone_analysis
mdl_cubejs_schema_v1            mdl_services → (external BI tools)
csod_observable_nodes_v1        cornerstone_analysis → cce_causal_analysis
csod_analysis_snapshot_v1       cornerstone_analysis → cce_causal_analysis
metrics_recommendation_v1       metrics_recommender → cornerstone_analysis
cce_graph_state_v1              cce_causal_analysis → cce_narration_orchestrator
cce_causal_subgraph_v1          cce_causal_analysis → alert_analysis
alert_classification_v1         alert_analysis → (downstream investigation agents)
```

### 19.3 Version Resolution

When producer supports `["v1", "v2"]` and consumer supports `["v2"]`:
→ Gateway writes `v2` to Redis. Consumer reads `v2`.

When producer supports `["v1", "v2"]` and consumer supports `["v1"]` only:
→ Gateway writes `v1` to Redis. Consumer reads `v1`. Producer supports backwards compat.

When producer supports `["v2"]` only and consumer supports `["v1"]` only:
→ Gateway detects incompatibility at plan time. Plan step is excluded.
→ User sees: "This analysis requires [consumer agent] which is incompatible with
   the current [producer agent] version. Please update [consumer agent] to continue."

---

## 20. Health Dependency Graph

The proxy maintains a directed graph of health dependencies derived from manifest
declarations. When an agent becomes degraded or unavailable, the proxy propagates
that status to all agents that depend on it.

### 20.1 Dependency Graph (derived from fleet manifests)

```
mdl_services
    │ provides: gold_layer_csod, mdl_schema_current, silver_layer_csod
    │
    ├── cornerstone_analysis (depends_on_capabilities: gold_layer_csod, mdl_schema_current)
    │       │
    │       └── cce_causal_analysis (consumes: csod_observable_nodes_v1)
    │               │
    │               └── alert_analysis (consumes: cce_causal_subgraph_v1)
    │               └── cce_narration_orchestrator (consumes: cce_graph_state_v1)
    │
    └── metrics_recommender (consumes: mdl_populated_tables_v1)
            │
            └── cornerstone_analysis (consumes: metrics_recommendation_v1)
```

### 20.2 Degradation Propagation Rules

```python
# State propagation when an agent's health changes:

DEGRADATION_RULES = {
    # If mdl_services → unavailable:
    "mdl_services_unavailable": {
        "cornerstone_analysis": "partially_degraded",
        # Can still run if gold layer exists in Redis (capability flag present)
        # Cannot run if gold layer is absent or stale
    },
    # If cornerstone_analysis → unavailable:
    "cornerstone_analysis_unavailable": {
        "cce_causal_analysis": "partially_degraded",
        # CCE can run for security queries (no CSOD dependency)
        # CCE degrades for LMS causal queries (no csod_observable_nodes)
    },
    # If cce_causal_analysis → unavailable:
    "cce_causal_analysis_unavailable": {
        "alert_analysis": "partially_degraded",
        # Alert analysis degrades to classification-only mode
        "cce_narration_orchestrator": "unavailable",
        # Narration orchestrator has no work without CCE
    },
}
```

### 20.3 Degraded Mode Declarations per Agent

Each agent's manifest should be read alongside its graceful degradation behaviour:

| Agent | Degraded dependency | Degraded behaviour |
|---|---|---|
| `cornerstone_analysis` | `mdl_services` unavailable, gold layer flag absent | Rejects queries; requests MDL rebuild via planner |
| `cornerstone_analysis` | `mdl_services` degraded but flag present | Runs against existing gold layer; warns data may be stale |
| `metrics_recommender` | Qdrant unreachable | Heuristic mode — returns rule-based recommendations with lower confidence; labels output as `corpus_match: heuristic` |
| `cce_causal_analysis` | `csod_observable_nodes_v1` missing | Runs security causal path normally; skips LMS domain; marks LMS nodes as `observable: false` in graph state |
| `alert_analysis` | `cce_causal_analysis` unavailable | Classification-only — classifies alert type and confidence; no causal root cause; routes to queue for CCE when recovered |
| `workflow_planner` | Any Tier 1 or Tier 2 agent degraded | Plans around available agents; explicitly names what steps are deferred; preserves workflow context for resumption |

---

*End of Design Document v3.0*

*Key changes from v2.0:*
*Section 1 — Fleet overview and agent-as-authority principle added*
*Section 2 — Full fleet architecture diagram; self-description contract; three mandatory endpoints*
*Section 5 — Dependency-aware planner; manifest-derived catalog; capability satisfaction check*
*Section 9 — Full fleet Redis key schema: context keys, capability flags, workflow context, manifest cache, health state*
*Section 10 — `describe()` mandatory on AgentAdapter; AgentManifest replaces AgentMeta; RemoteAgentAdapter base; registry rebuilt from manifests*
*Section 11 — Fleet event types: CONTEXT_KEY_WRITTEN, CAPABILITY_SATISFIED, workflow events, MDL events, alert events*
*Section 12 — Sequential executor with context key handoff; capability flag writing; operational event handling*
*Section 14 — Fleet failure handling: describe failures, manifest drift, missing context keys, version incompatibility, cascade degradation*
*Section 16 — NEW: Registry bootstrap; agents.yaml as sole hardcoded config; RegistryBootstrap; health monitor*
*Section 17 — NEW: Full fleet manifest JSONs for all 6 agents*
*Section 18 — NEW: Agent server implementation pattern; AGENT_MANIFEST constant; LangGraph graph pattern; context key writing; SSE utility; health check pattern*
*Section 19 — NEW: Context key handoff protocol; naming convention; version resolution*
*Section 20 — NEW: Health dependency graph; degradation propagation rules; per-agent degraded mode*