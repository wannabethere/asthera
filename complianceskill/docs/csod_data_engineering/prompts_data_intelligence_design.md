# CSOD Prompt Additions — Data Intelligence Layer (v2.1)
# Additions to 01_intent_classifier.md and 02_csod_planner.md

---

## ─── 01_intent_classifier.md ───────────────────────────────────────────────

### ADD TO: "Available Intent Classifications" — append 4 new data intelligence intents

- `data_discovery` — Explore available schemas, tables, and data assets to understand what analysis
  is possible from the configured data sources. Acts as a capability audit.
- `data_lineage` — Trace where a metric, KPI, or table value originates — from source tables
  through bronze/silver/gold transformations to the final number. Supports both upstream (source)
  and downstream (impact) tracing.
- `data_quality_analysis` — Assess completeness, freshness, referential integrity, and value-range
  accuracy of training data schemas before committing to an analysis.
- `data_planner` — Generate a complete data engineering plan (ingestion specs, medallion
  architecture, dbt model templates, dependency DAG) for a stated analysis goal.

---

### ADD TO: "Phase 2: Intent Classification" trigger patterns — append these 4 blocks

```
- `data_discovery` → "what data do I have", "what tables exist", "show me available schemas",
  "what can I analyse", "what data sources are configured", "what metrics can I build",
  "explore my data", "what's in my CSOD dataset", "data inventory", "asset catalog",
  "what information is available", "discover data", "what do I have access to"

- `data_lineage` → "where does this metric come from", "trace this number back",
  "what tables feed this KPI", "why did this metric change", "data lineage",
  "source of", "which tables are upstream", "what depends on this table",
  "downstream impact", "if I change X what breaks", "data flow from", "how is X calculated",
  "which raw tables drive", "show me the pipeline for"

- `data_quality_analysis` → "can I trust this data", "data quality", "are there nulls",
  "completeness", "how fresh is", "data freshness", "missing records", "duplicates",
  "referential integrity", "data issues", "bad data", "stale data", "is my data reliable",
  "data accuracy", "check data quality", "data health", "before I run analysis"

- `data_planner` → "plan the data pipeline", "what dbt models do I need",
  "design a medallion architecture", "what data engineering", "build me a data plan",
  "ingestion schedule", "how do I set up the data for", "data infrastructure for",
  "what tables do I need to ingest", "plan the pipeline for", "bronze silver gold plan",
  "data engineering roadmap", "what do I need to build"
```

---

### ADD TO: Output format "intent" enum — extend with 4 new values

```
"intent": "... | data_discovery | data_lineage | data_quality_analysis | data_planner"
```

---

### ADD TO: CORE DIRECTIVES — INTENT SELECTION GUIDANCE — append

**Data intelligence intents vs analysis intents:**

- `data_discovery` vs `metrics_recommendations`: Use `data_discovery` when the user is asking
  what data *exists* (asset exploration, capability audit). Use `metrics_recommendations` when
  the user already knows they have CSOD/Workday data and wants to know what to *measure*.

- `data_lineage` vs `anomaly_detection`: Use `data_lineage` when the question is about
  *origin* — how a metric is computed, which tables feed it. Use `anomaly_detection` when the
  question is about *an unexpected value* — detect it first, then offer lineage as a follow-up
  to explain the cause.

- `data_quality_analysis` vs `gap_analysis`: Use `data_quality_analysis` when the concern is
  whether the *data itself* is trustworthy (nulls, freshness, duplicates). Use `gap_analysis`
  when the data is trusted and the question is whether *business performance* meets targets.

- `data_planner` vs `metrics_recommender_with_gold_plan`: Use `data_planner` when the user
  wants the *engineering plan* as the primary output — what to build, in what order, on what
  schedule. Use `metrics_recommender_with_gold_plan` when the user wants *metric recommendations*
  that happen to include a supporting gold model plan as a secondary artifact.

**Auto-escalation rules** — when to detect that a data intelligence preflight is needed
even if not explicitly requested:
- If intent is `cohort_analysis`, `benchmark_analysis`, or `funnel_analysis` AND the user's
  query contains "trust", "accurate", "reliable", "clean", "correct" → emit
  `data_quality_analysis` first and note: "Quality check recommended before comparison analysis."
- If intent is any analysis type AND user says "I'm not sure what data I have" or "do we even
  have this data" → emit `data_discovery` first.

---

### ADD TO: Quick Reference table — append these rows

| Query Signal | Intent | needs_mdl | needs_metrics | Focus Areas | Persona |
|---|---|---|---|---|---|
| "What data do I have available?" | `data_discovery` | true | false | (from focus_domain if provided) | null |
| "Where does the completion rate metric come from?" | `data_lineage` | true | true | `ld_training` | null |
| "Are there data quality issues in my Cornerstone tables?" | `data_quality_analysis` | true | false | (from data_source) | null |
| "Plan the data pipeline to support my compliance dashboard" | `data_planner` | true | true | `compliance_training` | null |

---

### ADD TO: data_enrichment block logic

For data intelligence intents, set:
- `needs_mdl: true` always (all four need schema access)
- `needs_metrics: false` for `data_discovery` and `data_quality_analysis`
- `needs_metrics: true` for `data_lineage` and `data_planner`
- `metrics_intent: null` for `data_discovery` and `data_quality_analysis`

---

## ─── 02_csod_planner.md ────────────────────────────────────────────────────

### ADD TO: "AVAILABLE AGENTS" section — append 4 new data intelligence agents

---

**`data_discovery_agent`**
- Queries the Qdrant schema collections (`csod_db_schema`, `csod_table_descriptions`) to
  enumerate available tables, column metadata, and inferred metric buildability across all
  configured data sources
- Use when: intent is `data_discovery`
- Scoping: applies `discovery_scope` filter — `silver_gold_only` limits to analyst-ready
  tables; `focus_domain_tables` applies focus_area filter; `metrics_only` returns tables that
  appear as `source_schemas` in the lms_dashboard_metrics_registry
- Requires: `available_data_sources` list (from tenant config), optional `discovery_scope`
  and `focus_domain` from scoping_filters
- Outputs:
  - `schema_catalog`: list of {table_name, layer (bronze/silver/gold), data_source,
    row_count_estimate, last_updated, column_count, key_columns}
  - `available_metrics_list`: metrics from lms_dashboard_metrics_registry that are buildable
    given the discovered tables
  - `data_capability_assessment`: {tables_found, metrics_buildable, estimated_coverage_pct}
  - `coverage_gaps`: focus areas or metric categories where no supporting tables were found
- Note: This agent reuses the existing `csod_mdl_schema_retrieval_node` infrastructure but
  routes its output directly to `csod_output_assembler` rather than to `csod_metrics_retrieval`.
  No additional Qdrant collection is needed.

---

**`data_lineage_tracer`**
- Constructs a directed acyclic lineage graph by joining the medallion architecture metadata
  (from GoldStandardTables and resolved_schemas) with the lms_dashboard_metrics_registry
  `source_schemas` field. Walks the graph upstream (source → metric) or downstream
  (metric → dependent metrics and dashboards) based on `lineage_direction` scoping filter.
- Use when: intent is `data_lineage`
- Requires: scored_metrics (for identifying the subject metric/table), resolved_schemas
  (column-level DDL for transformation steps), optional causal_graph output (enriches
  lineage with causal weight annotations)
- `lineage_subject` scoping filter: can be a metric_id (trace back to source tables),
  a table_name (trace forward to all dependent metrics), or a KPI name
- Outputs:
  - `lineage_graph`: DAG with nodes = {id, type (table/gold_model/metric/kpi),
    layer (bronze/silver/gold/presentation), data_source} and edges = {from, to,
    transformation_type (join/aggregate/filter/direct_map), column_references}
  - `column_level_lineage`: for each output column of the subject, which source columns
    contribute to it and through what transformations
  - `transformation_steps`: natural language steps (no SQL) from source to metric
  - `impact_analysis` (downstream only): list of metrics/dashboards that would be affected
    if the subject table changed schema or stopped refreshing
- Integration pattern with anomaly_detection: when anomaly_detector flags a metric, the
  planner SHOULD include a `data_lineage_tracer` step with `lineage_direction: upstream`
  to surface whether the anomaly originates in a source table. Plan both in sequence:
  anomaly_detector → data_lineage_tracer → output_assembler.

---

**`data_quality_inspector`**
- Runs four quality dimension checks against resolved_schemas by analyzing column metadata,
  DDL, and schema descriptions. Does NOT execute live SQL — derives quality assessments from
  schema metadata, table descriptions, and Qdrant-stored statistics (row counts, null rates
  where available). Flags tables with known quality risks for human review.
- Use when: intent is `data_quality_analysis`
- `quality_dimension` scoping filter controls which checks run:
  - `completeness`: identifies columns with nullable=true on key analytical fields (status,
    date, learner_id); flags tables with estimated null rate > 10%
  - `freshness`: compares table `last_updated` metadata against `refresh_frequency` config
    or expected patterns (e.g., a daily-loaded table with a 3-day-old timestamp is stale)
  - `consistency`: checks for orphaned foreign key patterns (table A references table B column
    that does not appear in resolved_schemas), duplicate primary key risks (tables lacking a
    clear PK in DDL), and naming inconsistencies across related tables
  - `accuracy`: flags columns where DDL type does not match expected semantic type (e.g.,
    a completion_rate column stored as VARCHAR), or where value ranges in descriptions
    contradict expected bounds (e.g., a percentage field that can store > 100)
- Requires: resolved_schemas (all tables in scope), optional `table_scope` to narrow to
  specific layers; `time_period` scoping filter applied to freshness check only
- Outputs:
  - `quality_scorecard`: {table_name, completeness_score, freshness_score, consistency_score,
    accuracy_score, overall_score} per table (0–100 scale)
  - `issue_list`: [{issue_id, table_name, column_name, dimension, severity (critical/high/
    medium/low), description, recommended_action}]
  - `freshness_report`: {table_name, last_updated, expected_frequency, days_stale,
    is_stale} per table
  - `integrity_checks`: list of cross-table reference gaps and PK/FK inconsistencies
  - `quality_recommendations`: prioritized list of remediation actions

---

**`data_pipeline_planner`**
- Extends the existing `csod_medallion_planner` with ingestion layer planning and dbt model
  specification generation. Takes a stated `analysis_goal` scoping filter and works backward
  from the required metrics/gold models to specify the complete data engineering stack:
  source ingestion → bronze → silver → gold → serving layer.
- Use when: intent is `data_planner`
- Requires: metric_recommendations (from metrics_recommender, for knowing which metrics to
  serve), resolved_schemas (for knowing what already exists), gold_standard_tables (for
  knowing which gold models already exist), `refresh_frequency` and `analysis_goal` from
  scoping_filters
- Outputs:
  - `medallion_plan`: full GoldModelPlan spec (as per existing medallion_planner output format)
    extended with ingestion specs for each source table
  - `ingestion_schedule`: [{table_name, source_system, ingestion_method (api/jdbc/file_drop),
    frequency, expected_volume_rows, incremental_key}]
  - `dbt_model_specs`: [{model_name, layer (bronze/silver/gold), materialization, depends_on,
    description, expected_columns, tests (not_null/unique/accepted_values per column)}]
  - `dependency_dag`: ordered build sequence as a list of steps, each with
    {step_id, model_name, layer, depends_on_steps, estimated_build_minutes}
  - `estimated_build_complexity`: {total_models, total_sources, estimated_dev_days,
    complexity_tier (simple/moderate/complex)}
- Cross-quadrant trigger: when `crown_jewel_analysis` identifies top-priority metrics,
  the planner SHOULD offer `data_pipeline_planner` as the next logical step. Include a
  `gap_notes` entry: "Crown jewel metrics identified — run Data Planner to design the
  infrastructure that serves them."

---

### ADD TO: "Phase 2: Scope Determination" — intent → agent mapping additions

```
- `data_discovery`        → data_discovery_agent (no execution agents downstream)
- `data_lineage`          → data_lineage_tracer (preceded by scoring_validator)
- `data_quality_analysis` → data_quality_inspector (preceded by mdl_schema_retrieval only)
- `data_planner`          → metrics_recommender → data_pipeline_planner
```

---

### ADD TO: Step Count Guidelines — data intelligence rows

| Intent | MDL steps | Metrics steps | Execution | Validation | Total |
|---|---|---|---|---|---|
| `data_discovery` | 1 (broad scope) | 0 | 1 | 0 | 2 |
| `data_lineage` | 1 | 1 | 1 | 1 | 4 |
| `data_quality_analysis` | 1 | 0 | 1 | 0 | 2 |
| `data_planner` | 1 | 1–2 | 2 | 1 | 5–6 |

Note: `data_discovery` and `data_quality_analysis` skip `scoring_validator` since
they are metadata-level operations, not metric-retrieval operations.

---

### ADD TO: Output format "expected_outputs" — add these new keys

```json
{
  "expected_outputs": {
    "schema_catalog": false,
    "available_metrics_list": false,
    "data_capability_assessment": false,
    "coverage_gaps": false,
    "lineage_graph": false,
    "column_level_lineage": false,
    "transformation_steps": false,
    "impact_analysis": false,
    "quality_scorecard": false,
    "issue_list": false,
    "freshness_report": false,
    "integrity_checks": false,
    "quality_recommendations": false,
    "ingestion_schedule": false,
    "dbt_model_specs": false,
    "dependency_dag": false,
    "estimated_build_complexity": false
  }
}
```

---

## ─── 07_output_assembler.md ─────────────────────────────────────────────────

### ADD TO: "Phase 1: Intent-Based Assembly" — append 4 new intent rules

```
5. For `data_discovery`:
   - Include: schema_catalog, available_metrics_list, data_capability_assessment, coverage_gaps
   - Exclude: all analysis artifacts (metrics, dashboards, tests, plans)

6. For `data_lineage`:
   - Include: lineage_graph, column_level_lineage, transformation_steps,
     impact_analysis (if lineage_direction included downstream)
   - Exclude: standard metric/dashboard artifacts

7. For `data_quality_analysis`:
   - Include: quality_scorecard, issue_list, freshness_report, integrity_checks,
     quality_recommendations
   - Exclude: metric recommendations, dashboards, tests

8. For `data_planner`:
   - Include: medallion_plan, ingestion_schedule, dbt_model_specs, dependency_dag,
     estimated_build_complexity
   - Also include: metric_recommendations (required, as planning context)
   - Exclude: dashboards, test_cases
```

---

## ─── Workflow Refactoring Note ──────────────────────────────────────────────

### Short-circuit paths for data intelligence

`data_discovery` and `data_quality_analysis` do not need the full retrieval spine.
Their optimal execution paths are:

```
data_discovery:
  csod_intent_classifier → csod_planner → csod_mdl_schema_retrieval
  → data_discovery_agent → csod_output_assembler

data_quality_analysis:
  csod_intent_classifier → csod_planner → csod_mdl_schema_retrieval
  → data_quality_inspector → csod_output_assembler
```

Both skip `csod_metrics_retrieval` and `csod_scoring_validator` since they
operate on schema metadata, not on scored metrics.

Implement in `build_csod_retrieval_spine()` as a conditional edge from
`csod_mdl_schema_retrieval`:

```python
def _route_after_mdl_retrieval(state):
    intent = state.get("csod_intent", "")
    if intent in ("data_discovery", "data_quality_analysis"):
        return "execution_node"   # skip metrics retrieval + validator
    return "csod_metrics_retrieval"
```

`data_lineage` and `data_planner` use the full spine and then route to their
respective execution agents after `csod_scoring_validator`.

### Automatic preflight injection

In `csod_planner_node`, add a preflight check before building the execution plan:

```python
def _check_preflight_needs(state, intent):
    """
    Returns a list of preflight analysis types that should be suggested
    before the primary analysis runs.
    """
    preflights = []
    query = state.get("user_query", "").lower()

    # Data quality preflight for comparison analyses
    if intent in ("cohort_analysis", "benchmark_analysis", "funnel_analysis"):
        if any(w in query for w in ("trust", "accurate", "reliable", "clean", "correct")):
            preflights.append("data_quality_analysis")

    # Data discovery preflight when data sources unknown
    if not state.get("selected_data_sources"):
        preflights.append("data_discovery")

    # Data planner suggestion after crown jewel
    if intent == "crown_jewel_analysis":
        preflights.append("data_planner_suggested")  # soft suggestion, not blocking

    return preflights
```

Add `preflight_suggestions` to planner output so the UI can surface
"Would you like to check data quality before running this analysis?" prompts
without blocking the primary workflow.