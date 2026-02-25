# Dashboard Generation Flow — Design Document
# Detection & Triage Engineering Workflow Extension
# Version: 1.0

---

## 1. Executive Summary

This document defines a new **Dashboard Generation** sub-workflow that plugs into the existing Detection & Triage (DT) pipeline. The flow discovers relevant MDL tables for a user's question, asks for clarification, generates a list of natural language questions (later translated to SQL), and produces a dashboard specification object the user can curate before execution.

The key architectural principle: **we do not generate SQL, charts, or actual metrics here.** This step produces a *dashboard blueprint* — a curated list of natural-language questions with table anchors, component types, and reasoning — that feeds into the existing dashboard orchestrator pipeline at execution time.

---

## 2. Flow Overview

```
User Query (intent: dashboard_generation)
    │
    ▼
┌─────────────────────────────────┐
│  07_dashboard_context_discoverer │  ◄── New Node
│  (MDL table + dashboard KB scan) │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  08_dashboard_clarifier          │  ◄── New Node (human-in-the-loop)
│  (ask user for scope/priorities) │
└───────────────┬─────────────────┘
                │  user responds with selections
                ▼
┌─────────────────────────────────┐
│  09_dashboard_question_generator │  ◄── New Node
│  (NL questions + table anchors)  │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  10_dashboard_question_validator │  ◄── New Node
│  (traceability + completeness)   │
└───────────────┬─────────────────┘
                │
                ▼
        Dashboard Blueprint JSON
        (returned to user for selection)
                │
                ▼  user selects/edits questions
┌─────────────────────────────────┐
│  11_dashboard_assembler          │  ◄── New Node
│  (final dashboard object)        │
└───────────────┬─────────────────┘
                │
                ▼
            END / dt_playbook_assembler
```

---

## 3. New Qdrant Collection: `mdl_dashboards`

### 3.1 Purpose

Stores individual dashboard component patterns as **standalone documents** that serve as **few-shot examples** for the question generator. Each document represents ONE component from a previously built dashboard — a single question/KPI/metric/table/insight — with its parent dashboard's description and purpose carried as metadata context.

Key design decisions:

- **One document = one component.** A dashboard with 6 components produces 6 documents. This enables semantic search at the component level — when a user asks about "overdue training compliance," we retrieve the 5 most similar *individual components* across all dashboards, not entire dashboards.
- **Scoped to a single `project_id` / `source_id`.** Each component document belongs to exactly one project. A Cornerstone training component and a Qualys vulnerability component are separate documents with different `project_id` values.
- **Cross-project retrieval for few-shot.** When generating a new dashboard for a *different* data source or topic, we search across ALL project_ids to find structurally similar component patterns. A "drop-off rate" KPI from a training dashboard is a valid few-shot example for a "remediation drop-off rate" KPI on a vulnerability dashboard. The retrieval does NOT filter by `project_id` — it matches by semantic similarity of the question + reasoning, then the generator adapts the pattern to the user's actual tables.

### 3.2 Document Schema (one per component)

```json
{
  "id": "uuid",
  "project_id": "cornerstone",
  "source_id": "cornerstone",
  "dashboard_id": "uuid-of-parent-dashboard",
  "dashboard_name": "Training Compliance Overview",
  "dashboard_description": "Tracks training completion, drop-off, and overdue rates across the organization for compliance officers and L&D leadership.",
  "dashboard_type": "Dynamic",
  "component_sequence": 1,
  "question": "Which training has the highest drop-off rate (registered/approved but never completed)?",
  "component_type": "kpi",
  "data_tables": ["csod_training_records"],
  "reasoning": "Drop-off rate is a single aggregated value representing engagement failure. Best shown as a KPI card so executives see the worst performer at a glance.",
  "sql_query": "SELECT training_title, (COUNT(CASE WHEN completed_date IS NULL THEN 1 END) * 100.0 / COUNT(*)) AS drop_off_rate FROM csod_training_records WHERE lower(transcript_status) IN ('registered','approved') GROUP BY training_title ORDER BY drop_off_rate DESC LIMIT 1",
  "filters_available": ["training_title", "transcript_status", "due_date"],
  "chart_hint": "kpi_card",
  "columns_used": ["training_title", "transcript_status", "completed_date"],
  "tags": ["training", "compliance", "drop-off", "engagement", "lms"],
  "metadata": {
    "parent_component_count": 6,
    "created_at": "2025-10-21T14:51:50Z",
    "audience": "executive",
    "data_domain": "training_compliance"
  }
}
```

Field-by-field rationale:

| Field | Why it exists |
|-------|---------------|
| `dashboard_id`, `dashboard_name`, `dashboard_description` | Parent context. The generator needs to understand what dashboard this component came from to gauge its intent and audience. Multiple documents share the same `dashboard_id`. |
| `component_sequence` | Position in the parent dashboard. Helps the generator understand narrative ordering (KPIs first, tables later). |
| `question` | The natural language question. This is the **primary semantic search field** — it gets embedded for vector similarity. |
| `component_type` | kpi / metric / table / insight. Used as a filter during retrieval ("show me only KPI examples"). |
| `data_tables` | Which tables the component reads from. Stored as payload metadata, NOT used for filtering — the user's new dashboard will have different tables. |
| `reasoning` | Why this component type was chosen and what business value it provides. Concatenated with `question` for embedding to capture intent, not just topic. |
| `sql_query` | The actual SQL that was executed. Stored for reference but **not used by the generator** (generator produces NL questions only). Useful for the downstream orchestrator pipeline as SQL pattern examples. |
| `filters_available` | Interactive filter columns. Gives the generator ideas for filter suggestions on similar components. |
| `chart_hint` | Visualization type (kpi_card, bar_chart, line_chart, pie_chart, data_table, text_insight). Helps the generator suggest appropriate component types. |
| `columns_used` | Which columns from `data_tables` were actually needed. Helps the generator understand data shape without needing the full schema. |
| `tags` | Free-form topic tags for keyword filtering alongside vector search. |
| `metadata.data_domain` | Domain category (training_compliance, vulnerability_management, etc.). Enables hybrid search: vector similarity + domain filter. |
| `metadata.audience` | executive / operational / mixed. Enables audience-aware retrieval. |

### 3.3 Embedding Strategy

**Embedded text** = `question` + " | " + `reasoning` + " | " + `dashboard_description`

This concatenation ensures the vector captures three dimensions:
1. **What** is being asked (question)
2. **Why** it matters (reasoning)
3. **In what context** it was used (dashboard purpose)

Example embedding input:
```
Which training has the highest drop-off rate (registered/approved but never completed)? | 
Drop-off rate is a single aggregated value representing engagement failure. Best shown 
as a KPI card so executives see the worst performer at a glance. | 
Tracks training completion, drop-off, and overdue rates across the organization for 
compliance officers and L&D leadership.
```

**Payload metadata** (stored but not embedded):
- `project_id`, `source_id`, `dashboard_id` — for grouping
- `component_type` — for post-retrieval filtering
- `data_domain` — for hybrid search
- `tags` — for keyword boosting
- `chart_hint`, `filters_available`, `columns_used` — for generation context

### 3.4 Retrieval Pattern

When the `dt_dashboard_context_discoverer` searches this collection:

```python
# Pseudo-code for retrieval
results = qdrant_client.search(
    collection_name="mdl_dashboards",
    query_vector=embed(user_query),
    limit=10,
    # NO project_id filter — cross-project few-shot
    query_filter=None,  
)

# Optional: post-filter by component_type if user asked for specific types
# Optional: boost results from same data_domain via re-ranking
```

The key insight: we do **not** filter by `project_id` during retrieval. A training compliance KPI from project "cornerstone" is a perfectly valid few-shot example for generating a training compliance KPI for project "sumtotal" or even a structurally similar KPI for a completely different domain. The generator's job is to adapt the *pattern* to the user's actual available tables.

### 3.5 Ingestion Pipeline

**Source**: Existing dashboard API responses (like the uploaded JSON sample) are parsed into component-level documents by an ETL script.

**Parsing logic**:
```
For each dashboard_response:
    Extract dashboard-level fields (name, description, type, project_id)
    For each component in dashboard_response.content.components:
        Create one mdl_dashboards document:
            - Copy dashboard-level fields as parent context
            - Extract question, sql_query, chart_schema, reasoning
            - Infer component_type from chart_schema (kpi_metadata → kpi, bar → metric, etc.)
            - Extract data_tables from SQL (parse FROM/JOIN clauses)
            - Extract columns_used from SQL (parse SELECT clause)
            - Extract filters_available from chart_schema.encoding or sample_data.columns
            - Generate tags from question + dashboard_name (keyword extraction)
            - Infer data_domain from tags + table names
        Embed and upsert into Qdrant
```

**Update strategy**: When a dashboard is updated or regenerated, delete all documents with that `dashboard_id` and re-ingest. This keeps components in sync with the latest dashboard version.

### 3.6 Collection Sizing

| Metric | Estimate |
|--------|----------|
| Documents per dashboard | 2–10 (avg 5) |
| Dashboards per project | 5–50 |
| Projects per tenant | 1–10 |
| Total documents per tenant | 50–5,000 |
| Embedding dimension | 1536 (OpenAI ada-002) or 3072 (text-embedding-3-large) |
| Storage per document | ~6KB payload + embedding |

---

## 4. Node Definitions

### 4.1 `dt_dashboard_context_discoverer` (Node 07)

**Purpose**: Discover all relevant MDL tables and existing dashboard patterns for the user's query.

**Inputs**:
- `user_query` (from state)
- `data_enrichment.suggested_focus_areas` (from classifier)
- `active_project_id` (from state)
- `dt_resolved_schemas` (if MDL retrieval already ran upstream)

**Process**:
1. Use `ContextualDataRetrievalAgent.run()` to discover MDL tables relevant to the query (reuse existing infra)
2. Query `mdl_dashboards` collection filtered by `project_id` for similar dashboard component patterns
3. Merge results into a unified context: available tables with column metadata + reference dashboard patterns
4. Produce a `dt_dashboard_context` object with:
   - `available_tables`: list of `{table_name, columns, description, relevance_score}`
   - `reference_patterns`: list of matched dashboard components from `mdl_dashboards`
   - `suggested_domains`: inferred data domains (e.g., "training", "vulnerabilities", "access")
   - `ambiguities`: areas where user intent is unclear (used by clarifier)

**Outputs** (to state):
- `dt_dashboard_context`
- `dt_dashboard_available_tables`
- `dt_dashboard_reference_patterns`

---

### 4.2 `dt_dashboard_clarifier` (Node 08)

**Purpose**: Human-in-the-loop node that asks the user to refine scope, prioritize domains, and confirm table relevance before question generation.

**Inputs**:
- `dt_dashboard_context` (from discoverer)
- `user_query`

**Process**:
1. LLM analyzes `dt_dashboard_context.ambiguities` and the breadth of available tables
2. Generates 2–4 clarifying questions:
   - Which data domains to prioritize (if multiple detected)
   - Audience for the dashboard (executive vs. operational)
   - Time range preference (point-in-time vs. trend)
   - Any specific KPIs they must include
3. Returns a structured clarification request to the user

**Outputs** (to state):
- `dt_dashboard_clarification_request` (sent to user)
- After user response: `dt_dashboard_clarification_response`

**LangGraph Pattern**: Uses `interrupt_before` to pause the graph and wait for user input. The user's response is injected via `state["dt_dashboard_clarification_response"]` on resume.

---

### 4.3 `dt_dashboard_question_generator` (Node 09)

**Purpose**: Core generation node. Produces a list of natural language questions, each anchored to specific data tables, typed as KPI/Metric/Table/Insight, with reasoning.

**Inputs**:
- `dt_dashboard_context` (tables + patterns)
- `dt_dashboard_clarification_response` (user's scoping answers)
- `user_query`
- `active_project_id`

**Process**:
1. Build LLM prompt with:
   - Available tables and their column metadata
   - Reference dashboard patterns (few-shot)
   - User's clarification responses (priorities, audience, time range)
   - Original query
2. LLM generates 8–15 candidate questions, each as:
   ```json
   {
     "question_id": "q_001",
     "natural_language_question": "What is the overall training completion rate across all programs?",
     "data_tables": ["csod_training_records"],
     "component_type": "kpi",
     "reasoning": "Provides a single headline metric for executive view. Uses completed_date IS NOT NULL / total count.",
     "suggested_filters": ["training_title", "department"],
     "suggested_time_range": "last_90_days",
     "priority": "high",
     "audience": "executive"
   }
   ```
3. Component type taxonomy:
   - `kpi` — Single aggregated value (count, rate, score). Rendered as a card/gauge.
   - `metric` — Comparative or dimensional breakdown (by user, by category, by time). Rendered as bar/pie/line chart.
   - `table` — Detailed tabular data (drill-down, raw records). Rendered as a data table.
   - `insight` — Analytical narrative generated from data (anomaly callout, trend summary). Rendered as text + supporting data.

**Outputs** (to state):
- `dt_dashboard_candidate_questions` — the full candidate list

---

### 4.4 `dt_dashboard_question_validator` (Node 10)

**Purpose**: Quality gate ensuring every candidate question is traceable to real tables, has a valid component type, and the set provides adequate coverage.

**Validation Rules**:

| Rule ID | Category | Check |
|---------|----------|-------|
| DQ-T1 | Traceability | Every `data_tables` entry exists in `dt_dashboard_available_tables` |
| DQ-T2 | Traceability | Every question references at least one table |
| DQ-C1 | Completeness | At least 8 questions generated |
| DQ-C2 | Completeness | At least 1 KPI, 1 metric, and 1 table component present |
| DQ-C3 | Completeness | All user-specified priority domains have ≥ 2 questions |
| DQ-W1 | Quality | No duplicate questions (semantic similarity < 0.85) |
| DQ-W2 | Quality | `component_type` is consistent with question phrasing |
| DQ-W3 | Quality | Reasoning field is non-empty and ≥ 20 characters |
| DQ-W4 | Quality | `insight` type questions reference ≥ 2 tables for cross-analysis |

**Outputs** (to state):
- `dt_dashboard_validation_status` — `pass | fail | pass_with_warnings`
- `dt_dashboard_validated_questions` — the cleaned list (duplicates removed, types corrected)
- `dt_dashboard_validation_report`

**Routing**: If CRITICAL failures (DQ-T1, DQ-T2, DQ-C1), route back to question generator with refinement instructions (max 2 iterations).

---

### 4.5 `dt_dashboard_assembler` (Node 11)

**Purpose**: Receives user's selected questions and assembles the final dashboard object.

**Inputs**:
- `dt_dashboard_validated_questions` — the full candidate list presented to user
- `dt_dashboard_user_selections` — list of `question_id`s the user selected (injected via human-in-the-loop)
- `active_project_id`

**Process**:
1. Filter validated questions to only those selected by the user
2. Assign sequence numbers
3. Build the dashboard specification object

**Output Schema** (final deliverable):

```json
{
  "dashboard_id": "uuid",
  "project_id": "cornerstone",
  "dashboard_name": "auto-generated or user-provided",
  "created_at": "ISO timestamp",
  "components": [
    {
      "sequence": 1,
      "natural_language_question": "What is the overall training completion rate?",
      "data_tables": ["csod_training_records"],
      "component_type": "kpi",
      "reasoning": "Headline metric for executive dashboard",
      "suggested_filters": ["training_title", "department"],
      "suggested_time_range": "last_90_days"
    },
    {
      "sequence": 2,
      "natural_language_question": "Which users have the most overdue trainings?",
      "data_tables": ["csod_training_records"],
      "component_type": "metric",
      "reasoning": "Identifies compliance risk at individual level",
      "suggested_filters": ["full_name", "curriculum_title"],
      "suggested_time_range": null
    }
  ],
  "total_components": 2,
  "metadata": {
    "source_query": "original user query",
    "generated_at": "ISO timestamp",
    "workflow_id": "uuid"
  }
}
```

This object is then passed to the existing `dashboard_orchestrator_pipeline` for SQL translation and rendering.

---

## 5. Updated Graph Topology

```
dt_intent_classifier
  → dt_planner
    → dt_framework_retrieval
      → dt_metrics_retrieval (conditional)
        → dt_mdl_schema_retrieval (conditional)
          → calculation_needs_assessment
            → calculation_planner (conditional)
              → dt_scoring_validator
                │
                ├── [Template A/B/C] existing detection/triage path
                │
                └── [dashboard_generation intent] NEW PATH
                      → dt_dashboard_context_discoverer
                        → dt_dashboard_clarifier (interrupt)
                          → dt_dashboard_question_generator
                            → dt_dashboard_question_validator
                              → dt_dashboard_assembler (interrupt for selection)
                                → END
```

The dashboard path **branches at the scoring validator** via a new conditional edge when `intent == "dashboard_generation"`. It reuses all upstream retrieval (framework, metrics, MDL schemas) for context but diverges into the dashboard-specific sub-workflow.

---

## 6. State Schema Changes

### 6.1 New Fields for `DetectionTriageState`

```python
# ──────────────── Dashboard generation ────────────────
dt_dashboard_context: Optional[Dict[str, Any]]
dt_dashboard_available_tables: List[Dict[str, Any]]
dt_dashboard_reference_patterns: List[Dict[str, Any]]
dt_dashboard_clarification_request: Optional[Dict[str, Any]]
dt_dashboard_clarification_response: Optional[Dict[str, Any]]
dt_dashboard_candidate_questions: List[Dict[str, Any]]
dt_dashboard_validated_questions: List[Dict[str, Any]]
dt_dashboard_validation_status: Optional[str]   # "pass" | "fail" | "pass_with_warnings"
dt_dashboard_validation_report: Optional[Dict[str, Any]]
dt_dashboard_user_selections: List[str]          # selected question_ids
dt_dashboard_assembled: Optional[Dict[str, Any]] # final dashboard object
dt_dashboard_validation_iteration: int           # 0-indexed, max 2
```

### 6.2 Initial State Factory Update

Add to `create_dt_initial_state()`:

```python
# Dashboard generation fields
"dt_dashboard_context": None,
"dt_dashboard_available_tables": [],
"dt_dashboard_reference_patterns": [],
"dt_dashboard_clarification_request": None,
"dt_dashboard_clarification_response": None,
"dt_dashboard_candidate_questions": [],
"dt_dashboard_validated_questions": [],
"dt_dashboard_validation_status": None,
"dt_dashboard_validation_report": None,
"dt_dashboard_user_selections": [],
"dt_dashboard_assembled": None,
"dt_dashboard_validation_iteration": 0,
```

---

## 7. Workflow Code Changes

### 7.1 `dt_workflow.py` — New Routing Function

```python
def _route_after_scoring(state: EnhancedCompliancePipelineState) -> str:
    """Extended to include dashboard generation branch."""
    intent = state.get("classified_intent", "")
    
    # NEW: Dashboard generation bypasses detection/triage engineers
    if intent == "dashboard_generation":
        return "dt_dashboard_context_discoverer"
    
    # Existing logic unchanged...
    expected = state.get("dt_expected_outputs", {})
    template = state.get("dt_playbook_template", "A")
    if template == "B" or (not expected.get("siem_rules", True) 
                           and expected.get("metric_recommendations", False)):
        return "dt_triage_engineer"
    else:
        return "dt_detection_engineer"
```

### 7.2 `dt_workflow.py` — New Node Registration

```python
from app.agents.dt_nodes import (
    # ... existing imports ...
    dt_dashboard_context_discoverer_node,
    dt_dashboard_clarifier_node,
    dt_dashboard_question_generator_node,
    dt_dashboard_question_validator_node,
    dt_dashboard_assembler_node,
)

# In build_detection_triage_workflow():
workflow.add_node("dt_dashboard_context_discoverer", 
    instrument_langgraph_node(dt_dashboard_context_discoverer_node, 
                              "dt_dashboard_context_discoverer", "detection_triage"))
workflow.add_node("dt_dashboard_clarifier",
    instrument_langgraph_node(dt_dashboard_clarifier_node,
                              "dt_dashboard_clarifier", "detection_triage"))
workflow.add_node("dt_dashboard_question_generator",
    instrument_langgraph_node(dt_dashboard_question_generator_node,
                              "dt_dashboard_question_generator", "detection_triage"))
workflow.add_node("dt_dashboard_question_validator",
    instrument_langgraph_node(dt_dashboard_question_validator_node,
                              "dt_dashboard_question_validator", "detection_triage"))
workflow.add_node("dt_dashboard_assembler",
    instrument_langgraph_node(dt_dashboard_assembler_node,
                              "dt_dashboard_assembler", "detection_triage"))
```

### 7.3 `dt_workflow.py` — New Conditional Edges

```python
# Update scoring validator edges to include dashboard path
workflow.add_conditional_edges(
    "dt_scoring_validator",
    _route_after_scoring,
    {
        "dt_detection_engineer": "dt_detection_engineer",
        "dt_triage_engineer": "dt_triage_engineer",
        "dt_dashboard_context_discoverer": "dt_dashboard_context_discoverer",  # NEW
    },
)

# Dashboard sub-workflow edges
workflow.add_edge("dt_dashboard_context_discoverer", "dt_dashboard_clarifier")

# Clarifier is an interrupt node — after user responds, route to generator
workflow.add_edge("dt_dashboard_clarifier", "dt_dashboard_question_generator")

workflow.add_edge("dt_dashboard_question_generator", "dt_dashboard_question_validator")

# Validator routes back to generator on CRITICAL failure, else to assembler
workflow.add_conditional_edges(
    "dt_dashboard_question_validator",
    _route_after_dashboard_validator,
    {
        "dt_dashboard_question_generator": "dt_dashboard_question_generator",
        "dt_dashboard_assembler": "dt_dashboard_assembler",
    },
)

# Assembler is an interrupt node (user selects questions), then END
workflow.add_edge("dt_dashboard_assembler", END)
```

### 7.4 New Routing Functions

```python
MAX_DASHBOARD_VALIDATION_ITERATIONS = 2

def _route_after_dashboard_validator(state: EnhancedCompliancePipelineState) -> str:
    """Route after dashboard question validation."""
    status = state.get("dt_dashboard_validation_status", "pass")
    iteration = state.get("dt_dashboard_validation_iteration", 0)
    
    if status == "fail" and iteration < MAX_DASHBOARD_VALIDATION_ITERATIONS:
        state["dt_dashboard_validation_iteration"] = iteration + 1
        return "dt_dashboard_question_generator"
    
    return "dt_dashboard_assembler"
```

---

## 8. Intent Classifier Changes

### 8.1 Enrichment Signal Updates for `dashboard_generation`

The `01_intent_classifier.md` prompt already lists `dashboard_generation` as an intent. The following enrichment signals should be set when this intent is classified:

```json
{
  "data_enrichment": {
    "needs_mdl": true,
    "needs_metrics": true,
    "suggested_focus_areas": ["<from query context>"],
    "metrics_intent": "current_state | trend | benchmark",
    "playbook_template_hint": "triage_focused"
  }
}
```

`needs_mdl` is always `true` for dashboard generation because we need table schemas. `needs_metrics` is always `true` because dashboards inherently involve metrics/KPIs.

### 8.2 New `playbook_template_hint` Value

Add `"dashboard"` as a valid value for `playbook_template_hint`:
- `detection_focused` → Template A
- `triage_focused` → Template B
- `full_chain` → Template C
- `dashboard` → Template D (NEW — routes to dashboard sub-workflow)

---

## 9. Tool Integration Changes

### 9.1 `dt_tool_integration.py` — New Tool Map Entry

```python
DT_TOOL_MAP["dt_dashboard_context_discoverer"] = [
    "framework_control_search",
]

DT_TOOL_MAP["dt_dashboard_question_generator"] = [
    "framework_control_search",
]
```

### 9.2 New Retrieval Function: `dt_retrieve_dashboard_patterns`

```python
def dt_retrieve_dashboard_patterns(
    query: str,
    data_domain: str = None,
    component_type: str = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Query mdl_dashboards collection for reference dashboard component patterns.
    
    Cross-project retrieval: does NOT filter by project_id. Patterns from any 
    project are valid few-shot examples for generating dashboards on new 
    data sources or topics.
    
    Args:
        query: Semantic search query (user's dashboard request)
        data_domain: Optional domain filter for post-retrieval re-ranking
        component_type: Optional filter (kpi/metric/table/insight) 
        limit: Max results
    
    Returns:
        List of component-level pattern dicts with parent dashboard context
    """
    # Implementation uses Qdrant semantic search against mdl_dashboards collection
    # NO project_id filter — cross-project few-shot
    # Optional post-filter by component_type or re-rank by data_domain
    ...
```

---

## 10. Planner Changes

### 10.1 `02_detection_triage_planner.md` Updates

Add a new agent to the Available Agents section:

```
**`dashboard_context_discoverer`**
- Discovers relevant MDL tables and existing dashboard patterns
- Use when: intent is dashboard_generation
- Sources: ContextualDataRetrievalAgent + mdl_dashboards collection

**`dashboard_question_generator`**
- Generates NL questions anchored to discovered tables
- Use when: dashboard context is available and user has provided clarification
- Requires: dt_dashboard_context, dt_dashboard_clarification_response
```

Add new step count guidelines:

```
| dashboard_generation | 2-3     | 1-2           | 1         | 3 (discover+clarify+generate) | 1 | 8-10 |
```

Add a new Template D for the playbook template selection:

```
**Phase 4: Template Selection (Updated)**
- `detection_focused` → Template A
- `triage_focused` → Template B
- `full_chain` → Template C  
- `dashboard` → Template D (NEW)

Template D sections:
1. Context Discovery
2. User Clarification
3. Question Generation
4. Question Validation
5. Dashboard Assembly
```

---

## 11. File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `dt_state.py` | MODIFY | Add 12 new dashboard state fields to `DetectionTriageState` |
| `dt_workflow.py` | MODIFY | Add 5 new nodes, new routing functions, new conditional edges |
| `dt_nodes.py` | MODIFY | Add 5 new node functions |
| `dt_tool_integration.py` | MODIFY | Add tool map entries + `dt_retrieve_dashboard_patterns()` |
| `01_intent_classifier.md` | MODIFY | Add `dashboard` to `playbook_template_hint` values |
| `02_detection_triage_planner.md` | MODIFY | Add dashboard agents + Template D |
| `07_dashboard_context_discoverer.md` | NEW | Prompt for context discovery node |
| `08_dashboard_clarifier.md` | NEW | Prompt for clarification node |
| `09_dashboard_question_generator.md` | NEW | Prompt for question generation node |
| `10_dashboard_question_validator.md` | NEW | Prompt for validation node |
| `contextual_data_retrieval_agent.py` | REUSE | No changes — consumed by context discoverer |
| `dt_mdl_utils.py` | REUSE | Column pruning reused for dashboard table discovery |

---

## 12. Human-in-the-Loop Pattern

Two interrupt points require user interaction:

### 12.1 Clarifier Interrupt (Node 08)

```python
# In dt_dashboard_clarifier_node:
from langgraph.types import interrupt

def dt_dashboard_clarifier_node(state):
    # Generate clarification questions
    clarification = generate_clarification(state)
    
    # Interrupt and wait for user response
    user_response = interrupt(clarification)
    
    return {
        "dt_dashboard_clarification_request": clarification,
        "dt_dashboard_clarification_response": user_response,
    }
```

### 12.2 Assembler Interrupt (Node 11)

```python
# In dt_dashboard_assembler_node:
def dt_dashboard_assembler_node(state):
    validated_questions = state.get("dt_dashboard_validated_questions", [])
    
    # Present validated questions to user for selection
    selection_prompt = {
        "action": "select_dashboard_questions",
        "candidates": validated_questions,
        "instructions": "Select questions to include in your dashboard"
    }
    
    user_selections = interrupt(selection_prompt)
    
    # Build final dashboard object from selections
    dashboard = assemble_dashboard(validated_questions, user_selections, state)
    
    return {"dt_dashboard_assembled": dashboard}
```

---

## 13. Sequence Diagram

```
User                 Classifier      Planner       Upstream         Scoring     Dashboard Nodes
 │                       │              │          Retrieval            │              │
 │── query ─────────────►│              │              │               │              │
 │                       │── plan ─────►│              │               │              │
 │                       │              │── retrieve ─►│               │              │
 │                       │              │              │── score ─────►│              │
 │                       │              │              │               │── discover ─►│
 │                       │              │              │               │              │
 │◄── clarification ─────┼──────────────┼──────────────┼───────────────┼──────────────│
 │── response ──────────►│              │              │               │              │
 │                       │              │              │               │── generate ─►│
 │                       │              │              │               │── validate ─►│
 │                       │              │              │               │              │
 │◄── candidates ────────┼──────────────┼──────────────┼───────────────┼──────────────│
 │── selections ────────►│              │              │               │              │
 │                       │              │              │               │── assemble ─►│
 │◄── dashboard obj ─────┼──────────────┼──────────────┼───────────────┼──────────────│
```
