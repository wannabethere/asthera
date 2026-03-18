# CSOD Workflow Refactoring Design Document
# Version: 4.0 — Planner-Executor Architecture
# Changes from v3.0: adds executor registry, follow-up router, narrative layer

---

## 1. ARCHITECTURAL SHIFT: PLANNERS vs EXECUTORS

### Core principle
Planners decide. Executors run. Narrators explain.

- **Planners** read the user question + executor registry, then compose an
  ordered execution plan. They never run analysis themselves.
- **Executors** are self-contained agents in a registry. Each knows its
  required inputs, output fields, and narrative template. Any planner can call
  any executor — including on follow-up questions, skipping the full spine.
- **Narrative layer** emits user-facing progress messages at every
  executor transition via SSE.

### What this replaces from v3.0
- Hardcoded routing functions (`_route_after_causal_graph`, etc.) → replaced
  by planner reading executor registry + dynamic dispatch
- Static CCE bool gate → replaced by executor registry `cce_mode` field
- Single workflow file topology → replaced by executor registry + dispatch engine
- Silent execution → replaced by narrative emitter at each node boundary

---

## 2. EXECUTOR REGISTRY

### 2a. Registry structure

File: `app/agents/csod/executor_registry.py`

Each executor entry:

```python
EXECUTOR_REGISTRY = {

    # ── SQL Agents ────────────────────────────────────────────────────────────

    "anomaly_detector": {
        "executor_id":      "anomaly_detector",
        "type":             "sql",
        "display_name":     "Anomaly Detector",
        "description":      "Flags statistical anomalies in time-series training metrics",
        "capabilities":     ["anomaly_detection"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_shapley_scores", "csod_causal_edges"],
        "output_fields":    ["csod_anomaly_report", "csod_flagged_records", "csod_deviation_summary"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,   # can be called by follow-up router without full spine
        "narrative": {
            "start":  "I'm scanning your training data for unusual patterns and statistical outliers.",
            "end":    "I've identified {anomaly_count} anomalies in your data.",
            "detail": "Checking {metric_name} for deviations beyond {threshold} standard deviations."
        },
        "node_fn":          "csod_anomaly_detector_node",
        "prompt_file":      None,   # SQL-based, no LLM prompt
    },

    "funnel_analyzer": {
        "executor_id":      "funnel_analyzer",
        "type":             "sql",
        "display_name":     "Funnel Analyzer",
        "description":      "Computes stage-by-stage conversion and dropout rates",
        "capabilities":     ["funnel_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_causal_edges", "scoping_filters.funnel_stages"],
        "output_fields":    ["csod_funnel_chart", "csod_stage_conversion_rates", "csod_dropout_analysis"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm mapping your learner journey through each training stage.",
            "end":    "Funnel built across {stage_count} stages. Largest drop-off is at {dropout_stage}.",
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
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas", "csod_shapley_scores"],
        "optional_inputs":  ["scoping_filters.risk_threshold"],
        "output_fields":    ["csod_risk_scores", "csod_at_risk_learner_list", "csod_intervention_plan"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm scoring each learner for compliance risk using causal risk weights.",
            "end":    "{at_risk_count} learners flagged as high-risk before the deadline.",
            "detail": "Applying Shapley risk weights to {metric_name}."
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
        "optional_inputs":  ["csod_causal_graph_result"],
        "output_fields":    ["csod_behavioral_patterns", "csod_engagement_scores", "csod_behavioral_segments"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm analysing how learners engage with the platform — login patterns, session depth, content choices.",
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
        "optional_inputs":  ["csod_shapley_scores"],
        "output_fields":    ["csod_test_cases", "csod_test_queries", "csod_test_validation_passed"],
        "dt_required":      True,
        "cce_mode":         "optional",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm writing SQL test cases for your compliance controls.",
            "end":    "Generated {test_count} test cases with alert queries.",
            "detail": "Creating test for {control_name} — severity {severity}."
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
        "optional_inputs":  ["scoping_filters.quality_dimension", "scoping_filters.table_scope"],
        "output_fields":    ["csod_quality_scorecard", "csod_issue_list", "csod_freshness_report"],
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
        "description":      "Ranks metrics by business impact using DT scores + CCE centrality",
        "capabilities":     ["crown_jewel_analysis"],
        "required_inputs":  ["dt_scored_metrics"],
        "optional_inputs":  ["csod_causal_centrality"],
        "output_fields":    ["csod_ranked_metrics", "csod_impact_scores", "csod_priority_recommendations"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm ranking your metrics by business impact — combining relevance scores with causal influence.",
            "end":    "Top {top_n} crown jewel metrics identified.",
            "detail": "Scoring {metric_name}: DT={dt_score}, centrality={centrality}."
        },
        "node_fn":          "csod_crown_jewel_ranker_node",
        "prompt_file":      "16_crown_jewel_analysis.md",
    },

    "gap_analyzer": {
        "executor_id":      "gap_analyzer",
        "type":             "ml",
        "display_name":     "Gap Analyzer",
        "description":      "Computes delta between current metrics and targets, with Shapley root cause",
        "capabilities":     ["gap_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs":  ["csod_shapley_scores", "scoping_filters.target_source"],
        "output_fields":    ["csod_gap_report", "csod_metric_deltas", "csod_priority_gaps"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    True,
        "narrative": {
            "start":  "I'm measuring the gap between where you are and where you need to be.",
            "end":    "{gap_count} gaps found. Largest: {top_gap_name} at {top_gap_pct}% below target.",
            "detail": "Decomposing root cause for {metric_name} using causal attribution."
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
        "optional_inputs":  ["scoping_filters.cohort_definition", "csod_causal_edges"],
        "output_fields":    ["csod_cohort_comparison", "csod_group_metrics", "csod_segmentation_insights"],
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
        "output_fields":    ["csod_benchmark_report", "csod_performance_vs_baseline", "csod_ranking"],
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
        "optional_inputs":  ["csod_shapley_scores", "scoping_filters.skill_domain", "scoping_filters.job_role"],
        "output_fields":    ["csod_skill_gap_matrix", "csod_competency_heatmap", "csod_training_priority_list"],
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
        "description":      "Calculates training ROI by correlating costs with outcomes via Shapley attribution",
        "capabilities":     ["training_roi_analysis"],
        "required_inputs":  ["dt_scored_metrics", "csod_resolved_schemas", "csod_causal_graph_result"],
        "optional_inputs":  ["scoping_filters.cost_category"],
        "output_fields":    ["csod_roi_report", "csod_cost_efficiency_analysis", "csod_impact_attribution"],
        "dt_required":      True,
        "cce_mode":         "required",
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm calculating the return on your training investment using causal impact attribution.",
            "end":    "Overall ROI: {roi_ratio}x. Highest-return program: {top_program}.",
            "detail": "Attributing impact to {program_type} training using Shapley decomposition."
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
        "optional_inputs":  ["csod_metrics_layout", "csod_gold_standard_tables"],
        "output_fields":    ["csod_metric_recommendations", "csod_kpi_recommendations", "csod_table_recommendations"],
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
            "start":  "I'm enriching your metrics with deeper analytical patterns — trends, anomaly thresholds, correlations.",
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
        "display_name":     "Causal Graph Builder",
        "description":      "Builds metric adjacency graph and computes Shapley scores via CCE",
        "capabilities":     ["metric_kpi_advisor", "crown_jewel_analysis", "gap_analysis",
                             "anomaly_detection", "predictive_risk_analysis", "training_roi_analysis",
                             "funnel_analysis", "cohort_analysis", "skill_gap_analysis",
                             "metrics_recommender_with_gold_plan", "dashboard_generation_for_persona",
                             "compliance_test_generator", "behavioral_analysis"],
        "required_inputs":  ["dt_scored_metrics", "user_query"],
        "optional_inputs":  ["csod_causal_vertical"],
        "output_fields":    ["csod_causal_nodes", "csod_causal_edges", "csod_causal_graph_result",
                             "csod_shapley_scores", "csod_causal_centrality"],
        "dt_required":      True,
        "cce_mode":         "varies",   # set per-intent by planner from CCE_INTENT_CONFIG
        "can_be_direct":    False,
        "narrative": {
            "start":  "I'm mapping how your metrics influence each other — building the causal graph.",
            "end":    "Causal graph complete: {node_count} metrics, {edge_count} relationships mapped.",
            "detail": "Found causal link: {from_metric} → {to_metric} (weight={weight})."
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
        "optional_inputs":  ["scoping_filters.lineage_subject", "scoping_filters.lineage_direction",
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
        "description":      "Generates ingestion specs, dbt models, and dependency DAG for an analysis goal",
        "capabilities":     ["data_planner"],
        "required_inputs":  ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs":  ["scoping_filters.refresh_frequency", "scoping_filters.analysis_goal",
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

### 2b. Registry helper functions

```python
# executor_registry.py (continued)

def get_executors_for_capability(capability: str) -> list:
    """Return all executors that can serve a given intent/capability."""
    return [e for e in EXECUTOR_REGISTRY.values() if capability in e["capabilities"]]

def get_executors_by_type(executor_type: str) -> list:
    """Return all executors of a given type (sql / ml / dashboard / layout)."""
    return [e for e in EXECUTOR_REGISTRY.values() if e["type"] == executor_type]

def get_direct_executors() -> list:
    """Return executors callable directly by follow-up router (skip spine)."""
    return [e for e in EXECUTOR_REGISTRY.values() if e.get("can_be_direct")]

def get_executor_node_fn(executor_id: str):
    """Resolve executor id to its node function."""
    from app.agents.csod import (csod_analysis_nodes, csod_intelligence_nodes, 
                                  csod_layout_nodes, csod_nodes)
    entry = EXECUTOR_REGISTRY.get(executor_id)
    if not entry:
        return None
    fn_name = entry["node_fn"]
    for module in [csod_analysis_nodes, csod_intelligence_nodes, 
                   csod_layout_nodes, csod_nodes]:
        if hasattr(module, fn_name):
            return getattr(module, fn_name)
    return None
```

---

## 3. PLANNER CHANGES — READING THE REGISTRY

### 3a. csod_planner_node modifications

The planner now receives the executor registry as injected context and returns
an `execution_plan` where each step names an executor_id rather than an agent name.

```python
# In csod_planner_node, inject registry into prompt context:

from app.agents.csod.executor_registry import EXECUTOR_REGISTRY

registry_summary = [
    {
        "executor_id": e["executor_id"],
        "type":        e["type"],
        "display_name": e["display_name"],
        "capabilities": e["capabilities"],
        "required_inputs": e["required_inputs"],
        "cce_mode":    e["cce_mode"],
    }
    for e in EXECUTOR_REGISTRY.values()
]

human_message += f"\n\nAVAILABLE EXECUTORS:\n{json.dumps(registry_summary, indent=2)}"
```

**Execution plan output shape changes:**
```json
{
  "execution_plan": [
    {
      "step_id": "step_1",
      "phase": "retrieval",
      "executor_id": null,
      "agent": "mdl_schema_retrieval",
      "description": "Retrieve MDL schemas for focus areas"
    },
    {
      "step_id": "step_4",
      "phase": "qualification",
      "executor_id": null,
      "agent": "decision_tree_resolver",
      "description": "Qualify metrics via DT engine"
    },
    {
      "step_id": "step_5",
      "phase": "layout",
      "executor_id": "metrics_layout_resolver",
      "agent": "metrics_layout_resolver",
      "description": "Order metric groups by goal alignment"
    },
    {
      "step_id": "step_6",
      "phase": "enrichment",
      "executor_id": "causal_graph",
      "agent": "causal_graph",
      "description": "Build causal graph — required for gap root cause"
    },
    {
      "step_id": "step_7",
      "phase": "execution",
      "executor_id": "gap_analyzer",
      "agent": "gap_analyzer",
      "description": "Compute metric deltas and decompose root cause"
    }
  ]
}
```

### 3b. Prompt 02_csod_planner.md changes

**Add section — EXECUTOR SELECTION RULES:**
```
When building the execution plan, select executors following these rules:

1. ALWAYS include retrieval spine steps (mdl_schema_retrieval, metrics_retrieval,
   scoring_validator) unless intent is data_discovery or data_quality_analysis.

2. ALWAYS include decision_tree_resolver after scoring_validator for metric-bearing
   intents. Set executor_id=null for this step (it is a planner-layer node, not
   an executor).

3. Select layout executors BEFORE execution executors:
   - dashboard intents → dashboard_layout_resolver before dashboard_generator
   - metric intents → metrics_layout_resolver before metrics_recommender
   - other intents → no layout executor needed

4. Select the causal_graph executor when:
   - The intent's cce_mode is "required" OR "optional" (check CCE_INTENT_CONFIG)
   - Place it AFTER decision_tree_resolver, BEFORE execution executor

5. Select exactly ONE primary execution executor per intent (see intent→executor map
   in executor registry capabilities field).

6. Select secondary executors when the primary executor's required_inputs include
   output_fields from another executor:
   - gap_analyzer needs csod_shapley_scores → causal_graph must run first
   - roi_calculator needs csod_causal_graph_result → causal_graph must run first
   - dashboard_generator needs csod_dt_layout → dashboard_layout_resolver must run first

7. DO NOT select executors whose required_inputs are not satisfiable from:
   - The retrieval spine outputs
   - Outputs from earlier executors in this plan
   - State fields already in scoping_filters

8. For follow-up questions where context already exists in state:
   Emit follow_up_eligible: true and list which executors can be called directly.
   The follow-up router uses this list.
```

---

## 4. FOLLOW-UP ROUTER

### 4a. New node: `csod_followup_router_node`

```python
# csod_nodes.py addition

def csod_followup_router_node(state: CSOD_State) -> CSOD_State:
    """
    Lightweight router for follow-up questions.
    
    When context already exists (dt_scored_metrics + resolved_schemas in state),
    routes directly to the matching executor without re-running the full spine.
    
    Triggered when:
    - state["csod_session_turn"] > 1 (not first turn)
    - state["dt_scored_metrics"] is not empty
    - The new query is a follow-up on the same analysis (detected by LLM)
    
    Outputs:
    - csod_followup_executor_id: which executor to call directly
    - csod_followup_eligible: bool
    - csod_followup_intent: refined intent for this follow-up
    """
    try:
        # Check preconditions for follow-up routing
        turn = state.get("csod_session_turn", 1)
        dt_scored = state.get("dt_scored_metrics", [])
        resolved_schemas = state.get("csod_resolved_schemas", [])
        
        if turn <= 1 or not dt_scored or not resolved_schemas:
            state["csod_followup_eligible"] = False
            return state
        
        prompt_text = load_prompt("28_followup_router", prompts_dir=str(PROMPTS_CSOD))
        
        from app.agents.csod.executor_registry import get_direct_executors
        direct_executors = get_direct_executors()
        direct_executor_list = [
            {"executor_id": e["executor_id"], "display_name": e["display_name"],
             "capabilities": e["capabilities"], "description": e["description"]}
            for e in direct_executors
        ]
        
        # Build context summary of what analysis has already run
        prior_outputs = {
            "intent": state.get("csod_intent"),
            "dt_groups_available": len(state.get("dt_metric_groups", [])),
            "scored_metrics_count": len(dt_scored),
            "previous_executors_run": [
                s["agent_name"] for s in state.get("execution_steps", [])
                if s.get("status") == "completed"
            ],
            "artifacts_in_state": [
                f for f in [
                    "csod_gap_report", "csod_anomaly_report", "csod_funnel_chart",
                    "csod_cohort_comparison", "csod_benchmark_report",
                    "csod_ranked_metrics", "csod_dashboard_assembled"
                ] if state.get(f)
            ]
        }
        
        human_message = f"""New question: {state.get("user_query", "")}

Prior analysis context:
{json.dumps(prior_outputs, indent=2)}

Available direct executors:
{json.dumps(direct_executor_list, indent=2)}

Determine if this is a follow-up that can be routed directly to an executor.
Return JSON only."""
        
        response_content = _llm_invoke(
            state, "csod_followup_router", prompt_text, human_message,
            [], False, max_tool_iterations=2,
        )
        
        result = _parse_json_response(response_content, {})
        
        state["csod_followup_eligible"] = result.get("is_followup", False)
        state["csod_followup_executor_id"] = result.get("executor_id")
        state["csod_followup_intent"] = result.get("refined_intent", state.get("csod_intent"))
        state["csod_followup_reasoning"] = result.get("reasoning", "")
        
        _csod_log_step(
            state, "csod_followup_routing", "csod_followup_router",
            inputs={"user_query": state.get("user_query"), "turn": turn},
            outputs={
                "eligible": state["csod_followup_eligible"],
                "executor_id": state.get("csod_followup_executor_id"),
            },
        )
        
    except Exception as e:
        logger.error(f"csod_followup_router_node failed: {e}", exc_info=True)
        state["csod_followup_eligible"] = False
    
    return state
```

### 4b. Prompt: `28_followup_router.md`

```
ROLE: CSOD_FOLLOWUP_ROUTER

You are a follow-up question router. The user has already run an analysis and
is asking a new question in the same session. You must decide:

1. Is this genuinely a follow-up on the existing analysis context?
   - YES: "break this down by department" (cohort_comparator on existing metrics)
   - YES: "now show me who's at risk" (risk_predictor on same metric set)
   - YES: "add a quality check to this" (data_quality_inspector, direct call)
   - NO:  "what is training compliance?" (new question, needs full spine)
   - NO:  "help me with a dashboard for managers" (different intent, needs planning)

2. If YES: which executor can answer this directly from existing context?
   Match the follow-up question to the closest executor capability.
   Only return executors marked can_be_direct=True.

3. What is the refined intent for this follow-up?
   This may differ from the original intent.

Output JSON:
{
  "is_followup": true | false,
  "executor_id": "executor_id | null",
  "refined_intent": "intent string",
  "context_sufficient": true | false,
  "reasoning": "one sentence explaining the decision",
  "missing_context": ["list of state fields needed but absent — if context_sufficient=false"]
}

Rules:
- NEVER route to an executor whose required_inputs are absent from the prior context summary
- If context_sufficient=false, set is_followup=false (send back to full spine)
- "break down by X" always → cohort_comparator
- "who is at risk" / "flag high-risk" → risk_predictor
- "where is the drop-off" / "show stages" → funnel_analyzer
- "show me trends" / "over time" → anomaly_detector (for anomalies) or metrics_recommender
- "show me quality" / "is the data clean" → data_quality_inspector
- "what does X depend on" / "trace this back" → data_lineage_tracer
```

### 4c. Workflow routing change

In `csod_analytical_workflow.py`, add a pre-flight fork at the workflow entry:

```python
def _route_entry(state):
    """Fork: follow-up eligible → executor dispatch; else → full spine."""
    if state.get("csod_followup_eligible") and state.get("csod_followup_executor_id"):
        return "direct_executor_dispatch"
    return "csod_intent_classifier"
```

The `direct_executor_dispatch` node is a thin wrapper that:
1. Reads `csod_followup_executor_id` from state
2. Calls `get_executor_node_fn(executor_id)(state)` directly
3. Routes to `csod_output_assembler`

---

## 5. NARRATIVE LAYER

### 5a. Architecture

Four narrative components, all emitting to `csod_narrative_stream` in state:

```
csod_step_narrator          Emits before + after each executor node
csod_progress_emitter       Converts narrative_stream to SSE events
csod_planner_narrator       Existing 14_planner_narrator.md — extend for new steps
csod_summary_narrator       Final user-facing summary after output_assembler
```

### 5b. Narrative event structure

```python
# Added to state as a list that grows throughout execution
csod_narrative_stream: List[NarrativeEvent]

@dataclass
class NarrativeEvent:
    event_type:    str    # "step_start" | "step_end" | "step_detail" | "summary"
    executor_id:   str    # which executor this is about
    display_name:  str    # human-readable name
    message:       str    # the user-facing message (filled from narrative template)
    timestamp:     str    # ISO
    step_index:    int    # position in plan (1-based)
    total_steps:   int    # total planned executor steps
    metadata:      dict   # template variables used to fill message
```

### 5c. `csod_step_narrator_node` — new node

```python
def csod_step_narrator_node(state: CSOD_State) -> CSOD_State:
    """
    Emits a narrative event for the step that just completed.
    
    Reads from:
      - csod_pending_narrative_step: {"executor_id", "phase": "start"|"end", "metadata": {}}
    Writes to:
      - csod_narrative_stream: appends NarrativeEvent
    
    Called by the workflow BEFORE and AFTER each executor node.
    Uses the narrative templates in EXECUTOR_REGISTRY.
    """
    pending = state.get("csod_pending_narrative_step")
    if not pending:
        return state
    
    from app.agents.csod.executor_registry import EXECUTOR_REGISTRY
    
    executor_id = pending.get("executor_id")
    phase       = pending.get("phase", "start")  # "start" | "end"
    metadata    = pending.get("metadata", {})
    
    entry = EXECUTOR_REGISTRY.get(executor_id)
    if not entry:
        return state
    
    narrative_tmpl = entry["narrative"]
    template_str = narrative_tmpl.get(phase, narrative_tmpl.get("start", ""))
    
    # Fill template variables safely (missing vars → keep placeholder)
    try:
        message = template_str.format(**metadata)
    except KeyError as e:
        message = template_str  # use unfilled template rather than error
    
    event = {
        "event_type":   f"step_{phase}",
        "executor_id":  executor_id,
        "display_name": entry["display_name"],
        "message":      message,
        "timestamp":    datetime.utcnow().isoformat(),
        "step_index":   pending.get("step_index", 0),
        "total_steps":  pending.get("total_steps", 0),
        "metadata":     metadata,
    }
    
    stream = state.get("csod_narrative_stream", [])
    stream.append(event)
    state["csod_narrative_stream"] = stream
    
    # Also emit to progress emitter if SSE is active
    _emit_sse_event(state, event)
    
    return state


def _emit_sse_event(state: CSOD_State, event: dict) -> None:
    """
    Push event to SSE queue if active.
    The SSE queue is a thread-safe queue stored in state["csod_sse_queue"].
    The FastAPI SSE endpoint reads from this queue and streams to the browser.
    """
    sse_queue = state.get("csod_sse_queue")
    if sse_queue is not None:
        try:
            sse_queue.put_nowait({
                "type":    event["event_type"],
                "agent":   event["display_name"],
                "message": event["message"],
                "step":    event["step_index"],
                "total":   event["total_steps"],
            })
        except Exception:
            pass  # never block execution on narrative failure
```

### 5d. How narrative wraps each executor node

In `csod_analytical_workflow.py`, every executor node is sandwiched between
two `csod_step_narrator_node` calls via pre/post edge hooks:

```python
# Pattern for each executor in the workflow graph:

def _make_narrator_pre(executor_id: str, step_index: int, total_steps: int):
    """Create a pre-narrator state setter for this executor."""
    def _set_pending_start(state):
        state["csod_pending_narrative_step"] = {
            "executor_id": executor_id,
            "phase": "start",
            "step_index": step_index,
            "total_steps": total_steps,
            "metadata": _extract_narrative_metadata(state, executor_id, "start"),
        }
        return state
    return _set_pending_start

def _make_narrator_post(executor_id: str, step_index: int, total_steps: int):
    def _set_pending_end(state):
        state["csod_pending_narrative_step"] = {
            "executor_id": executor_id,
            "phase": "end",
            "step_index": step_index,
            "total_steps": total_steps,
            "metadata": _extract_narrative_metadata(state, executor_id, "end"),
        }
        return state
    return _set_pending_end

def _extract_narrative_metadata(state, executor_id, phase):
    """Extract template fill variables from state for a given executor + phase."""
    # Maps executor_id + phase → which state fields to pull
    META_MAP = {
        ("gap_analyzer", "end"): {
            "gap_count":    lambda s: len(s.get("csod_metric_deltas", [])),
            "top_gap_name": lambda s: (s.get("csod_priority_gaps") or [{}])[0].get("name", "—"),
            "top_gap_pct":  lambda s: (s.get("csod_priority_gaps") or [{}])[0].get("delta_pct", 0),
        },
        ("risk_predictor", "end"): {
            "at_risk_count": lambda s: len([
                r for r in s.get("csod_risk_scores", []) if r.get("risk_tier") == "high"
            ]),
        },
        ("dashboard_generator", "end"): {
            "component_count": lambda s: len(
                (s.get("csod_dashboard_assembled") or {}).get("components", [])
            ),
            "section_count": lambda s: len(
                (s.get("csod_dt_layout") or {}).get("sections", [])
            ),
        },
        # ... add for each executor
    }
    extractors = META_MAP.get((executor_id, phase), {})
    return {k: fn(state) for k, fn in extractors.items()}
```

### 5e. `csod_summary_narrator_node` — final summary

```python
def csod_summary_narrator_node(state: CSOD_State) -> CSOD_State:
    """
    Called after csod_output_assembler_node.
    Generates a final plain-language summary for the user.
    Uses 14_planner_narrator.md pattern but for the completed run.
    """
    stream = state.get("csod_narrative_stream", [])
    completed_steps = [e for e in stream if e["event_type"] == "step_end"]
    assembled = state.get("csod_assembled_output", {})
    intent = state.get("csod_intent", "")
    
    prompt_text = load_prompt("14_planner_narrator", prompts_dir=str(PROMPTS_CSOD))
    
    human_message = f"""
User question: {state.get("user_query", "")}
Steps completed: {json.dumps([s["message"] for s in completed_steps], indent=2)}
Output produced: {json.dumps(list(assembled.get("artifacts", {}).keys()), indent=2)}
Next step: None — this is the final step.

Write the final summary narrator message.
"""
    llm = get_llm(temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text.replace("{", "{{").replace("}", "}}")),
        ("human", "{input}"),
    ])
    response = (prompt | llm).invoke({"input": human_message})
    summary_text = response.content if hasattr(response, "content") else str(response)
    
    state["csod_final_narrative"] = summary_text
    
    # Emit final SSE summary event
    _emit_sse_event(state, {
        "event_type":   "summary",
        "executor_id":  "output_assembler",
        "display_name": "Summary",
        "message":      summary_text,
        "timestamp":    datetime.utcnow().isoformat(),
        "step_index":   len(completed_steps) + 1,
        "total_steps":  len(completed_steps) + 1,
        "metadata":     {},
    })
    
    return state
```

### 5f. SSE FastAPI endpoint pattern

```python
# app/api/routes/csod_stream.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from asyncio import Queue
import json

router = APIRouter()

@router.get("/csod/stream/{session_id}")
async def csod_narrative_stream(session_id: str):
    """
    SSE endpoint for CSOD workflow narrative events.
    The workflow writes to state["csod_sse_queue"] (a thread-safe queue).
    This endpoint reads from that queue and streams events to the browser.
    """
    async def event_generator():
        q = get_session_sse_queue(session_id)
        while True:
            event = await q.get()
            if event.get("type") == "done":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

---

## 6. NEW PROMPT: 28_followup_router.md

See Section 4b above for full spec.

The prompt key additions vs 01_intent_classifier.md:
- Receives "prior analysis context" (what executors ran, what artifacts exist)
- Receives "available direct executors" (filtered to can_be_direct=True)
- Does NOT classify into full 17-intent taxonomy — only matches to executor capabilities
- Outputs `is_followup`, `executor_id`, `context_sufficient`, `missing_context`

---

## 7. UPDATES TO 02_csod_planner.md

Add these sections to the planner prompt:

### New section: EXECUTOR REGISTRY (injected at runtime)
```
{executor_registry_json}
```
(Planner node injects the registry summary at invocation time)

### New section: EXECUTION PLAN RULES (additions)
```
6. Include follow_up_eligible and follow_up_executors in your output:
   - follow_up_eligible: true if the output state will have dt_scored_metrics
     and csod_resolved_schemas populated (true for most metric-bearing intents)
   - follow_up_executors: list of executor_ids from the registry that are
     can_be_direct=true AND whose capabilities intersect with related intents
     that a follow-up question might ask

Example: after gap_analysis completes, follow_up_executors might include:
  ["cohort_comparator", "anomaly_detector", "risk_predictor"]
because these can all run on the same dt_scored_metrics without re-planning.
```

### Add to output format:
```json
{
  "execution_plan": [...],
  "follow_up_eligible": true,
  "follow_up_executors": ["cohort_comparator", "anomaly_detector", "risk_predictor"],
  "estimated_execution_steps": 5,
  "narrative_preview": "I'll qualify your metrics, map causal relationships, then identify where you're falling short of targets."
}
```

The `narrative_preview` is a single sentence shown to the user immediately after
planning, before any executor runs. It sets expectations.

---

## 8. STATE ADDITIONS (delta from v3.0)

```python
# Follow-up router
csod_session_turn:            int           # incremented each conversation turn
csod_followup_eligible:       bool          # whether follow-up routing is available
csod_followup_executor_id:    Optional[str] # executor to call directly
csod_followup_intent:         Optional[str] # refined intent for follow-up
csod_followup_reasoning:      Optional[str] # router's reasoning

# Narrative layer
csod_narrative_stream:        List[dict]    # all NarrativeEvents emitted
csod_pending_narrative_step:  Optional[dict]# current step being narrated
csod_final_narrative:         Optional[str] # summary_narrator output
csod_sse_queue:               Optional[Any] # thread-safe queue for SSE emission

# Planner registry output
csod_follow_up_executors:     List[str]     # executors eligible for direct call
csod_narrative_preview:       Optional[str] # planner's one-line preview to user
```

---

## 9. FILE STRUCTURE ADDITIONS (delta from v3.0)

```
app/agents/csod/
│
├── executor_registry.py        ← NEW: full executor registry + helpers
├── csod_followup_router.py     ← NEW: follow-up router node
├── csod_narrative.py           ← NEW: step_narrator, summary_narrator,
│                                       progress_emitter, SSE helpers
│
└── prompts/
    ├── 28_followup_router.md   ← NEW
```

---

## 10. MIGRATION STEP ADDITIONS (appended to v3.0 Phase order)

### Phase 8 — Executor registry
```
34. Create executor_registry.py with all entries (use v3.0 node inventory)
35. Modify csod_planner_node to inject registry summary into prompt
36. Update 02_csod_planner.md with executor selection rules + follow_up_eligible output
37. Verify: planner output contains executor_ids, follow_up_eligible, narrative_preview
```

### Phase 9 — Follow-up router
```
38. Write csod_followup_router_node and csod_followup_router_node (28_followup_router.md)
39. Add entry-point fork to csod_analytical_workflow.py
40. Write direct_executor_dispatch node (reads csod_followup_executor_id, calls node_fn)
41. Verify: second-turn "break down by department" routes to cohort_comparator directly,
            skipping intent_classifier → planner → mdl_schema_retrieval chain
```

### Phase 10 — Narrative layer
```
42. Write csod_narrative.py: NarrativeEvent, step_narrator_node, summary_narrator_node,
    _extract_narrative_metadata (all executor entries), _emit_sse_event
43. Add csod_step_narrator_node as pre/post wrapper around every executor node
    in csod_analytical_workflow.py
44. Write SSE FastAPI endpoint: app/api/routes/csod_stream.py
45. Add csod_summary_narrator_node after csod_output_assembler_node
46. Verify: running gap_analysis emits start/end events for each step;
            SSE endpoint streams them in real-time
```

---

## 11. OPEN DECISIONS (additions to v3.0)

| # | Question | Recommendation |
|---|---|---|
| 6 | Should the planner's `narrative_preview` be generated by an LLM call or by a template from the registry? | Template first — use executor display names and count to compose "I'll run X, Y, and Z." Avoids extra LLM call at planning stage. |
| 7 | Should `csod_step_narrator_node` be a real LangGraph node (in graph) or a side-effect called directly inside each executor node? | Real node — keeps narrative concerns separate from executor logic. Easier to disable in test mode. |
| 8 | SSE queue implementation — `asyncio.Queue` vs `queue.Queue`? | Use `queue.Queue` (thread-safe sync) in the node, wrap with `asyncio.get_event_loop().run_in_executor` in the FastAPI endpoint. LangGraph nodes are sync; FastAPI is async. |
| 9 | Should `can_be_direct=False` executors (medallion_planner, roi_calculator) ever be reachable from follow-up router? | No — they have hard dependency chains. Document as "requires prior analysis" in the registry and have follow-up router skip them if context is insufficient. |
| 10 | Narrative metadata extraction (`_extract_narrative_metadata`) — maintain a META_MAP per executor or derive from state diff? | META_MAP — deterministic and testable. State diff is fragile. Add one entry per executor during Phase 10 implementation. |