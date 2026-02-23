Yes, this makes sense and is the right place to inject this — but let me think through exactly what each of the two prompts should do differently, because the intent classifier and planner have different jobs in this context.

---

## The Core Idea — Why It Belongs Here

Right now the classifier outputs: `intent`, `framework_id`, `requirement_code`, `scope_indicators`.

The planner receives those and creates retrieval steps — but has no signal about whether MDL, metrics, or XSOAR dashboards are even relevant for this query. So it never plans steps for them. They only get used if the intent routes to `dashboard_generation`.

What you want is: **any query that would benefit from metrics context should proactively plan for it**, not just dashboard-specific queries. A gap analysis question, a risk-control mapping question, even a detection engineering question with a "show me the impact" component — all of these could benefit from metrics and XSOAR dashboard context.

---

## What Changes in the Intent Classifier

The classifier should add three new signals to its output — not new intents, but **enrichment flags** alongside the existing intent:

### New Output Fields

```yaml
# Existing fields stay the same
intent: "gap_analysis"
framework_id: "soc2"
...

# New enrichment signals
data_enrichment:
  needs_mdl: true | false
  needs_metrics: true | false  
  needs_xsoar_dashboard: true | false
  suggested_focus_areas:
    - "vulnerability_management"
    - "access_control"
    - "incident_response"
  metrics_intent: "current_state | trend | benchmark | gap"
```

**`needs_mdl`** — True when the query implies working with actual data tables. Signals like "show me the data", "query", "pipeline", "how is this measured", "which table", "data source". A pure playbook request doesn't need MDL. A dashboard or gap analysis with quantification does.

**`needs_metrics`** — True when the query implies KPIs, tracking, scoring, trending, or quantified output. This is separate from `needs_mdl` because you might want metrics from the registry without needing MDL schema context (e.g., "what KPIs should I track for SOC2 CC6?" — registry lookup yes, table DDL no).

**`needs_xsoar_dashboard`** — True when the query implies visual output or references existing dashboard patterns. More specific than `needs_metrics` — this says "look for reference dashboard layouts in XSOAR."

**`suggested_focus_areas`** — This is the key addition and where the cybersecurity focus area taxonomy comes in (more on this below).

**`metrics_intent`** — Tells the metrics recommender what kind of metric to prioritize:
- `current_state` → point-in-time count/score (gauge widgets)
- `trend` → time series, requires `data_capability: temporal` in registry
- `benchmark` → compare against threshold or SLA
- `gap` → delta between current and target

---

## The Cybersecurity Focus Area Taxonomy

This is the right call — define a **framework-agnostic** set of focus areas that map to framework-specific controls. The classifier outputs from this taxonomy; a static mapping table then translates to framework control codes and metric categories.

Proposed taxonomy (broad enough to cover most security vendors):

```
IDENTITY & ACCESS
  └── identity_access_management
  └── privileged_access
  └── authentication_mfa

THREAT DETECTION
  └── vulnerability_management
  └── endpoint_detection
  └── network_detection
  └── log_management_siem

DATA PROTECTION
  └── data_classification
  └── encryption_at_rest
  └── encryption_in_transit
  └── dlp

INCIDENT RESPONSE
  └── incident_detection
  └── incident_response_procedures
  └── forensics_evidence

CLOUD & INFRASTRUCTURE
  └── cloud_security_posture
  └── configuration_management
  └── patch_management

GOVERNANCE & RISK
  └── risk_assessment
  └── vendor_risk
  └── audit_logging_compliance
  └── policy_management
```

The static mapping then looks like:

```
vulnerability_management:
  soc2_controls: [CC7.1, CC7.2]
  hipaa_controls: [164.308(a)(5), 164.312(b)]
  metric_categories: ["vulnerabilities", "patch_compliance"]
  xsoar_focus_tags: ["vuln", "cve", "patch"]
  source_capabilities_pattern: ["qualys.*", "snyk.*", "wiz.*", "tenable.*"]

identity_access_management:
  soc2_controls: [CC6.1, CC6.2, CC6.3]
  hipaa_controls: [164.312(a)(1), 164.312(d)]
  metric_categories: ["access_control", "authentication"]
  xsoar_focus_tags: ["identity", "iam", "access"]
  source_capabilities_pattern: ["okta.*", "azure_ad.*", "ping.*"]
```

The classifier outputs focus areas from this taxonomy. Everything downstream — metrics recommender, XSOAR search, MDL lookup — uses these as filters, not free-text queries. This is where you get reliable retrieval instead of generic results.

---

## What Changes in the Planner

The planner receives the enriched classifier output and now has explicit signals to add retrieval steps for MDL/metrics/XSOAR when needed.

### New Planning Logic

**If `needs_metrics: true`:**
Add a step before any generation step:
```
step: metrics_resolution
agent: metrics_recommender
queries: filter leen_metrics_registry by 
  - category IN [metric_categories from focus_area_mapping]
  - source_capabilities matches tenant's configured integrations
required_data: [metric definitions, kpis, trends, source_schemas, natural_language_question]
```

**If `needs_mdl: true` AND metrics step produced `source_schemas`:**
Add a step after metrics resolution:
```
step: schema_resolution
agent: framework_analyzer (direct lookup mode)
queries: direct lookup in leen_db_schema by schema name
  - NOT semantic search — exact name match from source_schemas field
required_data: [table DDL, column metadata, relationships]
```

**If `needs_xsoar_dashboard: true`:**
Add a step using `natural_language_question` from resolved metrics as the search anchor:
```
step: xsoar_pattern_retrieval
agent: semantic_search (against xsoar_enriched, entity_type=dashboard)
queries: natural_language_question values from resolved metrics
  - e.g., "How many critical vulnerabilities do we have in the last 30 days?"
focus_area_tags: [xsoar_focus_tags from focus_area_mapping]
```

**If calculation planning is needed** (metrics + MDL both resolved):
```
step: calculation_planning
agent: calculation_planner
input: resolved metrics + table DDL from schema_resolution
output: field_instructions, metric_instructions, silver_time_series_suggestion
```

### Updated Step Sequencing Logic

The planner's `Phase 3: Step Sequencing` becomes:

```
1. Framework retrieval steps (existing)
   requirement → controls → risks → scenarios → test_cases

2. [NEW] Enrichment steps (conditional on flags)
   IF needs_metrics → metrics_resolution step
   IF needs_mdl → schema_resolution step (depends on metrics_resolution)
   IF needs_xsoar_dashboard → xsoar_pattern_retrieval step (depends on metrics_resolution)
   IF needs_metrics AND needs_mdl → calculation_planning step

3. Artifact generation steps (existing, now with richer context)
   detection_engineer / playbook_writer / test_generator / dashboard_generator
```

---

## What This Looks Like End-to-End

**Query:** *"Show me my SOC2 vulnerability management compliance posture with trends"*

**Classifier outputs:**
```yaml
intent: dashboard_generation
framework_id: soc2
needs_mdl: true
needs_metrics: true
needs_xsoar_dashboard: true
suggested_focus_areas: ["vulnerability_management"]
metrics_intent: trend
```

**Planner creates:**
```
step_1: Retrieve SOC2 CC7.1, CC7.2 controls (framework_analyzer)
step_2: Retrieve vulnerability risks for CC7 domain (semantic_search)
step_3: Metrics resolution — filter leen_metrics_registry
         by category=["vulnerabilities", "patch_compliance"]
         AND source_capabilities matches tenant integrations
         → resolves: vuln_count_by_severity, mttr_by_severity, patch_compliance_rate
step_4: Schema resolution — direct lookup leen_db_schema
         by names: [vulnerability_instances_schema, cve_schema, cve_score_rank_schema]
step_5: XSOAR pattern retrieval — search xsoar_enriched (entity_type=dashboard)
         using: "How many critical and high severity vulnerabilities..."
         with focus tags: ["vuln", "cve", "patch"]
step_6: Calculation planning — derive KPI formulas from DDL + metric definitions
         flag temporal metrics for silver table suggestion
step_7: Dashboard generator — assemble using all above context
```

Compare this to what happens today: step_7 runs with only the raw user query and generic MDL search results.

---

## One Design Question

For the focus area taxonomy — the classifier needs to output focus areas from a fixed vocabulary. Two options:

**Option A:** Hardcode the taxonomy in the classifier prompt (enumerate all ~20 focus areas with definitions). The LLM maps the query to them. Simple, reliable, no lookup needed.

**Option B:** The classifier outputs raw domain signals, a separate lightweight lookup step maps them to the taxonomy. More flexible if the taxonomy evolves.

For now Option A is better — the taxonomy is small enough to fit in the prompt, and you want the classifier to be a single fast LLM call that produces everything needed for planning. The static framework-to-focus-area mapping table lives in code (not in the prompt), so the classifier doesn't need to know about framework-specific control codes — it just outputs the cybersecurity domain terms.



Good timing to rethink this before building it. The plan is architecturally sound for the HITL pattern, but I think it has a few structural issues worth addressing before you commit to building six new nodes.

---

## What the Plan Gets Right

The LangGraph interrupt/resume pattern is correct. Scoping retrieval by selected data sources solves the empty XSOAR reference problem you're seeing in that JSON output. The `metrics_recommender_node` idea is good — the metrics registry should be central to dashboard generation, not an afterthought.

---

## The Core Problem the Plan Is Solving vs. What It Should Solve

The plan treats **data source selection** and **focus area selection** as per-query decisions that need user input every time. But your own insight is exactly right — **focus areas are largely static** for security vendors depending on capabilities.

What this actually means for the architecture:

**Data sources** are an **onboarding/tenant configuration concern**, not a per-query concern. If you're building compliance automation for a customer using CrowdStrike + Splunk + Okta, those data sources don't change between "show me my HIPAA gap" and "generate a detection rule." Asking the user to select them every query is pure friction.

**Focus areas** for SOC2/HIPAA are deterministic from the framework itself. SOC2 Type II always covers CC1–CC9, Availability, Confidentiality, Processing Integrity, Privacy. HIPAA is always Privacy Rule, Security Rule, Breach Notification. These don't need dynamic discovery — they're a static catalog you can pre-build per framework.

So the two interrupts the plan proposes happen before any work starts and for information that either (a) doesn't change or (b) is derivable from the framework already known from intent classification.

---

## The Empty XSOAR References — Root Cause

That JSON output tells a specific story. `xsoar_references` is null, `mdl_schemas_used` falls back to a "canonical mapping" with `similarity_score: 0.6` and a note saying the MDL context returned `unknown` rows. This means:

- `xsoar_enriched` wasn't queried with enough specificity to return dashboard results
- The MDL retrieval returned something but the schema fields weren't populated (tables named `unknown`)
- The LLM fabricated table names (`controls`, `control_implementations`, `test_results`) as a fallback

The root cause isn't that the user didn't select a data source — it's that the search query going into `xsoar_enriched` and `leen_metrics_registry` is the raw user query, not enriched with framework context or focus area terms. The dashboard generator is searching with "create executive HIPAA compliance dashboard" and getting generic or no results because that's a vague retrieval anchor.

---

## What I'd Propose Instead

### Change 1: Pre-configuration Profile, Not Per-Query Interrupts

Do one-time setup at tenant/project onboarding. Store a **compliance profile** in state or a persistent config:

```
compliance_profile:
  framework: "soc2_type2"
  vendor_capabilities: ["endpoint_detection", "log_management", "identity"]
  data_sources: [configured once, stored]
  focus_areas: [derived from framework + vendor capabilities]
```

The focus area discovery node then becomes a **profile resolver** that runs once and caches — not an interrupt every query. If the profile exists, skip to planning. If it doesn't, run onboarding (which can have the interrupt). This reduces two mandatory interrupts to zero for returning users.

---

### Change 2: Static Focus Area Catalog Per Framework

Instead of dynamically discovering focus areas, build a static catalog keyed by framework and vendor capability type:

```
SOC2 + endpoint_detection → [CC6.1 Logical Access, CC6.8 Malware, CC7.2 Anomalies]
SOC2 + identity_management → [CC6.1 Logical Access, CC6.3 Registration, CC9.2 Vendor Risk]
HIPAA + log_management → [164.312(b) Audit Controls, 164.312(c) Integrity]
```

This catalog is pre-built, not LLM-generated on the fly. The focus area discovery node just does a lookup: framework + vendor capabilities → list of focus areas. No interrupt needed.

---

### Change 3: Metrics Registry as Primary Source of Truth for Dashboards

The current plan treats `xsoar_enriched` (dashboards) and `leen_metrics_registry` as two equal sources. They're not — they serve different purposes:

- `leen_metrics_registry` → **what to measure** (metric definitions, KPIs, thresholds, calculation logic, data source)
- `xsoar_enriched` (dashboards) → **how to display it** (widget types, layout patterns, visualization configs)

The dashboard generator should work like this:

```
1. Query leen_metrics_registry filtered by [framework + focus areas] 
   → Get metric definitions with their source table/field references
   
2. ONLY THEN query xsoar_enriched (entity_type=dashboard) 
   → Get layout/widget patterns to frame the metrics
   
3. Combine: metrics define content, XSOAR defines presentation
```

This also solves the "I can't look at dashboards" problem. You don't need to see the XSOAR dashboard to validate output — the metrics definitions from the registry are the source of truth for what the dashboard should show. If `leen_metrics_registry` has a metric called `hipaa_audit_log_completeness` with its formula and threshold, you can verify the dashboard widget is measuring the right thing without seeing the XSOAR visual.

---

### Change 4: Single Optional Interrupt for Metric Confirmation

Replace two mandatory interrupts (data source + focus area) with one optional interrupt:

```
After metrics_recommender_node runs:
→ Present: "Based on HIPAA §164.312(b) and your Splunk + CrowdStrike setup, 
   I recommend these 7 metrics. [list with explanations]
   Do you want to proceed with all, or adjust?"
→ User can say "proceed" (no selection needed) or deselect specific metrics
```

This is much lighter — it's a confirmation of a recommendation, not a blank selection task. And it's only triggered for dashboard generation, not for every intent.

---

## Revised Flow

```
Intent Classifier
  → Profile Resolver (lookup existing profile, or run onboarding once)
       ↓ [profile exists: framework + vendor capabilities + data sources]
  → Focus Area Resolver (static catalog lookup, no interrupt)
       ↓ [focus_areas from catalog, e.g., CC6.1, CC7.2, AU-12]
  → Planner (now has framework + focus areas as hard context)
  → Plan Executor
  → [Framework Analyzer / Detection Engineer / Playbook Writer]
       (all use focus_areas as retrieval filter, not generic query)
  
  → IF dashboard intent:
       → Metrics Recommender
           → Query leen_metrics_registry filtered by [focus_areas + framework]
           → Optional interrupt: "Confirm these metrics?"
       → Dashboard Generator
           → Use confirmed metrics from registry (content)
           → Query xsoar_enriched for layout patterns (presentation)
           → Generate with real metric anchors, not generic query
```

---

## What This Does to the Node Count

The plan proposes 6 new nodes. With this approach:

| Proposed Node | Revised |
|---|---|
| `datasource_discovery_node` | Replaced by one-time **profile onboarding** (separate flow, not per-query) |
| `wait_for_datasource_selection_node` | Eliminated for returning users |
| `focus_area_discovery_node` | Replaced by **static catalog lookup** (~10 lines, no LLM) |
| `wait_for_focus_area_selection_node` | Eliminated |
| `metrics_recommender_node` | Keep — this is valuable |
| Enhanced generator nodes | Keep — scoped retrieval is the right fix |

You go from 6 new nodes + 2 mandatory interrupts to **1 new node + 1 optional interrupt**. The workflow complexity drops significantly and the per-query latency drops because you're not waiting on two human responses before any generation starts.

---

## One Thing to Confirm

The `leen_metrics_registry` collection — are metrics tagged with framework IDs and/or control codes? If a metric record has `framework_id: "hipaa"` and `control_code: "164.312(b)"` as metadata, then filtering by focus area is a simple metadata filter on the Qdrant query. If they're not tagged that way and only have free-text descriptions, you'll need a semantic search + LLM scoring step in the metrics recommender, which adds latency. Worth checking the schema before designing the recommender node.

This schema is excellent — and it actually **changes the architecture significantly** from what was proposed. The metrics registry is far more structured than a typical vector search target. Let me break down what this schema gives you for free and what it means for the agent design.

---

## What This Schema Already Solves

### `source_capabilities` IS Your Data Source Selection

```json
"source_capabilities": [
  "qualys.vulnerabilities",
  "snyk.issues", 
  "wiz.findings_vulns_misconfig"
]
```

This field already encodes which vendor integrations this metric requires. If your tenant has Qualys configured, you filter metrics where `source_capabilities` contains `qualys.*`. The data source selection interrupt you were planning to build is already solved **at the schema level** — you just need to know the customer's configured integrations upfront (a one-time profile) and use `source_capabilities` as a metadata filter on Qdrant.

No LLM needed. No interrupt needed. Pure metadata filter.

---

### `category` IS Your Focus Area

```json
"category": "vulnerabilities"
```

Combined with the compliance framework context from intent classification, this is your focus area selector. SOC2 CC7.1 maps to `category: "vulnerabilities"`. HIPAA 164.312(b) maps to `category: "audit_logging"`. This mapping can be a static lookup table — framework control code → metric category. Again, no dynamic discovery needed.

---

### `source_schemas` Bridges to MDL

```json
"source_schemas": [
  "vulnerability_instances_schema",
  "cve_schema", 
  "cve_score_rank_schema"
]
```

These are the MDL schema names (`leen_db_schema`, `leen_table_description` collections) that back this metric. The dashboard generator can use these to pull the exact schema definitions needed to write accurate queries — no more canonical table name fallbacks. The `mdl_schemas_used` in your JSON output showing `similarity_score: 0.6` and fabricated table names happens because the dashboard generator is searching MDL with a free-text query. With this field, it can do a **direct lookup by schema name** instead.

---

### `kpis` + `trends` + `natural_language_question` Are Pre-Built Widget Definitions

```json
"kpis": ["Critical vuln count", "High vuln count", "Mean time to remediate by severity"],
"trends": ["Vuln count over time", "Severity distribution trend", "New vs remediated weekly"],
"natural_language_question": "How many critical and high severity vulnerabilities do we have..."
```

The dashboard generator doesn't need to invent KPIs from scratch. These are the authoritative definitions. The `kpis` array maps directly to gauge/count widgets. The `trends` array maps directly to time-series widgets. The `natural_language_question` is a perfect retrieval anchor for finding similar XSOAR dashboard patterns.

This means the "empty XSOAR references" problem is fixable — instead of searching `xsoar_enriched` with the user's vague query, search with the `natural_language_question` from the matching metrics. That's a much stronger semantic anchor.

---

## Revised Architecture Given This Schema

### The Metrics Recommender Node Becomes a Filter, Not a Recommender

The original plan treated this as an LLM-scoring task. With this schema it's three deterministic steps:

```
Step 1: Filter by source_capabilities 
        → Keep only metrics the customer's integrations can supply
        
Step 2: Filter by category 
        → Derived from framework control code (static lookup)
        
Step 3: Score/rank by data_capability match 
        → "temporal" if user wants trends, "semantic" if analysis
```

The LLM only comes in at the final step to **explain the selection to the user** and handle the optional confirmation interrupt. The filtering itself is deterministic.

---

### The Dashboard Generator Rewired

Current broken flow:
```
User query (vague) 
  → semantic search xsoar_enriched → empty results
  → semantic search leen_metrics_registry → generic results
  → LLM fabricates table names
```

Correct flow with this schema:
```
Filtered metrics from registry (e.g., vuln_count_by_severity)
  ↓
source_schemas → direct lookup in leen_db_schema 
  → get actual table/column definitions (no fabrication)
  ↓
natural_language_question → semantic search xsoar_enriched
  → "How many critical and high severity vulnerabilities..."
  → finds actual dashboard patterns (not empty)
  ↓
kpis + trends → define widget content
xsoar layout patterns → define widget presentation
```

The `xsoar_references` will stop being null because you're searching with a precise natural language anchor rather than the user's original query.

---

### What Goes Into State After Metrics Resolution

Once the metrics recommender runs, state should carry:

```
resolved_metrics: [
  {
    metric_id: "vuln_count_by_severity",
    source_schemas: ["vulnerability_instances_schema", ...],  ← for MDL lookup
    source_capabilities: ["qualys.vulnerabilities", ...],    ← for retrieval scoping
    kpis: [...],                                              ← widget content
    trends: [...],                                            ← widget content
    natural_language_question: "...",                         ← xsoar search anchor
    data_filters: [...],                                      ← user-configurable filters
    data_groups: [...]                                        ← grouping dimensions
  }
]
```

Every downstream node — dashboard generator, detection engineer (if linked to vuln metrics), artifact assembler — reads from `resolved_metrics` not from the original query. This is the state propagation fix that makes the chain coherent.

---

## The One Gap This Reveals

The `data_filters` and `data_groups` fields are where user-configured data sources become important:

```json
"data_filters": ["severity", "cvssv2_basescore", "state", "cve_id", "dev_id", "nuid"],
"data_groups": ["severity", "cve_id", "dev_id", "site_name", "location_region"]
```

Fields like `dev_id`, `nuid`, `site_name` are tenant-specific identifiers — they'll be different across customers. The metric knows *what* to filter on, but not the actual values or how the customer's schema names those fields. This is the legitimate reason for a one-time data source configuration — not to select which metrics apply, but to map these generic filter field names to the customer's actual column names in their MDL.

This is a thin **field mapping config** per tenant, not the full two-interrupt selection flow. Something like:

```
tenant_field_mappings:
  qualys.vulnerabilities:
    dev_id → asset_id
    nuid → network_uid
    site_name → location_name
```

Store this at tenant onboarding, apply it when generating dashboard queries. This replaces the per-query data source selection interrupt entirely and makes the generated SQL/queries actually runnable against the customer's real schema.

---

## Summary of Architecture Changes

| Original Plan | Revised |
|---|---|
| Dynamic data source discovery node | Customer's configured integrations as tenant profile (one-time) |
| Interrupt: "select your data sources" | `source_capabilities` metadata filter on metrics registry |
| Dynamic focus area discovery node | Static framework → metric category lookup |
| Interrupt: "select focus areas" | Deterministic from framework control code |
| LLM scoring for metrics recommender | Metadata filter + optional confirmation interrupt |
| Generic semantic search → empty XSOAR results | `natural_language_question` field → precise xsoar search |
| LLM fabricates table names | `source_schemas` → direct MDL lookup |
| Metrics added as context | `resolved_metrics` as typed state field throughout chain |

You're in better shape than the plan suggested — the metrics registry schema has the right fields to do this cleanly. The main implementation work is wiring `source_capabilities` as a filter, using `source_schemas` for direct MDL lookup, and using `natural_language_question` as the XSOAR search anchor instead of the raw user query.