"""Data science insights enricher (stub)."""
from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger

def csod_data_science_insights_enricher_node(state: CSOD_State) -> CSOD_State:
    """
    Enriches metric recommendations with data science insights (SQL functions, trend analysis, etc.).

    Used after csod_metrics_recommender and csod_dashboard_generator to add analytical depth.
    For each recommended metric/KPI/table, generates 3-5 insights using SQL functions from the library.

    Stub implementation: passes through state with empty insights. Full implementation would use
    prompt 09_data_science_insights_enricher.md and LLM to generate insights.
    """
    try:
        # Ensure csod_data_science_insights is set (stub: empty list for now)
        if "csod_data_science_insights" not in state or state["csod_data_science_insights"] is None:
            state["csod_data_science_insights"] = []

        _csod_log_step(
            state, "csod_data_science_insights_enricher", "csod_data_science_insights_enricher",
            inputs={
                "metric_count": len(state.get("csod_metric_recommendations", [])),
                "kpi_count": len(state.get("csod_kpi_recommendations", [])),
            },
            outputs={
                "insights_count": len(state.get("csod_data_science_insights", [])),
            },
        )
    except Exception as e:
        logger.warning(f"csod_data_science_insights_enricher_node: {e}", exc_info=True)
        state.setdefault("csod_data_science_insights", [])

    return state
