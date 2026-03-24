# Lexy — Conversational Flow Design
## Analysis Showcase: How Questions Become Answers

> **Reading guide:** This document explains how Lexy processes a user question from first word to final answer. It covers the architecture, the conversational flow patterns, all 8 analysis scenarios, and the narrative layer the user sees while analysis runs.

---

## Part 1 — Architecture Overview

### The three-layer model

Every analysis Lexy runs passes through three conceptually distinct layers. Understanding these layers is the key to understanding why the system behaves the way it does.

```
┌─────────────────────────────────────────────────────────────┐
│  PLANNER LAYER                                              │
│  Intent Classifier → Planner → DT Resolver                 │
│  Decides what to do. Never runs analysis itself.            │
├─────────────────────────────────────────────────────────────┤
│  EXECUTOR LAYER                                             │
│  SQL Agents │ ML/LLM Agents │ Dashboard Agents │ Layout     │
│  Runs the analysis. Registered in executor_registry.py.     │
├─────────────────────────────────────────────────────────────┤
│  NARRATIVE LAYER                                            │
│  Step Narrator → SSE Stream → Summary Narrator              │
│  Tells the user what is happening, step by step.            │
└─────────────────────────────────────────────────────────────┘
```

**Planners decide.** The intent classifier, planner node, and DT resolver read the user's question, understand its intent, qualify the relevant metrics, and compose an ordered execution plan that names specific executors to call. Planners never compute an answer themselves.

**Executors run.** Each executor is a self-contained agent registered in `executor_registry.py`. It declares what inputs it needs, what it produces, and what it tells the user when it starts and finishes. The planner selects 1–4 executors per request by matching the intent against each executor's `capabilities` list.

**Narrators explain.** At every executor boundary — before it starts and after it completes — the narrative layer emits a user-facing message via SSE. The user sees the analysis thinking out loud in real time.

---

### The shared retrieval spine

Before any executor runs, every metric-bearing analysis passes through a fixed retrieval pipeline. This spine is shared across all 13 analytical analysis types.

```
User question
     │
     ▼
[Turn > 1?] ──Yes──► Follow-up Router ──eligible──► Direct Executor Dispatch
     │                                    │
     │ No                          not eligible
     │                                    │
     ▼                                    ▼
Intent Classifier                  (falls through to spine)
     │
     ▼  intent + focus_areas + data_enrichment
Planner
     │
     ▼  execution_plan + narrative_preview + follow_up_eligible
MDL Schema Retrieval  ◄── short-circuit for data_discovery, data_quality
     │
     ▼  csod_resolved_schemas + csod_gold_standard_tables
Metrics Retrieval + DT Enrichment
     │
     ▼  resolved_metrics + dt_metric_groups (preliminary)
Scoring Validator
     │  (drops items below composite_score 0.50)
     ▼
DT Resolver  ◄── qualifies metrics per intent-specific constraints
     │
     ▼  dt_scored_metrics + dt_metric_decisions + dt_metric_groups
[Layout fork]
     ├── Dashboard intents → Dashboard Layout Resolver → csod_dt_layout
     └── Metric intents   → Metrics Layout Resolver   → csod_metrics_layout
     │
     ▼
[CCE fork — per csod_causal_mode]
     ├── required  → Causal Graph (blocks execution until complete)
     ├── optional  → Causal Graph (runs, fails gracefully)
     └── disabled  → skip
     │
     ▼  csod_causal_nodes + csod_causal_edges + csod_causal_centrality (if CCE ran)
     │  NOTE: NO csod_shapley_scores here — Shapley is computed inside each
     │  executor that needs it, against its specific goal variable, using
     │  csod_causal_edges as the coalition structure input.
Execution Agent(s)
     │
     ▼
Output Assembler
     │
     ▼
Summary Narrator
```

**Data intelligence short-circuit:** `data_discovery` and `data_quality_analysis` exit the spine after MDL Schema Retrieval. They skip metrics retrieval, scoring validator, DT resolver, and CCE entirely — they operate on schema metadata, not on scored metrics.

---

### The Decision Tree and CCE engines

Two engines enrich every analysis. Understanding their roles clarifies why the flow has the shape it does.

#### Decision Tree (DT) — metric qualification

The DT engine was previously embedded inside `csod_metrics_retrieval_node`. In the refactored architecture it runs as a standalone node (`csod_decision_tree_resolver_node`) after `scoring_validator`, for every metric-bearing intent.

Its job is to take the `scored_metrics` that passed the 0.50 threshold and run a second, intent-specific qualification pass:

| What it resolves | Why it matters |
|---|---|
| `use_case` — which analysis context | Filters metrics to only those valid for this analysis type |
| `goal` — which business goal | Groups metrics by goal-alignment into `dt_metric_groups` |
| `metric_type` — current_state / trend / forecast | `anomaly_detection` hard-drops all current_state metrics |
| `audience` — persona level | Shapes metric complexity for dashboard intents |
| `min_composite` — per-intent threshold | Crown jewel uses 0.60; benchmark uses 0.50 |
| Hard constraints | `requires_deadline_dimension`, `requires_target_value`, etc. |

The output — `dt_scored_metrics` — replaces `scored_metrics` as the primary input to all execution agents. **No executor should ever read raw `scored_metrics` directly.**

#### Causal Computation Engine (CCE) — two distinct roles

The CCE and Shapley distributions are separate concerns that operate at different points in the flow. Understanding this separation is essential.

**The causal graph node** runs in the spine before any execution agent. Its job is topology — it answers *which metrics relate, how, and in what direction*. It writes three things to shared state:
- `csod_causal_nodes` — the metric adjacency nodes
- `csod_causal_edges` — weighted directed edges (used by executors as structural input)
- `csod_causal_centrality` — `{metric_id: {in_degree, out_degree}}` derived from topology, not Shapley

**Shapley distributions** are computed *inside each executor* that needs attribution, at execution time, against that executor's specific goal variable. They are never precomputed at the spine level because the goal differs per executor — you cannot compute one generic Shapley distribution that serves gap analysis, risk prediction, and ROI decomposition simultaneously.

| Executor | What it reads from the graph | What it computes internally |
|---|---|---|
| `crown_jewel_ranker` | `csod_causal_centrality` (in/out degree) | No Shapley — centrality IS the structural measure |
| `gap_analyzer` | `csod_causal_edges` (coalition structure) | Shapley vs the specific gap metric's goal → `csod_gap_report.root_cause_shapley` |
| `risk_predictor` | `csod_causal_edges` (coalition structure) | Shapley vs compliance_posture goal → embedded in `csod_risk_scores[].shapley_contribution` |
| `roi_calculator` | `csod_causal_edges` (cost→outcome chains) | Shapley vs total ROI goal → `csod_roi_report.program_roi_breakdown[].shapley_roi_share_pct` |
| `anomaly_detector` | `csod_causal_edges` (upstream/downstream paths) | No Shapley — graph walk to distinguish pipeline vs business anomaly |
| `dashboard_generator` | `csod_causal_centrality` (leading/lagging) | No Shapley — topology-based component ordering only |
| `compliance_test_generator` | `csod_causal_edges` (control risk chains) | Optional Shapley internally → `test_case.severity_weight` |
| `skill_gap_assessor` | `csod_causal_edges` (skill unlock chains) | Optional Shapley internally → `csod_training_priority_list[].causal_weight` |

CCE has three modes, set per intent in the executor registry:

- **`required`** — execution agent needs `csod_causal_edges` to run properly. If CCE fails, the agent falls back and flags `cce_fallback: true`.
- **`optional`** — CCE enriches the output. If CCE fails, the agent proceeds without causal structure.
- **`disabled`** — no causal structure applicable. Benchmark comparison and all data intelligence skills.

---

### The executor registry

Every executor registers itself in `executor_registry.py`. The planner reads a summary of this registry at invocation time and selects executors by matching the intent against each executor's `capabilities` list.

```
EXECUTOR REGISTRY (20 executors)

SQL Agents          ML/LLM Agents         Dashboard Agents      Layout Agents
──────────────────  ────────────────────  ────────────────────  ──────────────────
anomaly_detector    crown_jewel_ranker    dashboard_generator   dashboard_layout
funnel_analyzer     gap_analyzer          metrics_recommender   metrics_layout
risk_predictor      cohort_comparator     medallion_planner     causal_graph (CCE)
behavioral_analyzer benchmark_comparator  data_science_enricher data_lineage_tracer
compliance_tester   skill_gap_assessor                          data_discovery
data_quality_insp.  roi_calculator                              data_pipeline_planner
```

Each registry entry declares:

```python
{
  "executor_id":     "gap_analyzer",
  "type":            "ml",
  "capabilities":    ["gap_analysis"],        # which intents this serves
  "required_inputs": ["dt_scored_metrics",    # must be in state before calling
                      "csod_resolved_schemas"],
  "output_fields":   ["csod_gap_report",      # what it writes to state
                      "csod_metric_deltas",
                      "csod_priority_gaps"],
  "dt_required":     True,                    # must run DT before calling this
  "cce_mode":        "required",              # CCE mode for this executor
  "can_be_direct":   True,                    # eligible for follow-up routing
  "narrative": {
    "start":  "I'm measuring the gap between where you are and where you need to be.",
    "end":    "{gap_count} gaps found. Largest: {top_gap_name} at {top_gap_pct}% below target.",
    "detail": "Decomposing root cause for {metric_name} using causal attribution."
  }
}
```

---

### The follow-up router

On every conversation turn after the first, the follow-up router runs before the spine. It checks whether:

1. `dt_scored_metrics` and `csod_resolved_schemas` are already in state
2. The new question can be answered by calling a single executor directly

If yes, it sets `csod_followup_executor_id` and the workflow forks directly to that executor, bypassing `intent_classifier → planner → mdl_schema_retrieval → metrics_retrieval → scoring_validator → dt_resolver`. This typically saves 4–6 spine steps.

```
Turn 1:  "Where are we falling short on compliance targets?"
         → Full spine (6 steps) → gap_analyzer → output

Turn 2:  "Break that down by department."
         → Follow-up router detects dt_scored_metrics in state
         → Routes directly to cohort_comparator
         → 4 steps skipped, ~70% latency reduction
```

Only executors with `can_be_direct: True` are reachable via follow-up routing. Executors with hard dependency chains (`medallion_planner`, `roi_calculator`) are excluded.

---

### The narrative layer

Four components work together to give the user real-time visibility into analysis progress.

```
Before executor runs:
  csod_step_narrator fills "start" template → appends to csod_narrative_stream
       ↓
  _emit_sse_event pushes to csod_sse_queue
       ↓
  FastAPI SSE endpoint streams to browser:
  { type: "step_start", agent: "Gap Analyzer",
    message: "I'm measuring the gap between where you are and where you need to be.",
    step: 4, total: 6 }

After executor completes:
  csod_step_narrator fills "end" template with actual values from state
  → "6 gaps found. Largest: Engineering at 32 points below target."

After output_assembler:
  csod_summary_narrator generates final summary using 14_planner_narrator.md
  → Streams as a "summary" SSE event
```

The planner also outputs a `narrative_preview` — a single sentence shown to the user before any executor runs, setting expectations: *"I'll qualify your metrics, map causal relationships, then identify where you're falling short of targets."*

---

## Part 2 — The Eight Scenarios

Each scenario below follows the same structure:
- **User question** — what the user literally types
- **What Lexy detects** — intent, confidence, constraints applied
- **Conversational flow** — the narrative the user sees, step by step
- **Final outcomes** — the natural language answers produced

---

### Scenario 1 — Gap Analysis `diagnostic`

**User question**
> *"Where are we falling short on our compliance training targets this quarter?"*

**What Lexy detects**
- Intent: `gap_analysis` (confidence 0.91)
- Focus areas: `compliance_training`, `ld_training`
- Metrics intent: `current_state` (DT will hard-drop trend metrics)
- DT constraint: `requires_target_value` — only metrics with a definable target survive
- CCE mode: `required` — Shapley needed for root cause decomposition
- Follow-up eligible: `true` — cohort, anomaly, risk executors available on turn 2

**Conversational flow the user sees**

```
◉ Intent Classifier
  Understood: you want to see where compliance training is missing targets.
  I've identified compliance training and learning operations as the focus areas.

◉ Planner
  I'll qualify your metrics, map causal relationships, then measure gaps against
  your 90% company target. 6 steps — starting now.

◉ Retrieving data
  Found 8 schemas and 22 candidate metrics across compliance and training domains.

◉ Decision Tree
  Qualifying metrics for gap analysis — keeping only point-in-time metrics
  with defined targets. Dropped 8 trend metrics. 14 metrics qualified across
  3 goal groups: training completion, compliance posture, HR alignment.

◉ Causal Graph (required)
  Mapping how your compliance metrics relate to each other.
  Causal graph complete: 14 metrics, 18 relationships.
  Top causal factors: assignment_volume → completion_rate,
  login_frequency → completion_rate, manager_engagement → compliance_posture.

◉ Gap Analyzer
  Measuring gaps against your 90% target.
  Running Shapley attribution internally against each gap metric to decompose root causes.
  6 gaps found. Largest: Engineering at 32 points below target.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| What is our current compliance training completion rate vs the 90% target? | **73.2%** — 16.8 points below target. Down from 76.1% last quarter. |
| Which department has the largest compliance gap? | **Engineering** at 58% completion — 32 points below target. `critical` |
| What is driving the shortfall in Engineering? | **61%** attributable to high assignment volume (8 courses assigned in Q4). 28% attributable to low login frequency. Manager engagement accounts for the remaining 11%. |
| Which learners are at immediate risk of non-compliance? | **47 employees** have less than 30% progress with due dates within 14 days. |
| If we fix the assignment volume issue, how much does the gap close? | Estimated **+14.2 points** — bringing Engineering from 58% to an estimated 72.2%. Still below target, but removes the critical flag. |

---

### Scenario 2 — Crown Jewel Analysis `diagnostic`

**User question**
> *"Which training metrics should we actually focus on? We're tracking too many things."*

**What Lexy detects**
- Intent: `crown_jewel_analysis` (confidence 0.88)
- Key signals: "which metrics", "focus on", "too many"
- DT min_composite: `0.60` (stricter than default — high confidence bar)
- DT grouping: by `goal` — groups become candidate pools for ranking
- CCE mode: `required` — graph centrality (in_degree / out_degree) contributes 30% of impact score
- Impact formula: `DT_composite × 0.5 + centrality × 0.3 + relevance × 0.2`

**Conversational flow the user sees**

```
◉ Intent Classifier
  Understood: you want to identify which metrics have the highest business impact
  and retire the ones that don't. I'll apply a strict qualification threshold.

◉ Planner
  I'll qualify your metrics, order them by goal, map causal influence, then rank
  by combined DT score and graph centrality. 7 steps.

◉ Retrieving data
  Found 7 schemas and 28 candidate metrics across all focus areas.

◉ Decision Tree (strict — min 0.60)
  Applying higher confidence threshold. 28 → 16 metrics retained.
  Dropped 12 with low goal-alignment scores.
  Groups: completion (6), engagement (5), operations (5).

◉ Metrics Layout Resolver
  Ordering metric groups. Tagging leading indicators (drive outcomes) vs
  lagging indicators (measure results).
  Leading: training_completion_rate, login_frequency, manager_nudge_rate.
  Lagging: pass_rate, certification_status, NPS_score.

◉ Causal Graph (required)
  Computing metric centrality — which metrics influence the most others.
  Centrality is derived from the graph topology (in-degree / out-degree),
  not Shapley. training_completion_rate: out_degree 6 (highest leverage).
  assessment_pass_rate: in_degree 5 (most dependent on others).

◉ Crown Jewel Ranker
  Applying impact formula across 16 metrics.
  Top crown jewel: training_completion_rate (impact score 0.89).
  Retirement candidates: 8 metrics scoring below 0.35.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| Which single metric has the highest causal leverage? | **Training Completion Rate** — centrality 0.78, driving 6 downstream outcomes including pass rates, certification status, and compliance posture. |
| What are the top 3 leading indicators worth tracking? | 1. **Login Frequency** 2. **Assignment Completion %** 3. **Manager Nudge Rate** — all have high out_degree (causal influence over outcomes). |
| Which of our 28 tracked metrics can we safely retire? | **8 metrics** scored below 0.35 impact — raw login count, page view count, time-on-platform (seconds), and 5 others. |
| How does Login Frequency drive downstream outcomes? | A **+1 login/week** increase correlates with a +8.3% completion probability within 30 days. Causal path: Login Freq → Content Engagement → Assignment Progress → Completion. |

---

### Scenario 3 — Cohort Analysis `exploratory` ⚡ follow-up

**User question** *(second turn, after Scenario 1)*
> *"Break the compliance gap down by department for me."*

**What Lexy detects via follow-up router**
- Turn 2 — `csod_session_turn` > 1
- `dt_scored_metrics` present (14 metrics from Scenario 1)
- `csod_resolved_schemas` present (8 tables)
- Question matches `cohort_comparator` capability
- **Decision: route directly to `cohort_comparator`, skip spine**

**Steps skipped:** intent_classifier, planner, MDL retrieval, metrics retrieval, scoring_validator, DT resolver — 4–6 spine steps bypassed (~70% latency reduction)

**Conversational flow the user sees**

```
⚡ Follow-up detected
  I still have your compliance metrics from the previous analysis.
  Routing directly to cohort comparison — no need to re-qualify.

◉ Cohort Comparator
  Splitting learners by department (11 departments found in workday_employees).
  Computing compliance_completion_rate per cohort.
  Identifying statistical outliers from company mean (73.2%).
  Comparison complete: 4 departments above target, 7 below.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| How does compliance completion compare across all 11 departments? | Range: **Legal 94%** → **Engineering 58%**. Company mean: 73.2%. 4 above target, 7 below. |
| Which department improved most since last quarter? | **Sales** improved **+11.2 points** — from 65% to 76.2%. Attributed to new manager accountability program. |
| Which departments are statistically below the company mean? | **Engineering** (58%), **Product** (61%), and **Operations** (64%) — all more than 1.5σ below the mean. |
| What is the spread between best and worst? | **36 percentage points** separating Legal (94%) from Engineering (58%). Median industry spread is ~18 points. |

---

### Scenario 4 — Anomaly Detection `diagnostic`

**User question**
> *"Something looks off with our learner engagement data this month — can you investigate?"*

**What Lexy detects**
- Intent: `anomaly_detection` (confidence 0.86)
- Key signals: "looks off", "investigate"
- **Hard constraint: `enforce_trend_only = True`** — current_state metrics are invalid for anomaly detection (no variance to analyse)
- CCE mode: `required`, running in **upstream-trace mode** — distinguishes data pipeline anomaly from genuine business signal
- Z-score threshold: 2.0 standard deviations over a 90-day window

**Conversational flow the user sees**

```
◉ Intent Classifier
  Understood: you're seeing unusual patterns in engagement data.
  I'll analyse time-series trends only — point-in-time metrics can't
  have anomalies by definition.

◉ Planner
  I'll retrieve engagement schemas, qualify trend metrics, trace the causal
  graph upstream, then scan for statistical deviations. 6 steps.

◉ Retrieving data
  Found 5 schemas with timestamp columns. 18 candidate engagement metrics.

◉ Decision Tree (trend-only enforced)
  Hard-dropping all current_state metrics.
  18 → 7 trend metrics retained.
  Dropped: 11 current_state metrics (login count, active learner count, etc.)
  Groups: engagement_trends (4), platform_usage (3).

◉ Causal Graph (upstream trace)
  Checking if anomaly originates in a source table (pipeline issue) or in
  the business data itself.
  ETL audit log: no job failures in the anomaly window.
  Raw session table: counts confirm the drop is real.
  Conclusion: genuine business signal, not a pipeline artifact.

◉ Anomaly Detector
  Applying Z-score method across 7 time-series (90-day window, threshold 2.0σ).
  2 anomalies found.
  Primary: login_frequency dropped to -3.2σ on November 14th.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| When did the anomaly start and how severe is it? | **November 14th** — 18 days ago. Login frequency dropped to **3.2σ** below the 90-day mean. Significant severity. |
| Is this a pipeline problem or a real business signal? | **Real business signal** — upstream ETL logs show no gaps or failures. Raw session counts confirm the drop is genuine. |
| What caused the engagement drop? | Correlates with **Q4 performance review cycle** — login frequency dropped 34% during review weeks. This pattern is historically recurring (Q4 2022, Q4 2023). |
| Which other metrics will this propagate to, and when? | **Completion rate** impacted in ~12 days. **Assessment attempts** in ~8 days. Both currently within normal range but trending toward anomaly threshold. |

---

### Scenario 5 — Predictive Risk Analysis `predictive`

**User question**
> *"Who's going to miss our SOC2 training deadline next Friday?"*

**What Lexy detects**
- Intent: `predictive_risk_analysis` (confidence 0.93)
- Key signals: "going to miss", "deadline", "next Friday"
- **Hard constraint: `requires_deadline_dimension = True`** — metrics without `due_date` or `expiry` columns are dropped
- Risk horizon: `days_7` (from "next Friday")
- CCE mode: `required` — Shapley scores become risk weight coefficients (replaces equal weighting)

**Risk score formula** *(when CCE available)*
```
risk_score = Σ (shapley_weight_i × normalized_feature_i)

Shapley weights computed for compliance_posture goal:
  days_remaining:       0.38
  completion_progress:  0.29
  login_recency:        0.19
  historical_on_time:   0.14
```

**Conversational flow the user sees**

```
◉ Intent Classifier
  Understood: you want to know who will miss the SOC2 deadline in 7 days.
  I'll enforce deadline-aware metrics only and use causal risk weighting.

◉ Planner
  Retrieve compliance schemas, qualify risk indicators, build causal weights,
  score all active learners. 7 steps.

◉ Retrieving data
  Found 6 schemas. Key tables confirmed:
  cornerstone_training_assignments (due_date ✓),
  workday_employees (manager hierarchy ✓),
  cornerstone_sessions (login history ✓).

◉ Decision Tree (deadline dimension enforced)
  Dropping 4 metrics without due_date or expiry columns.
  7 risk indicators retained.
  Groups: compliance_urgency (4), engagement_signals (3).

◉ Causal Graph (required)
  Mapping causal edges between compliance indicator metrics.
  These edges will be used by the risk predictor as the coalition structure
  for computing internal Shapley weights against the compliance_posture goal.
  14 compliance-related edges identified.

◉ Risk Predictor
  Scoring 1,847 active learners with SOC2 assignment.
  Running Shapley attribution internally against compliance_posture goal
  to derive per-feature risk weights. Results embedded per-learner.
  High-risk: 127 | Medium-risk: 89 | Low-risk: 1,631.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| How many employees will miss the deadline? | **127 high-risk** employees (likely to miss). **89 medium-risk** (may miss without intervention). Total exposure: 216 of 1,847. |
| Which manager owns the most at-risk learners? | **Sarah Chen's team** — 14 high-risk out of 22 team members (64%). Recommended: immediate manager notification. |
| What course is the single biggest bottleneck? | **SOC2 Access Control** module — 43% of high-risk learners stuck here with less than 20% completion. Average time in module before dropout: 8 minutes. |
| What intervention is recommended? | `high-risk` Automated calendar block + manager notification + direct link to stuck module. `medium-risk` In-app nudge with suggested 2-hour time slot. |
| If we act today, what's the expected completion rate by Friday? | Estimated **91.3%** vs 82.4% if no action. Intervention uplift: +8.9 points. Assumes 60% response rate on manager notifications. |

---

### Scenario 6 — Training ROI Analysis `predictive`

**User question**
> *"Is our compliance training investment actually paying off? We spent $240K on it last year."*

**What Lexy detects**
- Intent: `training_roi_analysis` (confidence 0.91)
- Key signals: "investment", "$240K", "paying off"
- **DT constraint: `requires_cost_and_outcome_pair`** — must retain at least one cost metric and one outcome metric after qualification
- CCE mode: `required` — `calculate_generic_impact` + Shapley decomposition across program types
- Focus: `ld_operations` — enterprise learning measurement goal

**Conversational flow the user sees**

```
◉ Intent Classifier
  Understood: you want to know the return on your $240K compliance training spend.
  I'll need both cost and outcome metrics — validating the pair before proceeding.

◉ Planner
  Retrieve cost and outcome schemas, validate metric pair, map causal impact,
  compute ROI and decompose by program type. 7 steps.

◉ Retrieving data
  Found 7 schemas.
  Cost metrics found: training_cost_per_employee, vendor_spend, admin_cost.
  Outcome metrics found: compliance_rate, incident_reduction_proxy,
  audit_finding_count.

◉ Decision Tree (cost+outcome pair validation)
  Validating: at least 1 cost metric + 1 outcome metric must survive.
  Cost retained: 3. Outcome retained: 4. Pair check: PASS.
  Groups: cost_efficiency (3), compliance_outcomes (4).

◉ Causal Graph (required)
  Mapping cost→outcome causal chains across program types.
  These edges provide the coalition structure for the ROI calculator's
  internal Shapley decomposition against the total ROI goal.

◉ ROI Calculator
  Correlating $240K spend against compliance outcomes and incident proxy.
  Running calculate_generic_impact + Shapley attribution internally against
  total ROI goal to decompose program contributions.
  Program breakdown: security ($95K), soft-skills ($72K),
  technical ($48K), onboarding ($25K). Overall ROI: 3.2x.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| What is the overall ROI ratio? | **3.2x** — $240K invested → estimated $768K in risk avoidance and audit cost savings. |
| Which program type delivers the highest return? | **Mandatory security training**: 4.8x ROI. Lowest cost per compliant employee ($51), highest correlation with incident reduction. |
| Which program is underperforming? | **Optional soft-skills compliance**: 0.9x ROI — costs more than measurable value delivered. $72K spend with weak compliance outcome correlation. |
| Where should we reallocate budget? | Shift **$45K** from soft-skills to technical security → estimated +$180K incremental value. Net new ROI: 4.0x on reallocated funds. |
| How does cost per compliant employee compare to last year? | **$127** this year vs $164 last year — a **22.6% efficiency improvement**. |

---

### Scenario 7 — Dashboard Generation `operational`

**User question**
> *"Build a compliance training dashboard for our L&D director showing this quarter's performance."*

**What Lexy detects**
- Intent: `dashboard_generation_for_persona` (confidence 0.95)
- Persona: `l&d_director`
- Focus: `compliance_training`, `ld_operations`
- Template: `enterprise-learning-measurement` (high complexity, 11 components)
- **Key flow difference:** dashboard_layout_resolver runs **before** dashboard_generator, replacing the generator's own section logic
- CCE mode: `optional` — leading/lagging annotations added to component metadata

**How DT drives the layout:**

```
DT metric groups (from dt_resolver):
  executive_kpis (4 metrics, goal_alignment 0.91)
  └── All metric_type=current_state → section: top_kpis → widget: kpi_card

  trend_charts (5 metrics, goal_alignment 0.84)
  └── All metric_type=trend → section: trends_row → widget: trend_line

  operational_detail (4 metrics, goal_alignment 0.77)
  └── Mixed types → section: detail_table + breakdown_charts

CCE centrality → ordering within sections:
  Leading indicators (high out_degree) → placed first
  Lagging indicators (high in_degree)  → placed last
```

**Conversational flow the user sees**

```
◉ Intent Classifier
  Building a dashboard for your L&D director.
  I'll select the right metric complexity for a director-level audience
  and use the enterprise learning measurement template.

◉ Planner
  Qualify metrics for L&D director persona, resolve layout from DT groups,
  annotate with causal context, build dashboard components. 8 steps.

◉ Retrieving data
  Found 9 schemas, 19 candidate metrics suited for L&D director
  (strategic + operational mix).

◉ Decision Tree (persona-scoped)
  Resolving l&d_director audience level.
  13 metrics retained across 3 goal groups.
  Groups mapped to sections: executive_kpis, trend_charts, operational_detail.

◉ Dashboard Layout Resolver
  Mapping 3 DT groups → dashboard sections.
  Leading indicators placed first in each section (CCE centrality).
  11 widget assignments: 4 kpi_cards, 4 trend_lines, 3 detail tables.

◉ Causal Graph (optional — leading/lagging annotations)
  Annotating 11 dashboard components as leading or lagging indicators.
  5 leading, 8 lagging. Annotations added to csod_dt_layout.

◉ Dashboard Generator
  Building 11 components from csod_dt_layout sections.
  Reading widget types from layout resolver — not deriving independently.
  Dashboard assembled.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| What is our overall compliance training completion rate this quarter? | **78.4%** ↑4.2% vs last quarter. Target: 90%. Gap: 11.6 points. |
| Which 3 departments need immediate attention? | **Engineering** 58%, **Operations** 61%, **Product** 64% — all below 65% and trending flat or declining. |
| How is compliance completion trending week-over-week? | **Steady improvement** — +1.8%/week over 8 consecutive weeks. On current trajectory: will reach 85% by quarter end (still below 90% target). |
| What is the certification renewal pipeline for the next 30 days? | **234** certifications expiring. 157 (67%) renewal in progress. 77 not yet started. |
| How much did we spend on training vs our L&D budget? | $187K spent of $240K budget — 78% utilisation at Q4 week 10. On track. |

---

### Scenario 8 — Data Discovery `data intelligence`

**User question**
> *"Before I start — what training data do I actually have available for analysis?"*

**What Lexy detects**
- Intent: `data_discovery` (confidence 0.89)
- Key signals: "what data do I have", "available", "before I start"
- **Short-circuit path** — skips metrics_retrieval, scoring_validator, DT resolver, CCE entirely
- Only 2 spine steps: broad MDL schema retrieval → data_discovery_agent
- This intent is designed to run **before** any analytical intent — its outputs help users decide which analysis to run

**Conversational flow the user sees**

```
◉ Intent Classifier
  Understood: you want a capability audit before choosing an analysis type.
  I'll take the short path — no metric qualification needed for this.

◉ Planner
  2-step plan. Broad schema scan, then capability mapping. No DT or CCE.

◉ MDL Schema Retrieval (broad scope)
  Scanning all configured data sources without focus area filtering.
  Found 23 tables across Cornerstone LMS and Workday HCM.

◉ Data Discovery Agent
  Cataloguing 23 tables.
  Mapping each to the metrics registry to identify buildable metrics.
  31 of 45 planned metrics are buildable with current data.
  3 key capability gaps identified.
```

**Final outcomes — natural language answers**

| Question | Answer |
|---|---|
| How many tables are available in my dataset? | **23 tables** — 4 bronze (raw), 12 silver (analyst-ready), 7 gold (pre-aggregated). Workday HCM connected but 3 tables pending sync. |
| Which of my planned metrics can I compute right now? | **31 of 45** planned metrics are buildable (69% coverage). The 14 unbuildable metrics require session_duration, manager_hierarchy, or historical_cost tables. |
| What data gaps would unlock the most additional analysis? | 1. **session_duration_minutes** — unlocks behavioral analysis (+8 metrics). 2. **manager_hierarchy** — unlocks cohort-by-manager (+4 metrics). 3. **historical_costs** — unlocks full ROI analysis. |
| How fresh is my available data? | **cornerstone_training_assignments**: updated 2 hours ago ✓. Oldest: **cornerstone_certifications**: 3 days stale — check before cert analysis. |
| Can I run a compliance risk analysis with current data? | **Yes** — all required tables present. Missing session data would improve behavioral risk scoring by ~15%, but core risk scoring is fully supported. |

---

## Part 3 — Flow Patterns Summary

### Pattern 1 — Full spine (first turn, metric-bearing analysis)

```
Question → Spine (6 nodes) → DT Resolver → [Layout?] → [CCE?] → Executor → Assembler
```
Used by: gap analysis, crown jewel, anomaly detection, risk analysis, ROI, skill gap, benchmark, cohort, dashboard generation, metrics recommendations

### Pattern 2 — Direct dispatch (follow-up turn)

```
Question → Follow-up Router → Direct Executor → Assembler
```
Used by: any second-turn question where `dt_scored_metrics` and `csod_resolved_schemas` are already in state and the question maps to a `can_be_direct=True` executor

Eligible executors: anomaly_detector, funnel_analyzer, risk_predictor, behavioral_analyzer, crown_jewel_ranker, gap_analyzer, cohort_comparator, benchmark_comparator, skill_gap_assessor, data_quality_inspector, data_lineage_tracer, data_discovery_agent, dashboard_generator, metrics_recommender

### Pattern 3 — Short-circuit (data intelligence)

```
Question → Spine (MDL only) → Intelligence Executor → Assembler
```
Used by: data_discovery, data_quality_analysis

Skips: metrics_retrieval, scoring_validator, DT resolver, CCE

### Pattern 4 — Chained executors (complex intents)

```
Question → Spine → DT → Layout Resolver → [CCE] → Primary Executor → Secondary Executor → Assembler
```
Used by: metrics_recommender_with_gold_plan (→ medallion_planner), metrics_dashboard_plan (→ data_science_enricher → calculation_planner), data_planner (→ metrics_recommender → data_pipeline_planner)

---

## Part 4 — Constraint Reference

### DT hard constraints by intent

| Intent | Hard constraint | Effect |
|---|---|---|
| `anomaly_detection` | `enforce_trend_only = True` | Drops ALL current_state metrics |
| `gap_analysis` | `requires_target_value = True` | Drops metrics without a definable target |
| `predictive_risk_analysis` | `requires_deadline_dimension = True` | Drops metrics without due_date / expiry column |
| `training_roi_analysis` | `requires_cost_and_outcome_pair = True` | Validates pair survives; logs gap if not |
| `funnel_analysis` | `requires_funnel_stages = True` | Keeps only metrics that map to a funnel stage |
| `cohort_analysis` | `requires_segment_dimension = True` | Keeps only metrics with a groupable column |
| `crown_jewel_analysis` | `min_composite = 0.60` | Higher bar than default 0.55 |

### CCE mode by intent

| Mode | Intents | What causal graph provides | What executor does with it |
|---|---|---|---|
| `required` | crown jewel | `csod_causal_centrality` (topology) | Reads centrality directly in impact formula — no Shapley |
| `required` | gap, risk, ROI, causal analysis | `csod_causal_edges` (structure) | Runs Shapley **internally** against executor-specific goal; embeds result in output artifact |
| `required` | anomaly, behavioral | `csod_causal_edges` (paths) | Graph traversal only — upstream/downstream walk; no Shapley |
| `optional` | funnel, cohort, skill gap, metrics rec, dashboard, compliance test | `csod_causal_edges` + `csod_causal_centrality` | Structural annotation or ordering; some run internal Shapley optionally |
| `disabled` | benchmark, all data intelligence | — | No causal structure applicable |

**Critical distinction:** `csod_causal_centrality` is topology-derived (in-degree / out-degree counts from graph structure). It is **not** a Shapley value. Shapley distributions are only ever computed inside execution agents, embedded in their output artifacts, and never written to shared state.

---

## Part 5 — New Files and Prompts

### New files

| File | Purpose |
|---|---|
| `executor_registry.py` | Single source of truth for all 20 executors |
| `csod_analysis_nodes.py` | 6 LLM + 4 SQL wrapper execution nodes |
| `csod_intelligence_nodes.py` | 4 data intelligence nodes |
| `csod_layout_nodes.py` | 2 DT layout nodes |
| `csod_base_workflow.py` | `build_csod_retrieval_spine()` shared builder |
| `csod_analytical_workflow.py` | Unified workflow replacing csod_workflow.py |
| `csod_intelligence_workflow.py` | Data intelligence short-circuit workflows |
| `csod_followup_router.py` | Follow-up router node |
| `csod_narrative.py` | Step narrator, summary narrator, SSE helpers |

### New prompts

| File | Used by |
|---|---|
| `15_decision_tree_resolver.md` | `csod_decision_tree_resolver_node` |
| `16_crown_jewel_analysis.md` | `csod_crown_jewel_ranker_node` |
| `17_gap_analysis.md` | `csod_gap_analyzer_node` |
| `18_cohort_analysis.md` | `csod_cohort_comparator_node` |
| `19_benchmark_analysis.md` | `csod_benchmark_comparator_node` |
| `20_skill_gap_analysis.md` | `csod_skill_gap_assessor_node` |
| `21_roi_analysis.md` | `csod_roi_calculator_node` |
| `22_data_discovery.md` | `csod_data_discovery_node` |
| `23_data_quality.md` | `csod_data_quality_inspector_node` |
| `24_data_lineage.md` | `csod_data_lineage_tracer_node` |
| `25_data_pipeline_planner.md` | `csod_data_pipeline_planner_node` |
| `26_dashboard_layout.md` | `csod_dashboard_layout_resolver_node` |
| `27_metrics_layout.md` | `csod_metrics_layout_resolver_node` |
| `28_followup_router.md` | `csod_followup_router_node` |

### Modified prompts

| File | Key changes |
|---|---|
| `01_intent_classifier.md` | Add 12 new intent strings, trigger patterns, auto-escalation block |
| `02_csod_planner.md` | Inject executor registry, add executor selection rules, `follow_up_eligible` output |
| `03_metrics_recommender.md` | Consume `dt_scored_metrics` not `scored_metrics` |
| `04_dashboard_generator.md` | Read `csod_dt_layout` sections from layout resolver |
| `05_compliance_test_generator.md` | Add causal edges context block — Shapley for severity weighting computed internally |
| `07_output_assembler.md` | 20+ new artifact types in collection block |
| `12_skill_advisor.md` | Add 12 new skill mappings |

---

*This document is the companion to `csod_refactoring_design_doc_v5.md`. The design doc covers the technical implementation; this document covers the user-facing conversational experience and flow patterns.*
