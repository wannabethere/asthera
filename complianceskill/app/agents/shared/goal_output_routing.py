"""
Map goal + LLM output-intent classification into workflow state flags.

Downstream graphs read ``output_format``, ``dt_generate_sql``, ``csod_generate_sql``,
``data_enrichment``, ``intent``, and ``compliance_profile`` — this module sets those
conservatively (OR with existing flags, never downgrade True→False).
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

# Deliverable ids (must align with goal intent catalog + LLM prompt)
DELIVERABLE_DASHBOARD = "dashboard"
DELIVERABLE_ADHOC = "adhoc_analysis"
DELIVERABLE_METRICS_REC = "metrics_recommendations"
DELIVERABLE_REPORT = "report"
DELIVERABLE_ALERTS = "alert_generation"
DELIVERABLE_AUTOMATION = "workflow_automation"

ALL_DELIVERABLES: Set[str] = {
    DELIVERABLE_DASHBOARD,
    DELIVERABLE_ADHOC,
    DELIVERABLE_METRICS_REC,
    DELIVERABLE_REPORT,
    DELIVERABLE_ALERTS,
    DELIVERABLE_AUTOMATION,
}


def normalize_deliverables(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        if isinstance(x, str) and x in ALL_DELIVERABLES and x not in out:
            out.append(x)
    return out


def apply_goal_output_routing_to_state(
    state: Dict[str, Any],
    classifier_result: Dict[str, Any],
    *,
    source_goal_intent: str,
) -> None:
    """
    Apply ``classifier_result`` from the goal output intent LLM into ``state``.

    Expected classifier keys:
      - ``deliverables``: list of ids
      - ``pipeline_flags``: optional dict with needs_gold_dbt_sql, needs_cubejs,
        needs_metrics_registry, needs_mdl_schemas, needs_calculation_plan
      - ``primary_user_goal_summary``, ``reasoning``, ``possible_outcomes_for_user`` (passthrough)
    """
    deliverables = normalize_deliverables(
        classifier_result.get("deliverables") or classifier_result.get("selected_outputs")
    )
    flags = classifier_result.get("pipeline_flags") if isinstance(classifier_result.get("pipeline_flags"), dict) else {}

    merged = {**classifier_result, "deliverables": deliverables, "source_goal_intent": source_goal_intent}
    state["goal_output_classifier_result"] = merged
    state["goal_output_intents"] = deliverables

    def _flag(name: str) -> bool:
        v = flags.get(name)
        return bool(v) if v is not None else False

    needs_gold = _flag("needs_gold_dbt_sql")
    needs_cube = _flag("needs_cubejs")
    needs_metrics = _flag("needs_metrics_registry")
    needs_mdl = _flag("needs_mdl_schemas")

    if DELIVERABLE_DASHBOARD in deliverables:
        needs_cube = True
        needs_metrics = True
        needs_mdl = True
    if DELIVERABLE_METRICS_REC in deliverables:
        needs_metrics = True
    if DELIVERABLE_ADHOC in deliverables:
        needs_metrics = True
        needs_mdl = True
    if DELIVERABLE_REPORT in deliverables:
        needs_metrics = True
    if DELIVERABLE_ALERTS in deliverables:
        needs_metrics = True

    if needs_gold:
        state["dt_generate_sql"] = bool(state.get("dt_generate_sql")) or True
        state["csod_generate_sql"] = bool(state.get("csod_generate_sql")) or True

    if needs_cube:
        state["output_format"] = "cubejs"

    de = dict(state.get("data_enrichment") or {})
    if needs_metrics:
        de["needs_metrics"] = True
    if needs_mdl:
        de["needs_mdl"] = True
    state["data_enrichment"] = de

    if DELIVERABLE_DASHBOARD in deliverables and not state.get("intent"):
        state["intent"] = "dashboard_generation"

    cp = dict(state.get("compliance_profile") or {})
    cp["goal_intent"] = source_goal_intent
    cp["goal_deliverables"] = deliverables
    cp["goal_pipeline_flags"] = {
        "needs_gold_dbt_sql": bool(needs_gold or state.get("dt_generate_sql") or state.get("csod_generate_sql")),
        "needs_cubejs": bool(needs_cube or state.get("output_format") == "cubejs"),
        "needs_metrics_registry": bool(needs_metrics),
        "needs_mdl_schemas": bool(needs_mdl),
        "needs_calculation_plan": bool(flags.get("needs_calculation_plan", False)),
    }
    cp["goal_output_summary"] = classifier_result.get("primary_user_goal_summary") or ""
    outcomes = classifier_result.get("possible_outcomes_for_user")
    if isinstance(outcomes, list):
        cp["goal_possible_outcomes"] = outcomes
    state["compliance_profile"] = cp
