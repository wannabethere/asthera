"""Decision tree resolver (post-scoring qualification)."""
from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger

def csod_decision_tree_resolver_node(state: CSOD_State) -> CSOD_State:
    """
    Qualifies scored_metrics through DT: applies intent-specific min_composite,
    groups by dt_group_by. Sits after scoring_validator, before causal_graph.
    Data intelligence intents skip DT (pass-through).
    """
    try:
        logger.info(
            "[CSOD pipeline] decision_tree_resolver: qualifying metrics (intent=%s)",
            state.get("csod_intent", ""),
        )
        from app.agents.csod.intent_config import (
            get_dt_config_for_intent,
            should_skip_dt_for_intent,
        )
        intent = state.get("csod_intent", "")
        scored_metrics = state.get("resolved_metrics", [])  # from scoring_validator

        if should_skip_dt_for_intent(intent):
            state["dt_scored_metrics"] = scored_metrics
            state["dt_metric_groups"] = []
            state["dt_metric_decisions"] = {}
            state["csod_dt_config"] = {}
            _csod_log_step(state, "decision_tree_resolver", "decision_tree_resolver", {"intent": intent, "skip_dt": True}, {"dt_scored_count": len(scored_metrics)})
            return state

        dt_config = get_dt_config_for_intent(intent)
        state["csod_dt_config"] = dt_config
        min_composite = dt_config.get("min_composite", 0.55)

        # Inject intent-based decisions so existing DT enrichment can use them
        state["dt_metric_decisions"] = {
            "use_case": dt_config.get("use_case"),
            "goal": dt_config.get("goal"),
            "focus_area": state.get("data_enrichment", {}).get("suggested_focus_areas", [])[:1] or None,
            "metric_type": dt_config.get("metric_type"),
            "audience": dt_config.get("audience"),
            "timeframe": dt_config.get("timeframe"),
            "dt_group_by": dt_config.get("dt_group_by"),
        }

        # Run existing DT enrichment (score + threshold + group)
        try:
            from app.agents.decision_trees.dt_metric_decision_nodes import enrich_metrics_with_decision_tree
            state = enrich_metrics_with_decision_tree(state)
        except Exception as e:
            logger.warning(f"DT enrich failed, passing through scored_metrics: {e}", exc_info=True)
            state["dt_scored_metrics"] = scored_metrics
            state["dt_metric_groups"] = []

        # Apply intent-specific min_composite filter
        dt_scored = state.get("dt_scored_metrics", [])
        if min_composite and dt_scored:
            filtered = [m for m in dt_scored if (m.get("composite_score") or m.get("score") or 0) >= min_composite]
            state["dt_scored_metrics"] = filtered
            _csod_log_step(state, "decision_tree_resolver", "decision_tree_resolver", {"intent": intent, "min_composite": min_composite}, {"before": len(dt_scored), "after": len(filtered)})
        else:
            _csod_log_step(state, "decision_tree_resolver", "decision_tree_resolver", {"intent": intent}, {"dt_scored_count": len(state.get("dt_scored_metrics", []))})

    except Exception as e:
        logger.error(f"csod_decision_tree_resolver_node failed: {e}", exc_info=True)
        state.setdefault("dt_scored_metrics", state.get("resolved_metrics", []))
        state.setdefault("dt_metric_groups", [])
        state.setdefault("dt_metric_decisions", {})
        state.setdefault("csod_dt_config", {})

    return state
