# Generic Dashboard Decision Tree — Design Document

## Purpose

This document defines a **destination-aware, registry-driven decision tree** for dashboard layout selection. It replaces the current per-workflow decision trees (CSOD, DT/LEEN) with a single generic tree that works across any domain, any metric registry, and any output destination.

The three dimensions that drive every decision:

1. **Context** — what category, focus areas, and metrics are in play
2. **Audience & use case** — who is reading the dashboard and why
3. **Destination** — how and where the dashboard will be rendered

All three must be resolved before the registry lookup fires.

---

## Architecture

```
Upstream State
  {goal_statement, metrics[], focus_areas[], framework_id, data_sources[]}
            │
            ▼
  ┌─────────────────────────────┐
  │   DECISION TREE RESOLVER    │  ← LLM call (prompt: generic_resolve_decisions.md)
  │                             │    with fallback to keyword matching
  │  Q1: Category               │
  │  Q2: Focus Area             │
  │  Q3: Metric Profile         │
  │  Q4: Audience               │
  │  Q5: Complexity             │
  │  Q6: Destination Type       │  ← NEW — PowerBI / Embedded / Simple
  │  Q7: Interaction Mode       │  ← NEW — drill-down / read-only / real-time
  └────────────┬────────────────┘
               │
               ▼  ResolvedDecisions
  ┌─────────────────────────────┐
  │   REGISTRY LOOKUP           │
  │                             │
  │  dashboard_registry.json    │  ← filtered by destination_type first
  │  ld_templates_registry.json │  ← then scored by all other dimensions
  │  future registries...       │
  └────────────┬────────────────┘
               │
               ▼  ScoredCandidates[]
  ┌─────────────────────────────┐
  │   DESTINATION ADAPTER       │  ← transforms scored spec for target renderer
  │                             │
  │  PowerBI  → pbix spec       │
  │  Embedded → ECharts spec    │
  │  Simple   → HTML/static     │
  └─────────────────────────────┘
```

---

## Decision Tree — Seven Questions

### Q1: Dashboard Category

Classifies the broad domain. Determines which sub-registry to search and which taxonomy slice to load.

| option_id | Label | Keywords | Maps to registry |
|---|---|---|---|
| `compliance_audit` | Compliance & Audit | soc2, hipaa, nist, audit, controls, compliance, framework | `dashboard_registry.json` |
| `security_operations` | Security Operations | incident, threat, vulnerability, siem, detection, alert | `dashboard_registry.json` |
| `learning_development` | Learning & Development | training, completion, lms, course, learner, cornerstone, csod | `ld_templates_registry.json` |
| `hr_workforce` | HR & Workforce | onboarding, headcount, attrition, workforce, employee, workday | `dashboard_registry.json` |
| `risk_management` | Risk Management | risk, exposure, vendor, third-party, grc, posture | `dashboard_registry.json` |
| `executive_reporting` | Executive / Board | board, executive, summary, leadership, ciso, kpi rollup | `dashboard_registry.json` |
| `data_operations` | Data Operations | pipeline, etl, dbt, data quality, freshness, schema | `dashboard_registry.json` |
| `cross_domain` | Cross-Domain | hybrid, unified, multi-framework, integrated | `dashboard_registry.json` + `ld_templates_registry.json` |

**Resolution priority:** `framework_id` → `data_sources` → `goal_statement` keywords → `metrics[].category`

---

### Q2: Focus Area

Narrows within the category. Loaded from `dashboard_domain_taxonomy.json` for the resolved category, so the option set is dynamic — not hardcoded.

**Resolution contract:**
```json
{
  "option_id": "vulnerability_management",
  "confidence": 0.85,
  "source": "suggested_focus_areas[0]"
}
```

**Common focus areas by category (illustrative — taxonomy is the source of truth):**

| Category | Focus Areas |
|---|---|
| `compliance_audit` | access_control, audit_logging, change_management, data_protection, training_compliance |
| `security_operations` | vulnerability_management, incident_response, threat_detection, asset_inventory |
| `learning_development` | training_completion, learner_engagement, content_effectiveness, compliance_training |
| `hr_workforce` | onboarding_offboarding, headcount_planning, performance_tracking, attrition_risk |
| `risk_management` | vendor_risk, control_effectiveness, risk_exposure, regulatory_change |

**LLM resolution:** The LLM receives the taxonomy slice for the resolved category and maps `suggested_focus_areas` from state → closest `option_id`. If no match, it picks the highest-frequency focus area from the metric list.

---

### Q3: Metric Profile

Characterises what types of metrics are present. Drives chart type selection and panel layout inside the template.

| option_id | Label | Signal | Effect on layout |
|---|---|---|---|
| `count_heavy` | Counts & Totals | >50% of metrics are `type: count` | Prioritises KPI strip + bar charts |
| `trend_heavy` | Trends & Time Series | >50% are `type: trend_line` or `widget_type: area` | Prioritises time-axis panels, minimises strip |
| `rate_percentage` | Rates & Percentages | dominant types are `percentage`, `rate` | Gauge charts, threshold colouring |
| `comparison` | Comparisons & Rankings | dominant types are `bar_grouped`, `rank`, `distribution` | Grouped bar, horizontal bar panels |
| `mixed` | Mixed | no dominant type | Balanced layout — equal strip + chart area |
| `scorecard` | Scorecards Only | all metrics are `kpi_card` or `score` | Strip-only or scorecard grid template |

**Resolution:** Computed deterministically from `metrics[].type` / `metrics[].widget_type` distribution — no LLM needed. Fallback: `mixed`.

---

### Q4: Audience

Who is the primary consumer. Influences complexity, default theme, and whether AI chat / causal graph panels are shown.

| option_id | Label | Keywords | Defaults |
|---|---|---|---|
| `security_ops` | Security Analyst | analyst, soc, tier1, tier2, siem, triage | complexity: high, theme: dark, chat: true |
| `compliance_team` | Compliance Officer | compliance, auditor, grc, controls, evidence | complexity: medium, theme: light, chat: false |
| `executive_board` | Executive / Board | ciso, board, vp, leadership, summary | complexity: low, theme: light, chat: false |
| `risk_management` | Risk Manager | risk, exposure, third-party, vendor | complexity: medium, theme: light, chat: false |
| `learning_admin` | L&D Administrator | learning, training, lms, admin, hr | complexity: medium, theme: light, chat: false |
| `data_engineer` | Data / Ops Team | pipeline, dbt, etl, data quality | complexity: high, theme: dark, chat: true |

**Resolution:** `metrics[].kpis` and `goal_statement` keywords. `persona` from upstream state is highest priority if present.

---

### Q5: Complexity

How much detail and how many panels. Derived from audience defaults + explicit override.

| option_id | Label | Strip cells | Max chart panels | Has causal graph |
|---|---|---|---|---|
| `low` | Summary View | 4–6 | 2 | No |
| `medium` | Standard | 6–8 | 4 | Optional |
| `high` | Full Detail | 8 | 6+ | Yes |

**Resolution:** Audience default → override from `goal_statement` (keywords: "detailed", "summary", "overview", "full").

---

### Q6: Destination Type *(new dimension)*

Where and how the dashboard is rendered. **This is the first filter applied in registry lookup** — templates that don't support the destination are excluded before scoring begins.

| option_id | Label | Description | Key constraints |
|---|---|---|---|
| `embedded` | Embedded (ECharts) | React / HTML component in a web app or CCE platform | Full ECharts feature set; AI chat panel supported; causal graph supported |
| `powerbi` | Power BI | .pbix report or Power BI Embedded | No AI chat; no custom React panels; DAX measures required; limited layout primitives |
| `simple` | Simple / Static | Standalone HTML or PDF-ready output | No interactivity; flat layout only; no chat, no graph |
| `slack_digest` | Slack / Email Digest | Scheduled summary message | Text + max 2 images; no panels; strip KPIs only |
| `api_json` | API / JSON Export | Headless — no visual render | Spec only; no layout primitives; metrics + thresholds as structured JSON |

**Resolution priority:** Explicit `output_format` from upstream state → `agent_config.default_output_format` → fallback: `embedded`.

**Destination type gates the following template fields:**

```
destination = embedded   → allow: all primitives, chat, causal_graph, ECharts types
destination = powerbi    → allow: strip, bar, line, pie, table only; exclude: chat, causal_graph
destination = simple     → allow: strip, bar, line only; exclude: chat, causal_graph, filters
destination = slack      → allow: strip only (max 6 cells); exclude: all panels, charts
destination = api_json   → allow: none — emit metric_spec[] with thresholds only
```

---

### Q7: Interaction Mode *(new dimension)*

How the user will interact with the rendered output. Drives filter chip inclusion, drill-down panel selection, and whether real-time refresh polling is configured in the n8n workflow.

| option_id | Label | Description | Effect |
|---|---|---|---|
| `drill_down` | Drill-Down | User clicks KPI strip cells to open detail panels | Enables left/right panels, card anatomy, filter chips |
| `read_only` | Read-Only | Static view — user scrolls, no clicks | Disables filter chips; collapses side panels to summary |
| `real_time` | Real-Time | Live refresh (< 5 min cadence) | Forces n8n trigger: `interval_5min`; disables heavy aggregations |
| `scheduled_report` | Scheduled Report | Delivered on a schedule, not interactive | No filters; strip + 2 charts max; optimised for print/PDF |

**Resolution:** `timeframe` from upstream state (realtime → `real_time`), `output_format` = `simple` / `slack` → `scheduled_report`, default: `drill_down`.

---

## ResolvedDecisions Object

The output of the decision tree resolver. Passed directly into registry lookup.

```json
{
  "category": {
    "option_id": "compliance_audit",
    "confidence": 0.92,
    "source": "framework_id"
  },
  "focus_area": {
    "option_id": "training_compliance",
    "confidence": 0.85,
    "source": "suggested_focus_areas[0]"
  },
  "metric_profile": {
    "option_id": "rate_percentage",
    "confidence": 1.0,
    "source": "deterministic"
  },
  "audience": {
    "option_id": "compliance_team",
    "confidence": 0.78,
    "source": "persona"
  },
  "complexity": {
    "option_id": "medium",
    "confidence": 0.9,
    "source": "audience_default"
  },
  "destination_type": {
    "option_id": "embedded",
    "confidence": 1.0,
    "source": "upstream_output_format"
  },
  "interaction_mode": {
    "option_id": "drill_down",
    "confidence": 0.8,
    "source": "default"
  },
  "overall_confidence": 0.86,
  "registry_target": "ld_templates_registry",
  "reasoning": "SOC2 framework + training metrics → compliance_audit / training_compliance. Persona=compliance_team → medium complexity, light theme. output_format=echarts → embedded destination."
}
```

---

## Registry Lookup — Scoring with Destination Gate

### Step 1: Destination Gate (hard filter, no scoring)

```python
candidates = [
    t for t in registry
    if resolved.destination_type in t["supported_destinations"]
]
# If empty, relax to destination_type = "embedded" and log a warning
```

Every template in `dashboard_registry.json` and `ld_templates_registry.json` must carry a `supported_destinations` array. Templates that don't declare it are treated as `["embedded"]` only.

```json
{
  "template_id": "hybrid-compliance",
  "supported_destinations": ["embedded", "powerbi"],
  "powerbi_constraints": {
    "excluded_primitives": ["chat_panel", "causal_graph"],
    "measure_format": "dax"
  }
}
```

### Step 2: Score Remaining Candidates

| Dimension | Points | Notes |
|---|---|---|
| `category` match | 30 | Direct match to `template.domains[]` |
| `focus_area` match | 20 | Match to `template.focus_areas[]` if present; else to `template.best_for[]` |
| `audience` match | 20 | Match to `template.audience_levels[]` |
| `metric_profile` match | 15 | e.g., `trend_heavy` → templates with area/line-dominant layouts score higher |
| `complexity` match | 10 | `template.complexity` must equal or be within ±1 level |
| Vector boost | +15 | From Retrieval Point 1 (semantic similarity on goal_statement) |
| Interaction mode match | +5 | e.g., `real_time` boosts templates with live-refresh support |

### Step 3: Destination-Specific Overrides

After scoring, apply destination-specific transformations to the winning spec before it reaches the adapter:

```python
if destination == "powerbi":
    spec = strip_powerbi_unsupported(spec)   # removes chat, causal_graph, custom JS
    spec = inject_dax_measure_stubs(spec)    # adds placeholder DAX for each metric
    spec["output_format"] = "pbix"

elif destination == "simple":
    spec = flatten_to_two_panel(spec)        # left panel only, center panel only
    spec["has_chat"] = False
    spec["has_filters"] = False

elif destination == "slack_digest":
    spec = extract_strip_only(spec)          # keeps strip_kpis[], drops everything else
    spec["max_kpi_cells"] = 6

elif destination == "api_json":
    spec = emit_metric_spec_only(spec)       # metric_id, threshold, good_direction only
```

---

## Destination Adapters

Each adapter takes a `ScoredSpec` and emits the format consumed by the downstream renderer.

### Embedded Adapter (ECharts)

No transformation needed — `ScoredSpec` is already in ECharts Intent Spec (EPS) format. Passes through directly to the renderer.

Output: `dashboard_layout_spec.json` (EPS v1.0)

### PowerBI Adapter

Strips unsupported primitives, maps chart types to Power BI equivalents, emits a `.pbix`-compatible layout manifest.

```
EPS chart_type         → Power BI visual type
────────────────────────────────────────────
line_basic             → lineChart
bar_grouped            → barChart
gauge                  → gauge (KPI)
area_stacked           → areaChart
scatter                → scatterChart
table_sortable         → tableEx
kpi_card               → card
```

Unsupported in Power BI: `causal_graph`, `chat_panel`, `heatmap_calendar`, `sankey`, `treemap`. These are removed and logged.

Output: `powerbi_layout_manifest.json`

### Simple / Static Adapter

Generates a single-file `dashboard.html` using inline Chart.js (no build step required). Layout is two-column max. Suitable for PDF export or email attachment.

Output: `dashboard.html`

### Slack / Email Digest Adapter

Produces a `digest_spec.json` with a `blocks[]` array in Slack Block Kit format. Only the KPI strip is rendered. Each strip cell becomes one section block with value + trend indicator.

Output: `digest_spec.json`

### API / JSON Export Adapter

Emits a flat `metric_spec.json` with no layout primitives — just metric definitions with thresholds, good_direction, and gold table references. Consumed by external systems.

Output: `metric_spec.json`

---

## LLM Resolution Prompt Contract

**Prompt file:** `app/agents/decision_trees/prompts/generic_resolve_decisions.md`

**Input to LLM:**
```json
{
  "goal_statement": "...",
  "metrics_summary": [{"id": "...", "type": "...", "category": "..."}],
  "focus_areas": ["..."],
  "framework_id": "soc2",
  "data_sources": ["cornerstone.lms"],
  "persona": "compliance_team",
  "output_format": "echarts",
  "timeframe": "monthly",
  "available_categories": ["compliance_audit", "learning_development", ...],
  "taxonomy_slice": { ... }
}
```

**LLM output contract:**
```json
{
  "resolved_decisions": {
    "category": {"option_id": "...", "confidence": 0.0–1.0, "source": "..."},
    "focus_area": {"option_id": "...", "confidence": 0.0–1.0, "source": "..."},
    "metric_profile": {"option_id": "...", "confidence": 0.0–1.0, "source": "deterministic"},
    "audience": {"option_id": "...", "confidence": 0.0–1.0, "source": "..."},
    "complexity": {"option_id": "...", "confidence": 0.0–1.0, "source": "..."},
    "destination_type": {"option_id": "...", "confidence": 0.0–1.0, "source": "..."},
    "interaction_mode": {"option_id": "...", "confidence": 0.0–1.0, "source": "..."}
  },
  "registry_target": "dashboard_registry | ld_templates_registry | both",
  "overall_confidence": 0.0–1.0,
  "reasoning": "..."
}
```

`metric_profile` is always resolved deterministically before the LLM call and injected as a pre-resolved field. The LLM does not reason over metric type distributions.

---

## Fallback Hierarchy

```
1. LLM resolution (primary)
      ↓ (fails or confidence < 0.5)
2. Keyword matching fallback (_resolve_from_state_fallback)
      ↓ (fails)
3. Destination-aware defaults table
      ↓ (destination unknown)
4. embedded + medium + mixed + drill_down defaults
```

**Destination-aware defaults table:**

| destination_type | category default | audience default | complexity default |
|---|---|---|---|
| `embedded` | `security_operations` | `security_ops` | `medium` |
| `powerbi` | `executive_reporting` | `executive_board` | `low` |
| `simple` | `compliance_audit` | `compliance_team` | `low` |
| `slack_digest` | `executive_reporting` | `executive_board` | `low` |
| `api_json` | — | — | — |

---

## Registry Schema — Required Changes

Both `dashboard_registry.json` and `ld_templates_registry.json` need two new fields per template:

```json
{
  "template_id": "hybrid-compliance",
  "supported_destinations": ["embedded", "powerbi"],
  "interaction_modes": ["drill_down", "read_only"],
  "metric_profile_fit": ["rate_percentage", "mixed"],
  "focus_areas": ["training_compliance", "access_control"],
  "powerbi_constraints": {
    "excluded_primitives": ["chat_panel", "causal_graph"],
    "measure_format": "dax"
  },
  "simple_constraints": {
    "max_panels": 2,
    "excluded_primitives": ["chat_panel", "causal_graph", "filters"]
  }
}
```

Templates that do not declare `supported_destinations` are treated as `["embedded"]` only. This is a non-breaking default.

---

## Integration with Existing Pipeline

This decision tree replaces the current `resolve_decisions()` call in `_resolve_from_state()`. The output `ResolvedDecisions` object is structurally compatible with the existing `resolution_payload` in `LayoutAdvisorState` — two new keys are added (`destination_type`, `interaction_mode`) and one is renamed (`category` replaces the old `domain` alias).

```python
# Before
resolution_payload = {
    "resolved_metric_groups": {...},
    "control_anchors": [...],
    "focus_areas": [...],
    "timeframe": "monthly",
    "audience": "compliance_team",
    "complexity": "medium",
}

# After
resolution_payload = {
    "resolved_metric_groups": {...},
    "control_anchors": [...],
    "focus_areas": [...],
    "timeframe": "monthly",
    "audience": "compliance_team",
    "complexity": "medium",
    # new fields:
    "destination_type": "embedded",
    "interaction_mode": "drill_down",
    "registry_target": "dashboard_registry",
    "metric_profile": "rate_percentage",
}
```

`scoring_node` reads `destination_type` and applies the gate before passing candidates to the LLM. `spec_generation_node` reads `destination_type` and routes to the correct adapter before writing the final spec.

---

## State Changes Required

Add to `LayoutAdvisorState`:

```python
# Decision tree outputs (new)
destination_type:  str   # "embedded" | "powerbi" | "simple" | "slack_digest" | "api_json"
interaction_mode:  str   # "drill_down" | "read_only" | "real_time" | "scheduled_report"
metric_profile:    str   # "count_heavy" | "trend_heavy" | "rate_percentage" | "comparison" | "mixed" | "scorecard"
registry_target:   str   # "dashboard_registry" | "ld_templates_registry" | "both"
```

---

## Testing Matrix

Each cell in this matrix should have a test case.

| Category | Focus Area | Destination | Expected registry | Expected template class |
|---|---|---|---|---|
| `compliance_audit` | `training_compliance` | `embedded` | `ld_templates_registry` | `hybrid-compliance` |
| `compliance_audit` | `training_compliance` | `powerbi` | `ld_templates_registry` | `hybrid-compliance` (stripped) |
| `security_operations` | `vulnerability_management` | `embedded` | `dashboard_registry` | `command-center` |
| `security_operations` | `vulnerability_management` | `simple` | `dashboard_registry` | `vulnerability-posture` (flattened) |
| `learning_development` | `learner_engagement` | `embedded` | `ld_templates_registry` | `lms-engagement` |
| `executive_reporting` | any | `slack_digest` | either | strip-only output |
| `executive_reporting` | any | `powerbi` | `dashboard_registry` | `executive-risk-summary` |
| any | any | `api_json` | skip registry | `metric_spec.json` only |