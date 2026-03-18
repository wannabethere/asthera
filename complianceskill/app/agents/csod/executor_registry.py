"""
CSOD Executor Registry — Planner-Executor Architecture (v4.0)

Planners decide. Executors run. Each executor declares required_inputs,
output_fields, capabilities, and narrative templates. The planner reads this
registry to build execution_plan with executor_id; the workflow dispatches
to the corresponding node_fn.

Data intelligence executors (data_discovery, data_lineage, data_quality_analysis,
data_planner) support short-circuit paths and are aligned with prompts_data_intelligence_design
and skill_config.json.
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Executor entry shape (matches csod_data_engineering_desing.md §2a)
# ---------------------------------------------------------------------------

EXECUTOR_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ── Data Intelligence (short-circuit: skip metrics retrieval when applicable) ──
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
    },
    "data_quality_inspector": {
        "executor_id": "data_quality_inspector",
        "type": "sql",
        "display_name": "Data Quality Inspector",
        "description": "Assesses completeness, freshness, consistency, and accuracy of training schemas",
        "capabilities": ["data_quality_analysis"],
        "required_inputs": ["csod_resolved_schemas"],
        "optional_inputs": ["scoping_filters.quality_dimension", "scoping_filters.table_scope"],
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
    },
    # ── Existing spine / execution executors (key subset for planner) ──
    "metrics_recommender": {
        "executor_id": "metrics_recommender",
        "type": "dashboard",
        "display_name": "Metrics Recommender",
        "description": "Generates metric and KPI recommendations ordered by metrics_layout",
        "capabilities": ["metrics_dashboard_plan", "metrics_recommender_with_gold_plan"],
        "required_inputs": ["dt_scored_metrics", "csod_resolved_schemas"],
        "optional_inputs": ["csod_metrics_layout", "csod_gold_standard_tables"],
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
    },
    "causal_graph": {
        "executor_id": "causal_graph",
        "type": "layout",
        "display_name": "Causal Graph Builder",
        "description": "Builds metric adjacency graph and computes Shapley scores via CCE",
        "capabilities": [
            "metric_kpi_advisor",
            "crown_jewel_analysis",
            "gap_analysis",
            "metrics_recommender_with_gold_plan",
            "dashboard_generation_for_persona",
        ],
        "required_inputs": ["dt_scored_metrics", "user_query"],
        "optional_inputs": ["csod_causal_vertical"],
        "output_fields": [
            "csod_causal_nodes",
            "csod_causal_edges",
            "csod_causal_graph_result",
            "csod_shapley_scores",
            "csod_causal_centrality",
        ],
        "dt_required": True,
        "cce_mode": "varies",
        "can_be_direct": False,
        "narrative": {
            "start": "I'm mapping how your metrics influence each other — building the causal graph.",
            "end": "Causal graph complete: {node_count} metrics, {edge_count} relationships mapped.",
            "detail": "Found causal link: {from_metric} → {to_metric} (weight={weight}).",
        },
        "node_fn": "csod_causal_graph_node",
        "prompt_file": None,
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
    },
}

# ---------------------------------------------------------------------------
# Intents that skip metrics retrieval (go MDL → executor → output_assembler)
# per prompts_data_intelligence_design.md "Short-circuit paths"
# ---------------------------------------------------------------------------
DATA_INTELLIGENCE_SHORT_CIRCUIT_INTENTS = frozenset({
    "data_discovery",
    "data_quality_analysis",
})

# ---------------------------------------------------------------------------
# Intent → primary executor (for routing when not using full plan)
# ---------------------------------------------------------------------------
INTENT_TO_PRIMARY_EXECUTOR: Dict[str, str] = {
    "data_discovery": "data_discovery_agent",
    "data_quality_analysis": "data_quality_inspector",
    "data_lineage": "data_lineage_tracer",
    "data_planner": "data_pipeline_planner",
    "metrics_dashboard_plan": "metrics_recommender",
    "metrics_recommender_with_gold_plan": "metrics_recommender",
    "dashboard_generation_for_persona": "csod_dashboard_generator",
    "compliance_test_generator": "csod_compliance_test_generator",
    "metric_kpi_advisor": "metrics_recommender",
}


def get_executors_for_capability(capability: str) -> List[Dict[str, Any]]:
    """Return all executors that can serve a given intent/capability."""
    return [
        e for e in EXECUTOR_REGISTRY.values()
        if capability in e.get("capabilities", [])
    ]


def get_executors_by_type(executor_type: str) -> List[Dict[str, Any]]:
    """Return all executors of a given type (sql / ml / dashboard / layout)."""
    return [e for e in EXECUTOR_REGISTRY.values() if e.get("type") == executor_type]


def get_direct_executors() -> List[Dict[str, Any]]:
    """Return executors callable directly by follow-up router (skip spine)."""
    return [e for e in EXECUTOR_REGISTRY.values() if e.get("can_be_direct")]


def get_executor(executor_id: str) -> Optional[Dict[str, Any]]:
    """Return executor entry by id."""
    return EXECUTOR_REGISTRY.get(executor_id)


def get_executor_node_fn(executor_id: str):
    """
    Resolve executor id to its node function.
    Imports from app.agents.csod.csod_nodes package (__init__ re-exports node fns).
    """
    entry = EXECUTOR_REGISTRY.get(executor_id)
    if not entry:
        return None
    fn_name = entry.get("node_fn")
    if not fn_name:
        return None
    from app.agents.csod import csod_nodes
    return getattr(csod_nodes, fn_name, None)


def registry_summary_for_planner() -> List[Dict[str, Any]]:
    """Summary of registry for injection into planner prompt (executor_id, type, display_name, capabilities, required_inputs, cce_mode)."""
    return [
        {
            "executor_id": e["executor_id"],
            "type": e["type"],
            "display_name": e["display_name"],
            "capabilities": e["capabilities"],
            "required_inputs": e["required_inputs"],
            "cce_mode": e["cce_mode"],
        }
        for e in EXECUTOR_REGISTRY.values()
    ]


def should_short_circuit_after_mdl(intent: Optional[str]) -> bool:
    """True if this intent should skip metrics_retrieval and scoring_validator (data_discovery, data_quality_analysis)."""
    return intent in DATA_INTELLIGENCE_SHORT_CIRCUIT_INTENTS
