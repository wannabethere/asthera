"""
Direct Question Preview Generator node.

Runs after csod_direct_sql_gateway in the direct question (csod_planner_only) flow.
Converts gateway SQL results into preview cards (summary, insights, vega-lite spec)
using the same shape as csod_sql_agent_preview_node so the UI renders them identically.

For multi-question plans (multi_question / causal_rca / compare_segments), one preview
card is produced per atomic result.  For single_direct, one card is produced from the
primary gateway result.

State inputs:
    csod_gateway_sql_result     — {status, query, project_ids, response, atomic_results[]}
    csod_question_rephraser_output — {rephrased_question, source_tables, focus_area, …}
    csod_direct_query_plan      — {planning_mode, atomic_questions[], …}
    csod_plan_summary           — planner one-line summary

State output:
    csod_metric_previews        — list of preview card dicts (same shape as explore flow)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step
from app.agents.csod.csod_nodes.narrative import append_csod_narrative

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_sql_execution_data(gateway_response: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Pull sql_execution_data out of a CombinedAskResponse-shaped dict."""
    if not gateway_response:
        return {}
    return (gateway_response.get("metadata") or {}).get("sql_execution_data") or {}


def _extract_primary_sql(gateway_response: Optional[Dict[str, Any]]) -> str:
    items = (gateway_response or {}).get("response") or []
    return items[0].get("sql", "") if items else ""


def _extract_answer(gateway_response: Optional[Dict[str, Any]]) -> str:
    if not gateway_response:
        return ""
    items = gateway_response.get("response") or []
    answer = gateway_response.get("answer") or (items[0].get("content", "") if items else "")
    return answer or ""


async def _build_preview_card(
    name: str,
    nl_question: str,
    sql: str,
    answer: str,
    explanation: str,
    sql_execution_data: Dict[str, Any],
    source_tables: List[str],
    focus_area: str,
    plan_summary: str,
    project_ids: List[str],
    index: int,
) -> Dict[str, Any]:
    """
    Build a single preview card.

    Uses generate_single_preview for LLM summary/insights/chart type, then
    overwrites result_data and vega_lite_spec with the real SQL execution data
    when the gateway returned rows.
    """
    from app.agents.csod.csod_nodes.preview_generator import (
        generate_single_preview,
        _build_vega_lite_spec,
    )

    preview = await generate_single_preview(
        name=name,
        item_type="metric",
        description=answer[:300] if answer else "",
        nl_question=nl_question,
        focus_area=focus_area,
        intent="direct_analysis",
        source_tables=source_tables,
        plan_context=plan_summary[:200] if plan_summary else "",
        project_ids=project_ids,
        index=index,
    )

    # Override with real gateway data when available
    rows = sql_execution_data.get("rows") or []
    columns = sql_execution_data.get("columns") or []
    if rows:
        result_data = {
            "columns": columns,
            "rows": rows,
            "row_count": sql_execution_data.get("row_count", len(rows)),
        }
        preview["result_data"] = result_data
        preview["vega_lite_spec"] = _build_vega_lite_spec(
            chart_type=preview.get("chart_type", "bar"),
            result_data=result_data,
            title=name[:60],
        )

    if sql:
        preview["sql"] = sql
    if answer:
        preview["summary"] = answer
    if explanation:
        preview["explanation"] = explanation

    preview["source"] = "direct_question_preview"
    return preview


def _run_async(coro):
    """Run a coroutine from a sync LangGraph node."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(_run_in_new_loop, coro).result()
    else:
        return _run_in_new_loop(coro)


def _run_in_new_loop(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _generate_all_previews(
    gateway_result: Dict[str, Any],
    rephraser_output: Dict[str, Any],
    plan_summary: str,
    planning_mode: str,
) -> List[Dict[str, Any]]:
    source_tables: List[str] = rephraser_output.get("source_tables") or []
    focus_area: str = rephraser_output.get("focus_area") or ""
    project_ids: List[str] = list(rephraser_output.get("project_ids") or gateway_result.get("project_ids") or [])
    primary_question: str = rephraser_output.get("rephrased_question") or gateway_result.get("query", "")

    previews: List[Dict[str, Any]] = []

    # Multi-question: one card per atomic result
    atomic_results: List[Dict[str, Any]] = gateway_result.get("atomic_results") or []
    if atomic_results and planning_mode in ("multi_question", "causal_rca", "compare_segments"):
        tasks = []
        for idx, ar in enumerate(atomic_results):
            tasks.append(generate_preview_for_item(
                name=ar.get("rephrased_question", f"Question {idx + 1}")[:80],
                nl_question=ar.get("rephrased_question") or primary_question,
                item_type="metric",
                source_tables=list(ar.get("source_tables") or source_tables),
                focus_area=ar.get("focus_area") or focus_area,
                project_ids=list(ar.get("project_ids") or project_ids),
                plan_summary=plan_summary,
                index=idx,
                existing_gateway_response=ar.get("response") or {},
            ))
        previews = await asyncio.gather(*tasks, return_exceptions=False)
    else:
        # Single-question: one card from primary result.
        # csod_gateway_sql_result["response"] is the CombinedAskResponse dict returned by
        # _fake_gateway_response / _real_gateway_call; pass that inner dict so
        # _extract_primary_sql can reach its nested "response" list correctly.
        primary_response = gateway_result.get("response") or {}
        previews = [await generate_preview_for_item(
            name=primary_question[:80],
            nl_question=primary_question,
            item_type="metric",
            source_tables=source_tables,
            focus_area=focus_area,
            project_ids=project_ids,
            plan_summary=plan_summary,
            index=0,
            existing_gateway_response=primary_response,
        )]

    return [p for p in previews if p]


# ---------------------------------------------------------------------------
# Shared gateway → preview card entry point (used by both flows)
# ---------------------------------------------------------------------------

async def generate_preview_for_item(
    name: str,
    nl_question: str,
    item_type: str,
    source_tables: List[str],
    focus_area: str,
    project_ids: List[str],
    plan_summary: str,
    index: int,
    *,
    existing_gateway_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a single preview card via gateway call + LLM summary.

    If ``existing_gateway_response`` is provided (direct question flow, which already
    ran the gateway), the response is used as-is and no additional gateway call is made.

    Otherwise (explore metrics / KPI / table flow), calls the fake gateway LLM
    (``DEMO_FAKE_SQL_AND_INSIGHTS=True``) or the real SQL gateway, then builds the
    preview card with ``_build_preview_card``.

    Returns an empty dict on real-mode invocations without a pre-existing response
    (callers should filter these out).
    """
    from app.core.settings import get_settings
    settings = get_settings()

    if existing_gateway_response is not None:
        gw_response = existing_gateway_response
    elif settings.DEMO_FAKE_SQL_AND_INSIGHTS:
        from app.agents.csod.csod_nodes.node_direct_sql_gateway import _fake_gateway_response
        gw_response = await _fake_gateway_response(
            rephrased_question=nl_question,
            question_type=item_type,
            project_ids=project_ids,
            source_tables=source_tables,
            focus_area=focus_area,
            plan_summary=plan_summary,
        )
    else:
        logger.warning(
            "[generate_preview_for_item] real mode but no gateway response for %s — skipping",
            name,
        )
        return {}

    return await _build_preview_card(
        name=name,
        nl_question=nl_question,
        sql=_extract_primary_sql(gw_response),
        answer=_extract_answer(gw_response),
        explanation=(gw_response.get("explanation") or ""),
        sql_execution_data=_extract_sql_execution_data(gw_response),
        source_tables=source_tables,
        focus_area=focus_area,
        plan_summary=plan_summary,
        project_ids=project_ids,
        index=index,
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def csod_direct_question_preview_node(state: CSOD_State) -> CSOD_State:
    """
    Generate preview cards from direct question gateway results.

    Produces csod_metric_previews in the same shape as csod_sql_agent_preview_node
    so the UI renders them identically whether the flow was explore-metrics or direct.

    Gated on DEMO_FAKE_SQL_AND_INSIGHTS — only runs in fake/demo mode.
    In real mode the gateway response already carries SQL execution data; skip here.
    """
    from app.core.settings import get_settings
    settings = get_settings()
    if not settings.DEMO_FAKE_SQL_AND_INSIGHTS:
        logger.info("[direct_question_preview] real mode — skipping LLM preview generation")
        return state

    gateway_result: Dict[str, Any] = state.get("csod_gateway_sql_result") or {}
    if not gateway_result or gateway_result.get("status") == "error":
        logger.warning(
            "[direct_question_preview] gateway result missing or errored — skipping previews"
        )
        state["csod_metric_previews"] = []
        return state

    rephraser_output: Dict[str, Any] = state.get("csod_question_rephraser_output") or {}
    plan: Dict[str, Any] = state.get("csod_direct_query_plan") or {}
    planning_mode: str = plan.get("planning_mode") or gateway_result.get("planning_mode") or "single_direct"
    plan_summary: str = state.get("csod_plan_summary") or ""

    logger.info(
        "[direct_question_preview] planning_mode=%s atomic_results=%d",
        planning_mode,
        len(gateway_result.get("atomic_results") or []),
    )

    try:
        previews = _run_async(
            _generate_all_previews(
                gateway_result=gateway_result,
                rephraser_output=rephraser_output,
                plan_summary=plan_summary,
                planning_mode=planning_mode,
            )
        )
    except Exception as exc:
        logger.error("[direct_question_preview] failed: %s", exc, exc_info=True)
        previews = []

    state["csod_metric_previews"] = previews

    _csod_log_step(
        state,
        "csod_direct_question_preview",
        "direct_question_preview",
        inputs={"planning_mode": planning_mode},
        outputs={"preview_count": len(previews)},
    )

    append_csod_narrative(
        state,
        "preview",
        "Direct Analysis Ready",
        f"Generated {len(previews)} preview card{'s' if len(previews) != 1 else ''} "
        "from your direct question. Review the results, charts, and insights in the dashboard.",
        {"preview_count": len(previews)},
    )

    return state
