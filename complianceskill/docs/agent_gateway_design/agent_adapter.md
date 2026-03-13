# Agent Gateway — Architecture Design Document

**Version:** 1.0  
**Status:** Draft  
**Author:** Comatrix Labs

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

---

## 1. Overview

The Agent Gateway is a framework-agnostic orchestration layer that sits between a frontend chat application and a fleet of heterogeneous AI agents (LangGraph, Claude SDK, Google A2A, and others). It is responsible for authentication, intent planning, context composition, agent fan-out, stream multiplexing, and memory write-back.

### Core Design Principles

- **Framework agnostic** — agent frameworks are implementation details behind an adapter interface. Swapping LangGraph for Claude SDK requires only a new adapter, not a protocol change.
- **Gateway owns all state** — agents are stateless. Thread history, memory, and context are composed by the gateway and delivered to agents, never stored by them.
- **Reference over hydration** — large context is passed by reference (Redis token) not by value (inline payload). Agents pull only what they need.
- **Streaming first** — the entire pipeline is designed around SSE. Every layer from agent to frontend is non-blocking.
- **JWT as capability manifest** — JWT claims control not just authentication but agent access, data scoping, feature flags, and parallel execution limits.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Request Sources                              │
│   Web App     Mobile App     CLI / API     Internal Services     │
│   (Browser)   (React Native) (curl/SDK)    (service-to-service)  │
└───────────┬──────────┬──────────────┬────────────────┬──────────┘
            │          │              │                │
            │          │   Per-source config applied   │
            │          │   (rate limits, CORS, auth)   │
            ▼          ▼              ▼                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                          │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Source Config│  │  JWT Auth    │  │   OTel + Prometheus  │   │
│  │ Middleware   │  │  Middleware  │  │   Middleware         │   │
│  └─────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Planner Agent                           │ │
│  │  intent classification → ExecutionPlan (DAG of steps)     │ │
│  └───────────────────────────┬────────────────────────────── ┘ │
│                               │                                  │
│  ┌────────────────────────────▼───────────────────────────────┐ │
│  │                  Orchestration Engine                      │ │
│  │   single / parallel / sequential / conditional fan-out     │ │
│  │   stream multiplexer → one SSE to frontend                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────┐  ┌───────────────┐  ┌───────────────────┐ │
│  │ Context Composer │  │ Thread Manager│  │  Memory Manager   │ │
│  │ (budget-aware)   │  │ (Postgres +   │  │  (Redis + pgvect) │ │
│  └─────────────────┘  │  Redis)        │  └───────────────────┘ │
│                        └───────────────┘                         │
└──────────────┬──────────────────────────────────────────────────┘
               │  ctx_token + slim payload (~1KB)
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Agent Server (separate host)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Adapter Registry                       │   │
│  │  agent_id → AgentAdapter (resolved at startup)           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │  LangGraph   │  │  Claude SDK  │  │  Google A2A / Custom  │ │
│  │  Adapter     │  │  Adapter     │  │  Adapter              │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     Context Sidecar  GET /internal/ctx/{token}           │   │
│  │     Fetches from Redis using signed ctx_token            │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
               │  SSE AgentEvent stream
               ▼
         back to gateway → multiplexed → frontend
```

---

## 3. Request Source Configuration

Different clients have different trust levels, rate limits, and authentication requirements. Source configuration is resolved at the middleware layer before JWT processing.

### Source Types

```yaml
# config/sources.yaml

sources:

  web_app:
    id: web_app
    trust_level: user              # user | service | internal
    auth_required: true
    auth_method: jwt_cookie        # jwt_cookie | jwt_header | api_key | mtls
    cors:
      allowed_origins:
        - https://app.comatrixlabs.io
      allow_credentials: true
    rate_limits:
      requests_per_minute: 60
      max_parallel_streams: 3
      max_tokens_per_day: 500000
    allowed_features:
      - multi_agent
      - streaming
    timeout_seconds: 120

  mobile_app:
    id: mobile_app
    trust_level: user
    auth_required: true
    auth_method: jwt_header
    cors: null                     # no CORS for native apps
    rate_limits:
      requests_per_minute: 30
      max_parallel_streams: 2
      max_tokens_per_day: 200000
    allowed_features:
      - streaming
    timeout_seconds: 90

  api_client:                      # SDK / programmatic access
    id: api_client
    trust_level: service
    auth_required: true
    auth_method: api_key
    rate_limits:
      requests_per_minute: 120
      max_parallel_streams: 10
      max_tokens_per_day: 5000000
    allowed_features:
      - multi_agent
      - streaming
      - batch                      # only API clients can batch
    timeout_seconds: 300

  internal_service:                # service-to-service, no user context
    id: internal_service
    trust_level: internal
    auth_required: true
    auth_method: mtls
    rate_limits:
      requests_per_minute: 1000
      max_parallel_streams: 50
    allowed_features:
      - all
    timeout_seconds: 600
```

### Source Resolution Middleware

```python
# middleware/source_config.py

class SourceConfigMiddleware:
    def __init__(self, sources: dict[str, SourceConfig]):
        self.sources = sources

    async def __call__(self, request: Request, call_next):
        source_id = self.resolve_source(request)
        config = self.sources.get(source_id)

        if not config:
            raise HTTPException(400, "Unknown request source")

        # Attach to request state — available downstream
        request.state.source = config

        # Apply rate limiting before JWT check
        await self.check_rate_limit(config, request)

        # CORS enforcement
        if config.cors:
            self.validate_origin(config.cors, request)

        return await call_next(request)

    def resolve_source(self, request: Request) -> str:
        # Resolved by header, subdomain, or API key prefix
        if "X-Source-ID" in request.headers:
            return request.headers["X-Source-ID"]
        if request.headers.get("Authorization", "").startswith("sk-"):
            return "api_client"
        if request.client.is_internal():
            return "internal_service"
        return "web_app"
```

---

## 4. JWT & Privilege Model

JWT is not just authentication — it is the **capability manifest** for every request. It controls which agents are accessible, what data is visible, and what execution strategies are permitted.

### JWT Payload Schema

```json
{
  "sub": "user_abc123",
  "tenant_id": "org_xyz",
  "iat": 1700000000,
  "exp": 1700003600,

  "roles": ["compliance_analyst", "vuln_reader"],

  "agent_access": [
    "vuln-scanner",
    "soc2-gap",
    "compliance-report",
    "layout-advisor"
  ],

  "feature_flags": {
    "multi_agent": true,
    "what_if_analysis": false,
    "max_parallel_agents": 3,
    "long_term_memory": true,
    "synthesis": true
  },

  "data_scope": {
    "asset_groups": ["group_a", "group_b"],
    "frameworks": ["SOC2", "NIST"],
    "classification_ceiling": "confidential"
  },

  "context_tier": "full",

  "source_id": "web_app"
}
```

### Claims Resolution

```python
# auth/claims.py

@dataclass
class ResolvedClaims:
    user_id: str
    tenant_id: str
    roles: list[str]
    agent_access: list[str]
    feature_flags: FeatureFlags
    data_scope: DataScope
    context_tier: Literal["minimal", "standard", "full"]
    source_config: SourceConfig

    def can_access_agent(self, agent_id: str) -> bool:
        return agent_id in self.agent_access

    def can_run_parallel(self, n: int) -> bool:
        return (
            self.feature_flags.multi_agent
            and n <= self.feature_flags.max_parallel_agents
            and self.source_config.allows_feature("multi_agent")
        )

    def scoped_input(self, raw_input: dict) -> dict:
        # Inject data scope filters into agent payload
        return {
            **raw_input,
            "filter": {
                "asset_groups": self.data_scope.asset_groups,
                "frameworks": self.data_scope.frameworks,
            }
        }
```

### Privilege Enforcement Points

| Layer | What is checked |
|---|---|
| Source middleware | Rate limits, CORS, feature availability per source |
| JWT middleware | Token validity, expiry, tenant resolution |
| Planner | Agent whitelist, feature flags, parallel limits |
| Context composer | `context_tier` controls memory hydration depth |
| Adapter | `data_scope` injected into every agent payload |
| Memory write-back | Only writes to tenant-scoped namespaces |

---

## 5. Intent & Planning Layer

The planner is a lightweight LLM node inside the gateway that transforms a raw user message into a typed `ExecutionPlan` — a DAG of agent steps with dependencies, execution strategy, and synthesis requirements.

### ExecutionPlan Schema

```python
# planner/models.py

class ExecutionStrategy(str, Enum):
    SINGLE       = "single"        # one agent, direct proxy
    PARALLEL     = "parallel"      # N agents run simultaneously
    SEQUENTIAL   = "sequential"    # output of A feeds B
    CONDITIONAL  = "conditional"   # branch based on intermediate result

@dataclass
class PlanStep:
    step_id: str                   # e.g. "step_1"
    agent_id: str
    input: str                     # may be rewritten from original
    depends_on: list[str]          # step_ids this waits for
    output_role: str               # "primary" | "supporting" | "validation"
    timeout_seconds: int = 60
    optional: bool = False         # if True, failure doesn't abort plan

@dataclass
class ExecutionPlan:
    run_id: str
    strategy: ExecutionStrategy
    steps: list[PlanStep]
    synthesis_required: bool
    original_input: str
    plan_reasoning: str            # short explanation emitted to frontend
    estimated_tokens: int
```

### Planner Agent

```python
# planner/planner.py

PLANNER_SYSTEM_PROMPT = """
You are a routing planner for a security compliance platform.
Given a user message and a catalog of available agents, 
return a JSON ExecutionPlan.

Rules:
- Only use agents from the provided catalog
- Prefer parallel execution unless one agent needs the output of another
- Only set synthesis_required=true if multiple agents produce complementary output
- Rewrite agent inputs to be specific and self-contained
- Never include agents the user has no access to
"""

class PlannerAgent:
    async def plan(
        self,
        user_input: str,
        claims: ResolvedClaims,
        registry: AgentRegistry
    ) -> ExecutionPlan:

        available = registry.agents_for_claims(claims)

        prompt = f"""
        User message: {user_input}

        Available agents:
        {json.dumps([a.to_catalog_entry() for a in available], indent=2)}

        User roles: {claims.roles}
        Multi-agent allowed: {claims.feature_flags.multi_agent}
        Max parallel: {claims.feature_flags.max_parallel_agents}

        Return a valid ExecutionPlan JSON.
        """

        raw = await self.llm.ainvoke([
            SystemMessage(PLANNER_SYSTEM_PROMPT),
            HumanMessage(prompt)
        ])

        plan = ExecutionPlan.parse_raw(raw.content)
        return self.enforce_claim_limits(plan, claims)

    def enforce_claim_limits(self, plan, claims) -> ExecutionPlan:
        parallel_steps = [s for s in plan.steps if not s.depends_on]
        if len(parallel_steps) > claims.feature_flags.max_parallel_agents:
            # Collapse to sequential, emit plan_modified event
            plan = self.collapse_to_sequential(plan)
            plan.modified_reason = "parallel_limit_exceeded"
        return plan
```

---

## 6. Thread Management

Threads are the top-level container for a conversation. The gateway owns thread lifecycle entirely.

### Thread Schema

```sql
-- Postgres

CREATE TABLE threads (
    thread_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    source_id       TEXT NOT NULL,               -- web_app | api_client | etc.
    title           TEXT,                        -- auto-generated from first message
    status          TEXT DEFAULT 'active',       -- active | archived | deleted
    agent_id        TEXT,                        -- last agent used
    metadata        JSONB DEFAULT '{}',          -- arbitrary per-thread config
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

CREATE TABLE messages (
    message_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       UUID REFERENCES threads(thread_id),
    run_id          TEXT,                        -- links to agent execution
    role            TEXT NOT NULL,               -- user | assistant | tool
    content         TEXT NOT NULL,
    agent_id        TEXT,                        -- which agent produced this
    step_id         TEXT,                        -- which plan step
    token_count     INT,
    metadata        JSONB DEFAULT '{}',          -- tool results, citations etc.
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_runs (
    run_id          TEXT PRIMARY KEY,
    thread_id       UUID REFERENCES threads(thread_id),
    plan            JSONB,                       -- serialized ExecutionPlan
    status          TEXT,                        -- running | completed | failed
    input_tokens    INT,
    output_tokens   INT,
    latency_ms      INT,
    started_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
```

### Thread Manager

```python
# threads/manager.py

class ThreadManager:

    async def get_or_create(
        self,
        thread_id: str | None,
        claims: ResolvedClaims,
        source_id: str
    ) -> Thread:
        if thread_id:
            thread = await self.db.get_thread(thread_id)
            self.assert_ownership(thread, claims)   # tenant isolation check
            return thread
        return await self.db.create_thread(
            tenant_id=claims.tenant_id,
            user_id=claims.user_id,
            source_id=source_id
        )

    async def append_user_message(self, thread_id, content, token_count):
        await self.db.insert_message(
            thread_id=thread_id,
            role="user",
            content=content,
            token_count=token_count
        )
        await self.redis.update_thread_meta(thread_id, {
            "last_message_at": now_iso(),
            "message_count": await self.redis.incr(f"thread:{thread_id}:msg_count")
        })

    async def append_agent_message(self, thread_id, run_id, step_id, agent_id, content):
        await self.db.insert_message(
            thread_id=thread_id,
            run_id=run_id,
            role="assistant",
            content=content,
            agent_id=agent_id,
            step_id=step_id,
            token_count=count_tokens(content)
        )
```

---

## 7. History & Memory Model

### Three-Tier Memory Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Tier 1 — Working Memory                                     │
│  Scope:   current session / thread                           │
│  Content: last 10 messages, active tool results              │
│  Storage: Redis  (key: thread:{id}:working_mem)              │
│  TTL:     2 hours from last activity                         │
│  Written: gateway after each turn                            │
│  Max size: ~20KB per thread                                  │
├──────────────────────────────────────────────────────────────┤
│  Tier 2 — Session Memory                                     │
│  Scope:   full thread history                                │
│  Content: all messages, agent run results, tool outputs      │
│  Storage: Postgres (messages table)                          │
│  TTL:     permanent                                          │
│  Written: gateway on FINAL event                             │
├──────────────────────────────────────────────────────────────┤
│  Tier 3 — Long-term Memory                                   │
│  Scope:   cross-session, per tenant/user                     │
│  Content: extracted facts, org config, compliance posture    │
│  Storage: Postgres + pgvector (semantic retrieval)           │
│  TTL:     permanent, versioned                               │
│  Written: async memory agent triggered by gateway            │
└──────────────────────────────────────────────────────────────┘
```

### Memory Write-Back Flow

```python
# memory/writeback.py

class MemoryWriteback:
    """
    Called after every FINAL event.
    Never in the streaming critical path — always async.
    """

    async def on_final(self, run_result: RunResult):

        # Tier 1: update Redis working memory
        await self.redis.lpush(
            f"thread:{run_result.thread_id}:working_mem",
            json.dumps({
                "role": "assistant",
                "content": run_result.final_text,
                "agent_id": run_result.agent_id,
                "timestamp": now_iso()
            })
        )
        await self.redis.ltrim(
            f"thread:{run_result.thread_id}:working_mem", 0, 19  # keep last 20
        )

        # Tier 2: write to Postgres
        await self.thread_manager.append_agent_message(
            thread_id=run_result.thread_id,
            run_id=run_result.run_id,
            step_id=run_result.step_id,
            agent_id=run_result.agent_id,
            content=run_result.final_text
        )

        # Tier 3: async extraction — every 10 turns or if facts detected
        msg_count = await self.redis.get(f"thread:{run_result.thread_id}:msg_count")
        if int(msg_count) % 10 == 0 or run_result.has_extractable_facts:
            await self.memory_queue.publish({
                "job": "extract_and_store",
                "thread_id": run_result.thread_id,
                "tenant_id": run_result.tenant_id,
                "content": run_result.final_text
            })
```

---

## 8. Context Composition

Context composition is the most critical pre-invocation step. It assembles a budget-aware context window from all three memory tiers and delivers it to the agent via a signed Redis token.

### Token Budget Per Agent

```python
# context/budget.py

@dataclass
class ContextBudget:
    total: int                      # from AgentMeta.context_window_tokens
    system_reserved: int            # agent persona + tool schemas
    turn_reserved: int              # always raw, never compressed
    session_budget: int             # history summary + working memory
    response_reserved: int          # space for agent output

    @classmethod
    def from_agent_meta(cls, meta: AgentMeta) -> "ContextBudget":
        return cls(
            total             = meta.context_window_tokens,
            system_reserved   = meta.system_ctx_tokens,
            turn_reserved     = meta.turn_ctx_tokens,
            session_budget    = meta.session_ctx_tokens,
            response_reserved = meta.response_reserve_tokens
        )
```

### Composition Strategy

```python
# context/composer.py

class ContextComposer:

    async def compose(
        self,
        thread_id: str,
        user_input: str,
        agent_meta: AgentMeta,
        claims: ResolvedClaims,
        step_index: int = 0          # parallel agents share budget
    ) -> ComposedContext:

        budget = ContextBudget.from_agent_meta(agent_meta)

        # In multi-agent plans, session budget is split across steps
        if step_index > 0:
            budget.session_budget = budget.session_budget // (step_index + 1)

        # Layer 1 — System context (static, from registry)
        system_ctx = self.build_system_context(agent_meta, claims)

        # Layer 2 — Session context (dynamic, budget-constrained)
        session_ctx = await self.build_session_context(
            thread_id=thread_id,
            claims=claims,
            token_limit=budget.session_budget
        )

        # Layer 3 — Turn context (last N raw messages + current input)
        turn_ctx = await self.build_turn_context(
            thread_id=thread_id,
            user_input=user_input,
            token_limit=budget.turn_reserved
        )

        return ComposedContext(
            system=system_ctx,
            session=session_ctx,
            turn=turn_ctx
        )

    async def build_session_context(self, thread_id, claims, token_limit):
        messages = await self.redis.lrange(
            f"thread:{thread_id}:working_mem", 0, 49
        )

        token_count = count_tokens(messages)

        if token_count <= token_limit:
            return SessionContext(type="raw", messages=messages)

        # Try trim first
        trimmed = trim_to_budget(messages, token_limit)
        if coverage(trimmed, messages) > 0.7:
            return SessionContext(type="trimmed", messages=trimmed)

        # Use cached rolling summary + last 5 raw
        summary = await self.redis.get(f"thread:{thread_id}:summary")
        recent = messages[-5:]
        if summary and fits_budget(summary, recent, token_limit):
            return SessionContext(
                type="summary+raw",
                summary=summary,
                recent=recent
            )

        # Fallback: trigger async re-summary, use trimmed for now
        asyncio.create_task(self.refresh_summary(thread_id, messages))
        return SessionContext(type="trimmed_fallback", messages=trimmed)

    async def refresh_summary(self, thread_id, messages):
        existing = await self.redis.get(f"thread:{thread_id}:summary")
        prompt = f"""
        Existing summary: {existing or 'None'}
        New messages: {format_messages(messages[-10:])}

        Return a concise updated summary (max 300 words) capturing:
        - Key decisions and conclusions
        - Entities mentioned (assets, controls, users, frameworks)
        - Open questions or pending actions
        - Current topic and intent
        """
        summary = await self.llm.ainvoke(prompt)
        await self.redis.setex(
            f"thread:{thread_id}:summary", 86400, summary
        )
```

### Context Token — Delivery Mechanism

Context is never sent inline in the agent invocation payload. The gateway mints a short-lived signed token pointing to pre-computed context in Redis.

```python
# context/token.py

class ContextTokenService:

    async def mint(self, context: ComposedContext, ttl: int = 300) -> str:
        ctx_key = f"ctx:{uuid4().hex}"
        await self.redis.setex(ctx_key, ttl, context.model_dump_json())
        return self.signer.sign(ctx_key)        # HMAC-SHA256

    async def resolve(self, token: str) -> ComposedContext:
        ctx_key = self.signer.verify(token)     # raises if tampered
        raw = await self.redis.get(ctx_key)
        if not raw:
            raise ContextExpiredError(token)
        return ComposedContext.model_validate_json(raw)
```

**Resulting agent invocation payload** (~1–2KB):

```json
{
  "input": "Assess our SOC2 gap for CC6.1",
  "thread_id": "t_abc123",
  "run_id": "run_xyz",
  "step_id": "step_1",
  "ctx_token": "v1.hmac.abc123...",
  "hint": {
    "message_count": 14,
    "has_summary": true,
    "has_memory": true,
    "tenant_id": "org_xyz",
    "context_tier": "full"
  },
  "data_scope": {
    "frameworks": ["SOC2"],
    "asset_groups": ["group_a"]
  }
}
```

---

## 9. Redis Caching Architecture

### Key Schema

All Redis keys follow a namespaced, hierarchical schema to support TTL management, tenant isolation, and bulk invalidation.

```
# Thread working memory (list, capped at 20 items)
thread:{thread_id}:working_mem          TTL: 2h from last write

# Rolling summary (string)
thread:{thread_id}:summary              TTL: 24h

# Thread metadata (hash)
thread:{thread_id}:meta                 TTL: 2h
  → last_message_at, message_count, active_agent, status

# Active run tracking (hash)
run:{run_id}:state                      TTL: 10m
  → status, step_ids, started_at, tenant_id

# Context payload (string, JSON)
ctx:{token_id}                          TTL: 5m (single use)

# Long-term memory hot cache (hash, tenant-scoped)
memory:{tenant_id}:facts                TTL: 1h
  → key-value facts extracted from sessions

# Agent registry metadata (hash, global)
registry:agents                         TTL: none (reloaded on startup)

# Rate limiting (per source + user)
ratelimit:{source_id}:{user_id}:rpm     TTL: 60s (sliding window)
ratelimit:{source_id}:{user_id}:daily   TTL: 86400s

# Source config cache (hash)
source:{source_id}:config               TTL: 5m (synced from YAML)
```

### Cache Sizing & Eviction

```python
# config/redis.py

REDIS_CONFIG = {
    "maxmemory": "2gb",
    "maxmemory-policy": "volatile-lru",    # evict TTL keys by LRU first
    "maxmemory-samples": 10,

    # Per-key size guards (enforced in application layer)
    "max_working_mem_bytes":  20_000,      # ~20KB per thread
    "max_ctx_payload_bytes":  50_000,      # ~50KB per context token
    "max_summary_bytes":       3_000,      # ~3KB per summary
    "max_memory_facts_bytes": 10_000,      # ~10KB per tenant fact store
}
```

### Cache Warming on Thread Resume

When a thread is resumed after Redis TTL expiration, the gateway rebuilds the hot cache from Postgres:

```python
# cache/warmer.py

class CacheWarmer:
    async def warm_thread(self, thread_id: str, tenant_id: str):
        # Check if already warm
        if await self.redis.exists(f"thread:{thread_id}:working_mem"):
            return

        # Rebuild from Postgres
        messages = await self.db.get_last_k_messages(thread_id, k=20)

        pipe = self.redis.pipeline()
        for msg in reversed(messages):
            pipe.rpush(
                f"thread:{thread_id}:working_mem",
                json.dumps(msg)
            )
        pipe.expire(f"thread:{thread_id}:working_mem", 7200)
        await pipe.execute()

        # Restore metadata
        meta = await self.db.get_thread_meta(thread_id)
        await self.redis.hset(f"thread:{thread_id}:meta", mapping=meta)
        await self.redis.expire(f"thread:{thread_id}:meta", 7200)
```

---

## 10. Agent Adapter Layer

### Abstract Interface

```python
# adapters/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator

class AgentAdapter(ABC):
    """
    All agent frameworks implement this interface.
    Adapters are stateless — all state is in the ComposedContext.
    """

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
        """
        Map framework-native event shapes to AgentEvent protocol.
        """
        ...
```

### Agent Registry

```python
# adapters/registry.py

@dataclass
class AgentMeta:
    agent_id: str
    display_name: str
    framework: str                     # "langgraph" | "claude-sdk" | "a2a"
    capabilities: list[str]            # ["streaming", "tool_use", "multi_step"]
    context_window_tokens: int = 8000
    system_ctx_tokens: int     = 1500
    session_ctx_tokens: int    = 3000
    turn_ctx_tokens: int       = 2000
    response_reserve_tokens: int = 1500
    requires_memory: bool      = False
    requires_memory_keys: list[str] = field(default_factory=list)
    required_role: str         = "viewer"
    feature_flag: str | None   = None
    routing_tags: list[str]    = field(default_factory=list)
    tenant_scoped: bool        = True

    def to_catalog_entry(self) -> dict:
        # Stripped version sent to planner LLM
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "routing_tags": self.routing_tags,
        }


class AgentRegistry:
    def __init__(self):
        self._adapters: dict[str, AgentAdapter] = {}
        self._meta: dict[str, AgentMeta] = {}

    def register(self, meta: AgentMeta, adapter: AgentAdapter):
        self._adapters[meta.agent_id] = adapter
        self._meta[meta.agent_id] = meta

    def get_adapter(self, agent_id: str) -> AgentAdapter:
        if agent_id not in self._adapters:
            raise AgentNotFoundError(agent_id)
        return self._adapters[agent_id]

    def get_meta(self, agent_id: str) -> AgentMeta:
        return self._meta[agent_id]

    def agents_for_claims(self, claims: ResolvedClaims) -> list[AgentMeta]:
        return [
            m for m in self._meta.values()
            if claims.can_access_agent(m.agent_id)
            and self._role_ok(claims.roles, m.required_role)
            and self._flag_ok(claims.feature_flags, m.feature_flag)
        ]
```

### LangGraph Adapter

```python
# adapters/langgraph_adapter.py

class LangGraphAdapter(AgentAdapter):
    def __init__(self, graph, context_client: ContextClient):
        self.graph = graph
        self.ctx_client = context_client

    async def stream(self, payload, context, config) -> AsyncIterator[AgentEvent]:
        graph_input = {
            "input": payload["input"],
            "chat_history": to_langchain_messages(
                context.turn.recent + context.session.messages
            ),
            "context_summary": context.session.summary,
            "memory": context.system.memory,
            "data_scope": payload.get("data_scope", {})
        }

        async for raw in self.graph.astream_events(graph_input, version="v2"):
            event = self.normalize_event(raw)
            if event:
                yield event

    def normalize_event(self, raw) -> AgentEvent | None:
        kind = raw.get("event")
        if kind == "on_chat_model_stream":
            token = raw["data"]["chunk"].content
            if not token:
                return None
            return AgentEvent(type=EventType.TOKEN, data={"text": token})
        if kind == "on_tool_start":
            return AgentEvent(type=EventType.TOOL_START, data={"tool": raw["name"]})
        if kind == "on_tool_end":
            return AgentEvent(type=EventType.TOOL_END, data={"output": str(raw["data"].get("output", ""))})
        if kind == "on_chain_end" and raw.get("name") == "AgentFinish":
            return AgentEvent(type=EventType.FINAL, data={"text": raw["data"]["output"]["output"]})
        return None
```

### Claude SDK Adapter

```python
# adapters/claude_adapter.py

class ClaudeAgentAdapter(AgentAdapter):
    def __init__(self, client: anthropic.AsyncAnthropic, system_prompt: str):
        self.client = client
        self.system_prompt = system_prompt

    async def stream(self, payload, context, config) -> AsyncIterator[AgentEvent]:
        messages = to_claude_messages(context.turn.recent)
        messages.append({"role": "user", "content": payload["input"]})

        system = f"{self.system_prompt}\n\nContext:\n{context.session.summary or ''}"

        async with self.client.messages.stream(
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
```

---

## 11. Event Protocol

### AgentEvent Schema

```python
# protocol/events.py

class EventType(str, Enum):
    # Core streaming
    TOKEN            = "token"           # streaming LLM token
    TOOL_START       = "tool_start"      # agent invoking a tool
    TOOL_END         = "tool_end"        # tool finished

    # Lifecycle
    STEP_START       = "step_start"      # one plan step beginning
    STEP_FINAL       = "step_final"      # one plan step complete
    STEP_ERROR       = "step_error"      # one step failed (others may continue)
    FINAL            = "final"           # entire run complete

    # Orchestration
    PLAN             = "plan"            # gateway emits plan before execution
    PLAN_MODIFIED    = "plan_modified"   # plan changed due to auth limits
    SYNTHESIS_START  = "synthesis_start" # synthesizer beginning to merge
    ERROR            = "error"           # fatal error


class AgentEvent(BaseModel):
    type: EventType
    agent_id: str
    run_id: str
    step_id: str
    tenant_id: str
    data: dict
    metadata: dict = {}                  # latency_ms, token_count, node_name

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"
```

### SSE Wire Format Examples

```
# Planner emits plan first — frontend can show "I'm going to..."
data: {"type":"plan","agent_id":"planner","run_id":"r_abc","step_id":"plan",
       "data":{"strategy":"parallel","steps":[{"agent_id":"vuln-scanner"},
       {"agent_id":"soc2-gap"}],"reasoning":"Query requires both vulnerability
       and compliance data."}}

# Two agents streaming in parallel — tagged by step_id
data: {"type":"token","agent_id":"vuln-scanner","run_id":"r_abc","step_id":"step_1",
       "data":{"text":"Found 3 critical CVEs"}}

data: {"type":"token","agent_id":"soc2-gap","run_id":"r_abc","step_id":"step_2",
       "data":{"text":"Control CC6.1 is partially met"}}

# Tool invocation mid-stream
data: {"type":"tool_start","agent_id":"vuln-scanner","run_id":"r_abc",
       "step_id":"step_1","data":{"tool":"qualys_scan","input":{"asset":"10.0.0.1"}}}

data: {"type":"tool_end","agent_id":"vuln-scanner","run_id":"r_abc",
       "step_id":"step_1","data":{"tool":"qualys_scan","output":"3 findings"}}

# One step complete
data: {"type":"step_final","agent_id":"vuln-scanner","run_id":"r_abc",
       "step_id":"step_1","data":{"text":"Full vuln summary..."}}

# Synthesizer begins
data: {"type":"synthesis_start","agent_id":"synthesizer","run_id":"r_abc",
       "step_id":"synthesis","data":{"merging_steps":["step_1","step_2"]}}

# Final merged response
data: {"type":"final","agent_id":"synthesizer","run_id":"r_abc",
       "step_id":"synthesis","data":{"text":"Based on both scans..."}}
```

---

## 12. Multi-Agent Orchestration

### Execution Engine

```python
# orchestration/engine.py

class OrchestrationEngine:

    async def execute(
        self,
        plan: ExecutionPlan,
        claims: ResolvedClaims,
        thread_id: str,
        output_queue: asyncio.Queue
    ):
        if plan.strategy == ExecutionStrategy.SINGLE:
            await self.execute_single(plan.steps[0], claims, thread_id, output_queue)

        elif plan.strategy == ExecutionStrategy.PARALLEL:
            await self.execute_parallel(plan.steps, claims, thread_id, output_queue)

        elif plan.strategy == ExecutionStrategy.SEQUENTIAL:
            await self.execute_sequential(plan.steps, claims, thread_id, output_queue)

        if plan.synthesis_required:
            await self.synthesize(plan, output_queue)

    async def execute_parallel(self, steps, claims, thread_id, queue):
        async def run_step(step, idx):
            context = await self.context_composer.compose(
                thread_id=thread_id,
                user_input=step.input,
                agent_meta=self.registry.get_meta(step.agent_id),
                claims=claims,
                step_index=idx
            )
            ctx_token = await self.ctx_token_svc.mint(context)
            payload = self.build_payload(step, ctx_token, claims)
            adapter = self.registry.get_adapter(step.agent_id)

            await queue.put(AgentEvent(
                type=EventType.STEP_START,
                agent_id=step.agent_id,
                step_id=step.step_id,
                data={}
            ))
            try:
                async for event in adapter.stream(payload, context, {}):
                    event.agent_id = step.agent_id
                    event.step_id = step.step_id
                    await queue.put(event)
            except Exception as e:
                if not step.optional:
                    raise
                await queue.put(AgentEvent(
                    type=EventType.STEP_ERROR,
                    step_id=step.step_id,
                    data={"error": str(e)}
                ))

        await asyncio.gather(*[run_step(s, i) for i, s in enumerate(steps)])

    async def execute_sequential(self, steps, claims, thread_id, queue):
        step_results = {}
        for step in steps:
            # Augment input with prior step output if dependent
            if step.depends_on:
                prior_output = step_results.get(step.depends_on[0], "")
                step.input = f"{step.input}\n\nPrior context:\n{prior_output}"

            final_text = ""
            async for event in self.run_step_stream(step, claims, thread_id, queue):
                if event.type == EventType.FINAL:
                    final_text = event.data.get("text", "")
            step_results[step.step_id] = final_text
```

### Synthesizer

```python
# orchestration/synthesizer.py

class Synthesizer:
    async def synthesize(
        self,
        step_results: dict[str, str],
        original_input: str,
        queue: asyncio.Queue
    ):
        await queue.put(AgentEvent(
            type=EventType.SYNTHESIS_START,
            agent_id="synthesizer",
            step_id="synthesis",
            data={"merging_steps": list(step_results.keys())}
        ))

        prompt = f"""
        User asked: {original_input}

        Agent findings:
        {self.format_results(step_results)}

        Synthesize into a single coherent response.
        Highlight agreements, conflicts, and gaps between findings.
        Do not repeat identical information.
        """

        async for token in self.llm.astream(prompt):
            await queue.put(AgentEvent(
                type=EventType.TOKEN,
                agent_id="synthesizer",
                step_id="synthesis",
                data={"text": token}
            ))
```

---

## 13. Observability

Every agent run is traced end-to-end with a single `run_id`. Spans are nested: `gateway.invoke` → `planner` → `step.{agent_id}` → `adapter.stream`.

```python
# middleware/observability.py

@app.post("/v1/agents/invoke")
async def invoke(request: InvokeRequest, claims: ResolvedClaims = Depends(verify_jwt)):
    run_id = str(uuid4())

    with tracer.start_as_current_span("gateway.invoke") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("tenant_id", claims.tenant_id)
        span.set_attribute("user_id", claims.user_id)
        span.set_attribute("source_id", request.source_id)

        async def event_stream():
            t0 = time.time()
            token_count = 0
            try:
                async for event in orchestrator.run(request, claims, run_id):
                    if event.type == EventType.TOKEN:
                        token_count += 1
                    yield event.to_sse()
            finally:
                latency_ms = (time.time() - t0) * 1000
                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("token_count", token_count)
                metrics.record_run(run_id, latency_ms, token_count, claims.tenant_id)

        return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 14. Failure Handling

| Failure | Behavior |
|---|---|
| Agent timeout | Emit `step_error`, mark step optional if plan allows, continue |
| Context token expired | Re-compose context, re-mint token, retry once |
| Redis unavailable | Fall back to Postgres direct fetch, log degraded mode |
| Planner returns invalid plan | Fallback to single-agent using routing_tags match |
| JWT expired mid-stream | Close SSE stream with `error` event, 401 on next request |
| Agent returns no FINAL event | Gateway emits synthetic FINAL after timeout, writes partial to history |
| Parallel step fails | If `optional=true` proceed to synthesis with note; if `optional=false` abort run |
| Redis cache miss (ctx_token) | ContextExpiredError → 408 to client, client retries with new request |
| Synthesis LLM fails | Return concatenated step finals with `synthesis_failed` metadata flag |
| Over token budget | Trim session context first, never trim turn context, log budget overflow metric |

---

*End of Design Document*