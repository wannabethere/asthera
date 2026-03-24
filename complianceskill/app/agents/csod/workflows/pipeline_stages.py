"""
Pipeline stage metadata — used by the UI to display the analysis flow.

Each stage defines its nodes, their display names, and how they map to
the reasoning trace / narrative stream. The UI reads PIPELINE_STAGES
to render the stage-by-stage flow timeline.
"""
from __future__ import annotations

from typing import Any, Dict, List


# ── Stage definitions ─────────────────────────────────────────────────────────

PIPELINE_STAGES: List[Dict[str, Any]] = [
    {
        "stage_id": "intent_planning",
        "stage_number": 1,
        "display_name": "Intent & Planning",
        "description": "Classify the user query, refine with skill context, and produce an execution plan.",
        "icon": "brain",
        "nodes": [
            {"node_id": "csod_followup_router",   "display_name": "Followup Router",      "role": "router"},
            {"node_id": "csod_intent_classifier",  "display_name": "Intent Classifier",    "role": "classifier"},
            {"node_id": "skill_intent_identifier", "display_name": "Skill Refinement",     "role": "skill"},
            {"node_id": "skill_analysis_planner",  "display_name": "Skill Data Plan",      "role": "skill"},
            {"node_id": "csod_planner",            "display_name": "Execution Planner",    "role": "planner"},
        ],
    },
    {
        "stage_id": "retrieval",
        "stage_number": 2,
        "display_name": "Retrieval",
        "description": "Fetch causal graph topology, metric registry candidates, and MDL schemas from vector stores.",
        "icon": "database-search",
        "nodes": [
            {"node_id": "csod_causal_graph",        "display_name": "Causal Graph (CCE)",    "role": "retrieval"},
            {"node_id": "csod_cross_concept_check",  "display_name": "Cross-Concept Check",   "role": "enrichment"},
            {"node_id": "csod_metrics_retrieval",    "display_name": "Metrics Retrieval",      "role": "retrieval"},
            {"node_id": "csod_mdl_schema_retrieval", "display_name": "MDL Schema Retrieval",   "role": "retrieval"},
        ],
    },
    {
        "stage_id": "decisions",
        "stage_number": 3,
        "display_name": "Decisions",
        "description": "Score, qualify through decision tree, group by goal, and resolve layout ordering.",
        "icon": "git-branch",
        "nodes": [
            {"node_id": "csod_metric_qualification", "display_name": "Metric Qualification",  "role": "scoring"},
            {"node_id": "csod_layout_resolver",       "display_name": "Layout Resolver",       "role": "layout"},
        ],
    },
    {
        "stage_id": "analysis",
        "stage_number": 4,
        "display_name": "Analysis",
        "description": "Skill-augmented metric recommendation, post-validation, and output format selection.",
        "icon": "chart-bar",
        "nodes": [
            {"node_id": "skill_recommender_prep",     "display_name": "Skill Recommender",     "role": "skill"},
            {"node_id": "csod_metrics_recommender",    "display_name": "Metrics Recommender",   "role": "recommender"},
            {"node_id": "skill_validator",             "display_name": "Skill Validator",        "role": "validator"},
            {"node_id": "csod_output_format_selector", "display_name": "Format Selector",       "role": "selector"},
        ],
    },
    {
        "stage_id": "output",
        "stage_number": 5,
        "display_name": "Output",
        "description": "Execute domain-specific agents, generate deliverables, assemble final output, and produce narration.",
        "icon": "file-output",
        "nodes": [
            # Execution agents (conditional — not all run)
            {"node_id": "csod_data_science_insights_enricher", "display_name": "Insights Enricher",    "role": "executor"},
            {"node_id": "calculation_planner",                  "display_name": "Calculation Planner",  "role": "executor"},
            {"node_id": "csod_medallion_planner",              "display_name": "Medallion Planner",    "role": "executor"},
            {"node_id": "csod_gold_model_sql_generator",       "display_name": "Gold SQL Generator",   "role": "executor"},
            {"node_id": "cubejs_schema_generation",            "display_name": "CubeJS Schema",        "role": "executor"},
            {"node_id": "csod_dashboard_generator",            "display_name": "Dashboard Generator",  "role": "executor"},
            {"node_id": "csod_compliance_test_generator",      "display_name": "Test Generator",       "role": "executor"},
            {"node_id": "data_pipeline_planner",               "display_name": "Pipeline Planner",     "role": "executor"},
            {"node_id": "data_lineage_tracer",                 "display_name": "Lineage Tracer",       "role": "executor"},
            {"node_id": "data_discovery_agent",                "display_name": "Data Discovery",       "role": "executor"},
            {"node_id": "data_quality_inspector",              "display_name": "Data Quality",         "role": "executor"},
            {"node_id": "csod_scheduler",                      "display_name": "Scheduler",            "role": "executor"},
            # Assembly
            {"node_id": "csod_output_assembler",     "display_name": "Output Assembler",    "role": "assembler"},
            {"node_id": "csod_completion_narration",  "display_name": "Completion Narration", "role": "narration"},
        ],
    },
]


# ── Lookup helpers ────────────────────────────────────────────────────────────

# Node ID → stage metadata (for quick lookup during execution)
_NODE_TO_STAGE: Dict[str, Dict[str, Any]] = {}
for stage in PIPELINE_STAGES:
    for node in stage["nodes"]:
        _NODE_TO_STAGE[node["node_id"]] = {
            "stage_id": stage["stage_id"],
            "stage_number": stage["stage_number"],
            "stage_display_name": stage["display_name"],
            "node_display_name": node["display_name"],
            "role": node["role"],
        }


def get_stage_for_node(node_id: str) -> Dict[str, Any]:
    """Return stage metadata for a given node_id, or a default 'unknown' stage."""
    return _NODE_TO_STAGE.get(node_id, {
        "stage_id": "unknown",
        "stage_number": 0,
        "stage_display_name": "Unknown",
        "node_display_name": node_id,
        "role": "unknown",
    })


def get_all_stages() -> List[Dict[str, Any]]:
    """Return all pipeline stages for UI rendering."""
    return PIPELINE_STAGES


def get_stage_summary() -> List[Dict[str, Any]]:
    """Return compact stage summary (without node details) for UI progress bar."""
    return [
        {
            "stage_id": s["stage_id"],
            "stage_number": s["stage_number"],
            "display_name": s["display_name"],
            "description": s["description"],
            "icon": s["icon"],
            "node_count": len(s["nodes"]),
        }
        for s in PIPELINE_STAGES
    ]


def build_flow_timeline_from_execution_steps(
    execution_steps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Transform raw execution_steps (from state) into a UI-ready flow timeline
    grouped by pipeline stage.

    Each entry includes the stage context + node-level details from execution.
    The UI renders this as a vertical stage-by-stage timeline.
    """
    timeline: List[Dict[str, Any]] = []
    seen_stages: Dict[str, Dict[str, Any]] = {}

    for step in execution_steps:
        node_id = step.get("step_name", "")
        stage_meta = get_stage_for_node(node_id)
        stage_id = stage_meta["stage_id"]

        if stage_id not in seen_stages:
            seen_stages[stage_id] = {
                "stage_id": stage_id,
                "stage_number": stage_meta["stage_number"],
                "display_name": stage_meta["stage_display_name"],
                "status": "completed",
                "steps": [],
            }
            timeline.append(seen_stages[stage_id])

        seen_stages[stage_id]["steps"].append({
            "node_id": node_id,
            "display_name": stage_meta["node_display_name"],
            "role": stage_meta["role"],
            "status": step.get("status", "completed"),
            "timestamp": step.get("timestamp"),
            "outputs_summary": _summarize_outputs(step.get("outputs", {})),
        })

    # Sort timeline by stage_number
    timeline.sort(key=lambda s: s["stage_number"])
    return timeline


def _summarize_outputs(outputs: Dict[str, Any]) -> str:
    """Create a 1-line summary from step outputs for timeline display."""
    if not outputs:
        return ""
    parts = []
    for k, v in list(outputs.items())[:3]:
        if isinstance(v, (int, float)):
            parts.append(f"{k}={v}")
        elif isinstance(v, str) and len(v) < 60:
            parts.append(f"{k}={v}")
        elif isinstance(v, list):
            parts.append(f"{k}={len(v)} items")
        elif isinstance(v, bool):
            parts.append(f"{k}={'yes' if v else 'no'}")
    return ", ".join(parts)
