# Goal-Driven Dashboard Generation — System Design
**Pipeline: Resolve → Bind → Score → Recommend → Verify**

---

## Design Philosophy

The pipeline has five named stages, each with a distinct role and a clean contract to the next. The human is not an afterthought at the end — they are the **approval gate between Recommend and the final committed spec**. Nothing is rendered, stored, or handed to downstream systems until Verify fires.

```
User Goal Input
      ↓
  [RESOLVE]   — Decision tree classifies goal into structured intent
      ↓
   [BIND]     — Metric groups + control anchors joined from registries
      ↓
  [SCORE]     — Templates + charts ranked against bound context
      ↓
[RECOMMEND]   — Top-N options surfaced with rationale + diff view
      ↓
  [VERIFY]    — Human reviews, approves, adjusts, or rejects
      ↓
  Unified Dashboard Spec committed → Spec Store → Renderer
```

Each stage is independently testable. A failure or ambiguity at any stage surfaces to the user with a specific, actionable message — not a generic error.

---

## The Registries and What They Own

| Registry | Stage It Feeds | Role |
|---|---|---|
| `control_domain_taxonomy.json` | BIND | Maps SOC2/HIPAA/NIST controls to `focus_areas` and `risk_categories` |
| `metric_use_case_groups.json` | BIND | Maps named goals to required/optional metric groups + audience + timeframe |
| `dashboard_domain_taxonomy.json` | RESOLVE + SCORE | Maps domains to audience levels, complexity, theme preference |
| `cce_layout_registry.json` | SCORE | 23 templates with scoring weights, primitives, panel configs |

---

## Stage 1 — RESOLVE

### What It Does

Classifies the user's goal into a structured **Dashboard Intent Object**. No metrics, no templates, no charts at this stage — just intent.

**Input:** Goal statement (freeform text or taxonomy selection) + optional context overrides

**Output — Dashboard Intent Object:**
```json
{
  "use_case_group": "soc2_audit",
  "domain": "hybrid_compliance",
  "framework": ["soc2"],
  "audience": "auditor",
  "complexity": "high",
  "theme": "light",
  "timeframe": "monthly",
  "resolution_path": "decision_tree | llm_advisor",
  "confidence": 0.95
}
```

### Decision Tree Structure

The tree has four branching axes evaluated in order. Each axis narrows the candidate space before passing to the next.

```
ROOT
│
├── AXIS 1 — PRIMARY INTENT (what is the user trying to accomplish?)
│   ├── Audit / Compliance evidence        → use_case_group: soc2_audit
│   ├── Training / Learning oversight      → use_case_group: lms_learning_target
│   ├── Risk communication to leadership   → use_case_group: risk_posture_report
│   ├── Executive KPI summary              → use_case_group: executive_dashboard
│   └── Day-to-day operational monitoring  → use_case_group: operational_monitoring
│
├── AXIS 2 — COMPLIANCE FRAMEWORK (which framework governs this goal?)
│   ├── SOC2         → control_prefix: CC, resolve CC1–CC9
│   ├── HIPAA        → resolve 164.308 / 164.312 controls
│   ├── NIST AI RMF  → resolve GOVERN / MAP / MEASURE / MANAGE
│   └── None/internal → skip control binding in BIND stage
│
├── AXIS 3 — AUDIENCE (who consumes this dashboard?)
│   ├── Auditor / GRC manager    → complexity: high,   theme: light
│   ├── Executive / Board        → complexity: low,    theme: light
│   ├── Security Ops / SOC       → complexity: high,   theme: dark
│   ├── Learning Admin / L&D     → complexity: medium, theme: light
│   └── Team Manager             → complexity: medium, theme: light
│
└── AXIS 4 — DATA SCOPE (what source systems are in scope?)
    ├── LMS only (Cornerstone / SumTotal)  → domain: ld_training or ld_operations
    ├── Security tooling (Snyk / Qualys)   → domain: security_operations or vuln_mgmt
    ├── HR (Workday)                        → domain: hr_workforce
    └── Multi-source                        → domain: hybrid_compliance
```

### Two Resolution Paths

The decision tree handles **known, named goals** with zero LLM calls. Ambiguous or freeform goals route to the Layout Advisor Agent, which runs a guided conversation and outputs a Dashboard Intent Object in the same contract.

```
Taxonomy pick   → Decision Tree (deterministic, <50ms)
Freeform input  → Layout Advisor Agent (LangGraph conversation)
                           ↓
                  Both produce the same Dashboard Intent Object
                           ↓
                       BIND stage
```

The tree builder **validates at build time**: every leaf must resolve to a `use_case_group` that exists in `metric_use_case_groups.json`, and every referenced framework must exist in `control_domain_taxonomy.json`. Invalid nodes fail at authoring time, not at user runtime.

---

## Stage 2 — BIND

### What It Does

Takes the Dashboard Intent Object and **joins it against the registries** to produce a fully populated **Resolution Payload** — the complete set of metric groups, control anchors, focus areas, and risk categories that constrain everything downstream.

No templates, no charts yet. BIND is purely about what *must* be in the dashboard.

### Pass 1 — Use Case Group Expansion

Given `use_case_group = "soc2_audit"`, expand from `metric_use_case_groups.json`:

```json
{
  "required_groups": ["compliance_posture", "control_effectiveness", "risk_exposure"],
  "optional_groups": ["operational_security", "remediation_velocity"],
  "default_audience": "auditor",
  "default_timeframe": "monthly"
}
```

Optional group inclusion is **complexity-gated**:
- `high` → all optional groups included
- `medium` → first optional group only
- `low` → required groups only, no optionals

### Pass 2 — Control Taxonomy Join

Given `framework = ["soc2"]`, join resolved `focus_areas` from each required metric group against `control_domain_taxonomy.json`:

| Metric Group | Focus Areas | Matched Controls |
|---|---|---|
| `compliance_posture` | training_compliance, access_control | CC1, CC6 |
| `control_effectiveness` | change_management, access_control | CC5, CC8 |
| `risk_exposure` | vulnerability_management, data_protection | CC3, CC7, CC9 |

**Output — Resolution Payload:**
```json
{
  "resolved_metric_groups": {
    "required": ["compliance_posture", "control_effectiveness", "risk_exposure"],
    "optional_included": ["operational_security", "remediation_velocity"]
  },
  "control_anchors": [
    { "id": "CC1", "domain": "control_environment",     "focus": "training_compliance",      "risk_categories": ["untrained_staff"] },
    { "id": "CC3", "domain": "risk_assessment",         "focus": "vulnerability_management", "risk_categories": ["unassessed_risk"] },
    { "id": "CC5", "domain": "control_activities",      "focus": "change_management",        "risk_categories": ["control_failure"] },
    { "id": "CC6", "domain": "logical_physical_access", "focus": "access_control",           "risk_categories": ["unauthorized_access"] },
    { "id": "CC7", "domain": "system_operations",       "focus": "vulnerability_management", "risk_categories": ["unpatched_systems"] },
    { "id": "CC8", "domain": "change_management",       "focus": "change_management",        "risk_categories": ["configuration_drift"] },
    { "id": "CC9", "domain": "risk_mitigation",         "focus": "data_protection",          "risk_categories": ["data_leak"] }
  ],
  "focus_areas": ["training_compliance", "access_control", "vulnerability_management", "change_management", "data_protection"],
  "risk_categories": ["untrained_staff", "unauthorized_access", "unpatched_systems", "configuration_drift"],
  "timeframe": "monthly",
  "audience": "auditor",
  "complexity": "high"
}
```

### What BIND Anchors Downstream

The Resolution Payload serves three downstream consumers:

1. **SCORE** — control anchors constrain which templates are viable; focus areas constrain which chart types are appropriate
2. **Posture Strip** — one strip cell is reserved per control anchor; cells are sourced from the Metric Catalog by `control_id` match
3. **EPS IntentSpec semantics** — every chart's `semantics.control_id` is auto-populated from the matched anchor

---

## Stage 3 — SCORE

### What It Does

Takes the Resolution Payload and runs **two parallel scoring passes** — one against layout templates, one against chart type candidates. Produces ranked candidate lists, not a single selection. SCORE never makes a final choice; that belongs to RECOMMEND.

### Pass A — Template Scoring

The full 23-template pool is **pre-filtered** by domain and theme before scoring, reducing the scoring set to 3–6 candidates. Scoring runs on the filtered set only.

**Scoring dimensions:**

| Dimension | Weight | Source |
|---|---|---|
| Domain match | 30 pts | `domain_taxonomy.domain` vs template `best_for` tags |
| Audience match | 20 pts | `complexity` tier vs template complexity rating |
| Control coverage | 20 pts | % of control anchors coverable by template's posture strip + panel slots |
| Metric group fit | 15 pts | Required metric groups mappable to template panel components |
| Theme match | 10 pts | `theme_hint` vs template origin (light/dark) |
| Vector similarity boost | +15 pts | Embedding distance between goal text and template embedding text |

**Output — Ranked template candidates:**
```json
[
  { "template_id": "hybrid-compliance", "score": 87, "coverage_gaps": [] },
  { "template_id": "command-center",    "score": 71, "coverage_gaps": ["CC5", "CC8"] },
  { "template_id": "posture-overview",  "score": 58, "coverage_gaps": ["CC3", "CC7", "CC9"] }
]
```

`coverage_gaps` lists control anchors from the Resolution Payload that the template cannot surface — this feeds directly into the RECOMMEND rationale. Gaps are **never silently swallowed**.

### Pass B — Chart Type Scoring

For each resolved metric group, score chart type candidates from the EPS catalog against the metric's `display_type` hint, `grain`, and the audience's complexity tier.

| Metric Group | Top Candidate | Runner-Up | Ranking Reason |
|---|---|---|---|
| `compliance_posture` | gauge + kpi_card | bar_compare | Strip-native for auditors |
| `control_effectiveness` | bar_compare (per control) | radar | Per-control readability |
| `risk_exposure` | treemap | scatter | Hierarchical risk visibility |
| `operational_security` | signal_meter + list_card | heatmap | Operational scan pattern |
| `remediation_velocity` | trend_line | waterfall | Time-series SLA tracking |

### Scoring Contract

SCORE outputs a **Scored Candidate Set** — ranked options with scores, gaps, and rationale fragments. RECOMMEND consumes this; it never reaches the human directly.

---

## Stage 4 — RECOMMEND

### What It Does

Consumes the Scored Candidate Set and **assembles it into human-readable options** for the VERIFY stage. RECOMMEND is the presentation layer between the machine's scoring logic and the human's decision.

It surfaces **top-3 layout options** with:
- The template name, score, and plain-language ranking rationale
- Which control anchors it covers vs. misses
- The proposed posture strip cell lineup (one cell per anchor)
- A chart type selection per panel
- Pre-computed **adjustment handles** the human can apply at VERIFY without re-running the pipeline

### Recommendation Output Structure

```
RECOMMENDED OPTION 1 — hybrid-compliance (score: 87)
  Rationale:    Best coverage of all 7 control anchors. Three-panel layout gives
                dedicated space for posture strip, causal path detail, and AI chat.
                Matches auditor complexity tier (high). Full required + optional
                metric groups accommodated.
  Strip cells:  CC1 → Training Completion %  | CC6 → Open Access Reviews
                CC7 → Unpatched Critical      | CC3 → Risk Score
                CC5 → Control Pass Rate       | CC8 → Change Failure Rate
                CC9 → Data Protection Score
  Panels:       Left:   SOC2 control list with severity filter
                Center: Gauge (posture) + Bar (per-control effectiveness) + Signal meters
                Right:  AI chat seeded with SOC2 auditor context
  Coverage:     ✅ Full — no gaps

RECOMMENDED OPTION 2 — command-center (score: 71)
  Rationale:    Strong operational coverage. Misses CC5/CC8 (change management).
                Consider if audit scope excludes change controls.
  Coverage gap: CC5 (control_activities), CC8 (change_management)
  Adjustment:   promote_control(CC5, CC8) → adds both to strip + panel section

RECOMMENDED OPTION 3 — posture-overview (score: 58)
  Rationale:    Simpler two-panel layout suitable for executive summary only.
                Significant gap across operational controls.
  Coverage gap: CC3, CC7, CC8, CC9
  Adjustment:   Switch to hybrid-compliance if full audit evidence is required
```

### Pre-Computed Adjustment Handles

| Handle | What It Changes | Re-triggers |
|---|---|---|
| `promote_control(CC5)` | Adds CC5 to strip + creates panel section | Chart scoring only |
| `swap_chart(risk_exposure, scatter)` | Replaces treemap with scatter | Nothing |
| `add_optional_group(remediation_velocity)` | Adds trend_line panel | Layout re-score |
| `change_timeframe(quarterly)` | Adjusts all metric grain bindings | Data binding only |
| `override_theme(dark)` | Switches to dark theme primitives | Nothing |

Adjustments that require re-running a full stage (e.g., changing `use_case_group`) surface a warning and route back to the appropriate stage rather than applying silently.

---

## Stage 5 — VERIFY (Human-in-the-Loop)

### What It Does

VERIFY is the **approval gate**. Nothing is committed to the Spec Store, no data queries are executed, and the renderer is not called until a human explicitly approves. The Unified Dashboard Spec holds `status: pending_approval` throughout VERIFY.

### What the Human Sees

1. **Recommendation card** — top-scored option with full rationale, strip cells, and panel breakdown
2. **Alternative options** — options 2 and 3 as switchable views with their gap summaries
3. **Coverage map** — visual grid of which control anchors are covered/missing per option
4. **Adjustment panel** — the pre-computed handles, each one-click with an inline description of what changes
5. **Spec diff view** — if an adjustment is applied, a before/after diff of the spec is shown before confirming

### VERIFY Decision Paths

```
Human reviews RECOMMEND output
         │
         ├── APPROVE (no changes)
         │     → status: pending_approval → approved
         │     → Spec committed to Spec Store
         │     → Renderer triggered
         │
         ├── APPROVE WITH ADJUSTMENT (applies one or more handles)
         │     → Adjustment applied to spec
         │     → Diff shown to human
         │     → On confirm: committed, rendered
         │
         ├── SWITCH OPTION (pick option 2 or 3)
         │     → Spec rebuilt from ranked alternative
         │     → VERIFY re-presents with new option as primary
         │
         ├── REQUEST RE-SCORE (change a parameter: timeframe, add framework, etc.)
         │     → Routes back to BIND with updated parameters
         │     → SCORE + RECOMMEND re-run
         │     → VERIFY re-presents
         │
         └── REJECT (goal was wrong, start over)
               → Routes back to RESOLVE
               → Prior session saved as rejected draft with rejection note
```

### Committed Spec — Full Contract

```json
{
  "dashboard_id": "uuid",
  "status": "approved",
  "approved_by": "user_id",
  "approved_at": "2025-03-05T...",

  "goal": "soc2_audit",
  "use_case_group": "soc2_audit",
  "domain": "hybrid_compliance",
  "audience": "auditor",
  "framework": ["soc2"],
  "timeframe": "monthly",
  "resolution_path": "decision_tree",

  "compliance_context": {
    "control_anchors": ["CC1", "CC3", "CC5", "CC6", "CC7", "CC8", "CC9"],
    "focus_areas": ["training_compliance", "access_control", "vulnerability_management", "change_management"],
    "risk_categories": ["untrained_staff", "unauthorized_access", "unpatched_systems", "configuration_drift"]
  },

  "layout_spec": {
    "template_id": "hybrid-compliance",
    "score": 87,
    "theme": "light",
    "primitives": ["topbar", "posture_strip", "three_panel"],
    "adjustments_applied": []
  },

  "panel_bindings": { "..." : "..." },
  "chart_specs": ["...EPS IntentSpecs with semantics.control_id populated..."],
  "posture_strip": ["...one cell per control anchor..."],

  "pipeline_audit": {
    "resolve_path": "decision_tree",
    "bind_control_count": 7,
    "score_candidates_evaluated": 6,
    "recommend_options_presented": 3,
    "verify_adjustments_applied": 0,
    "verify_options_switched": 0
  }
}
```

The `pipeline_audit` block records exactly how the dashboard was generated: which resolution path fired, how many candidates were evaluated, how many options the human was shown, and what they changed. This is the CCE's own compliance record for the dashboard-generation process.

---

## Complete Pipeline Flow

```
User states goal (freeform or taxonomy pick)
              ↓
        ┌── RESOLVE ──┐
        │ Decision    │  ← fast path (known goal)
        │ Tree Engine │
        │   or        │  ← fallback (ambiguous / freeform)
        │ LangGraph   │
        │ Advisor     │
        └──────┬───────┘
               │  Dashboard Intent Object
               ↓
          ┌── BIND ──┐
          │ Use case │
          │ group ×  │
          │ control  │
          │ taxonomy │
          │ join     │
          └────┬─────┘
               │  Resolution Payload
               ↓
         ┌── SCORE ──┐
         │ Pass A:   │  ← template scoring (pre-filtered by domain/theme)
         │ templates │
         │           │
         │ Pass B:   │  ← chart type scoring per metric group
         │ charts    │
         └─────┬─────┘
               │  Scored Candidate Set
               ↓
       ┌── RECOMMEND ──┐
       │ Top-3 options │
       │ with rationale│
       │ coverage map  │
       │ + adjustment  │
       │ handles       │
       └──────┬────────┘
              │  Recommendation presented to human
              ↓
        ┌── VERIFY ──┐  ← Human approval gate
        │            │
        │ APPROVE    │──────────────────────────────┐
        │ ADJUST     │──→ diff → confirm ────────────┤
        │ SWITCH     │──→ re-present ────────────────┤
        │ RE-SCORE   │──→ back to BIND ──────────────┤
        │ REJECT     │──→ back to RESOLVE            │
        └────────────┘                               │
                                                     ↓
                                        Approved Unified Dashboard Spec
                                                     ↓
                                           Spec Store (committed,
                                            versioned, audited)
                                                     ↓
                                                Renderer
                                      (Layout + Charts + Data Binding)
                                                     ↓
                                              Live Dashboard
```

---

## Stage Responsibilities Summary

| Stage | LLM Required | Human Interaction | Gate Type | Output |
|---|---|---|---|---|
| RESOLVE | Only for freeform goals | None (or conversation) | Classification | Dashboard Intent Object |
| BIND | No | None | Deterministic join | Resolution Payload |
| SCORE | No | None | Ranking | Scored Candidate Set |
| RECOMMEND | Optional (rationale text) | Read-only preview | Presentation | Options + adjustment handles |
| VERIFY | No | **Full approval authority** | **Commit gate** | Approved Unified Dashboard Spec |

---

## Key Design Invariants

**Nothing commits without VERIFY.** The spec is `pending_approval` from generation through VERIFY. No data queries run, no renderer fires, no storage write happens until the human approves.

**SCORE ranks — RECOMMEND explains — VERIFY decides.** The scoring engine produces candidates. RECOMMEND translates scores into human-readable rationale. The human collapses to a final choice. These three responsibilities never bleed across stages.

**Adjustments are pre-computed, not re-generated.** Adjustment handles are calculated during SCORE so they apply instantly at VERIFY without re-running the pipeline. Only adjustments that cross a stage boundary trigger a partial re-run — and the human is told which stage will re-run before they confirm.

**Coverage gaps are always surfaced.** If a control anchor from the Resolution Payload cannot be represented by a given template, RECOMMEND names it explicitly. The human decides if the gap is acceptable. The system never makes that call silently.

**The pipeline_audit block is always written.** Every committed spec records how it was generated, what the human saw, and what they changed. This is the CCE's own process-level compliance trail.
