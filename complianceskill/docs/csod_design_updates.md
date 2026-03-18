# Planner Narrator Stream — Design

**Scope:** `base_langgraph_adapter.py` · `csod_planner_workflow.py` · `app/adapters/base.py`
**Builds on:** `planner_reasoning_stream_design.md` (replaces the template-message approach)

---

## 1. The Idea

Instead of pre-written template messages, a small **narrator LLM** runs after each
planner node completes. It reads the node's structured output, the user's original
question, and everything it has already said, then **streams tokens** back to the
UI explaining what it found and what it is about to do next — in first-person,
present-tense natural language.

The result looks like a thinking panel that builds incrementally:

```
I looked at your question and searched the knowledge base for relevant topic areas.
I found two candidates: Compliance Training Risk and Learning Program Effectiveness.

Looking more closely, your question focuses on overdue mandatory training and
certification deadlines — that maps clearly to Compliance Training Risk.
I'm confident in that match.

Now I need to understand what kind of analysis you want. Your question sounds like
you need metrics and KPIs to track compliance gaps, so I'm checking whether that
fits the metrics advisor or the standard workflow...
```

Each sentence arrives as a streaming token. The panel never shows a spinner waiting
for the whole paragraph — the first word arrives within ~300ms of the node completing.

---

## 2. Architecture Overview

```
LangGraph graph.astream_events()
        │
        │  on_chain_end fires for each node
        ▼
BaseLangGraphAdapter.stream()
        │
        │  intercepts on_chain_end for known narrator nodes
        │  extracts structured node_output from state
        │
        ▼
NarratorLLM.astream(context)           ← async, streams tokens
        │
        │  yields tokens
        ▼
REASONING_TOKEN events → SSE → UI      ← token by token, no buffering
        │
        │  after all tokens streamed
        ▼
REASONING_DONE event                   ← signals end of this step's narrative
        │
        │  then normal CHECKPOINT / FINAL event if present
        ▼
continue to next node
```

The narrator runs **inline inside the existing async generator** in `stream()`.
No background tasks, no separate threads. The graph is paused at its own `END`
node (after a checkpoint) or between node completions, so there is no race.

---

## 3. New Event Types

```python
class EventType(str, Enum):
    TOKEN             = "token"           # existing — LLM output tokens
    TOOL_START        = "tool_start"      # existing
    TOOL_END          = "tool_end"        # existing
    CHECKPOINT        = "checkpoint"      # existing
    FINAL             = "final"           # existing
    STEP_START        = "step_start"      # existing
    STEP_FINAL        = "step_final"      # existing
    STEP_ERROR        = "step_error"      # existing
    REASONING_TOKEN   = "reasoning_token" # NEW — one token from narrator stream
    REASONING_DONE    = "reasoning_done"  # NEW — narrator finished for this step
```

`REASONING_TOKEN` carries a single token, same shape as `TOKEN` but distinct so the
UI can route it to the thinking panel instead of the main response area.

`REASONING_DONE` carries the full accumulated text for this step and a `node` label
so the UI can mark the step as complete and optionally collapse it.

---

## 4. Structured Node Output — What the Narrator Reads

Each planner node writes a `csod_node_output` dict into state before returning.
This is the narrator's primary input — it tells the narrator exactly what the node
found, not how to describe it. The narrator decides the words.

```python
# Shape of csod_node_output:
{
    "node":     str,           # node name
    "status":   str,           # "success" | "no_results" | "skipped" | "error"
    "findings": dict,          # node-specific structured results (see per-node below)
    "next":     str | None,    # what will happen next (for the narrator's "I will now..." sentence)
}
```

### Per-node `findings` payloads

**`csod_concept_resolver`**
```python
{
    "candidates": [
        {"id": "compliance_training", "name": "Compliance Training Risk",
         "score": 0.40, "keywords": ["compliance", "mandatory", "overdue"]},
        {"id": "learning_effectiveness", "name": "Learning Program Effectiveness",
         "score": 0.33, "keywords": ["learning", "effectiveness", "assessment"]},
    ],
    "llm_primary":   "compliance_training",
    "llm_confidence": "high",
    "llm_reasoning":  "Query focuses on mandatory training deadlines and certification gaps.",
    "datasource_inferred": "cornerstone",
}
```

**`csod_skill_identifier`**
```python
{
    "primary_skill":       "metrics_recommendations",
    "primary_display":     "Metrics & KPI Recommendations",
    "secondary_skills":    ["dashboard_generation"],
    "reasoning":           "User wants to track and measure compliance gaps with KPIs.",
    "concept_context":     "Compliance Training Risk",
}
```

**`csod_scoping_node`**
```python
{
    "filters_needed":    ["org_unit", "time_period", "training_type"],
    "filters_answered":  [],
    "questions_queued":  3,
    "skipped":           False,
}
```

**`csod_area_matcher`**
```python
{
    "areas_matched": [
        {"id": "compliance_risk_by_dept",  "name": "Compliance Risk by Department",  "score": 0.88},
        {"id": "overdue_cert_tracking",    "name": "Overdue Certification Tracking",  "score": 0.74},
    ],
    "primary_area_id":   "compliance_risk_by_dept",
    "primary_area_name": "Compliance Risk by Department",
    "scoping_used":      {"org_unit": "department", "time_period": "current_quarter"},
}
```

**`csod_workflow_router`**
```python
{
    "target_workflow": "csod_metric_advisor_workflow",
    "next_agent_id":   "csod-metric-advisor",
    "intent":          "metric_kpi_advisor",
    "reason":          "Skill maps to metric advisor workflow.",
}
```

---

## 5. The Narrator LLM

### 5.1 System prompt — `data/prompts/csod/14_planner_narrator.md`

```
You are the internal voice of an AI analytics assistant called Lexy.

Lexy is working through a multi-step process to understand a user's question about
their learning and compliance data. After each step, you explain what Lexy just
found or decided — in first person, present tense, as if thinking out loud.

Rules:
- Write in first person: "I found...", "I can see...", "I'm now...", "This tells me..."
- Be concise: 1–4 sentences per step. No padding.
- Build on what was said before. Do not repeat information already in the narrative.
- Reference the user's actual question. Do not be generic.
- When confidence is high, state the finding directly. When low, express appropriate uncertainty.
- Do not use technical IDs, field names, or system terminology.
- End with a brief "I'm now..." sentence that previews the next step — unless this is the final step.
- Never use bullet points. Pure flowing prose only.

You will receive:
- The user's original question
- A summary of what each prior step found (narrative_so_far)
- The structured output of the step that just completed (step_output)
- The name of the next step that will run (next_step), if any

Respond with only the narrator text. No preamble, no labels, no formatting.
```

### 5.2 Narrator context object built by adapter

```python
@dataclass
class NarratorContext:
    user_query:       str
    node_name:        str
    node_output:      dict          # csod_node_output.findings
    node_status:      str           # success | skipped | no_results
    narrative_so_far: str           # accumulated text from all prior steps this turn
    next_step_label:  str | None    # plain-English label for what runs next
```

### 5.3 `_build_narrator_prompt(ctx: NarratorContext) -> str`

```python
def _build_narrator_prompt(ctx: NarratorContext) -> str:
    parts = [f"User question: {ctx.user_query}\n"]

    if ctx.narrative_so_far:
        parts.append(f"What I have said so far:\n{ctx.narrative_so_far}\n")

    parts.append(f"Step just completed: {ctx.node_name}")
    parts.append(f"Status: {ctx.node_status}")
    parts.append(f"What this step found:\n{json.dumps(ctx.node_output, indent=2)}")

    if ctx.next_step_label:
        parts.append(f"Next step: {ctx.next_step_label}")
    else:
        parts.append("This is the final step.")

    return "\n\n".join(parts)
```

---

## 6. Adapter Integration — Where the Narrator Runs

### 6.1 Which nodes trigger the narrator

Not every `on_chain_end` should trigger a narrator call — only the meaningful
planner nodes. Define this as a config on the adapter:

```python
# In CSODLangGraphAdapter:
NARRATOR_NODES = {
    "csod_concept_resolver",
    "csod_skill_identifier",
    "csod_scoping_node",
    "csod_area_matcher",
    "csod_workflow_router",
}

# Human-readable label for what comes next after each node
NEXT_STEP_LABELS = {
    "csod_concept_resolver":  "understanding what kind of analysis you need",
    "csod_skill_identifier":  "gathering a bit of context before searching",
    "csod_scoping_node":      "finding the best analysis framework for your question",
    "csod_area_matcher":      "selecting the right agent to answer your question",
    "csod_workflow_router":   None,   # final step
}
```

### 6.2 Modify `stream()` — narrator inline with the event loop

The stream loop in `BaseLangGraphAdapter.stream()` becomes:

```python
async for raw_event in self.graph.astream_events(graph_input, version="v2", config=graph_config):

    event_type = raw_event.get("event", "")
    node_name  = raw_event.get("name", "")
    output     = raw_event.get("data", {}).get("output", {})

    # ── Narrator intercept ────────────────────────────────────────────────────
    if (event_type == "on_chain_end"
            and isinstance(output, dict)
            and node_name in self.get_narrator_nodes()):

        node_output_entry = output.get("csod_node_output")
        if node_output_entry:
            async for r_event in self._stream_narrator(
                node_name=node_name,
                node_output=node_output_entry,
                state=output,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
            ):
                yield r_event
    # ─────────────────────────────────────────────────────────────────────────

    # Drain reasoning stream from previous design (still present as fallback)
    if event_type == "on_chain_end" and isinstance(output, dict):
        for r_event in self.extract_reasoning_events_from_state(output, node_name):
            r_event.agent_id = agent_id
            r_event.run_id = run_id
            yield r_event

    # Standard event normalization
    event = self.normalize_event(raw_event, graph_config)
    if event:
        event.agent_id = agent_id
        event.run_id   = run_id
        event.step_id  = step_id
        event.tenant_id = tenant_id
        yield event
```

### 6.3 `_stream_narrator()` — the async generator

```python
async def _stream_narrator(
    self,
    node_name:  str,
    node_output: dict,
    state:       dict,
    agent_id:    str,
    run_id:      str,
    step_id:     str,
    tenant_id:   str,
) -> AsyncIterator[AgentEvent]:
    """
    Call the narrator LLM and stream its tokens as REASONING_TOKEN events.
    Appends the completed text to csod_reasoning_narrative in state.
    """
    try:
        narrator_prompt = load_prompt("14_planner_narrator", prompts_dir=str(PROMPTS_CSOD))
    except FileNotFoundError:
        return  # Narrator prompt missing — degrade gracefully, emit nothing

    # Build context
    narrative_so_far = "\n".join(
        entry.get("text", "") for entry in state.get("csod_reasoning_narrative", [])
    )
    ctx = NarratorContext(
        user_query       = state.get("user_query", ""),
        node_name        = node_name,
        node_output      = node_output.get("findings", {}),
        node_status      = node_output.get("status", "success"),
        narrative_so_far = narrative_so_far,
        next_step_label  = self.NEXT_STEP_LABELS.get(node_name),
    )
    human_message = _build_narrator_prompt(ctx)

    # Build LangChain chain
    llm = get_llm(temperature=0.3, streaming=True)   # slight temperature for natural prose
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", narrator_prompt),
        ("human", "{input}"),
    ])
    chain = prompt_template | llm

    # Stream tokens
    accumulated = []
    try:
        async for chunk in chain.astream({"input": human_message}):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                accumulated.append(token)
                yield AgentEvent(
                    type=EventType.REASONING_TOKEN,
                    agent_id=agent_id,
                    run_id=run_id,
                    step_id=step_id,
                    tenant_id=tenant_id,
                    data={"text": token, "node": node_name},
                    metadata={"node": node_name},
                )
    except Exception as e:
        logger.warning(f"Narrator LLM error for node {node_name}: {e}")
        return  # Degrade gracefully — reasoning stream drops this step

    # Emit REASONING_DONE with the full step text
    full_text = "".join(accumulated)
    yield AgentEvent(
        type=EventType.REASONING_DONE,
        agent_id=agent_id,
        run_id=run_id,
        step_id=step_id,
        tenant_id=tenant_id,
        data={
            "node":       node_name,
            "text":       full_text,
            "node_output": node_output,   # structured findings for UI detail panel
        },
        metadata={"node": node_name},
    )

    # Append to accumulated narrative in state so next narrator call has context
    # State is the output dict — mutation is safe here (in-memory only)
    if "csod_reasoning_narrative" not in state:
        state["csod_reasoning_narrative"] = []
    state["csod_reasoning_narrative"].append({
        "node": node_name,
        "text": full_text,
    })
```

---

## 7. State Fields

```python
# In CSODState (csod_state.py):

csod_node_output: Optional[Dict[str, Any]]
# Written by each narrator-aware node before returning.
# Shape: {node, status, findings, next}
# Read by _stream_narrator(). Not persisted across turns (overwritten each node).

csod_reasoning_narrative: List[Dict[str, Any]]
# Accumulated narrator text across all nodes in the current planner run.
# Each entry: {node: str, text: str}
# Reset to [] in create_csod_planner_initial_state().
# Persisted in checkpointer across checkpoint turns (user sees full story).
```

---

## 8. How Nodes Write `csod_node_output`

Nodes call a single helper before returning. No LLM call inside nodes — just structured data:

```python
def _set_node_output(
    state: dict,
    node: str,
    status: str,           # "success" | "no_results" | "skipped"
    findings: dict,        # node-specific structured results
    next_step: str = None, # next node name (used for NEXT_STEP_LABELS lookup)
) -> None:
    state["csod_node_output"] = {
        "node":     node,
        "status":   status,
        "findings": findings,
        "next":     next_step,
    }
```

### Example — `csod_concept_resolver_node`

```python
def csod_concept_resolver_node(state):
    # ... vector search ...
    concept_matches = resolve_intent_to_concept(...)

    # ... LLM ranking ...
    llm_ranking = _rank_concepts_with_llm(user_query, concept_matches)

    # Set checkpoint for user ...

    _set_node_output(state, "csod_concept_resolver",
        status="success" if concept_matches else "no_results",
        findings={
            "candidates": [
                {"id": m.concept_id, "name": m.display_name,
                 "score": round(m.score, 3),
                 "keywords": m.trigger_keywords[:5]}
                for m in concept_matches
            ],
            "llm_primary":         llm_ranking.get("primary_concept_id") if llm_ranking else None,
            "llm_confidence":      llm_ranking.get("confidence") if llm_ranking else "low",
            "llm_reasoning":       llm_ranking.get("reasoning") if llm_ranking else None,
            "datasource_inferred": state.get("csod_selected_datasource"),
        },
        next_step="csod_skill_identifier",
    )
    return state
```

---

## 9. Full SSE Stream for One Planner Run

```
{type: "step_start"}

  ← csod_concept_resolver runs (vector search + LLM ranking) →

{type: "reasoning_token", data: {text: "I",          node: "csod_concept_resolver"}}
{type: "reasoning_token", data: {text: " searched",  node: "csod_concept_resolver"}}
{type: "reasoning_token", data: {text: " your",      node: "csod_concept_resolver"}}
... (tokens stream in)
{type: "reasoning_token", data: {text: " next.",     node: "csod_concept_resolver"}}
{type: "reasoning_done",  data: {
    node: "csod_concept_resolver",
    text: "I searched your question and found two candidate topic areas:
           Compliance Training Risk and Learning Program Effectiveness.
           Your focus on overdue mandatory training maps clearly to Compliance
           Training Risk — I'm confident in that match.
           I'm now working out what type of analysis you need.",
    node_output: {findings: {...}}
}}
{type: "checkpoint", data: {phase: "concept_select", message: "I'll analyse
    Compliance Training Risk for you. Is that right?", options: [...]}}

{type: "step_final"}

  ← user confirms concept → Turn 2 starts →

{type: "step_start"}

  ← csod_skill_identifier runs →

{type: "reasoning_token", data: {text: "You've",     node: "csod_skill_identifier"}}
... (tokens stream in)
{type: "reasoning_done",  data: {
    node: "csod_skill_identifier",
    text: "You've confirmed you're asking about Compliance Training Risk.
           Reading your question more carefully, you want to measure and track
           compliance gaps — that points to Metrics & KPI Recommendations rather
           than a dashboard or ad-hoc query.
           I'm now gathering a bit of context before I search for the best
           analysis framework.",
    node_output: {findings: {...}}
}}

  ← csod_scoping_node runs →

{type: "reasoning_token", data: {text: "Before",    node: "csod_scoping_node"}}
... (tokens stream in)
{type: "reasoning_done",  data: {
    node: "csod_scoping_node",
    text: "Before I can find the most relevant analysis approach, I need to
           understand which part of your organisation is in scope and what
           time period you care about most.",
    node_output: {findings: {...}}
}}
{type: "checkpoint", data: {phase: "scoping", questions: [...], ...}}

{type: "step_final"}
```

---

## 10. UI Rendering Contract

```typescript
// Two new event types
interface ReasoningTokenEvent {
  type: "reasoning_token";
  data: { text: string; node: string };
}

interface ReasoningDoneEvent {
  type: "reasoning_done";
  data: {
    node:        string;
    text:        string;       // full narrator text for this step
    node_output: object;       // structured findings (for optional detail panel)
  };
}
```

### Rendering rules

The thinking panel is a side panel or collapsible section above the checkpoint card.

```
┌─ Lexy is thinking... ──────────────────────────────────────────┐
│                                                                  │
│  I searched your question and found two candidate topic areas:   │← reasoning_done node 1
│  Compliance Training Risk and Learning Program Effectiveness.    │
│  Your focus on overdue mandatory training maps clearly to        │
│  Compliance Training Risk — I'm confident in that match.        │
│  I'm now working out what type of analysis you need.            │
│                                                                  │
│  You've confirmed Compliance Training Risk. Reading your         │← reasoning_done node 2
│  question, you want to measure compliance gaps — that points to  │
│  Metrics & KPI Recommendations. I'm now gathering context...    │
│                                                                  │
│  Before I find the best framework, I need to know which part    │← streaming now (tokens arriving)
│  of your organisation█                                           │
└──────────────────────────────────────────────────────────────────┘

┌─ Context questions ────────────────────────────────────────────┐   ← checkpoint card below
│  Which part of the organisation should I focus on?              │
│  ○ Whole company  ○ Department  ○ Team  ○ Role                  │
└──────────────────────────────────────────────────────────────────┘
```

| Event | UI action |
|---|---|
| `reasoning_token` | Append token to current paragraph in thinking panel. Show cursor `█`. |
| `reasoning_done` | Remove cursor. Add subtle separator below completed paragraph. Begin next paragraph slot. |
| `checkpoint` | Stop all streaming. Show checkpoint card below thinking panel. |

---

## 11. Graceful Degradation

The narrator is purely additive. If it fails, the planner still works:

| Failure scenario | Behaviour |
|---|---|
| Prompt file `14_planner_narrator.md` missing | `_stream_narrator` returns early with no events. Planner continues. |
| LLM call throws | `_stream_narrator` catches, logs, returns. REASONING_TOKEN stream stops mid-sentence. UI shows partial text. |
| `csod_node_output` not written by node | `_stream_narrator` receives empty findings. Narrator generates a generic "I completed this step" sentence. |
| `csod_reasoning_narrative` missing from state | Treated as `[]`. Narrator has no prior context — each step narrates independently. Still coherent. |

---

## 12. Implementation Checklist

| # | File | Change |
|---|---|---|
| 1 | `app/adapters/base.py` | Add `REASONING_TOKEN` and `REASONING_DONE` to `EventType` |
| 2 | `app/agents/csod/csod_state.py` | Add `csod_node_output` and `csod_reasoning_narrative` fields |
| 3 | `csod_planner_workflow.py` | Add `_set_node_output()` helper |
| 4 | `csod_planner_workflow.py` | Add `_set_node_output()` calls in 5 nodes: concept_resolver, skill_identifier, scoping_node, area_matcher, workflow_router |
| 5 | `data/prompts/csod/14_planner_narrator.md` | Create narrator system prompt |
| 6 | `csod_langgraph_adapter.py` | Add `NARRATOR_NODES` set and `NEXT_STEP_LABELS` dict |
| 7 | `base_langgraph_adapter.py` | Add `_stream_narrator()` async generator method |
| 8 | `base_langgraph_adapter.py` | In `stream()`, intercept `on_chain_end` for narrator nodes and `async for` the narrator before yielding normal event |
| 9 | `csod_planner_workflow.py` | Add `csod_reasoning_narrative: []` to `create_csod_planner_initial_state()` |
| 10 | `automated_agent_conversation.py` | Collect and log `reasoning_token` and `reasoning_done` events |