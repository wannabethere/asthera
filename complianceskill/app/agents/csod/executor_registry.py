"""
CSOD Executor Registry — Planner vs executor (v5.0).

Causal graph emits topology only (nodes, edges, centrality). Shapley is computed
inside each executor that needs attribution, not at spine level.
"""

from typing import Any, Dict, List, Optional

from app.agents.csod.executor_registry_planned import planned_executors_v5

# Implemented executors (override / extend planned entries with same executor_id)
_CORE_IMPLEMENTED: Dict[str, Dict[str, Any]] = {
    "data_discovery_agent": {
        "executor_id": "data_discovery_agent",
        "type": "layout",
        "display_name": "Data Discovery",
        "description": "Enumerates available schemas, tables, and buildable metrics",
        "capabilities": ["data_discovery"],
        "required_inputs": ["csod_resolved_schemas"],
        "optional_inputs": ["scoping_filters.discovery_scope"],
        "output_fields": [
            "csod_schema_catalog",
            "csod_available_metrics_list",
            "csod_data_capability_assessment",
            "csod_coverage_gaps",
        ],
        "dt_required": False,
        "cce_mode": "disabled",
        "can_be_direct": True,
        "narrative": {
            "start": "I'm exploring what data you have available and what analysis it can support.",
            "end": "Found {table_count} tables. {metric_count} metrics are buildable from your data.",
            "detail": "Cataloguing {table_name} — {column_count} columns.",
        },
        "node_fn": "csod_data_discovery_node",
        "prompt_file": "22_data_discovery.md",
        "implemented": True,
    },
    "data_quality_inspector": {
        "executor_id": "data_quality_inspector",
        "type": "sql",
        "display_name": "Data Quality Inspector",
        "description": "Assesses completeness, freshness, consistency, and accuracy of training schemas",
        "capabilities": ["data_quality_analysis"],
        "required_inputs": ["csod_resolved_schemas"],
        "optional_inputs": [
            "scoping_filters.quality_dimension",
            "scoping_filters.table_scope",
        ],
        "output_fields": [
            "csod_quality_scorecard",
            "csod_issue_list",
            "csod_freshness_report",
        ],
        "dt_required": False,
        "cce_mode": "disabled",
        "can_be_direct": True,
        "narrative": {
            "start": "I'm checking your data for quality issues — completeness, freshness, and integrity.",
            "end": "Quality scan complete. {issue_count} issues found across {table_count} tables.",
            "detail": "Checking {dimension} on {table_name}.",
        },
        "node_fn": "csod_data_quality_inspector_node",
        "prompt_file": "23_data_quality.md",
        "implemented": True,
    },
    "data_lineage_tracer": {
        "executor_id": "data_lineage_tracer",
        "type": "layout",
        "display_name": "Data Lineage Tracer",
        "description": "Traces a metric or table upstream to source or downstream to dependents",
        "capabilities": ["data_lineage"],
        "required_inputs": ["csod_resolved_schemas"],
        "optional_inputs": [
            "scoping_filters.lineage_subject",
            "scoping_filters.lineage_direction",
            "dt_scored_metrics",
        ],
        "output_fields": [
            "csod_lineage_graph",
            "csod_column_level_lineage",
            "csod_transformation_steps",
            "csod_impact_analysis",
        ],
        "dt_required": False,
        "cce_mode": "disabled",
        "can_be_direct": True,
        "narrative": {
            "start": "I'm tracing where your data comes from — following the pipeline from source to metric.",
            "end": "Lineage traced: {node_count} nodes, {depth} layers deep.",
            "detail": "{from_table} → {to_metric} via {transformation}.",
        },
        "node_fn": "csod_data_lineage_tracer_node",
        "prompt_file": "24_data_lineage.md",
        "implemented": True,
    },
    "data_pipeline_planner": {
        "executor_id": "data_pipeline_planner",
        "type": "layout",
        "display_name": "Data Pipeline Planner",
        "description": "Generates ingestion specs, dbt models, and dependency DAG for an analysis goal",
        "capabilities": ["data_planner"],
        "required_inputs": ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs": [
            "scoping_filters.refresh_frequency",
            "scoping_filters.analysis_goal",
            "csod_medallion_plan",
        ],
        "output_fields": [
            "csod_ingestion_schedule",
            "csod_dbt_model_specs",
            "csod_dependency_dag",
            "csod_build_complexity",
        ],
        "dt_required": False,
        "cce_mode": "disabled",
        "can_be_direct": False,
        "narrative": {
            "start": "I'm designing the data engineering plan — what to ingest, what models to build, and in what order.",
            "end": "Pipeline plan ready: {model_count} dbt models, {source_count} ingestion sources.",
            "detail": "Specifying {model_name}: {materialization}, depends on {dep_count} upstreams.",
        },
        "node_fn": "csod_data_pipeline_planner_node",
        "prompt_file": "25_data_pipeline_planner.md",
        "implemented": True,
    },
    "metrics_recommender": {
        "executor_id": "metrics_recommender",
        "type": "dashboard",
        "display_name": "Metrics Recommender",
        "description": "Unified metric/KPI recommendations for dashboard, gold-plan, and analytical intents; optional csod_causal_centrality for leading/lagging tags",
        "capabilities": [
            "metrics_dashboard_plan",
            "metrics_recommender_with_gold_plan",
            "metric_kpi_advisor",
            "crown_jewel_analysis",
            "gap_analysis",
            "anomaly_detection",
            "predictive_risk_analysis",
            "training_roi_analysis",
            "funnel_analysis",
            "cohort_analysis",
            "benchmark_analysis",
            "skill_gap_analysis",
            "behavioral_analysis",
        ],
        "required_inputs": ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs": [
            "csod_metrics_layout",
            "csod_gold_standard_tables",
            "csod_causal_centrality",
        ],
        "output_fields": [
            "csod_metric_recommendations",
            "csod_kpi_recommendations",
            "csod_table_recommendations",
        ],
        "dt_required": True,
        "cce_mode": "optional",
        "can_be_direct": True,
        "narrative": {
            "start": "I'm selecting the best metrics for your use case from the qualified candidate set.",
            "end": "Recommended {metric_count} metrics and {kpi_count} KPIs.",
            "detail": "Evaluating {metric_name} for {focus_area}.",
        },
        "node_fn": "csod_metrics_recommender_node",
        "prompt_file": "03_metrics_recommender.md",
        "implemented": True,
    },
    "causal_graph": {
        "executor_id": "causal_graph",
        "type": "layout",
        "display_name": "Causal Graph",
        "description": "Builds metric relationship graph (topology). Shapley is NOT computed here — executors compute attribution internally.",
        "capabilities": [
            "metric_kpi_advisor",
            "crown_jewel_analysis",
            "gap_analysis",
            "anomaly_detection",
            "predictive_risk_analysis",
            "training_roi_analysis",
            "funnel_analysis",
            "cohort_analysis",
            "skill_gap_analysis",
            "metrics_recommender_with_gold_plan",
            "dashboard_generation_for_persona",
            "compliance_test_generator",
            "behavioral_analysis",
        ],
        "required_inputs": ["dt_scored_metrics", "user_query"],
        "optional_inputs": ["csod_causal_vertical"],
        "output_fields": [
            "csod_causal_nodes",
            "csod_causal_edges",
            "csod_causal_graph_result",
            "csod_causal_centrality",
        ],
        "dt_required": True,
        "cce_mode": "varies",
        "can_be_direct": False,
        "narrative": {
            "start": "I'm mapping how your metrics relate to each other — building the causal structure.",
            "end": "Causal graph complete: {node_count} metrics, {edge_count} relationships mapped.",
            "detail": "Found causal link: {from_metric} → {to_metric} (strength={weight}).",
        },
        "node_fn": "csod_causal_graph_node",
        "prompt_file": None,
        "implemented": True,
    },
    "medallion_planner": {
        "executor_id": "medallion_planner",
        "type": "dashboard",
        "display_name": "Medallion Planner",
        "description": "Plans bronze→silver→gold data model from metric recommendations",
        "capabilities": ["metrics_recommender_with_gold_plan", "data_planner"],
        "required_inputs": ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs": ["csod_gold_standard_tables"],
        "output_fields": ["csod_medallion_plan"],
        "dt_required": False,
        "cce_mode": "disabled",
        "can_be_direct": False,
        "narrative": {
            "start": "I'm designing the data model that will serve your priority metrics.",
            "end": "Medallion plan ready: {bronze_count} bronze, {silver_count} silver, {gold_count} gold models.",
            "detail": "Specifying gold model {model_name} from {source_count} silver tables.",
        },
        "node_fn": "csod_medallion_planner_node",
        "prompt_file": "08_medallion_planner.md",
        "implemented": True,
    },
    "compliance_test_generator": {
        "executor_id": "compliance_test_generator",
        "type": "sql",
        "display_name": "Compliance Test Generator",
        "description": "SQL compliance tests; optional csod_causal_edges for internal severity Shapley",
        "capabilities": ["compliance_test_generator"],
        "required_inputs": ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs": ["csod_causal_edges"],
        "output_fields": [
            "csod_test_cases",
            "csod_test_queries",
            "csod_test_validation_passed",
        ],
        "dt_required": True,
        "cce_mode": "optional",
        "can_be_direct": False,
        "narrative": {
            "start": "I'm writing SQL test cases for your compliance controls.",
            "end": "Generated {test_count} test cases with alert queries.",
            "detail": "Creating test for {control_name} — severity derived from causal risk contribution.",
        },
        "node_fn": "csod_compliance_test_generator_node",
        "prompt_file": "05_compliance_test_generator.md",
        "implemented": True,
    },
    "dashboard_generator": {
        "executor_id": "dashboard_generator",
        "type": "dashboard",
        "display_name": "Dashboard Generator",
        "description": "Dashboard spec; use csod_causal_centrality when present for leading/lagging ordering",
        "capabilities": [
            "dashboard_generation_for_persona",
            "metrics_dashboard_plan",
        ],
        "required_inputs": ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs": ["csod_dt_layout", "csod_persona", "csod_causal_centrality"],
        "output_fields": ["csod_dashboard_assembled"],
        "dt_required": True,
        "cce_mode": "optional",
        "can_be_direct": True,
        "narrative": {
            "start": "I'm assembling your dashboard — mapping metrics to components and laying out sections.",
            "end": "Dashboard ready: {component_count} components across {section_count} sections.",
            "detail": "Building {widget_type} for {metric_name}.",
        },
        "node_fn": "csod_dashboard_generator_node",
        "prompt_file": "04_dashboard_generator.md",
        "implemented": True,
    },
    "data_science_enricher": {
        "executor_id": "data_science_enricher",
        "type": "dashboard",
        "display_name": "Data Science Enricher",
        "description": "Enriches metrics with SQL-function analytical insights",
        "capabilities": [
            "metrics_dashboard_plan",
            "metrics_recommender_with_gold_plan",
        ],
        "required_inputs": ["csod_metric_recommendations", "csod_resolved_schemas"],
        "optional_inputs": [],
        "output_fields": ["csod_data_science_insights"],
        "dt_required": False,
        "cce_mode": "disabled",
        "can_be_direct": False,
        "narrative": {
            "start": "I'm enriching your metrics with deeper analytical patterns — trends, thresholds, correlations.",
            "end": "Added {insight_count} data science insights across your metrics.",
            "detail": "Generating {insight_type} insight for {metric_name}.",
        },
        "node_fn": "csod_data_science_insights_enricher_node",
        "prompt_file": "09_data_science_insights_enricher.md",
        "implemented": True,
    },
}

EXECUTOR_REGISTRY: Dict[str, Dict[str, Any]] = {
    **planned_executors_v5(),
    **_CORE_IMPLEMENTED,
}

DATA_INTELLIGENCE_SHORT_CIRCUIT_INTENTS = frozenset({
    "data_discovery",
    "data_quality_analysis",
})

INTENT_TO_PRIMARY_EXECUTOR: Dict[str, str] = {
    "data_discovery": "data_discovery_agent",
    "data_quality_analysis": "data_quality_inspector",
    "data_lineage": "data_lineage_tracer",
    "data_planner": "data_pipeline_planner",
    "metrics_dashboard_plan": "metrics_recommender",
    "metrics_recommender_with_gold_plan": "metrics_recommender",
    "dashboard_generation_for_persona": "dashboard_generator",
    "compliance_test_generator": "compliance_test_generator",
    "metric_kpi_advisor": "metrics_recommender",
    # Analytical intents share one implemented tail (DT → CCE → metrics_recommender spine).
    "crown_jewel_analysis": "metrics_recommender",
    "gap_analysis": "metrics_recommender",
    "anomaly_detection": "metrics_recommender",
    "predictive_risk_analysis": "metrics_recommender",
    "training_roi_analysis": "metrics_recommender",
    "funnel_analysis": "metrics_recommender",
    "cohort_analysis": "metrics_recommender",
    "benchmark_analysis": "metrics_recommender",
    "skill_gap_analysis": "metrics_recommender",
    "behavioral_analysis": "metrics_recommender",
}


def get_executors_for_capability(capability: str) -> List[Dict[str, Any]]:
    return [
        e
        for e in EXECUTOR_REGISTRY.values()
        if capability in e.get("capabilities", [])
    ]


def get_executors_by_type(executor_type: str) -> List[Dict[str, Any]]:
    return [e for e in EXECUTOR_REGISTRY.values() if e.get("type") == executor_type]


def get_direct_executors() -> List[Dict[str, Any]]:
    return [
        e
        for e in EXECUTOR_REGISTRY.values()
        if e.get("can_be_direct") and e.get("implemented") is True
    ]


def get_executor(executor_id: str) -> Optional[Dict[str, Any]]:
    return EXECUTOR_REGISTRY.get(executor_id)


def get_executor_node_fn(executor_id: str):
    entry = EXECUTOR_REGISTRY.get(executor_id)
    if not entry:
        return None
    fn_name = entry.get("node_fn")
    if not fn_name:
        return None
    from app.agents.csod import csod_nodes

    return getattr(csod_nodes, fn_name, None)


def registry_summary_for_planner() -> List[Dict[str, Any]]:
    return [
        {
            "executor_id": e["executor_id"],
            "type": e["type"],
            "display_name": e["display_name"],
            "capabilities": e["capabilities"],
            "required_inputs": e["required_inputs"],
            "cce_mode": e["cce_mode"],
            "implemented": e.get("implemented", bool(e.get("node_fn"))),
        }
        for e in EXECUTOR_REGISTRY.values()
        if e.get("implemented") is True
    ]


def should_short_circuit_after_mdl(intent: Optional[str]) -> bool:
    return intent in DATA_INTELLIGENCE_SHORT_CIRCUIT_INTENTS
