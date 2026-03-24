# Lexy AI — Unified Pipeline Design

**Version:** 1.0.0  
**Status:** Working Draft  
**Scope:** End-to-end question-to-agent-handoff pipeline for all intent types  
**Related files:** `stage_1_intent_examples.json`, `lms_causal_nodes_seed.json`, `lms_causal_edges_v2.json`, `lms_focus_area_taxonomy.json`, `lms_metric_use_case_groups_v2.json`, `attribution_placeholder.py`, `lexy_causal_concept_mapping_design.md`

---

## 1. Core Principle

Every question — regardless of intent type — runs the same pipeline spine. The spine ends at a human-reviewed, agent-ready question list. External agents (SQL, insight, data) execute against that list. The pipeline never touches data directly.

The three intent families (metrics/dashboard, analysis, data ops) differ only in what the goal planner extracts and what the question generator produces. The structural stages are identical.

---

## 2. Intent Families

The top-level classifier routes every question into one of three families before the pipeline starts. Classification uses a prompt with few-shot examples drawn from `stage_1_intent_examples.json`.

| Family | Intents | What the user wants |
|---|---|---|
| **Metrics / Dashboard** | `dashboard_generation_for_persona`, `training_plan_dashboard`, `current_state_metric_lookup`, `metrics_dashboard_plan`, `metrics_recommender_with_gold_plan`, `metric_kpi_advisor`, `crown_jewel_analysis`, `data_discovery` | A ranked metric list, a dashboard layout, or a KPI recommendation — no causal attribution needed |
| **Analysis** | `gap_analysis`, `compliance_gap_close`, `cohort_analysis`, `predictive_risk_analysis`, `anomaly_detection`, `funnel_analysis`, `benchmark_analysis`, `skill_gap_analysis`, `training_roi_analysis`, `behavioral_analysis` | A diagnostic, predictive, or comparative answer that requires causal reasoning |
| **Data Ops** | `compliance_test_generator`, `data_lineage`, `data_quality_analysis`, `data_planner` | Schema discovery, lineage tracing, quality checks, or pipeline design — no metric ranking needed |

---

## 3. Pipeline Stages

### Stage 0 — Goal Intent Classifier

**What it does:** Classifies the user's question into an intent family and a specific intent. Identifies active domains (lms, security, hr, finance). Sets `advisory_mode` flag — True for metrics/dashboard family, False for analysis and data ops.

**Inputs:** Raw user question  
**Outputs:** `intent`, `intent_family`, `active_domains`, `advisory_mode`, `confidence`

**Prompt design:**
- System prompt: intent taxonomy with one-sentence description per intent
- Few-shot examples: 2 examples per intent from `stage_1_intent_examples.json`
- Output: structured JSON with `intent`, `family`, `confidence`, `domain_signals[]`

**Follow-up routing:** If `confidence < 0.70`, emit a clarification card to the user before proceeding. If `confidence >= 0.70`, proceed without interruption.

---

### Stage 1 — Analysis Goal Planner

**What it does:** Given the classified intent and user question, produces a structured analysis plan. Calls MDL retrieval as a side-call to ground concept names and focus areas against what actually exists in the schema. The plan output is the contract that feeds every subsequent stage.

**Inputs:** `intent`, `intent_family`, `user_question`, `active_domains`  
**Side-call:** MDL retrieval — fetches concept definitions and focus area mappings for the identified domains  
**Outputs:** `analysis_plan`

**`analysis_plan` schema:**
```json
{
  "goal_statement":    "Close the compliance training gap from 71% to 90% before SOC2 audit",
  "terminal_metric":   "compliance_rate",
  "goal_value":        0.90,
  "current_value":     0.71,
  "deadline_days":     30,
  "focus_areas":       ["training_compliance", "learner_operations"],
  "intent":            "compliance_gap_close",
  "intent_family":     "analysis",
  "active_domains":    ["lms"],
  "mdl_concepts":      ["Compliance Training", "Learner Operations", "Deadline & SLA"],
  "excluded_concepts": [{"name": "ILT Scheduling", "reason": "web-based courses only"}],
  "requires_attribution": true,
  "deadline_bounded":  true,
  "implicit_questions": [
    "Can 19 points be closed in 30 days?",
    "Is the gap caused by disengagement or assignment overload?"
  ]
}
```

**Prompt design:**
- System prompt: goal extraction instructions + plan schema definition
- Few-shot examples: one example per intent family showing a complete `analysis_plan`
- If `instructions` field is populated for the intent (from intent config), append to system prompt
- MDL side-call result injected into prompt as available concept vocabulary

**Metrics/dashboard family:** Goal planner runs in lightweight mode — no `terminal_metric` or `deadline_days` extraction. Output is `goal_statement`, `focus_areas`, `active_domains`, and `mdl_concepts` only.

**Data ops family:** Goal planner extracts `target_tables`, `lineage_direction` (upstream/downstream), `quality_checks[]`, or `pipeline_entities[]` depending on intent. No metric fields.

---

### Stage 2 — Metric Registry Lookup

**What it does:** Filters the metric registry against `analysis_plan.focus_areas`, `analysis_plan.intent`, and `active_domains`. Returns candidate metrics that are relevant to the stated goal.

**Inputs:** `analysis_plan`  
**Outputs:** `resolved_metric_candidates[]`

Each candidate:
```json
{
  "metric_id":              "overdue_count",
  "display_name":           "Overdue Assignment Count",
  "node_type":              "mediator",
  "focus_areas":            ["training_compliance", "learner_operations"],
  "required_capabilities":  ["deadline.dimension", "lms.assignment_load"],
  "optional_capabilities":  [],
  "collider_warning":       false,
  "domain":                 "lms"
}
```

**Filtering rules:**
1. Include all metrics whose `focus_areas` intersect with `analysis_plan.focus_areas`
2. Include all metrics whose `node_type` is `terminal` for the identified `terminal_metric`
3. Exclude metrics whose `domains` do not overlap with `active_domains`
4. For data ops family: skip metric registry entirely — go directly to MDL schema lookup

---

### Stage 3 — Capability Resolver

**What it does:** For each candidate metric, resolves which connected data sources can provide its required capabilities. Flags conflicts when multiple sources satisfy the same capability.

**Inputs:** `resolved_metric_candidates[]`, `connected_sources[]`  
**Outputs:** `capability_coverage{}`, `adapter_conflicts[]`, `buildable_metrics[]`

**Conflict handling:** When `adapter_conflicts` is non-empty, emit a source selection card to the user before proceeding. User selects one source per conflicting capability. Pipeline resumes with `adapter_conflict_resolved = True`.

**Buildability gate:** Any metric with `coverage_score = 0.0` is removed from `buildable_metrics` and written to `excluded_metrics` with a machine-readable reason. This exclusion is surfaced in the human review at Stage 6.

---

### Stage 4 — Concept Graph Retrieval

**What it does:** Retrieves causal nodes and edges from the vector store (Qdrant `lexy_causal_nodes` / `lexy_causal_edges`) using the enriched query derived from the analysis plan and buildable metrics. Runs LLM graph assembly to select the relevant subgraph.

**Inputs:** `analysis_plan`, `buildable_metrics[]`, `active_domains[]`  
**Outputs:** `causal_proposed_nodes[]`, `causal_proposed_edges[]`, `causal_graph_metadata{}`

**Retrieval query enrichment:** Combines `goal_statement` + top `focus_areas` + `terminal_metric` name into a single semantic query. This ensures nodes relevant to the goal surface ahead of tangentially related nodes.

**LLM graph assembly:** Single LLM call per the design in `lexy_causal_concept_mapping_design.md` §5.4. Selects relevant subset of retrieved nodes and edges. Identifies: terminal nodes, root nodes, collider nodes, confounder nodes, hot paths. Produces a `diagnosis` string — 2–4 sentences describing the most likely causal mechanism for the question.

**Cross-domain framing:** If `active_domains` has more than one entry, LLM graph assembly emits `clarification_questions[]` per §7.6 of the design doc. User selects framing before the pipeline continues.

**Metrics/dashboard family:** Graph retrieval runs identically. The topology is used to classify metrics as leading/lagging and to surface collider warnings. LLM assembly runs in advisory mode — `diagnosis` and `collider_nodes` are still produced; hot paths and intervention ordering are skipped.

---

### Stage 5 — CCE + Lag Analysis

**What it does:** Reads the assembled graph and computes the lag structure — how many days does a change at each root node take to reach the terminal metric. Identifies which intervention paths are reachable within the deadline window. Flags colliders. Produces a suggested intervention ordering.

**Inputs:** `causal_proposed_nodes[]`, `causal_proposed_edges[]`, `analysis_plan.deadline_days`  
**Outputs:** `lag_structure{}`, `reachable_paths[]`, `blocked_paths[]`, `suggested_intervention_order[]`

**Operates on graph only — no data.** No SQL queries run at this stage. All lag estimates come from `lag_window_days` fields on edges in the seed data. Attribution (Shapley ϕ) is a stub at this stage per `attribution_placeholder.py` — returns empty `contributions[]` and `is_placeholder: True`. Real attribution runs post-approval in Phase 2/3.

**Lag structure per path:**
```json
{
  "path":            ["overdue_count", "missed_deadline_count", "compliance_rate"],
  "lag_total_days":  28,
  "reachable":       true,
  "path_confidence": 0.82
}
```

**Blocked path example:**
```json
{
  "path":           ["compliance_assigned_distribution", "overdue_count", "compliance_rate"],
  "lag_total_days":  42,
  "reachable":       false,
  "block_reason":   "Full chain takes 42 days — outside 30-day deadline window",
  "note":           "Root cause for documentation, not for intervention"
}
```

**Intervention ordering formula:** rank reachable paths by `path_confidence / lag_total_days`. Higher score = act first.

**Metrics/dashboard family:** CCE runs but skips deadline filtering and intervention ordering. Produces only `lag_structure` and `collider_flags`. Used by question generator to sequence data questions in causal order.

---

### Stage 6 — Question Generator

**What it does:** Converts the assembled graph, lag structure, and capability map into an ordered list of natural language questions — one per agent type. This list is the only output the external agents consume.

**Inputs:** `causal_node_index{}`, `capability_coverage{}`, `lag_structure{}`, `suggested_intervention_order[]`, `analysis_plan`, `advisory_mode`  
**Outputs:** `generated_questions[]`

**Question types:**

| Type | Agent | When generated | Example |
|---|---|---|---|
| Data retrieval | SQL | Always, for each buildable terminal and mediator | "What is the current compliance_rate for Engineering over the last 30 days?" |
| Trend retrieval | SQL | When `temporal_grain = weekly/daily` and trend needed | "How has overdue_count trended over the last 8 weeks for Engineering?" |
| Analysis | Insight | When graph has ≥ 3 nodes and `advisory_mode = False` | "Given compliance_rate is 71% and overdue_count spiked 34% — what is the most likely root cause reachable within 30 days?" |
| Metric recommendation | Insight | When `advisory_mode = True` | "Given the goal of tracking course completion rate across Cornerstone and Workday, which metrics should we prioritise and why?" |
| Attribution | Attribution (stub) | When `requires_attribution = True` | Placeholder — returns empty result today |
| Schema / lineage | Data | Data ops family | "What tables in the gold layer contain certification expiry events joined to employee data?" |

**Question ordering:** SQL data questions first (sorted by causal priority — terminals before mediators before roots). Insight analysis question last (needs SQL results as context). Attribution question after insight.

**Context bundle per question:**
```json
{
  "question":    "What is the current compliance_rate for Engineering?",
  "agent":       "sql",
  "priority":    1,
  "metric_id":   "compliance_rate",
  "node_type":   "terminal",
  "source_id":   "csod",
  "expression":  "csod_completion_log.status",
  "context":     {},
  "why":         "Terminal metric — current value needed to compute gap"
}
```

The insight agent question bundles the graph summary, collider warnings, deadline, and all SQL results (populated after SQL agents return) into its `context` field. The insight agent reasons from that bundle — it never queries data directly.

---

### Stage 7 — Human Review: Framing

**What it does:** Presents the assembled plan for human approval before any data execution begins. Shows: goal statement, terminal metric, causal graph summary, intervention ordering, collider warnings, excluded metrics with reasons, and the full question list.

**Inputs:** `analysis_plan`, `causal_graph_metadata`, `suggested_intervention_order`, `generated_questions[]`, `excluded_metrics[]`  
**Outputs:** `framing_approved: bool`, `user_framing_edits{}` (optional)

**Presented to user:**

```
Goal:           Close compliance_rate gap from 71% to 90% in 30 days
Terminal:       compliance_rate (Cornerstone)
Reachable path: overdue_count → missed_deadline → compliance_rate (28 days ✓)
Blocked path:   assignment_distribution → ... → compliance_rate (42 days ✗)
Collider:       completion_rate — tracked on dashboard, not used for diagnosis
Excluded:       ILT Scheduling — web-based courses, not applicable

Planned questions (6):
  1. [SQL]     Current compliance_rate for Engineering (30d)
  2. [SQL]     overdue_count trend — 8 weeks
  3. [SQL]     login_count_weekly_trend — 8 weeks
  4. [SQL]     compliance_assigned_distribution — last batch event
  5. [Insight] Root cause + reachable interventions given data above
  6. [Attrib]  Placeholder — ϕ estimates in Phase 2

Approve to continue, or edit the plan.
```

**Edit actions available:**
- Remove a question from the list
- Change the deadline window (re-runs lag filter)
- Override a blocked path (user accepts longer timeline)
- Change the terminal metric

If the user edits, the question generator re-runs from Stage 6 with the updated inputs. CCE and graph retrieval do not re-run unless the terminal metric changes.

**Metrics/dashboard family:** Review is lighter — presents the ranked metric list, source tags, leading/lagging classification, and collider notes. No intervention ordering shown. User approves or removes metrics.

---

### Stage 8 — Agent Handoff

**What it does:** Dispatches the approved question list to external agents. Collects results. Passes SQL results to the insight agent as context. Assembles final output.

**Inputs:** `generated_questions[]` (approved), `framing_approved: True`  
**Outputs:** Final user response — inline analysis, dashboard, or alert

**Execution order:**

1. SQL agent questions execute first — in parallel where questions are independent (different metrics, same source), sequentially where one result is needed as filter context for another
2. Data agent questions execute alongside SQL where applicable
3. Insight agent executes after all SQL results are available — its `context` bundle is populated with SQL results before dispatch
4. Attribution agent executes alongside insight agent — today returns stub, merged into output as empty ϕ bars

**Output assembler:** Merges all agent responses into the final output type (inline analysis, dashboard, alert) based on `intent_family` and `output_type` from the analysis plan. Maps agent responses to the dashboard layout JSON from `lexy_dashboard_layouts.json` where intent is `dashboard_generation_for_persona` or `training_plan_dashboard`.

---

## 4. State Contract

All stages read and write a shared `LexyPipelineState`. Key fields added by this design:

```python
class LexyPipelineState(TypedDict, total=False):

    # Stage 0
    intent:              str
    intent_family:       str          # "metrics_dashboard" | "analysis" | "data_ops"
    active_domains:      List[str]
    advisory_mode:       bool
    intent_confidence:   float

    # Stage 1
    analysis_plan:       Dict[str, Any]

    # Stage 2
    resolved_metric_candidates: List[Dict]
    excluded_metrics:    List[Dict]   # [{metric_id, reason, coverage_score}]

    # Stage 3
    capability_coverage: Dict[str, Any]
    adapter_conflicts:   List[Dict]
    buildable_metrics:   List[Dict]
    adapter_conflict_resolved: bool

    # Stage 4
    causal_proposed_nodes:  List[Dict]
    causal_proposed_edges:  List[Dict]
    causal_graph_metadata:  Dict[str, Any]
    causal_node_index:      Dict[str, Dict]
    pending_clarification_questions: List[Dict]   # cross-domain framing
    user_clarification_answers:      Dict[str, str]
    causal_graph_clarification_required: bool

    # Stage 5
    lag_structure:             Dict[str, Any]
    reachable_paths:           List[Dict]
    blocked_paths:             List[Dict]
    suggested_intervention_order: List[Dict]

    # Stage 6
    generated_questions:  List[Dict]

    # Stage 7
    framing_approved:     bool
    user_framing_edits:   Dict[str, Any]

    # Stage 8
    agent_results:        Dict[str, Any]   # agent_id → response
    attribution_result:   Dict[str, Any]   # stub today

    # Shared / compat
    user_query:           str
    connected_sources:    List[str]
    vertical:             str              # compat alias → primary active_domain
    messages:             List
    error:                Optional[str]
    current_phase:        str
```

---

## 5. LangGraph Node Map

```
goal_intent_classifier_node
  → analysis_goal_planner_node
      [side-call: mdl_retrieval]
  → metric_registry_lookup_node
  → capability_resolver_node
      [interrupt: adapter_conflict_clarification  if conflicts]
  → concept_graph_retrieval_node
      [interrupt: cross_domain_framing            if multi-domain]
  → cce_lag_analysis_node
  → question_generator_node
  → human_review_framing_node                     [interrupt: always]
      [re-entry: question_generator_node          if user edits]
  → agent_handoff_node
      → sql_agent_dispatcher
      → data_agent_dispatcher
      → insight_agent_dispatcher                  [waits for SQL results]
      → attribution_agent_dispatcher              [stub today]
  → output_assembler_node
```

**Interrupt points summary:**

| Interrupt | Trigger | User action | Resume at |
|---|---|---|---|
| Source conflict | `adapter_conflicts` non-empty | Select source per capability | `capability_resolver_node` |
| Cross-domain framing | Multi-domain graph, `clarification_questions` non-empty | Select primary terminal framing | `concept_graph_retrieval_node` (re-run with augmented query) |
| Human review | Always after `question_generator_node` | Approve or edit plan | `agent_handoff_node` or `question_generator_node` |

---

## 6. Prompt Templates

### 6.1 Goal Intent Classifier

```
System:
You are the goal intent classifier for Lexy AI, an enterprise analytics platform.
Classify the user's question into exactly one intent and one intent family.

Intent families:
  metrics_dashboard — user wants a metric list, dashboard, or KPI recommendation
  analysis          — user wants a diagnostic, predictive, or comparative answer
  data_ops          — user wants schema discovery, lineage, quality checks, or pipeline design

Intents (with family):
  [metrics_dashboard] dashboard_generation_for_persona, training_plan_dashboard,
    current_state_metric_lookup, metrics_dashboard_plan, metrics_recommender_with_gold_plan,
    metric_kpi_advisor, crown_jewel_analysis, data_discovery
  [analysis] gap_analysis, compliance_gap_close, cohort_analysis,
    predictive_risk_analysis, anomaly_detection, funnel_analysis, benchmark_analysis,
    skill_gap_analysis, training_roi_analysis, behavioral_analysis
  [data_ops] compliance_test_generator, data_lineage, data_quality_analysis, data_planner

Output JSON only:
{
  "intent":        "<intent_id>",
  "intent_family": "<family>",
  "confidence":    <0.0–1.0>,
  "domain_signals": ["lms", "security", ...]
}

Few-shot examples:
{examples}```

### 6.2 Analysis Goal Planner

```
System:
You are the analysis goal planner for Lexy AI.
Given a user question and its classified intent, extract a structured analysis plan.
Use the MDL concepts provided to ground your concept and focus area selections.

Instructions (if provided for this intent, append here):
{intent_instructions}

Available MDL concepts for domains {active_domains}:
{mdl_concepts}

Extract:
- goal_statement: one sentence describing what the user wants to achieve
- terminal_metric: the primary outcome metric (from MDL concepts if available)
- goal_value: numeric target if stated, else null
- current_value: numeric current value if stated, else null
- deadline_days: integer if deadline stated, else null
- focus_areas: list from the MDL focus area taxonomy
- mdl_concepts: relevant concept names from the provided vocabulary
- excluded_concepts: [{name, reason}] — concepts checked but ruled out
- requires_attribution: true if the question needs causal attribution
- deadline_bounded: true if a hard deadline is present
- implicit_questions: list of unstated questions the user probably wants answered

Output JSON only matching the analysis_plan schema.

Few-shot examples:
{examples}
```

### 6.3 Question Generator (per question type)

**Data question template:**
```
What is the {metric.display_name} for {scope} over the last {window}?
Source: {source_id} via {expression}.
```

**Trend question template:**
```
How has {metric.display_name} trended over the last {window} for {scope}?
{annotation_note if batch_event_detected}
Source: {source_id} via {expression}.
```

**Analysis question template:**
```
Given:
{for each sql_result: "- {metric_display_name}: {value} ({delta if available})"}

Graph context:
- Terminal: {terminal_metric}
- Reachable intervention paths: {reachable_paths summary}
- Blocked paths: {blocked_paths summary}
- Collider warning: {collider_notes if any}
- Deadline: {deadline_days} days

{goal_statement}

What is the most likely root cause? What interventions are reachable within the
deadline? What is a defensible posture if the target cannot be fully reached?
```

**Metric recommendation template (metrics/dashboard family):**
```
Goal: {goal_statement}
Available metrics (topology-ranked):
{for each buildable_metric: "- {display_name} | {node_type} | source: {source_id} | {leading_or_lagging}"}
Collider warnings: {collider_notes if any}

Which of these metrics should we prioritise for tracking this goal and why?
For each recommended metric, state: what it measures, why it predicts the goal,
and what it signals when it changes.
```

---

## 7. Agent Contracts

### 7.1 SQL Agent

Receives questions of type `sql`. Responsible for: parsing the NL question, generating correct SQL against the specified source and expression, executing the query, and returning a structured result.

**Input per question:**
```json
{
  "question":   "What is the current compliance_rate for Engineering (last 30d)?",
  "agent":      "sql",
  "source_id":  "csod",
  "expression": "csod_completion_log.status",
  "metric_id":  "compliance_rate",
  "context":    {}
}
```

**Output:**
```json
{
  "metric_id":    "compliance_rate",
  "value":        0.71,
  "formatted":    "71%",
  "delta":        -0.029,
  "delta_label":  "-2.9pp vs prior period",
  "scope":        "Engineering",
  "window":       "last 30 days",
  "source_id":    "csod",
  "freshness":    "2026-03-20T09:14:00Z",
  "query":        "<generated SQL>",
  "row_count":    847
}
```

### 7.2 Insight Agent

Receives questions of type `insight`. Responsible for: reasoning over the data and graph context bundle, producing a natural language narrative, and returning structured findings.

**Input per question:**
```json
{
  "question":  "<analysis question with all SQL results in context>",
  "agent":     "insight",
  "context": {
    "sql_results":        [{...}, {...}],
    "graph_summary":      "...",
    "collider_warning":   "completion_rate is a collider — not a valid filter",
    "reachable_paths":    [{...}],
    "blocked_paths":      [{...}],
    "deadline_days":      30,
    "intent":             "compliance_gap_close"
  }
}
```

**Output:**
```json
{
  "narrative":          "Root cause is assignment queue overload, not disengagement...",
  "root_cause":         "overdue_count (assignment batch event)",
  "reachable_actions":  ["Direct outreach to 247 overdue learners", "Manager activation for Engineering"],
  "blocked_actions":    ["Redistribute assignment batches (42d chain — outside window)"],
  "audit_posture":      "84% with corrective action documentation is defensible for SOC2",
  "follow_up_suggestions": ["Break down by department", "Who is at highest risk?"]
}
```

### 7.3 Data Agent

Receives questions of type `data`. Responsible for: schema inspection, lineage traversal, quality checks, or pipeline planning against MDL tables.

**Input per question:**
```json
{
  "question":  "What gold-layer tables contain certification expiry events?",
  "agent":     "data",
  "context": {
    "target_tables":       ["csod_certifications", "csod_cert_expiry"],
    "lineage_direction":   "upstream",
    "mdl_layer":           "gold"
  }
}
```

### 7.4 Attribution Agent (stub)

Receives questions of type `attribution`. Today returns the placeholder result from `attribution_placeholder.py`. Phase 2 replaces with LLM-based path contribution. Phase 3 replaces with Shapley on observed data.

**Output today:** `{is_placeholder: true, contributions: [], intervention_order: []}`  
**UI behaviour:** ϕ bars not shown. "Attribution analysis available in a future release" note displayed.

---

## 8. Human Review Payload

The review presented at Stage 7 is a structured object, not free text. The UI renders it as a review card. The user can approve, edit, or reject.

```json
{
  "type": "framing_review",
  "goal_statement": "Close compliance_rate gap from 71% to 90% in 30 days",
  "terminal_metric": {
    "id": "compliance_rate", "current": "71%", "target": "90%", "gap": "19pp"
  },
  "reachable_paths": [
    {"path": "overdue_count → missed_deadline → compliance_rate",
     "lag_days": 28, "confidence": 0.82}
  ],
  "blocked_paths": [
    {"path": "assignment_distribution → ... → compliance_rate",
     "lag_days": 42,
     "note": "Root cause — document for audit, not actionable in window"}
  ],
  "collider_warnings": [
    {"metric": "completion_rate",
     "note": "Safe for dashboard tracking. Do not use as diagnostic filter."}
  ],
  "excluded_metrics": [
    {"metric": "ilt_instructor_count",
     "reason": "Web-based SOC2 courses — ILT not applicable"}
  ],
  "questions": [
    {"priority": 1, "agent": "sql",     "question": "Current compliance_rate (Engineering, 30d)"},
    {"priority": 2, "agent": "sql",     "question": "overdue_count trend — 8 weeks"},
    {"priority": 3, "agent": "sql",     "question": "login_count_weekly_trend — 8 weeks"},
    {"priority": 4, "agent": "sql",     "question": "assignment batch event timing"},
    {"priority": 5, "agent": "insight", "question": "Root cause + reachable interventions"},
    {"priority": 6, "agent": "attribution", "question": "Contribution estimates (placeholder)"}
  ],
  "edit_actions": [
    "remove_question",
    "change_deadline",
    "override_blocked_path",
    "change_terminal_metric"
  ]
}
```

---

## 9. Invariants

These hold across all intent families and all stages:

1. **No data before approval.** SQL, data, and insight agents never execute until `framing_approved = True`. The pipeline never queries a source during Stages 0–7.

2. **Collider guard is always enforced.** Any metric with `collider_warning = True` is included in the question list only as a dashboard-tracking question (SQL, `node_type = collider`), never as a filter or as a terminal for analysis questions. The insight agent prompt always includes the collider warning note.

3. **Capability coverage gate.** Any metric with `coverage_score = 0.0` is excluded from `generated_questions`. It is listed in the review under `excluded_metrics` with the machine-readable reason. The user can override at Stage 7.

4. **CCE and graph retrieval are graph-only.** Neither stage reads from any connected data source. All lag estimates come from `lag_window_days` in the seed data. Attribution is a stub until Phase 2.

5. **One response shape per agent type.** Output assembler consumes agent results by type without branching on which method produced them. Stub results and real results are structurally identical.

6. **Attribution label is honest.** LLM-estimated contributions are labeled `estimated_contribution`, not `shapley_phi`, until Phase 3 Shapley-on-data is implemented.

---

## 10. What Is Not in Scope (This Version)

| Item | Deferred to |
|---|---|
| Real Shapley attribution (LLM path) | Phase 2 — replace `llm_attribution_and_ordering` stub |
| Real Shapley on observed time-series | Phase 3 — replace `shapley_on_observations` stub |
| Multi-turn follow-up routing (direct dispatch) | Follow-up handling module — reuses `causal_node_index` from parent turn |
| Finance / HR domain manifests | Domain manifest files — same pattern as LMS manifest |
| Scorer weight learning (nightly Bayesian update) | `lexy_scorer_weights` Postgres table + nightly batch job |
| CSV / file upload adapter registration | `lexy_registered_adapters` Postgres table + ingestion worker |