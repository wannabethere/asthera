"""
Global Filter Configurator Node
================================

STAGE 5 node — runs after csod_gold_model_sql_generator.

Reads resolved MDL schemas + selected metrics/KPIs + generated gold model SQL
and calls GlobalFilterRecommender (LLM) to produce a ``csod_global_filter_config``
dict that the output assembler and frontend can use to render a global filter bar.

State inputs:
  csod_resolved_schemas         — MDL silver tables with column metadata
  csod_metric_recommendations   — selected metrics
  csod_kpi_recommendations      — selected KPIs
  csod_generated_gold_model_sql — generated dbt gold model SQL
  csod_intent                   — pipeline intent
  user_query                    — original user question

State outputs:
  csod_global_filter_config     — GlobalFilterConfig serialised to dict
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    logger,
)
from app.agents.csod.csod_tool_integration import run_async


def csod_global_filter_configurator_node(state: CSOD_State) -> CSOD_State:
    """
    Recommend a global filter configuration for the dashboard.

    Always runs (even when no gold SQL was generated) because filter
    dimensions come from the MDL schemas and metric source tables.
    Skips gracefully if no schemas or metrics are available.
    """
    resolved_schemas = state.get("csod_resolved_schemas") or []
    metric_recs = state.get("csod_metric_recommendations") or []
    kpi_recs = state.get("csod_kpi_recommendations") or []
    gold_sql = state.get("csod_generated_gold_model_sql") or []

    if not resolved_schemas and not metric_recs and not kpi_recs:
        logger.info(
            "csod_global_filter_configurator: skipping — no schemas or metrics available"
        )
        state["csod_global_filter_config"] = None
        return state

    try:
        from app.agents.shared.global_filter_recommender import GlobalFilterRecommender

        recommender = GlobalFilterRecommender(timeout=30.0)
        config = run_async(
            recommender.recommend(
                resolved_schemas=resolved_schemas,
                metric_recommendations=metric_recs,
                kpi_recommendations=kpi_recs,
                gold_model_sql=gold_sql,
                intent=state.get("csod_intent", ""),
                user_query=state.get("user_query", ""),
            )
        )

        state["csod_global_filter_config"] = config.model_dump()

        _csod_log_step(
            state,
            "csod_global_filter_configuration",
            "csod_global_filter_configurator",
            inputs={
                "schemas": len(resolved_schemas),
                "metrics": len(metric_recs),
                "kpis": len(kpi_recs),
                "gold_models": len(gold_sql),
            },
            outputs={
                "filters_recommended": len(config.filters),
                "primary_date_field": config.primary_date_field,
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"Global Filter Config: recommended {len(config.filters)} filter dimensions "
                f"(primary date: {config.primary_date_field or 'n/a'})"
            )
        ))
        logger.info(
            "csod_global_filter_configurator: produced %d filters, date=%s",
            len(config.filters), config.primary_date_field,
        )

    except Exception as exc:
        logger.exception("csod_global_filter_configurator failed: %s", exc)
        state["csod_global_filter_config"] = None

    return state
