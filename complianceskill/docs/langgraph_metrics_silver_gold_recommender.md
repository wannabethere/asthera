# Detection & Triage Engineering Workflow Architecture

**Version:** 1.0 — Architecture Only  
**Scope:** New workflow engine for HIPAA/SOC2 breach detection with data-source-aware metric generation  
**Status:** Pre-implementation design

---

## 1. Overview

This workflow is a focused two-agent engine that operates strictly within the boundary of configured data sources. It does not hallucinate table names, invent metrics, or reference schemas not explicitly available in the system. Every output — detection rule, triage step, KPI, or widget recommendation — is traceable to a real data source or framework control.

### Two Core Agents

**Detection Engineer** — Generates SIEM rules (Splunk SPL, Sigma, KQL) anchored to framework controls, risks, and attack scenarios retrieved from the Framework KB.

**Triage Engineer** — Identifies how to measure and calculate the KPIs relevant to the detected risk. Works exclusively from the Metrics Registry, MDL schemas, and GoldStandardTables. Produces the medallion architecture plan (bronze → silver → gold) and a set of natural language metric recommendations.

---

## 2. Workflow Graph

```
User Query
    │
    ▼
┌─────────────────────┐
│  INTENT CLASSIFIER  │  → Classifies intent + extracts enrichment signals
│                     │    (needs_metrics, needs_mdl, focus_areas, metrics_intent)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      PLANNER        │  → Builds atomic retrieval + execution steps
│                     │    Inputs: focus_area_config, available_frameworks
│                     │    Outputs: semantic questions, retrieval steps, playbook template
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│                  RETRIEVAL PHASE                     │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Framework  │  │   Metrics   │  │    MDL      │ │
│  │  Controls & │  │  Registry   │  │   Schema    │ │
│  │  Risks      │  │  Lookup     │  │   Lookup    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         └────────────────┴────────────────┘         │
│                          │                           │
│                          ▼                           │
│              ┌─────────────────────┐                 │
│              │  RELEVANCE SCORING  │                 │
│              │  & VALIDATION       │                 │
│              └──────────┬──────────┘                 │
└─────────────────────────┼───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                  EXECUTION PHASE                     │
│                                                      │
│  ┌───────────────────┐   ┌───────────────────────┐  │
│  │  DETECTION        │   │  TRIAGE               │  │
│  │  ENGINEER         │   │  ENGINEER             │  │
│  │                   │   │                       │  │
│  │  Flow:            │   │  Flow:                │  │
│  │  Raw Events →     │   │  Metrics/KPIs →       │  │
│  │  SIEM Rules →     │   │  Signals →            │  │
│  │  Signals →        │   │  Risks →              │  │
│  │  KPIs →           │   │  Controls             │  │
│  │  Risks →          │   │                       │  │
│  │  Controls         │   │  Input:               │  │
│  │                   │   │  - Scored metrics     │  │
│  │  Input:           │   │  - MDL schemas        │  │
│  │  - Controls       │   │  - GoldStandardTables │  │
│  │  - Risks          │   │  - Focus areas        │  │
│  │  - Scenarios      │   │  - Controls (for       │  │
│  │  - Raw Events     │   │    traceability)      │  │
│  │                   │   │                       │  │
│  │  Output:          │   │  Output:              │  │
│  │  - SIEM rules     │   │  - Signals            │  │
│  │  - Signals        │   │  - Risks              │  │
│  │  - KPIs           │   │  - Controls           │  │
│  │  - Risks          │   │  - Medallion plan     │  │
│  │  - Controls       │   │  - 10+ metric recs    │  │
│  │    (log sources)  │   │                       │  │
│  │                   │   │                       │  │
│  └─────────┬─────────┘   └──────────┬────────────┘  │
└────────────┼──────────────────────  ┼───────────────┘
             │                        │
             ▼                        ▼
┌─────────────────────────────────────────────────────┐
│                  VALIDATION PHASE                    │
│                                                      │
│  ┌─────────────────┐     ┌─────────────────────────┐│
│  │  SIEM Rule      │     │  Metric & Calculation   ││
│  │  Validator      │     │  Validator              ││
│  └────────┬────────┘     └────────────┬────────────┘│
└───────────┼──────────────────────────┼──────────────┘
            │                          │
            ▼                          ▼
         PASS?                      PASS?
            │                          │
     ┌──────┴──────┐            ┌──────┴──────┐
     │   SUCCESS   │            │   FEEDBACK  │
     │             │            │   LOOP      │ ← Max 3 iterations
     └─────────────┘            └──────┬──────┘
                                       │
                                       └→ Back to generator
```

---

## 3. Node Definitions

### 3.1 Intent Classifier

**Purpose:** Classify the query and produce enrichment signals that gate downstream retrieval.

**Inputs:**
- Raw user query

**Outputs — Existing Fields:**
- `intent` — one of the standard intent categories
- `framework_id` — normalized framework identifier
- `requirement_code` — extracted if present
- `confidence_score`
- `scope_indicators` — domain, asset_type, risk_area

**Outputs — New Enrichment Signals:**

| Field | Type | Description |
|---|---|---|
| `needs_mdl` | bool | True when query implies working with real data tables |
| `needs_metrics` | bool | True when query implies KPIs, scoring, or quantified output |
| `suggested_focus_areas` | List[str] | Focus areas from cybersecurity taxonomy (see Section 5) |
| `metrics_intent` | enum | `current_state` / `trend` / `benchmark` / `gap` |
| `playbook_template_hint` | enum | `detection_focused` / `triage_focused` / `full_chain` |

**Classification Logic for New Signals:**

`needs_mdl = True` when query contains: "show me the data", "query", "pipeline", "measure", "calculate", "which table", "data source", "silver", "gold table"

`needs_metrics = True` when query contains: "KPI", "metrics", "track", "score", "compliance rate", "trend", "how many", "measure", "count", "percentage"

`metrics_intent` mapping:
- Queries with "right now", "current", "today" → `current_state`
- Queries with "over time", "trend", "last N days", "weekly" → `trend`
- Queries with "SLA", "target", "threshold", "benchmark" → `benchmark`
- Queries with "gap", "missing", "not meeting", "below" → `gap`

---

### 3.2 Planner

**Purpose:** Decompose the classified intent into atomic, ordered retrieval and execution steps. Every step produces a semantic question used for vector store search. No step may reference a data source not in the configured source list.

**Inputs:**
- Classifier output (intent + enrichment signals)
- `focus_area_config` — hardcoded per-source focus areas (see Section 5)
- `available_frameworks` — list of frameworks loaded in the system
- `available_data_sources` — tenant's configured source integrations

**Outputs:**
- `execution_plan` — ordered list of atomic steps (see schema below)
- `retrieval_questions` — semantic questions for each retrieval step
- `playbook_template` — recommended template structure (see Section 6)
- `data_source_scope` — confirmed list of sources to be used

**Step Schema:**
```
Step:
  step_id:          unique identifier
  phase:            retrieval | execution | validation
  agent:            framework_analyzer | metrics_lookup | mdl_lookup | 
                    scoring_validator | detection_engineer | triage_engineer
  semantic_question: the natural language question used for vector search
  reasoning:        why this step is needed
  required_data:    what fields this step must produce
  dependencies:     step_ids this step depends on
  data_source:      which configured source this step reads from
  focus_areas:      list of focus areas from taxonomy that scope this step
```

**Planning Rules:**

The planner MUST NOT create steps for data sources not in `available_data_sources`. If a metric requires `qualys.vulnerabilities` and Qualys is not configured, that metric step is omitted and noted in plan reasoning.

Step ordering is always:
1. Framework retrieval steps (controls → risks → scenarios)
2. Metrics Registry lookup steps (filtered by focus areas + available sources)
3. MDL Schema lookup steps (direct lookup by `source_schemas` names from metric records)
4. Scoring and validation step
5. Execution steps (detection_engineer, triage_engineer)
6. Validation steps

---

### 3.3 Retrieval Phase

Three parallel retrieval streams, each producing scored results.

#### 3.3.1 Framework Controls & Risks Retrieval

**Source:** `framework_controls`, `framework_requirements`, `framework_risks`, `framework_scenarios` (Qdrant — Framework KB)

**Method:** Semantic search using the planner's semantic questions, filtered by `framework_id` and `focus_areas`

**Output per record:**
```
{
  id, code, name, description,
  control_type, domain,
  relevance_score: float  ← cosine similarity from vector search
}
```

#### 3.3.2 Metrics Registry Lookup

**Source:** `leen_metrics_registry` (Qdrant)

**Filtering logic (in order):**
1. Filter by `source_capabilities` — keep only metrics where at least one source capability matches a configured tenant integration
2. Filter by `category` — derived from focus area → metric category mapping (static lookup, see Section 5)
3. Rank by `data_capability` match — if `metrics_intent = trend`, prefer metrics with `data_capability: temporal`

**Output per metric:**
```
{
  id, name, description, category,
  source_capabilities,     ← confirmed against tenant config
  source_schemas,          ← used for MDL direct lookup
  data_filters,
  data_groups,
  kpis[],
  trends[],
  natural_language_question,
  relevance_score: float   ← semantic similarity + capability match score
}
```

#### 3.3.3 MDL Schema Lookup

**Source:** `leen_db_schema`, `leen_table_description` (Qdrant)

**Method:** Direct lookup by schema name from `source_schemas` field of resolved metrics. NOT semantic search — exact name match to avoid fabricated table references.

**Also queries:** `leen_project_meta` for GoldStandardTables available under the tenant's ProjectId

**Output per schema:**
```
{
  schema_name,
  table_name,
  table_ddl,
  column_metadata[],
  description,
  is_gold_standard: bool  ← true if found in GoldStandardTables for this ProjectId
  relevance_score: float  ← exact match = 1.0, partial = lower
}
```

---

### 3.4 Relevance Scoring & Validation Node

**Purpose:** Cross-score all retrieved artifacts against the identified controls and risks. Drop low-relevance items. Produce a clean, scoped context package for execution agents.

**Scoring dimensions:**

| Dimension | How Scored |
|---|---|
| Metric → Control alignment | Does the metric's `category` map to the control's `domain`? |
| Schema → Metric coverage | Does the schema contain the columns referenced in `data_filters` and `data_groups`? |
| Source capability confirmation | Is the metric's `source_capabilities` satisfied by tenant config? |
| GoldStandard availability | Is a GoldStandardTable available for this metric's category? |

**Drop threshold:** Items scoring below 0.5 composite score are excluded with a note in the plan reasoning.

**Output:** `scored_context` — a trimmed, validated package containing only high-relevance controls, metrics, and schemas.

---

### 3.5 Detection Engineer

**Purpose:** Generate SIEM rules from raw events, transform them through a complete detection pipeline: Raw Events → SIEM Rules → Signals → KPIs → Risks → Controls. Also produces medallion plan and metrics.

**Flow:**
1. **Raw Events → SIEM Rules**: Generate detection rules from raw event sources
2. **SIEM Rules → Signals**: Extract detection signals from rule outputs
3. **Signals → KPIs**: Aggregate signals into KPIs (counts, rates, trends)
4. **KPIs → Risks**: Derive risk assessments from KPI patterns
5. **Risks → Controls**: Map risks to framework controls

**Inputs from scored_context:**
- Controls (filtered by type = detective)
- Risks (filtered by severity threshold)
- Attack scenarios
- Raw Events / Log Sources (from configured data sources)
- MDL schemas (for understanding data structure)
- GoldStandardTables (for medallion planning)

**Tools available (conditional):**
- `cve_to_attack_mapper` — if CVE mentioned in query
- `attack_technique_lookup` — always
- `epss_lookup` — if CVE mentioned
- `cisa_kev_check` — if CVE mentioned

**Sub-phases:**

#### Sub-phase A: Raw Events → SIEM Rules

Generate SIEM detection rules from raw event sources:

```
siem_rules[]:
  - rule_id
  - title
  - platform: splunk | sigma | kql
  - spl_code / sigma_yaml / kql_query
  - mapped_controls[]
  - mapped_attack_techniques[]
  - alert_config: { threshold, severity, timewindow }
  - data_sources_required[]   ← which log sources must be enabled
  - raw_events_source[]       ← which raw event tables/log sources feed this rule
```

#### Sub-phase B: SIEM Rules → Signals

Extract detection signals from SIEM rule outputs:

```
signals[]:
  - signal_id
  - signal_name
  - source_rule_id            ← links back to siem_rule
  - signal_type: alert | event | anomaly
  - detection_criteria        ← what conditions trigger this signal
  - mapped_scenarios[]        ← which attack scenarios this detects
  - raw_event_source          ← which raw event table/log source
  - signal_frequency          ← expected frequency (hourly, daily, etc.)
```

#### Sub-phase C: Signals → KPIs (Aggregates/Trends)

Transform signals into KPIs through aggregation. These KPIs will be integrated into the medallion plan structure:

```
kpis[]:
  - kpi_id
  - kpi_name
  - kpi_type: count | rate | percentage | trend | score
  - source_signal_ids[]       ← which signals feed into this KPI
  - aggregation_window: hourly | daily | weekly
  - calculation_method:       ← natural language description
    - "Count signals per hour"
    - "Calculate rolling 7-day average"
    - "Percentage of signals above threshold"
  - trend_indicators:          ← rising | falling | stable
  - thresholds:                ← alert thresholds for this KPI
  - mapped_controls[]          ← which controls this KPI measures
  - medallion_layer: bronze | silver | gold  ← will be assigned in Sub-phase F
```

**Note:** These KPIs are integrated into the `medallion_plan.kpis[]` structure in Sub-phase F.

#### Sub-phase D: KPIs → Risks

Derive risk assessments from KPI patterns:

```
risks[]:
  - risk_id
  - risk_name
  - risk_severity: critical | high | medium | low
  - source_kpi_ids[]          ← which KPIs indicate this risk
  - likelihood_score: float   ← derived from KPI trends (0-100)
  - impact_score: float       ← from framework risk definition (0-100)
  - risk_category:            ← vulnerability | access | data | incident
  - risk_indicators:           ← what KPI patterns indicate this risk
    - "KPI X showing rising trend"
    - "KPI Y above threshold for 7 days"
  - mapped_scenarios[]        ← which attack scenarios this risk enables
```

#### Sub-phase E: Risks → Controls

Map risks to framework controls:

```
controls[]:
  - control_id
  - control_code
  - control_name
  - control_type: detective | preventive | corrective
  - mapped_risk_ids[]         ← which risks this control addresses
  - control_effectiveness:     ← derived from risk mitigation
    - effectiveness_score: float (0-100)
    - coverage:               ← which risks are fully/partially covered
  - control_gaps:             ← risks not adequately covered
  - recommended_actions:       ← actions to improve control effectiveness
```

#### Sub-phase F: Medallion Plan with KPIs & Metrics

Produce medallion architecture plan with KPIs and metrics integrated:

```
medallion_plan:
  bronze_tables: []           ← raw event sources
  silver_tables: []            ← signal aggregations (time series)
  gold_tables: []              ← KPI-ready tables
  signal_to_kpi_pipeline: []   ← how signals flow to KPIs
  kpi_to_risk_pipeline: []     ← how KPIs inform risk models
  
  # KPIs integrated in medallion plan
  kpis[]:
    - kpi_id
    - kpi_name
    - kpi_type: count | rate | percentage | trend | score
    - source_signal_ids[]       ← which signals feed into this KPI
    - aggregation_window: hourly | daily | weekly
    - calculation_method:       ← natural language description
    - trend_indicators:          ← rising | falling | stable
    - thresholds:                ← alert thresholds
    - medallion_layer: bronze | silver | gold
    - bronze_table:             ← source table
    - silver_table:             ← if needed for time series
    - gold_table:               ← KPI-ready table
  
  # Metrics integrated in medallion plan
  metrics[]:
    - metric_id
    - metric_name
    - source_kpi_ids[]           ← which KPIs this metric tracks
    - metric_type: gauge | trend_line | bar | heatmap | table
    - calculation_steps: []      ← natural language only
    - medallion_layer: bronze | silver | gold
    - bronze_table:             ← source table
    - silver_table:             ← if needed
    - gold_table:               ← metric-ready table
    - traceability:
      - control_codes: []        ← which controls this measures
      - risk_ids: []             ← which risks this addresses
      - signal_ids: []           ← which signals feed this metric
      - kpi_ids: []              ← which KPIs feed this metric
```

#### Sub-phase G: Control & Risk to Metrics Mappings

Map controls and risks to metrics:

```
control_to_metrics_mappings[]:
  - control_id
  - control_code
  - control_name
  - mapped_metric_ids[]         ← which metrics measure this control
  - metric_coverage_score: float ← how well metrics cover this control (0-100)
  - coverage_gaps: []            ← control aspects not covered by metrics
  - recommended_metrics: []     ← additional metrics needed

risk_to_metrics_mappings[]:
  - risk_id
  - risk_name
  - mapped_metric_ids[]         ← which metrics indicate this risk
  - metric_risk_score: float   ← risk score derived from metrics (0-100)
  - risk_indicators: []          ← which metric patterns indicate this risk
  - recommended_metrics: []     ← additional metrics to better track this risk
```

**Complete Output:**
- SIEM rules (Sub-phase A)
- Signals (Sub-phase B)
- KPIs (Sub-phase C) — integrated into medallion plan
- Risks (Sub-phase D)
- Controls (Sub-phase E)
- Medallion plan with KPIs and metrics (Sub-phase F)
- Control to metrics mappings (Sub-phase G)
- Risk to metrics mappings (Sub-phase G)

---

### 3.6 Triage Engineer

**Purpose:** Identify signals, risks, and controls from metrics/KPIs, then plan how to measure and calculate KPIs for the identified risks using available data sources. Produces a medallion architecture plan and metric recommendations. Does not generate SQL — produces natural language calculation steps and identifies the correct medallion layer for each output.

**Flow:**
1. **Metrics/KPIs → Signals**: Identify detection signals from metric patterns
2. **Signals → Risks**: Derive risk assessments from signal patterns
3. **Risks → Controls**: Map risks to framework controls
4. **Medallion Planning**: Plan data architecture with KPIs and metrics
5. **Mappings**: Map controls and risks to metrics

**Inputs from scored_context:**
- Resolved metrics (from Metrics Registry)
- MDL schemas (from direct lookup)
- GoldStandardTables available under ProjectId
- Focus areas
- Controls (for traceability and mapping)
- Risks (for traceability and mapping)
- Scenarios (for context)

**Sub-phases:**

#### Sub-phase A: Metrics/KPIs → Signals

Identify detection signals from metric and KPI patterns:

```
signals[]:
  - signal_id
  - signal_name
  - source_metric_ids[]         ← which metrics indicate this signal
  - source_kpi_ids[]             ← which KPIs indicate this signal
  - signal_type: alert | event | anomaly | trend
  - detection_criteria           ← what metric/KPI patterns trigger this signal
  - signal_frequency              ← expected frequency (hourly, daily, etc.)
  - medallion_layer: bronze | silver | gold
  - mapped_scenarios[]           ← which attack scenarios this signal detects
  - mapped_controls[]             ← which controls this signal supports
```

#### Sub-phase B: Signals → Risks

Derive risk assessments from signal patterns:

```
risks[]:
  - risk_id
  - risk_name
  - risk_severity: critical | high | medium | low
  - source_signal_ids[]          ← which signals indicate this risk
  - source_metric_ids[]           ← which metrics indicate this risk
  - likelihood_score: float       ← derived from signal/metric trends (0-100)
  - impact_score: float          ← from framework risk definition (0-100)
  - risk_category:               ← vulnerability | access | data | incident
  - risk_indicators:              ← what signal/metric patterns indicate this risk
    - "Signal X showing rising trend"
    - "Metric Y above threshold for 7 days"
  - mapped_scenarios[]            ← which attack scenarios this risk enables
  - mapped_controls[]             ← which controls address this risk
```

#### Sub-phase C: Risks → Controls

Map risks to framework controls:

```
controls[]:
  - control_id
  - control_code
  - control_name
  - control_type: detective | preventive | corrective
  - mapped_risk_ids[]            ← which risks this control addresses
  - mapped_signal_ids[]           ← which signals support this control
  - control_effectiveness:        ← derived from risk mitigation
    - effectiveness_score: float (0-100)
    - coverage:                  ← which risks are fully/partially covered
  - control_gaps:                 ← risks not adequately covered
  - recommended_actions:          ← actions to improve control effectiveness
  - metric_coverage:              ← which metrics measure this control
```

#### Sub-phase D: Medallion Architecture Planning with KPIs & Metrics

For each resolved metric, classify its source data and output into the correct medallion layer. KPIs and metrics are integrated into the medallion plan structure:

```
Bronze Layer (source tables):
  - Raw ingest tables from the configured source
  - Direct from MDL schema: vulnerability_instances_schema, cve_schema, etc.
  - No transformation, append-only

Silver Layer (time series / intermediate):
  - When data_capability includes "temporal" → suggest time series silver table
  - Applies lag, lead, rolling windows, deduplication
  - One silver table per source + time grain combination
  - Triggered when metric trends[] array is non-empty

Gold Layer (KPI-ready):
  - GoldStandardTables from ProjectId where available
  - Aggregated to reporting grain (daily, weekly)
  - Directly feeds dashboard widgets
```

The triage engineer outputs a medallion plan with integrated KPIs and metrics:

```
medallion_plan:
  bronze_tables: []           ← raw source tables
  silver_tables: []            ← time series aggregations
  gold_tables: []              ← KPI-ready tables
  
  # KPIs integrated in medallion plan
  kpis[]:
    - kpi_id
    - kpi_name
    - kpi_type: count | rate | percentage | trend | score
    - aggregation_window: hourly | daily | weekly
    - calculation_method:       ← natural language description
    - medallion_layer: bronze | silver | gold
    - bronze_table:             ← source table
    - silver_table:             ← if needed for time series
    - gold_table:               ← KPI-ready table
    - gold_available:           ← true if GoldStandardTable exists
  
  # Metrics integrated in medallion plan (10+ minimum)
  metrics[]:
    - metric_id
    - metric_name
    - natural_language_question: from metrics registry
    - widget_type:              gauge | trend_line | bar | heatmap | table
    - kpi_value_type:           count | percentage | duration | score
    - source_kpi_ids[]:          ← which KPIs this metric tracks
    - calculation_plan_steps: [] ← natural language only
      - step 1: natural language description of the aggregation
      - step 2: description of the filter applied
      - step 3: description of the grouping
    - available_filters:        from data_filters field of metric record
    - available_groups:         from data_groups field of metric record
    - data_source_required:     which source capability feeds this
    - medallion_layer:          bronze | silver | gold
    - bronze_table:             ← name of raw source table
    - needs_silver:             ← bool
    - silver_table_suggestion:
    name:
      grain:                    hourly | daily | weekly
      calculation_steps: []     ← natural language only
      advanced_functions: []     ← lag, lead, rolling_avg, rank, etc.
    - gold_table:               ← name of GoldStandard table or suggested name
    - gold_available:           ← true if GoldStandardTable exists for ProjectId
    - sla_or_threshold:         ← if benchmark metrics_intent, the target value
    - traceability:
      control_codes: []         ← which framework controls this measures
      risk_ids: []              ← which risks this addresses
      kpi_ids: []               ← which KPIs feed this metric
```

Minimum 10 metric recommendations are required. If the Metrics Registry returns fewer than 10 high-relevance metrics for the configured sources, the triage engineer notes the gap and recommends which additional source integrations would unlock more metrics.

#### Sub-phase E: Control & Risk to Metrics Mappings

Map controls and risks to metrics:

```
control_to_metrics_mappings[]:
  - control_id
  - control_code
  - control_name
  - mapped_metric_ids[]         ← which metrics measure this control
  - mapped_signal_ids[]          ← which signals support this control
  - metric_coverage_score: float ← how well metrics cover this control (0-100)
  - coverage_gaps: []            ← control aspects not covered by metrics
  - recommended_metrics: []     ← additional metrics needed

risk_to_metrics_mappings[]:
  - risk_id
  - risk_name
  - mapped_metric_ids[]         ← which metrics indicate this risk
  - mapped_signal_ids[]          ← which signals indicate this risk
  - metric_risk_score: float   ← risk score derived from metrics (0-100)
  - risk_indicators: []          ← which metric/signal patterns indicate this risk
  - recommended_metrics: []     ← additional metrics to better track this risk
```

**Complete Output:**
- Signals (Sub-phase A)
- Risks (Sub-phase B)
- Controls (Sub-phase C)
- Medallion plan with KPIs and metrics (Sub-phase D)
- Control to metrics mappings (Sub-phase E)
- Risk to metrics mappings (Sub-phase E)

---

### 3.7 Validation Phase

#### SIEM Rule Validator
Validates syntax, logic, and completeness of generated SIEM rules. Same as current `siem_rule_validator_node`.

#### Metric & Calculation Validator
New validator specific to triage engineer output:

**Checks:**
- Every metric recommendation has a traceable control code
- Every `source_schemas` reference exists in the MDL lookup results (no fabricated tables)
- Every silver table suggestion has at least 2 calculation steps
- Every gold table reference either matches a known GoldStandardTable or is explicitly marked as a suggestion
- Minimum 10 metric recommendations present
- No SQL or code present in `calculation_plan_steps` (natural language only)

**On failure:** Feedback routed back to triage engineer with specific fix instructions. Max 3 iterations.

---

## 4. State Schema Additions

New fields required in `EnhancedCompliancePipelineState`:

```
# Enrichment signals from classifier
needs_mdl: bool
needs_metrics: bool
suggested_focus_areas: List[str]
metrics_intent: str
playbook_template_hint: str

# Retrieval outputs
scored_metrics: List[Dict]          ← validated metrics from registry
resolved_schemas: List[Dict]        ← MDL schemas from direct lookup
gold_standard_tables: List[Dict]    ← GoldStandardTables for ProjectId

# Execution outputs (Detection Engineer)
signals: List[Dict]                 ← detection engineer output (Sub-phase B)
medallion_plan: Dict                ← detection engineer output (Sub-phase F)
  # Contains: bronze_tables, silver_tables, gold_tables, kpis[], metrics[]
control_to_metrics_mappings: List[Dict]  ← detection engineer output (Sub-phase G)
risk_to_metrics_mappings: List[Dict]     ← detection engineer output (Sub-phase G)

# Execution outputs (Triage Engineer)
signals: List[Dict]                 ← triage engineer output (Sub-phase A)
risks: List[Dict]                   ← triage engineer output (Sub-phase B)
controls: List[Dict]                ← triage engineer output (Sub-phase C)
medallion_plan: Dict                ← triage engineer output (Sub-phase D)
  # Contains: bronze_tables, silver_tables, gold_tables, kpis[], metrics[]
control_to_metrics_mappings: List[Dict]  ← triage engineer output (Sub-phase E)
risk_to_metrics_mappings: List[Dict]     ← triage engineer output (Sub-phase E)

# Data source context
available_data_sources: List[str]   ← tenant configured sources
active_project_id: str              ← for GoldStandardTable lookup
```

---

## 5. Focus Area Configuration

Static per-source configuration. Hardcoded in system config, not LLM-generated.

### Cybersecurity Focus Area Taxonomy

```
THREAT DETECTION
  vulnerability_management
  endpoint_detection
  network_detection
  log_management_siem

IDENTITY & ACCESS
  identity_access_management
  privileged_access
  authentication_mfa

DATA PROTECTION
  data_classification
  encryption_at_rest
  dlp

INCIDENT RESPONSE
  incident_detection
  incident_response_procedures

CLOUD & INFRASTRUCTURE
  cloud_security_posture
  configuration_management
  patch_management

GOVERNANCE & RISK
  risk_assessment
  audit_logging_compliance
  vendor_risk
```

### Focus Area → Framework + Metric Category Mapping

| Focus Area | SOC2 Controls | HIPAA Controls | Metric Categories | Source Capability Pattern |
|---|---|---|---|---|
| `vulnerability_management` | CC7.1, CC7.2 | 164.308(a)(5), 164.312(b) | vulnerabilities, patch_compliance | qualys.*, snyk.*, wiz.*, tenable.* |
| `identity_access_management` | CC6.1, CC6.2, CC6.3 | 164.312(a)(1), 164.312(d) | access_control, authentication | okta.*, azure_ad.*, ping.* |
| `log_management_siem` | CC7.2, CC7.3 | 164.312(b) | audit_logging, siem_events | splunk.*, elastic.*, sentinel.* |
| `incident_detection` | CC7.4, CC7.5 | 164.308(a)(6) | incidents, mttr, alert_volume | crowdstrike.*, sentinelone.*, pagerduty.* |
| `cloud_security_posture` | CC6.6, CC6.7 | 164.308(a)(7) | cloud_findings, misconfigs | wiz.*, prisma.*, aws_security_hub.* |
| `patch_management` | CC7.1 | 164.308(a)(5) | patch_compliance, cve_exposure | qualys.*, tenable.*, tanium.* |
| `authentication_mfa` | CC6.1, CC6.8 | 164.312(d) | mfa_adoption, failed_logins | okta.*, duo.*, azure_ad.* |

---

## 6. Playbook Template

The planner selects one of the following templates based on `playbook_template_hint`. The selected template structure is passed to the execution agents as the output scaffold.

### Template A: Detection-Focused

For queries where SIEM rule generation is the primary output.

```
1. Executive Summary
   - Threat scenario
   - Framework controls addressed
   - Data sources required

2. Detection Rules
   - Rule per scenario (Splunk SPL / Sigma / KQL)
   - Alert configuration
   - Required log sources

3. Triage Metrics
   - Top 5 KPIs for measuring detection effectiveness
   - Each as a natural language question
   - Medallion layer for each KPI

4. Data Source Requirements
   - Required source capabilities
   - Configured vs. missing sources
   - Gap notes if sources unavailable

5. Validation Steps
   - How to test each SIEM rule
   - Expected alert behavior
```

### Template B: Triage-Focused

For queries where metric and KPI generation is the primary output.

```
1. Executive Summary
   - Compliance area and framework
   - Data sources in scope
   - GoldStandardTables available

2. Medallion Architecture Plan
   - Bronze tables (source tables with schema references)
   - Silver tables (time series suggestions)
   - Gold tables (KPI-ready, with availability status)

3. Metric Recommendations (10+)
   - Each metric as natural language question
   - Widget type
   - Calculation steps (natural language)
   - Filters and grouping dimensions
   - Traceability to control codes

4. Gap Analysis
   - Metrics not available due to missing source integrations
   - Recommended integrations to unlock full coverage

5. Implementation Notes
   - Which metrics are available from GoldStandardTables today
   - Which require silver table creation
   - Priority order for implementation
```

### Template C: Full Chain

For `full_pipeline` and `compliance_validation` intents. Combines both Template A and B with an added traceability section linking each SIEM rule to its corresponding KPIs.

---

## 7. What This Workflow Does NOT Do

- Does not query XSOAR collections (deferred to separate workflow)
- Does not generate SQL queries (natural language calculation steps only)
- Does not create data pipelines (medallion plan is a recommendation, not executable code)
- Does not reference schemas not found via direct MDL lookup
- Does not use data sources not present in `available_data_sources`
- Does not exceed 3 validation iterations per artifact

---

## 8. Open Questions Before Implementation

1. **GoldStandardTables access** — How is `active_project_id` determined at runtime? Is it per-tenant config or per-query input?

2. **Minimum metric threshold** — If fewer than 10 metrics are available for the configured sources, should the triage engineer surface partial results or block and surface a gap report?

3. **Calculation step granularity** — Should calculation steps describe a single SQL operation per step (GROUP BY, JOIN, FILTER), or a logical business operation (e.g., "calculate the 30-day rolling average of daily patch rates")?

4. **Silver table naming convention** — Should suggested silver table names follow an existing convention in the MDL (e.g., `silver_{source}_{category}_{grain}`) or be free-form?

5. **Validation of metric traceability** — The metric validator checks that every recommendation has a control code. Should this be a hard failure (block output) or a warning (proceed with note)?