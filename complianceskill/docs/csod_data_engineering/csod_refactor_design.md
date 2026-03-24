# CSOD Workflow Refactoring Design Document
# Version: 5.0 — Causal Graph / Shapley Separation
# Changes from v4.0:
#   Causal graph = topology layer (reasoning, exploration, structure)
#   Shapley distributions = execution-time computation, internal to each executor
#   csod_shapley_scores removed as a spine-level state field
#   csod_risk_weight_coefficients removed (internal to risk_predictor)
#   Causal centrality stays (topology-derived, used by layout + crown jewel)

---

## 1. ARCHITECTURAL SHIFT: PLANNERS vs EXECUTORS

### Core principle
Planners decide. Executors run. Narrators explain.

- **Planners** read the user question + executor registry, compose an ordered
  execution plan, and name which executors to call. They never run analysis.
- **Executors** are self-contained agents in a registry. Each declares required
  inputs, output fields, and narrative templates. Any planner can call any
  executor — including on follow-up questions, bypassing the full spine.
- **Narrative layer** emits user-facing progress messages at every executor
  boundary via SSE.

### The two engines — what each does and when

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CAUSAL GRAPH  (spine enrichment — runs before execution agents)        │
│                                                                         │
│  Role: topology + reasoning                                             │
│  Answers: which metrics relate to each other, how, and in what          │
│           direction. Provides the structural map.                       │
│                                                                         │
│  Outputs written to state:                                              │
│    csod_causal_nodes       adjacency node list                          │
│    csod_causal_edges       weighted directed edges                      │
│    csod_causal_graph_result full graph metadata                         │
│    csod_causal_centrality  {metric_id: {in_degree, out_degree}}         │
│                            derived from topology — NOT Shapley          │
│                                                                         │
│  Used for:  exploration, reasoning, leading/lagging tagging,            │
│             metric relationship visualisation, causal_analysis intent   │
├─────────────────────────────────────────────────────────────────────────┤
│  SHAPLEY DISTRIBUTIONS  (execution-time — computed inside each          │
│                          executor that needs attribution)               │
│                                                                         │
│  Role: attribution + weighting                                          │
│  Answers: given that this executor is trying to explain GAP / RISK /    │
│           ROI / SEVERITY — what fraction of that outcome is             │
│           attributable to each input metric?                            │
│                                                                         │
│  NOT written to shared state. Embedded in each executor's output:       │
│    csod_gap_report.root_cause_shapley                                   │
│    csod_risk_scores[].shapley_contribution                              │
│    csod_roi_report.program_roi_breakdown[].shapley_roi_share_pct        │
│    test_case.severity_weight (compliance_test_generator)                │
│                                                                         │
│  Each executor computes against its own goal, using                     │
│  csod_causal_edges as the structural input to the Shapley game.         │
│  The goal differs per executor — you cannot precompute Shapley          │
│  generically at the spine level.                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Shapley cannot be precomputed in the spine

Shapley attribution requires specifying **which outcome variable** you are
attributing against. This differs per executor:

| Executor | Shapley goal variable |
|---|---|
| `gap_analyzer` | The specific metric that has a gap (varies per run) |
| `risk_predictor` | `compliance_posture` — probability of non-compliance |
| `roi_calculator` | Total ROI — cost vs outcome correlation |
| `compliance_test_generator` | Control risk contribution to compliance failure |
| `crown_jewel_ranker` | Does NOT use Shapley — uses graph centrality directly |
| `anomaly_detector` | Does NOT use Shapley — uses graph for structural traversal |

Precomputing a single `csod_shapley_scores` at the spine level would require
choosing one goal at planning time and forcing all executors to use it — which
is wrong for every intent except one. Each executor runs Shapley against the
goal it is actually optimising.

---

## 2. EXECUTOR REGISTRY

### 2a. Full registry

```python
EXECUTOR_REGISTRY = {

    # ── SQL Agents ────────────────────────────────────────────────────────────
    # These wrap existing SQL pipelines. Causal graph is consumed as structural
    # input (edges for traversal or Shapley structure). Shapley computed internally
    # where needed and embedded in the output artifact.

    "anomaly_detector": {
        "executor_id":      "anomaly_detector",
        "type":             "sql",
        "display_name":     "Anomaly Detector",
        "description":      "Flags statistical anomalies in time-series training metrics",
        "capabilities":     ["anomaly_detection"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges"],
        # csod_causal_edges used for upstream/downstream traversal —
        # distinguishes pipeline anomaly from business signal via graph walk.
        # No Shapley needed: this is structural traversal, not attribution.
        "output_fields":    ["csod_anomaly_report", "csod_flagged_records",
                             "csod_deviation_summary"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm scanning your training data for unusual patterns and statistical outliers.",
            "end":    "I've identified {anomaly_count} anomalies. Checking whether each originates upstream.",
            "detail": "Checking {metric_name} — {threshold}σ threshold, {window}-day window."
        },
        "node_fn":          "csod_anomaly_detector_node",
        "prompt_file":      None,
    },

    "funnel_analyzer": {
        "executor_id":      "funnel_analyzer",
        "type":             "sql",
        "display_name":     "Funnel Analyzer",
        "description":      "Computes stage-by-stage conversion and dropout rates",
        "capabilities":     ["funnel_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges",
                             "scoping_filters.funnel_stages"],
        # csod_causal_edges used to annotate stage transition causal weights.
        # No Shapley needed.
        "output_fields":    ["csod_funnel_chart", "csod_stage_conversion_rates",
                             "csod_dropout_analysis"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm mapping your learner journey through each training stage.",
            "end":    "Funnel built across {stage_count} stages. Largest drop-off: {dropout_stage}.",
            "detail": "Calculating conversion from {from_stage} to {to_stage}."
        },
        "node_fn":          "csod_funnel_analyzer_node",
        "prompt_file":      None,
    },

    "risk_predictor": {
        "executor_id":      "risk_predictor",
        "type":             "sql",
        "display_name":     "Risk Predictor",
        "description":      "Scores learners and teams for compliance non-completion risk",
        "capabilities":     ["predictive_risk_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas",
                             "csod_causal_edges"],
        # csod_causal_edges required — risk_predictor runs Shapley internally
        # against compliance_posture goal using these edges as the coalition
        # structure. Output shapley scores are embedded in csod_risk_scores[].
        "optional_inputs":  ["scoping_filters.risk_threshold"],
        "output_fields":    ["csod_risk_scores", "csod_at_risk_learner_list",
                             "csod_intervention_plan"],
        # csod_risk_scores[i] contains:
        #   risk_score, risk_tier, days_remaining,
        #   shapley_contribution: {metric_id: weight}  ← executor-internal Shapley
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm scoring each learner for compliance risk — weighing deadlines, progress, and engagement patterns.",
            "end":    "{at_risk_count} learners flagged as high-risk before the deadline.",
            "detail": "Computing risk score for {cohort_name} using causal feature weights."
        },
        "node_fn":          "csod_risk_predictor_node",
        "prompt_file":      None,
    },

    "behavioral_analyzer": {
        "executor_id":      "behavioral_analyzer",
        "type":             "sql",
        "display_name":     "Behavioral Analyzer",
        "description":      "Segments learners by engagement pattern and predicts completion likelihood",
        "capabilities":     ["behavioral_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges"],
        # csod_causal_edges optionally used to map engagement patterns → outcomes.
        # No Shapley needed — behavioral segmentation is clustering, not attribution.
        "output_fields":    ["csod_behavioral_patterns", "csod_engagement_scores",
                             "csod_behavioral_segments"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm analysing how learners engage — login patterns, session depth, content choices.",
            "end":    "Segmented {learner_count} learners into {segment_count} engagement profiles.",
            "detail": "Computing {feature} for learner cohort."
        },
        "node_fn":          "csod_behavioral_analyzer_node",
        "prompt_file":      None,
    },

    "compliance_test_generator": {
        "executor_id":      "compliance_test_generator",
        "type":             "sql",
        "display_name":     "Compliance Test Generator",
        "description":      "Generates SQL-based compliance test cases and alert queries",
        "capabilities":     ["compliance_test_generator"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges"],
        # csod_causal_edges optionally used to: compute Shapley contribution of
        # each control metric to compliance failure, then assign severity.
        # Shapley is executor-internal, embedded as test_case.severity_weight.
        "output_fields":    ["csod_test_cases", "csod_test_queries",
                             "csod_test_validation_passed"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm writing SQL test cases for your compliance controls.",
            "end":    "Generated {test_count} test cases with alert queries.",
            "detail": "Creating test for {control_name} — severity derived from causal risk contribution."
        },
        "node_fn":          "csod_compliance_test_generator_node",
        "prompt_file":      "05_compliance_test_generator.md",
    },

    "data_quality_inspector": {
        "executor_id":      "data_quality_inspector",
        "type":             "sql",
        "display_name":     "Data Quality Inspector",
        "description":      "Assesses completeness, freshness, consistency, and accuracy of training schemas",
        "capabilities":     ["data_quality_analysis"],
        "required_inputs":  ["csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.quality_dimension",
                             "scoping_filters.table_scope"],
        "output_fields":    ["csod_quality_scorecard", "csod_issue_list",
                             "csod_freshness_report"],
        "dt_required":      False,
        "cce_mode":         "disabled",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm checking your data for quality issues — completeness, freshness, and integrity.",
            "end":    "Quality scan complete. {issue_count} issues found across {table_count} tables.",
            "detail": "Checking {dimension} on {table_name}."
        },
        "node_fn":          "csod_data_quality_inspector_node",
        "prompt_file":      "23_data_quality.md",
    },

    # ── ML / LLM Agents ──────────────────────────────────────────────────────

    "crown_jewel_ranker": {
        "executor_id":      "crown_jewel_ranker",
        "type":             "ml",
        "display_name":     "Crown Jewel Ranker",
        "description":      "Ranks metrics by business impact using DT composite score and causal centrality",
        "capabilities":     ["crown_jewel_analysis"],
        "required_inputs":  ["dt_scored_metrics"],
        "optional_inputs":  ["csod_causal_centrality"],
        # csod_causal_centrality (in_degree, out_degree) is topology-derived
        # from the causal graph — NOT Shapley. No Shapley needed here.
        # Impact formula: dt_composite×0.5 + centrality×0.3 + relevance×0.2
        "output_fields":    ["csod_ranked_metrics", "csod_impact_scores",
                             "csod_priority_recommendations"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm ranking your metrics by business impact — combining relevance scores with causal influence.",
            "end":    "Top {top_n} crown jewel metrics identified. {retire_count} candidates for retirement.",
            "detail": "Scoring {metric_name}: DT={dt_score}, centrality={centrality_score}."
        },
        "node_fn":          "csod_crown_jewel_ranker_node",
        "prompt_file":      "16_crown_jewel_analysis.md",
    },

    "gap_analyzer": {
        "executor_id":      "gap_analyzer",
        "type":             "ml",
        "display_name":     "Gap Analyzer",
        "description":      "Computes delta between current metrics and targets, with internal Shapley root cause decomposition",
        "capabilities":     ["gap_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges",
                             "scoping_filters.target_source"],
        # csod_causal_edges optionally consumed to run Shapley attribution
        # INTERNALLY against the specific gap metric being decomposed.
        # Shapley output is embedded in csod_gap_report.root_cause_shapley —
        # NOT written to shared state as csod_shapley_scores.
        "output_fields":    ["csod_gap_report", "csod_metric_deltas",
                             "csod_priority_gaps", "csod_remediation_recommendations"],
        # csod_gap_report contains:
        #   metric_deltas, priority_gaps,
        #   root_cause_shapley: {upstream_metric: contribution_pct}  ← internal
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm measuring the gap between where you are and where you need to be.",
            "end":    "{gap_count} gaps found. Largest: {top_gap_name} at {top_gap_pct}% below target.",
            "detail": "Decomposing root cause for {metric_name} — tracing contribution of upstream factors."
        },
        "node_fn":          "csod_gap_analyzer_node",
        "prompt_file":      "17_gap_analysis.md",
    },

    "cohort_comparator": {
        "executor_id":      "cohort_comparator",
        "type":             "ml",
        "display_name":     "Cohort Comparator",
        "description":      "Segments learners and compares metrics across groups",
        "capabilities":     ["cohort_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.cohort_definition",
                             "csod_causal_edges"],
        # csod_causal_edges optionally used to test whether cohort differences
        # are causally structured vs purely observational (structural test only —
        # no Shapley needed).
        "output_fields":    ["csod_cohort_comparison", "csod_group_metrics",
                             "csod_segmentation_insights"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm splitting your learners into groups and comparing performance across them.",
            "end":    "Compared {cohort_count} cohorts. {top_cohort} leads on {top_metric}.",
            "detail": "Computing {metric_name} for {cohort_name}."
        },
        "node_fn":          "csod_cohort_comparator_node",
        "prompt_file":      "18_cohort_analysis.md",
    },

    "benchmark_comparator": {
        "executor_id":      "benchmark_comparator",
        "type":             "ml",
        "display_name":     "Benchmark Comparator",
        "description":      "Compares current metrics against historical or external benchmarks",
        "capabilities":     ["benchmark_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.benchmark_source"],
        # No causal graph or Shapley — pure relative comparison.
        "output_fields":    ["csod_benchmark_report", "csod_performance_vs_baseline",
                             "csod_ranking"],
        "dt_required":      True,
        "cce_mode":         "disabled",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm comparing your metrics against the selected benchmark.",
            "end":    "{above_count} metrics above benchmark, {below_count} below.",
            "detail": "Comparing {metric_name} against {benchmark_source}."
        },
        "node_fn":          "csod_benchmark_comparator_node",
        "prompt_file":      "19_benchmark_analysis.md",
    },

    "skill_gap_assessor": {
        "executor_id":      "skill_gap_assessor",
        "type":             "ml",
        "display_name":     "Skill Gap Assessor",
        "description":      "Joins competency requirements against training completion to surface skill gaps",
        "capabilities":     ["skill_gap_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges",
                             "scoping_filters.skill_domain",
                             "scoping_filters.job_role"],
        # csod_causal_edges optionally used to order training_priority_list —
        # skills that causally unlock other skills get higher priority.
        # No Shapley needed for gap assessment itself.
        # If Shapley is desired for training impact attribution, it runs
        # internally and is embedded in csod_training_priority_list[].causal_weight.
        "output_fields":    ["csod_skill_gap_matrix", "csod_competency_heatmap",
                             "csod_training_priority_list"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm measuring the gap between required competencies and current skill levels.",
            "end":    "{gap_skill_count} skill gaps identified. Top priority: {top_skill}.",
            "detail": "Assessing {skill_name} across {role_count} roles."
        },
        "node_fn":          "csod_skill_gap_assessor_node",
        "prompt_file":      "20_skill_gap_analysis.md",
    },

    "roi_calculator": {
        "executor_id":      "roi_calculator",
        "type":             "ml",
        "display_name":     "ROI Calculator",
        "description":      "Calculates training ROI with internal Shapley-based program attribution",
        "capabilities":     ["training_roi_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas",
                             "csod_causal_edges"],
        # csod_causal_edges required — roi_calculator runs calculate_generic_impact
        # and Shapley attribution INTERNALLY against total ROI as the goal variable.
        # Shapley decomposition across program types is embedded in:
        #   csod_roi_report.program_roi_breakdown[].shapley_roi_share_pct
        "optional_inputs":  ["scoping_filters.cost_category"],
        "output_fields":    ["csod_roi_report", "csod_cost_efficiency_analysis",
                             "csod_impact_attribution"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm calculating the return on your training investment — tracing spend to compliance outcomes.",
            "end":    "Overall ROI: {roi_ratio}x. Highest-return program: {top_program}.",
            "detail": "Attributing impact to {program_type} training using causal structure."
        },
        "node_fn":          "csod_roi_calculator_node",
        "prompt_file":      "21_roi_analysis.md",
    },

    # ── Dashboard Agents ──────────────────────────────────────────────────────

    "dashboard_generator": {
        "executor_id":      "dashboard_generator",
        "type":             "dashboard",
        "display_name":     "Dashboard Generator",
        "description":      "Generates a complete dashboard spec for a persona from DT layout",
        "capabilities":     ["dashboard_generation_for_persona", "metrics_dashboard_plan"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas", "csod_dt_layout"],
        "optional_inputs":  ["csod_persona", "csod_causal_centrality"],
        # csod_causal_centrality used to annotate components as leading/lagging.
        # Centrality is topology-derived — no Shapley needed.
        "output_fields":    ["csod_dashboard_assembled"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm assembling your dashboard — mapping metrics to components and laying out sections.",
            "end":    "Dashboard ready: {component_count} components across {section_count} sections.",
            "detail": "Building {widget_type} for {metric_name}."
        },
        "node_fn":          "csod_dashboard_generator_node",
        "prompt_file":      "04_dashboard_generator.md",
    },

    "metrics_recommender": {
        "executor_id":      "metrics_recommender",
        "type":             "dashboard",
        "display_name":     "Metrics Recommender",
        "description":      "Generates metric and KPI recommendations ordered by metrics_layout",
        "capabilities":     ["metrics_dashboard_plan", "metrics_recommender_with_gold_plan"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_metrics_layout", "csod_gold_standard_tables",
                             "csod_causal_centrality"],
        # csod_causal_centrality optionally used to annotate recommended metrics
        # as leading/lagging indicators.
        "output_fields":    ["csod_metric_recommendations", "csod_kpi_recommendations",
                             "csod_table_recommendations"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm selecting the best metrics for your use case from the qualified candidate set.",
            "end":    "Recommended {metric_count} metrics and {kpi_count} KPIs.",
            "detail": "Evaluating {metric_name} for {focus_area}."
        },
        "node_fn":          "csod_metrics_recommender_node",
        "prompt_file":      "03_metrics_recommender.md",
    },

    "medallion_planner": {
        "executor_id":      "medallion_planner",
        "type":             "dashboard",
        "display_name":     "Medallion Planner",
        "description":      "Plans bronze→silver→gold data model from metric recommendations",
        "capabilities":     ["metrics_recommender_with_gold_plan", "data_planner"],
        "required_inputs":  ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_gold_standard_tables"],
        "output_fields":    ["csod_medallion_plan"],
        "dt_required":      False,
        "cce_mode":         "disabled",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm designing the data model that will serve your priority metrics.",
            "end":    "Medallion plan ready: {bronze_count} bronze, {silver_count} silver, {gold_count} gold models.",
            "detail": "Specifying gold model {model_name} from {source_count} silver tables."
        },
        "node_fn":          "csod_medallion_planner_node",
        "prompt_file":      "08_medallion_planner.md",
    },

    "data_science_enricher": {
        "executor_id":      "data_science_enricher",
        "type":             "dashboard",
        "display_name":     "Data Science Enricher",
        "description":      "Enriches metrics with SQL-function-based analytical insights",
        "capabilities":     ["metrics_dashboard_plan", "metrics_recommender_with_gold_plan"],
        "required_inputs":  ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs":  [],
        "output_fields":    ["csod_data_science_insights"],
        "dt_required":      False,
        "cce_mode":         "disabled",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm enriching your metrics with deeper analytical patterns — trends, thresholds, correlations.",
            "end":    "Added {insight_count} data science insights across your metrics.",
            "detail": "Generating {insight_type} insight for {metric_name}."
        },
        "node_fn":          "csod_data_science_insights_enricher_node",
        "prompt_file":      "09_data_science_insights_enricher.md",
    },

    # ── Layout Agents ─────────────────────────────────────────────────────────

    "dashboard_layout_resolver": {
        "executor_id":      "dashboard_layout_resolver",
        "type":             "layout",
        "display_name":     "Dashboard Layout Resolver",
        "description":      "Maps DT metric groups to dashboard sections and widget types",
        "capabilities":     ["dashboard_generation_for_persona", "metrics_dashboard_plan"],
        "required_inputs":  ["dt_metric_groups", "csod_persona"],
        "optional_inputs":  ["csod_causal_centrality"],
        # csod_causal_centrality used to order within sections:
        # high out_degree (causal influence) → leading indicators → placed first.
        # This is topology-derived — no Shapley.
        "output_fields":    ["csod_dt_layout"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm deciding how to arrange your metrics into a dashboard — which go on top, which become charts.",
            "end":    "Layout resolved: {section_count} sections, {widget_count} widgets.",
            "detail": "Assigning {metric_name} to {section} as {widget_type}."
        },
        "node_fn":          "csod_dashboard_layout_resolver_node",
        "prompt_file":      "26_dashboard_layout.md",
    },

    "metrics_layout_resolver": {
        "executor_id":      "metrics_layout_resolver",
        "type":             "layout",
        "display_name":     "Metrics Layout Resolver",
        "description":      "Orders DT metric groups with leading/lagging tagging for display",
        "capabilities":     ["metrics_dashboard_plan", "metrics_recommender_with_gold_plan",
                             "crown_jewel_analysis", "metric_kpi_advisor"],
        "required_inputs":  ["dt_metric_groups", "dt_metric_decisions"],
        "optional_inputs":  ["csod_causal_centrality"],
        # csod_causal_centrality: high out_degree = leading (drives outcomes),
        # high in_degree = lagging (result of others). Topology-derived — no Shapley.
        "output_fields":    ["csod_metrics_layout"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm ordering your metrics — leading indicators first, then the outcomes they drive.",
            "end":    "Metrics ordered into {group_count} goal-aligned groups.",
            "detail": "Tagging {metric_name} as {indicator_type} indicator."
        },
        "node_fn":          "csod_metrics_layout_resolver_node",
        "prompt_file":      "27_metrics_layout.md",
    },

    "causal_graph": {
        "executor_id":      "causal_graph",
        "type":             "layout",
        "display_name":     "Causal Graph",
        "description":      "Builds metric relationship graph for reasoning, exploration, and structural enrichment. Does NOT compute Shapley — that happens inside each execution agent.",
        "capabilities":     ["metric_kpi_advisor", "crown_jewel_analysis", "gap_analysis",
                             "anomaly_detection", "predictive_risk_analysis",
                             "training_roi_analysis", "funnel_analysis", "cohort_analysis",
                             "skill_gap_analysis", "metrics_recommender_with_gold_plan",
                             "dashboard_generation_for_persona", "compliance_test_generator",
                             "behavioral_analysis"],
        "required_inputs":  ["dt_scored_metrics", "user_query"],
        "optional_inputs":  ["csod_causal_vertical"],
        "output_fields":    [
            "csod_causal_nodes",        # adjacency node list with metric metadata
            "csod_causal_edges",        # weighted directed edges — used by executors
                                        #   for traversal (anomaly), Shapley coalition
                                        #   structure (risk, gap, roi), and ordering
                                        #   (skill gap, funnel, layout resolvers)
            "csod_causal_graph_result", # full graph metadata
            "csod_causal_centrality",   # {metric_id: {in_degree, out_degree}}
                                        #   TOPOLOGY-DERIVED — NOT Shapley
                                        #   used by: layout resolvers, crown_jewel_ranker,
                                        #            dashboard_generator, metrics_recommender
        ],
        # NOTE: csod_shapley_scores is NOT an output of this node.
        # Each executor that needs Shapley computes it internally against
        # its specific goal variable, using csod_causal_edges as input.
        "dt_required":      True,
        "cce_mode":         "varies",   # set per-intent by planner
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm mapping how your metrics relate to each other — building the causal structure.",
            "end":    "Causal graph complete: {node_count} metrics, {edge_count} relationships mapped.",
            "detail": "Found causal link: {from_metric} → {to_metric} (strength={weight})."
        },
        "node_fn":          "csod_causal_graph_node",
        "prompt_file":      None,
    },

    "data_lineage_tracer": {
        "executor_id":      "data_lineage_tracer",
        "type":             "layout",
        "display_name":     "Data Lineage Tracer",
        "description":      "Traces a metric or table upstream to source or downstream to dependents",
        "capabilities":     ["data_lineage"],
        "required_inputs":  ["csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.lineage_subject",
                             "scoping_filters.lineage_direction",
                             "dt_scored_metrics"],
        "output_fields":    ["csod_lineage_graph", "csod_column_level_lineage",
                             "csod_transformation_steps", "csod_impact_analysis"],
        "dt_required":      False,
        "cce_mode":         "disabled",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm tracing where your data comes from — following the pipeline from source to metric.",
            "end":    "Lineage traced: {node_count} nodes, {depth} layers deep.",
            "detail": "{from_table} → {to_metric} via {transformation}."
        },
        "node_fn":          "csod_data_lineage_tracer_node",
        "prompt_file":      "24_data_lineage.md",
    },

    "data_discovery_agent": {
        "executor_id":      "data_discovery_agent",
        "type":             "layout",
        "display_name":     "Data Discovery",
        "description":      "Enumerates available schemas, tables, and buildable metrics",
        "capabilities":     ["data_discovery"],
        "required_inputs":  ["csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.discovery_scope"],
        "output_fields":    ["csod_schema_catalog", "csod_available_metrics_list",
                             "csod_data_capability_assessment", "csod_coverage_gaps"],
        "dt_required":      False,
        "cce_mode":         "disabled",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm exploring what data you have available and what analysis it can support.",
            "end":    "Found {table_count} tables. {metric_count} metrics are buildable from your data.",
            "detail": "Cataloguing {table_name} — {column_count} columns."
        },
        "node_fn":          "csod_data_discovery_node",
        "prompt_file":      "22_data_discovery.md",
    },

    "data_pipeline_planner": {
        "executor_id":      "data_pipeline_planner",
        "type":             "layout",
        "display_name":     "Data Pipeline Planner",
        "description":      "Generates ingestion specs, dbt models, and dependency DAG",
        "capabilities":     ["data_planner"],
        "required_inputs":  ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.refresh_frequency",
                             "scoping_filters.analysis_goal",
                             "csod_medallion_plan"],
        "output_fields":    ["csod_ingestion_schedule", "csod_dbt_model_specs",
                             "csod_dependency_dag", "csod_build_complexity"],
        "dt_required":      False,
        "cce_mode":         "disabled",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm designing the data engineering plan — what to ingest, what models to build, and in what order.",
            "end":    "Pipeline plan ready: {model_count} dbt models, {source_count} ingestion sources.",
            "detail": "Specifying {model_name}: {materialization}, depends on {dep_count} upstreams."
        },
        "node_fn":          "csod_data_pipeline_planner_node",
        "prompt_file":      "25_data_pipeline_planner.md",
    },
}
```

---

## 3. CCE INTENT CONFIG — UPDATED

`cce_output_used` now precisely describes what the causal graph provides and
what each executor computes internally.

```python
CCE_INTENT_CONFIG = {

    # ── required ──────────────────────────────────────────────────────────
    "crown_jewel_analysis": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "csod_causal_centrality (in/out degree topology)",
        "executor_uses":         "crown_jewel_ranker reads centrality directly in impact formula — no Shapley",
    },
    "gap_analysis": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "csod_causal_edges (metric relationship structure)",
        "executor_uses":         "gap_analyzer runs Shapley INTERNALLY against the gap metric's goal; embeds result in csod_gap_report.root_cause_shapley",
    },
    "anomaly_detection": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "csod_causal_edges (upstream/downstream paths)",
        "executor_uses":         "anomaly_detector traverses edges to distinguish pipeline vs business anomaly — graph walk, no Shapley",
    },
    "predictive_risk_analysis": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "csod_causal_edges (compliance metric coalition structure)",
        "executor_uses":         "risk_predictor runs Shapley INTERNALLY against compliance_posture goal; weights embedded in csod_risk_scores[].shapley_contribution",
    },
    "training_roi_analysis": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "csod_causal_edges (cost→outcome causal chains)",
        "executor_uses":         "roi_calculator runs calculate_generic_impact + Shapley INTERNALLY against ROI goal; embeds in csod_roi_report.program_roi_breakdown[].shapley_roi_share_pct",
    },
    "metric_kpi_advisor": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "full graph (csod_causal_nodes + edges + centrality) — graph IS the primary output for this intent",
        "executor_uses":         "metric_advisor uses graph directly for reasoning plan — causal structure is the answer, not an input to further attribution",
    },

    # ── optional ──────────────────────────────────────────────────────────
    "funnel_analysis": {
        "enabled": True, "mode": "optional",
        "causal_graph_provides": "csod_causal_edges (stage transition weights)",
        "executor_uses":         "funnel_analyzer annotates stage transitions with edge weights — structural annotation, no Shapley",
    },
    "cohort_analysis": {
        "enabled": True, "mode": "optional",
        "causal_graph_provides": "csod_causal_edges (structural dependency test)",
        "executor_uses":         "cohort_comparator tests whether cohort differences are causally structured — path existence test, no Shapley",
    },
    "skill_gap_analysis": {
        "enabled": True, "mode": "optional",
        "causal_graph_provides": "csod_causal_edges (skill unlock chains)",
        "executor_uses":         "skill_gap_assessor uses edge paths to order training_priority_list by causal unlock potential; optionally runs Shapley INTERNALLY for impact ordering",
    },
    "metrics_recommender_with_gold_plan": {
        "enabled": True, "mode": "optional",
        "causal_graph_provides": "csod_causal_centrality (leading/lagging tagging)",
        "executor_uses":         "metrics_recommender annotates recommendations — topology only, no Shapley",
    },
    "dashboard_generation_for_persona": {
        "enabled": True, "mode": "optional",
        "causal_graph_provides": "csod_causal_centrality (component ordering)",
        "executor_uses":         "dashboard_layout_resolver + dashboard_generator use centrality for section ordering — topology only",
    },
    "compliance_test_generator": {
        "enabled": True, "mode": "optional",
        "causal_graph_provides": "csod_causal_edges (control risk chains)",
        "executor_uses":         "compliance_test_generator runs Shapley INTERNALLY against compliance_posture to weight test case severity",
    },
    "behavioral_analysis": {
        "enabled": True, "mode": "required",
        "causal_graph_provides": "csod_causal_edges (engagement → outcome paths)",
        "executor_uses":         "behavioral_analyzer maps engagement segments to likely outcomes via edge traversal — no Shapley",
    },

    # ── disabled ──────────────────────────────────────────────────────────
    "benchmark_analysis": {
        "enabled": False, "mode": "disabled",
        "rationale": "Relative comparison — no causal structure or attribution needed",
    },
    "data_discovery":       {"enabled": False, "mode": "disabled"},
    "data_lineage":         {"enabled": False, "mode": "disabled"},
    "data_quality_analysis":{"enabled": False, "mode": "disabled"},
    "data_planner":         {"enabled": False, "mode": "disabled"},
}
```

---

## 4. STATE FIELDS — UPDATED

```python
# ── Causal graph outputs (topology only) ─────────────────────────────────────
csod_causal_nodes:         Optional[List]   # adjacency node list
csod_causal_edges:         Optional[List]   # weighted directed edges
csod_causal_graph_result:  Optional[Dict]   # full graph metadata
csod_causal_centrality:    Optional[Dict]   # {metric_id: {in_degree, out_degree}}
                                            # TOPOLOGY-DERIVED — NOT Shapley
csod_causal_mode:          Optional[str]    # 'required' | 'optional' | 'disabled'

# ── REMOVED fields (were in v4.0, incorrect) ─────────────────────────────────
# csod_shapley_scores          ← removed — computed internally by each executor
# csod_risk_weight_coefficients ← removed — internal to risk_predictor

# ── Executor-embedded Shapley (not top-level state — lives inside output dicts) ─
# csod_gap_report["root_cause_shapley"]            gap_analyzer
# csod_risk_scores[i]["shapley_contribution"]      risk_predictor
# csod_roi_report["program_roi_breakdown"][i]
#     ["shapley_roi_share_pct"]                    roi_calculator
# csod_test_cases[i]["severity_weight"]            compliance_test_generator (optional)
# csod_training_priority_list[i]["causal_weight"]  skill_gap_assessor (optional)

# ── Intervention points (executor output, not CCE output) ─────────────────────
csod_intervention_points:  Optional[List]   # written by risk_predictor
                                            # [{metric_id, intervention_type, impact}]
                                            # based on executor-internal Shapley
```

---

## 5. CCE CONSUMPTION PATTERNS FOR EXECUTOR PROMPTS

Each executor prompt gets a block explaining exactly what the causal graph
provides and what the executor computes internally.

### gap_analyzer (17_gap_analysis.md)

```
### CAUSAL GRAPH CONTEXT

The causal graph provides csod_causal_edges — a list of weighted directed edges
between your dt_scored_metrics. This represents the causal structure of how
metrics relate.

When you find a gap in a metric, use csod_causal_edges to run Shapley attribution
INTERNALLY against that metric's gap:
  - Build a cooperative game where the upstream metrics (edges pointing INTO the
    gap metric) are the players
  - The characteristic function is: "how much of the gap is explained if I
    include this upstream metric in the coalition?"
  - The Shapley value of each upstream metric is its fractional contribution
    to the observed gap

Embed the result as:
  root_cause_shapley: [
    { "metric_id": "assignment_volume", "contribution_pct": 61, "direction": "positive" },
    { "metric_id": "login_frequency",   "contribution_pct": 28, "direction": "positive" },
    { "metric_id": "other_factors",     "contribution_pct": 11, "direction": "residual" }
  ]

DO NOT write Shapley scores to shared state. They live inside csod_gap_report only.
If csod_causal_edges is not available (cce_fallback: true), omit root_cause_shapley
and note "causal attribution unavailable — showing raw metric deltas only".
```

### risk_predictor (SQL node — implementation note)

```
### CAUSAL GRAPH CONTEXT

csod_causal_edges provides the coalition structure for computing per-feature
Shapley risk weights internally.

Steps:
1. Identify all edges pointing INTO compliance-related outcome metrics
   (e.g., compliance_completion_rate, certification_status)
2. Run Shapley attribution with the goal variable = P(non-compliance)
3. Each risk feature metric's Shapley value becomes its weight coefficient
   in the risk scoring formula:
   risk_score = Σ (shapley_weight_i × normalized_feature_i)
4. Write per-learner as: csod_risk_scores[i].shapley_contribution = {metric_id: weight}

If csod_causal_edges unavailable: fall back to equal weighting across features.
Log: cce_fallback: true, shapley_method: "equal_weight_fallback".
```

### roi_calculator (21_roi_analysis.md)

```
### CAUSAL GRAPH CONTEXT

csod_causal_edges provides the cost→outcome causal chains. Two internal
computations:

1. calculate_generic_impact(cost_metrics, outcome_metrics, causal_edges)
   → returns estimated_impact_value per program type

2. Shapley decomposition with goal = total_ROI:
   Players = program types (mandatory, technical, soft_skills, onboarding)
   Characteristic function = marginal ROI contribution
   → shapley_roi_share_pct per program type

Embed in output:
  csod_roi_report.program_roi_breakdown[i].shapley_roi_share_pct

If csod_causal_edges unavailable: use direct correlation only.
Log: cce_fallback: true.
```

### crown_jewel_ranker (16_crown_jewel_analysis.md)

```
### CAUSAL GRAPH CONTEXT

csod_causal_centrality provides {metric_id: {in_degree, out_degree}} derived
from the causal graph topology. This is NOT Shapley — it is a structural
property of the graph.

Use centrality in the impact formula:
  centrality_score = (in_degree + out_degree) / total_metrics
  impact_score = (dt_composite × 0.5) + (centrality_score × 0.3) + (relevance × 0.2)

High out_degree = leading indicator (drives many outcomes) → higher impact
High in_degree  = lagging indicator (driven by many others) → lower impact

Do NOT compute Shapley for crown jewel ranking. Centrality is the correct
structural measure for identifying leverage points.
```

### anomaly_detector (SQL node — implementation note)

```
### CAUSAL GRAPH CONTEXT

csod_causal_edges provides upstream/downstream paths for graph traversal.

When an anomaly is flagged in metric M:
1. UPSTREAM WALK: find all metrics with edges pointing INTO M.
   Check if those upstream metrics also show anomalies in the same window.
   If yes → anomaly_origin = "upstream" (root cause is in an upstream metric)
   If no  → anomaly_origin = "primary" (this metric IS the root cause)

2. DOWNSTREAM WALK: find all metrics M points INTO.
   These will be impacted. Estimate lag in days from edge weights.
   Add to impact_analysis list.

No Shapley needed — this is path traversal, not attribution.
```

---

## 6. STATE ADDITIONS (delta from v4.0, same structure otherwise)

```python
# Removed from v4.0:
# csod_shapley_scores            (was incorrectly a spine-level pre-computation)
# csod_risk_weight_coefficients  (internal to risk_predictor)

# Unchanged from v4.0 (all other state fields remain):
# csod_causal_centrality         (topology-derived, still a spine-level output)
# csod_intervention_points       (risk_predictor output)
# All other executor output fields
# All narrative/follow-up router fields
```

---

## 7. SUMMARY OF CHANGES FROM v4.0

| Location | v4.0 | v5.0 |
|---|---|---|
| `causal_graph` output_fields | included `csod_shapley_scores`, `csod_causal_centrality` | removed `csod_shapley_scores`; keep `csod_causal_centrality` (topology) |
| `causal_graph` description | "builds graph and computes Shapley scores" | "builds relationship graph for reasoning and structural enrichment" |
| `risk_predictor` required_inputs | `csod_shapley_scores` as required input | `csod_causal_edges` as required input; Shapley computed internally |
| `gap_analyzer` optional_inputs | `csod_shapley_scores` | `csod_causal_edges` |
| `roi_calculator` required_inputs | `csod_causal_graph_result` | `csod_causal_edges` |
| `anomaly_detector` optional_inputs | `csod_shapley_scores`, `csod_causal_edges` | `csod_causal_edges` only |
| `skill_gap_assessor` optional_inputs | `csod_shapley_scores` | `csod_causal_edges` |
| `compliance_test_generator` optional_inputs | `csod_shapley_scores` | `csod_causal_edges` |
| Spine-level state field | `csod_shapley_scores: Optional[Dict]` | **removed** |
| Spine-level state field | `csod_risk_weight_coefficients: Optional[Dict]` | **removed** |
| Shapley output location | top-level state | embedded inside executor output artifacts |
| CCE consumption patterns | "CCE outputs Shapley → executor reads" | "executor computes Shapley internally using csod_causal_edges as coalition structure" |
| `causal_graph` narrative.end | "Causal graph complete: {n} metrics, {e} relationships mapped." | unchanged — Shapley mention removed from description only |