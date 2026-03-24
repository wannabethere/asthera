# CSOD Pipeline Split: Phase 1 (Analysis) → SQL Agent → Phase 2 (Output)

## Overview

Split the monolithic CSOD graph into two independent graphs with a SQL agent bridge:

```
PHASE 1 GRAPH: Intent → Metrics Selection + Preview (stops, returns state)
   ↕ SQL Agent (preview metrics, adhoc queries, RCA queries)
PHASE 2 GRAPH: Output Selection → Assembly → Narration (separate invocation)
```

The user flow becomes:
1. Ask question → Phase 1 runs → metrics recommended → user selects metrics
2. SQL agent previews selected metrics (dummy for now) → user sees previews
3. UI asks "What would you like to do?" (dashboard, report, alerts, etc.)
4. User picks → Phase 2 runs → output assembled → completion narration

For **adhoc analysis** and **RCA analysis** intents:
- Phase 1 runs through CCE (causal graph) but skips recommender
- SQL agent generates NL queries from causal graph context
- SQL agent executes (placeholder returns dummy data/visuals/insights)
- Phase 1 ends with results + metric selection

---

## Changes

### 1. Split `csod_main_graph.py` into two graph builders

**File: `app/agents/csod/workflows/csod_main_graph.py`**

**`build_csod_phase1_workflow()`** — Stages 1-4, ends at metric selection + SQL preview:
```
Entry → followup_router → intent_classifier → skill_intent → skill_planner → csod_planner
      → causal_graph → cross_concept → metrics_retrieval → mdl_schema_retrieval
      → metric_qualification → [layout_resolver] → skill_recommender_prep
      → metrics_recommender → skill_validator → metric_selection
      → sql_agent_preview → END   ← NEW: preview selected metrics
```

For **adhoc/RCA intents**, route after CCE:
```
      → causal_graph → cross_concept → [skip metrics_retrieval if adhoc/rca]
      → sql_agent_adhoc → metric_selection → sql_agent_preview → END
```

**`build_csod_phase2_workflow()`** — Stages 5, starts from output selection:
```
Entry → goal_intent → output_format_selector
      → [insights → calculation → medallion → gold_sql → cubejs → scheduler]
      → output_assembler → completion_narration → END
```

Keep **`build_csod_workflow()`** unchanged (full monolith for backward compat).

Add:
- `create_csod_phase1_app()` / `get_csod_phase1_app()`
- `create_csod_phase2_app()` / `get_csod_phase2_app()`

### 2. Create SQL Agent Placeholder Node

**New file: `app/agents/csod/csod_nodes/node_sql_agent.py`**

Two node functions:

**`csod_sql_agent_preview_node(state)`** — Preview selected metrics:
- Reads: `csod_metric_recommendations`, `csod_selected_metric_ids`, `csod_resolved_schemas`
- For each selected metric, generates a placeholder response:
  - `preview_data`: 5 dummy rows (period, value, delta)
  - `preview_visual`: chart type hint (line, bar, gauge)
  - `preview_summary`: LLM-generated 2-sentence summary of what this metric shows
  - `preview_insights`: LLM-generated 2-3 bullet insights
- Writes: `csod_metric_previews` (list of preview objects per metric)

**`csod_sql_agent_adhoc_node(state)`** — Adhoc/RCA SQL generation:
- Reads: `user_query`, `csod_causal_nodes`, `csod_causal_edges`, `csod_resolved_schemas`
- For adhoc: generates NL→SQL query from user question + schema context
- For RCA: uses causal graph to generate multiple NL queries (one per causal path)
- Calls placeholder SQL agent (returns dummy results)
- Writes: `csod_sql_agent_results` (list of {query, nl_question, result_data, visual, summary, insights})
- Also writes: `csod_metric_recommendations` (synthetic metric-like objects from SQL results, so metric_selection can present them)

Both nodes call a shared `_call_sql_agent_placeholder()` that returns LLM-generated dummy data.

### 3. Update Routing for Adhoc/RCA

**File: `app/agents/csod/workflows/csod_main_routing.py`**

Add `route_after_cross_concept_check()`:
```python
def route_after_cross_concept_check(state):
    intent = state.get("csod_intent", "")
    # Adhoc and RCA skip metrics retrieval — go straight to SQL agent
    if intent in ("adhoc_analysis", "alert_rca"):
        return "csod_sql_agent_adhoc"
    return "csod_metrics_retrieval"
```

Add `route_after_metric_selection()`:
```python
def route_after_metric_selection(state):
    # After user selects metrics, preview them via SQL agent
    return "csod_sql_agent_preview"
```

### 4. Update Phase 1 Graph Edges

In `build_csod_phase1_workflow()`:

```python
# After cross_concept_check: conditional → metrics_retrieval OR sql_agent_adhoc
workflow.add_conditional_edges(
    "csod_cross_concept_check",
    R.route_after_cross_concept_check,
    {
        "csod_metrics_retrieval": "csod_metrics_retrieval",
        "csod_sql_agent_adhoc": "csod_sql_agent_adhoc",
    },
)

# Adhoc SQL agent → metric_selection (presents SQL results as selectable metrics)
workflow.add_edge("csod_sql_agent_adhoc", "csod_metric_selection")

# After metric selection → SQL preview → END
workflow.add_edge("csod_metric_selection", "csod_sql_agent_preview")
workflow.add_edge("csod_sql_agent_preview", END)
```

### 5. Phase 2 Graph

**`build_csod_phase2_workflow()`**:
- Entry point: `csod_goal_intent` (output format selection)
- Receives full state from Phase 1 (metrics, selections, previews)
- Runs: goal_intent → format_selector → execution agents → output_assembler → narration → END

### 6. Export New Apps

**File: `app/agents/csod/csod_workflow.py`**

```python
from app.agents.csod.workflows.csod_main_graph import (
    create_csod_app,
    get_csod_app,
    create_csod_phase1_app,
    get_csod_phase1_app,
    create_csod_phase2_app,
    get_csod_phase2_app,
)
```

### 7. Update chat.html — Metric Selection + Output Format UI

**File: `/Users/sameerm/ComplianceSpark/byziplatform/unstructured/asthera/chat.html`**

The `displayCheckpointUI()` function needs to handle two new checkpoint types:

**`metric_selection`** checkpoint:
- Renders as a card grid with checkboxes
- Each card shows: metric name, description, preview chart (from `csod_metric_previews`), summary
- "Select All" / "Deselect All" toggles
- "Continue" button sends selected metric IDs back

**`goal_intent`** checkpoint (already exists but should be rendered AFTER metric previews):
- Radio card selection (Dashboard, Report, Ad hoc, Alerts, etc.)
- Should show a preview of what each option produces
- "Continue" button sends goal_intent back and triggers Phase 2

### 8. Register New Nodes

**File: `app/agents/csod/csod_nodes/__init__.py`**

Add exports:
```python
from .node_sql_agent import csod_sql_agent_preview_node, csod_sql_agent_adhoc_node
```

---

## File Changes Summary

| File | Action |
|------|--------|
| `csod_nodes/node_sql_agent.py` | **NEW** — SQL agent placeholder (preview + adhoc/RCA) |
| `workflows/csod_main_graph.py` | **EDIT** — Add phase1/phase2 builders + new nodes/edges |
| `workflows/csod_main_routing.py` | **EDIT** — Add adhoc/RCA routing + metric_selection routing |
| `csod_nodes/__init__.py` | **EDIT** — Export new node functions |
| `csod_workflow.py` | **EDIT** — Export phase1/phase2 app builders |
| `asthera/chat.html` | **EDIT** — Metric selection UI + output format UI rendering |

---

## Backward Compatibility

- `get_csod_app()` and `create_csod_app()` **unchanged** — full monolith still works
- `build_csod_workflow()` **unchanged** — existing edges preserved
- Phase 1/Phase 2 are **new additions**, not replacements
- Direct invocation via `agent_invocation_service.py` can use either full or split apps
- SQL agent placeholder returns dummy data — no external dependency needed
