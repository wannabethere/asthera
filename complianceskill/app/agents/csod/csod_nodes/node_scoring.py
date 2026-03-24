"""
Metric Qualification Node — merged scoring + decision tree qualification.

Replaces the previous two-node sequence of ``csod_scoring_validator`` →
``decision_tree_resolver`` with a single pass that scores, qualifies via DT,
and groups metrics.

Phase A: Score metrics/schemas by intent + focus area alignment (threshold 0.50)
Phase B: Qualify through decision tree (enrich, min_composite, group)
"""
import json
from typing import Dict

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger


# ── Scoring constants ─────────────────────────────────────────────────────────
THRESHOLD = 0.50
WARN_THRESHOLD = 0.65


def _score_item(item: Dict, intent: str, user_query: str, focus_cats: list) -> Dict:
    """Score an item based on intent keyword alignment + focus area match."""
    item_str = json.dumps(item).lower()
    intent_keywords = intent.replace("_", " ").split()
    query_words = [w for w in user_query.split() if len(w) > 3]
    combined = intent_keywords + query_words

    matches = sum(1 for kw in combined if kw in item_str)
    intent_score = min(1.0, matches / max(len(combined), 1) * 2)

    focus_score = 0.5
    if focus_cats:
        for cat in focus_cats:
            if cat.replace("_", " ") in item_str:
                focus_score = 1.0
                break

    composite = (intent_score * 0.5) + (focus_score * 0.5)
    return {
        **item,
        "composite_score": round(composite, 3),
        "low_confidence": composite < WARN_THRESHOLD,
    }


def _run_scoring(state: CSOD_State, intent: str) -> tuple:
    """Phase A: Score metrics and schemas, filter by threshold."""
    data_enrichment = state.get("data_enrichment", {})
    focus_cats = state.get("focus_area_categories", [])
    user_query = state.get("user_query", "").lower()

    metrics = state.get("resolved_metrics", [])
    scored_metrics = [_score_item(m, intent, user_query, focus_cats) for m in metrics]
    scored_metrics = [m for m in scored_metrics if m["composite_score"] >= THRESHOLD]
    scored_metrics.sort(key=lambda m: m.get("composite_score", 0.0), reverse=True)

    schemas = state.get("csod_resolved_schemas", [])
    scored_schemas = [_score_item(s, intent, user_query, focus_cats) for s in schemas]
    scored_schemas = [s for s in scored_schemas if s["composite_score"] >= THRESHOLD]

    return metrics, schemas, scored_metrics, scored_schemas


def _run_dt_qualification(state: CSOD_State, intent: str, scored_metrics: list) -> None:
    """Phase B: Decision tree enrichment, min_composite filter, grouping."""
    from app.agents.csod.intent_config import should_skip_dt_for_intent

    if should_skip_dt_for_intent(intent):
        state["dt_scored_metrics"] = scored_metrics
        state["dt_metric_groups"] = []
        state["dt_metric_decisions"] = {}
        state["csod_dt_config"] = {}
        return

    from app.agents.capabilities.capability_spine import seed_csod_decision_tree_axis_state

    seed_csod_decision_tree_axis_state(state)
    dt_config = state.get("csod_dt_config") or {}
    min_composite = dt_config.get("min_composite", 0.55)

    try:
        from app.agents.decision_trees.dt_metric_decision_nodes import enrich_metrics_with_decision_tree
        state.update(enrich_metrics_with_decision_tree(state))
    except Exception as e:
        logger.warning("DT enrich failed, passing through scored_metrics: %s", e, exc_info=True)
        state["dt_scored_metrics"] = scored_metrics
        state["dt_metric_groups"] = []

    hint = state.get("dt_group_by_hint")
    if hint and isinstance(state.get("dt_metric_decisions"), dict):
        state["dt_metric_decisions"]["dt_group_by"] = hint

    dt_scored = state.get("dt_scored_metrics", [])
    if min_composite and dt_scored:
        state["dt_scored_metrics"] = [
            m for m in dt_scored
            if (m.get("composite_score") or m.get("score") or 0) >= min_composite
        ]


# ── Main merged node ──────────────────────────────────────────────────────────

def csod_metric_qualification_node(state: CSOD_State) -> CSOD_State:
    """
    Unified metric qualification: scoring + decision tree in a single pass.

    Phase A — Score metrics/schemas by intent + focus area alignment.
    Phase B — Qualify through decision tree (enrich, min_composite, group).

    Writes: csod_scored_context, resolved_metrics, csod_resolved_schemas,
            dt_scored_metrics, dt_metric_groups, dt_metric_decisions, csod_dt_config
    """
    try:
        intent = state.get("csod_intent", "")
        logger.info("[CSOD pipeline] metric_qualification: scoring + DT (intent=%s)", intent)

        # Phase A: Scoring
        metrics_in, schemas_in, scored_metrics, scored_schemas = _run_scoring(state, intent)

        scored_context = {
            "scored_metrics": scored_metrics,
            "resolved_schemas": scored_schemas,
            "gold_standard_tables": state.get("csod_gold_standard_tables", []),
        }
        state["csod_scored_context"] = scored_context
        state["resolved_metrics"] = scored_metrics
        state["csod_resolved_schemas"] = scored_schemas

        # Phase B: DT qualification
        _run_dt_qualification(state, intent, scored_metrics)

        # Logging
        dt_count = len(state.get("dt_scored_metrics", []))
        group_count = len(state.get("dt_metric_groups", []))
        _csod_log_step(
            state, "metric_qualification", "metric_qualification",
            inputs={"metrics_in": len(metrics_in), "schemas_in": len(schemas_in)},
            outputs={
                "scored_metrics": len(scored_metrics),
                "scored_schemas": len(scored_schemas),
                "dt_scored": dt_count,
                "dt_groups": group_count,
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"Metric qualification: {len(scored_metrics)} scored → "
                f"{dt_count} DT-qualified across {group_count} groups"
            )
        ))

        try:
            from app.agents.csod.csod_nodes.narrative import append_csod_narrative
            append_csod_narrative(
                state, "dt",
                "Metric qualification",
                f"Scored {len(metrics_in)} → {len(scored_metrics)} metrics, "
                f"DT-qualified {dt_count} across {group_count} goal-aligned groups.",
            )
        except Exception:
            pass

    except Exception as e:
        logger.error("csod_metric_qualification_node failed: %s", e, exc_info=True)
        state["error"] = f"Metric qualification failed: {str(e)}"
        state["csod_scored_context"] = {
            "scored_metrics": state.get("resolved_metrics", []),
            "resolved_schemas": state.get("csod_resolved_schemas", []),
            "gold_standard_tables": state.get("csod_gold_standard_tables", []),
        }
        state.setdefault("dt_scored_metrics", state.get("resolved_metrics", []))
        state.setdefault("dt_metric_groups", [])
        state.setdefault("dt_metric_decisions", {})
        state.setdefault("csod_dt_config", {})

    return state


# ── Backward compat aliases ───────────────────────────────────────────────────
# Old names still work — import from here if needed.
csod_scoring_validator_node = csod_metric_qualification_node
csod_decision_tree_resolver_node = csod_metric_qualification_node
