# Agent Adapter System

This directory implements the Agent Gateway adapter layer following the design in `docs/agent_gateway_design/agent_adapter.md`.

## Overview

The adapter system provides a framework-agnostic interface for invoking agents. All agents (LangGraph, Claude SDK, etc.) implement the `AgentAdapter` interface, allowing the orchestration layer to invoke them uniformly.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Orchestration Layer (Gateway)              │
│  - JWT verification                                      │
│  - Intent planning                                       │
│  - Context composition                                   │
│  - Agent fan-out                                         │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / SSE
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent Server (This)                     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Agent Registry                         │  │
│  │  agent_id → AgentAdapter + AgentMeta             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ LangGraph    │  │ Claude SDK   │  │ Custom      │ │
│  │ Adapter      │  │ Adapter      │  │ Adapter     │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │     Context Sidecar  GET /internal/ctx/{token}   │  │
│  │     Fetches from Redis using signed ctx_token    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Base Adapter Interface (`base.py`)

- `AgentAdapter`: Abstract interface all agents implement
- `AgentEvent`: Standardized event protocol
- `EventType`: Event type enumeration
- `ComposedContext`: Context structure delivered to agents

### 2. LangGraph Adapter (`langgraph_adapter.py`)

Converts LangGraph `astream_events` output to `AgentEvent` protocol.

**Usage:**
```python
from app.adapters.langgraph_adapter import LangGraphAdapter
from app.agents.csod.csod_workflow import get_csod_app

app = get_csod_app()
adapter = LangGraphAdapter(app)
```

### 3. Agent Registry (`registry.py`)

Maintains catalog of available agents with metadata.

**Registration:**
```python
from app.adapters.registry import AgentRegistry, AgentMeta
from app.adapters.langgraph_adapter import LangGraphAdapter

registry = AgentRegistry()
meta = AgentMeta(
    agent_id="my-agent",
    display_name="My Agent",
    framework="langgraph",
    capabilities=["streaming", "tool_use"],
    context_window_tokens=8000,
    routing_tags=["compliance"],
)
adapter = LangGraphAdapter(my_app)
registry.register(meta, adapter)
```

**Querying:**
```python
# Get adapter
adapter = registry.get_adapter("my-agent")

# Get metadata
meta = registry.get_meta("my-agent")

# Filter by claims
accessible = registry.agents_for_claims(claims)
```

### 4. Context Composition Service (`services/context_composer.py`)

Assembles budget-aware context from memory tiers:
- **System context**: Static, from registry
- **Session context**: Dynamic, from working memory (Redis)
- **Turn context**: Last N messages + current input
- **Memory context**: Long-term memory (if required)

### 5. Context Token Service (`services/context_token.py`)

Mints and resolves signed tokens for context delivery. Context is never sent inline - agents receive a `ctx_token` and fetch context via `/internal/ctx/{token}`.

### 6. Agent Invocation Service (`services/agent_invocation_service.py`)

Main service layer that orchestrates:
- Context composition
- Token minting
- Agent invocation
- Event streaming

## API Endpoints

### POST `/v1/agents/invoke`

Invoke an agent and stream events.

**Request:**
```json
{
  "agent_id": "csod-workflow",
  "input": "Assess our SOC2 gap for CC6.1",
  "thread_id": "thread_abc123",
  "step_id": "step_1",
  "step_index": 0,
  "timeout_seconds": 60,
  "use_context_token": true,
  "data_scope": {
    "frameworks": ["SOC2"],
    "asset_groups": ["group_a"]
  }
}
```

**Response:** SSE stream of `AgentEvent` objects

### GET `/v1/agents/internal/ctx/{token}`

Internal endpoint for agents to fetch context by token.

**Response:**
```json
{
  "system": {...},
  "session": {...},
  "turn": {...},
  "memory": {...}
}
```

### GET `/v1/agents/registry`

List available agents filtered by JWT claims.

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "csod-workflow",
      "display_name": "CSOD Metrics & KPIs Workflow",
      "capabilities": ["streaming", "tool_use"],
      "routing_tags": ["csod", "metrics"]
    }
  ],
  "count": 5
}
```

### GET `/v1/agents/registry/{agent_id}`

Get metadata for a specific agent.

## Registered Agents

The following agents are automatically registered at startup (see `services/agent_registration.py`):

1. **csod-planner**: CSOD Planner Workflow
2. **csod-workflow**: CSOD Metrics & KPIs Workflow
3. **dt-workflow**: Detection & Triage Workflow
4. **compliance-workflow**: Compliance Automation Workflow
5. **dashboard-agent**: Dashboard Layout Advisor

## Usage Example

```python
from app.services.agent_invocation_service import get_agent_invocation_service

# Get service
service = get_agent_invocation_service()

# Invoke agent
payload = {
    "input": "Analyze our compliance posture",
    "thread_id": "thread_123",
    "run_id": "run_456",
    "step_id": "step_1",
}

claims = {
    "tenant_id": "org_xyz",
    "agent_access": ["compliance-workflow"],
    "roles": ["compliance_analyst"],
}

async for event in service.invoke_agent(
    agent_id="compliance-workflow",
    payload=payload,
    claims=claims,
):
    print(f"{event.type}: {event.data}")
```

## Event Protocol

Events follow the `AgentEvent` schema:

```python
{
  "type": "token" | "tool_start" | "tool_end" | "step_start" | "step_final" | "final" | "error",
  "agent_id": "csod-workflow",
  "run_id": "run_abc123",
  "step_id": "step_1",
  "tenant_id": "org_xyz",
  "data": {...},
  "metadata": {...}
}
```

## Context Token Flow

1. Gateway composes context
2. Gateway mints signed token via `ContextTokenService.mint()`
3. Token included in agent payload as `ctx_token`
4. Agent fetches context via `GET /internal/ctx/{token}`
5. Token expires after 5 minutes (TTL)

## JWT Authentication

**JWT is OPTIONAL for testing.** The system works without JWT tokens:

- **No JWT provided**: Uses default permissive claims (access to all agents)
- **JWT in Authorization header**: Extracts token (verification not implemented yet, uses default claims)
- **Claims in request body**: Can override claims by passing `claims` field in request

For production, implement JWT verification in `ClaimsDependency.get_claims()`.

## Next Steps

1. **JWT Integration**: Implement actual JWT verification in `ClaimsDependency` (currently optional for testing)
2. **Postgres Integration**: Add Postgres fallback for context when Redis cache misses
3. **Memory Write-back**: Implement async memory extraction and storage
4. **Monitoring**: Add OpenTelemetry spans for agent invocations
5. **Rate Limiting**: Add rate limiting per agent and tenant
