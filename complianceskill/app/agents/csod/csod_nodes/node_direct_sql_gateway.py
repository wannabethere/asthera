"""
Direct SQL Gateway node.

After the question rephraser resolves a DIRECT_SQL / TREND_ANALYTICAL / ALERT_RCA
question and its target project_ids, this node dispatches to the Genieml Agents
gateway (combined_ask) and stores the SQL execution result in state.

Flag gating (mirrors preview_generator.py pattern):
  DEMO_FAKE_SQL_AND_INSIGHTS=False (default)
    → calls Genieml Agents /api/v1/combined/combined with the planner-enriched query
  DEMO_FAKE_SQL_AND_INSIGHTS=True
    → generates a fake combined_ask-shaped response locally via LLM + dummy data
      (no HTTP call; real warehouse not required)

State inputs:
    csod_question_rephraser_output  — {rephrased_question, project_ids, question_type,
                                        source_tables, focus_area}
    csod_plan_summary               — planner's one-line summary
    csod_execution_plan             — [{step_id, description, semantic_question, …}]
    csod_data_sources_in_scope      — resolved data sources

State output:
    csod_gateway_sql_result         — {status, query, project_ids, question_type, response}
    response mirrors CombinedAskResponse:
      {status, type, response[{sql, content}], metadata{sql_execution_data}, answer, explanation}
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt for fake SQL + answer generation
# ---------------------------------------------------------------------------

_FAKE_GATEWAY_PROMPT = """\
Generate a minimal demo SQL result for this compliance question. Be brief.

Type: {question_type}
Question: {rephrased_question}
Tables: {source_tables}
Focus: {focus_area}

Return ONLY valid JSON, no markdown. Max 4 rows. Keep SQL short (1–3 lines).
{{
  "sql": "SELECT col1, col2 FROM table LIMIT 4",
  "answer": "One sentence answer with a plausible number.",
  "explanation": "One sentence.",
  "columns": ["col1", "col2"],
  "rows": [{{"col1": "v", "col2": 42}}]
}}
"""


# ---------------------------------------------------------------------------
# Fake response builder (no warehouse needed)
# ---------------------------------------------------------------------------

async def _fake_gateway_response(
    rephrased_question: str,
    question_type: str,
    project_ids: List[str],
    source_tables: List[str],
    focus_area: str,
    plan_summary: str,
) -> Dict[str, Any]:
    """
    Generate a CombinedAskResponse-shaped dict entirely via LLM.
    SQL, answer, explanation, columns, and rows are all LLM-generated.
    No HTTP calls; safe to run without a warehouse.
    """
    import asyncio

    prompt = _FAKE_GATEWAY_PROMPT.format(
        question_type=question_type,
        rephrased_question=rephrased_question[:400],
        source_tables=", ".join(source_tables[:5]) or "N/A",
        focus_area=focus_area or "compliance",
        plan_summary=plan_summary[:200] or "N/A",
    )

    llm_result: Dict[str, Any] = {}
    try:
        from app.core.dependencies import get_llm
        llm = get_llm()
        resp = await asyncio.wait_for(llm.ainvoke(prompt), timeout=15.0)
        content = resp.content if hasattr(resp, "content") else str(resp)
        llm_result = _parse_json_safe(content)
    except asyncio.TimeoutError:
        logger.warning("[csod_direct_sql_gateway] fake LLM timed out")
    except Exception as exc:
        logger.warning("[csod_direct_sql_gateway] fake LLM failed: %s", exc)

    fake_sql: str = llm_result.get("sql") or _fallback_sql(rephrased_question, source_tables)
    answer: str = llm_result.get("answer") or f"Demo answer for: {rephrased_question[:100]}"
    explanation: str = llm_result.get("explanation") or ""
    reasoning: str = llm_result.get("sql_generation_reasoning") or ""
    columns: List[str] = llm_result.get("columns") or []
    rows: List[Dict[str, Any]] = llm_result.get("rows") or []

    sql_execution_data: Dict[str, Any] = {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }

    return {
        "status": "finished",
        "type": "TEXT_TO_SQL",
        "response": [
            {
                "sql": fake_sql,
                "content": answer,
            }
        ],
        "error": None,
        "retrieved_tables": source_tables or None,
        "sql_generation_reasoning": reasoning,
        "is_followup": False,
        "quality_scoring": None,
        "invalid_sql": None,
        "metadata": {
            "sql_execution_data": sql_execution_data,
        },
        "processing_time_seconds": 0.0,
        "timestamp": datetime.utcnow().isoformat(),
        "answer": answer,
        "explanation": explanation,
    }


def _fallback_sql(question: str, tables: List[str]) -> str:
    tbl = tables[0] if tables else "compliance_records"
    slug = re.sub(r"[^\w ]", "", question.lower())[:40].strip().replace(" ", "_")
    return (
        f"-- Demo: {slug}\n"
        f"SELECT department, COUNT(*) AS record_count, "
        f"ROUND(AVG(completion_rate), 2) AS avg_completion_rate\n"
        f"FROM {tbl}\n"
        f"WHERE status = 'active'\n"
        f"GROUP BY department\n"
        f"ORDER BY avg_completion_rate DESC\n"
        f"LIMIT 20;"
    )



def _parse_json_safe(raw: str) -> Dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return {}


# ---------------------------------------------------------------------------
# Real gateway call
# ---------------------------------------------------------------------------

async def _real_gateway_call(
    query: str,
    project_ids: List[str],
    base_url: str,
    timeout: float,
) -> Dict[str, Any]:
    """POST to /api/v1/combined/combined and return the response as a dict."""
    url = f"{base_url.rstrip('/')}/api/v1/combined/combined"
    primary_project_id = project_ids[0] if project_ids else None

    payload: Dict[str, Any] = {
        "query_id": str(uuid.uuid4()),
        "query": query,
        "project_ids": project_ids,
        "histories": [],
        "enable_scoring": True,
    }
    if primary_project_id:
        payload["project_id"] = primary_project_id

    logger.info(
        "[csod_direct_sql_gateway] POST %s | project_ids=%s | query_len=%d",
        url, project_ids, len(query),
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def _build_gateway_query(
    rephrased_question: str,
    plan_summary: str,
    execution_plan: List[Dict[str, Any]],
) -> str:
    """
    Compose the query string sent to combined_ask.

    The rephrased question is the primary ask; planner context follows as
    bracketed hints so the SQL agent can use schema-grounded step descriptions.
    """
    parts = [rephrased_question]

    if plan_summary:
        parts.append(f"\n[Analysis context: {plan_summary}]")

    step_nl = [
        s.get("semantic_question") or s.get("description", "")
        for s in (execution_plan or [])[:5]
        if s.get("semantic_question") or s.get("description")
    ]
    if step_nl:
        parts.append("\n[Execution steps: " + " | ".join(step_nl) + "]")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def _dispatch_one(
    run_async: Any,
    settings: Any,
    rephrased_question: str,
    question_type: str,
    project_ids: List[str],
    source_tables: List[str],
    focus_area: str,
    plan_summary: str,
    execution_plan: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Dispatch a single question (fake or real) and return the gateway response dict."""
    query = _build_gateway_query(rephrased_question, plan_summary, execution_plan)
    if settings.DEMO_FAKE_SQL_AND_INSIGHTS:
        response = run_async(
            _fake_gateway_response(
                rephrased_question=rephrased_question,
                question_type=question_type,
                project_ids=project_ids,
                source_tables=source_tables,
                focus_area=focus_area,
                plan_summary=plan_summary,
            )
        )
    else:
        response = run_async(
            _real_gateway_call(
                query=query,
                project_ids=project_ids,
                base_url=settings.GENIEML_AGENTS_BASE_URL,
                timeout=settings.GENIEML_AGENTS_TIMEOUT,
            )
        )
    return {"query": query, "response": response}


def csod_direct_sql_gateway_node(state: CSOD_State) -> CSOD_State:
    """
    Dispatch rephrased question(s) to the Genieml Agents gateway OR generate
    fake responses locally, depending on DEMO_FAKE_SQL_AND_INSIGHTS.

    For multi-question plans (multi_question / causal_rca / compare_segments)
    each atomic rephrased question is dispatched and stored in
    ``csod_gateway_sql_result.atomic_results``.  The primary result is always
    in ``csod_gateway_sql_result.response`` for backward compat.
    """
    from app.agents.csod.csod_tool_integration import run_async

    settings = get_settings()
    rephraser_output: Dict[str, Any] = state.get("csod_question_rephraser_output") or {}
    planning_mode: str = rephraser_output.get("planning_mode") or "single_direct"

    rephrased_question: str = rephraser_output.get("rephrased_question") or state.get("user_query", "")
    project_ids: List[str] = list(rephraser_output.get("project_ids") or [])
    question_type: str = rephraser_output.get("question_type", "DIRECT_SQL")
    source_tables: List[str] = rephraser_output.get("source_tables") or []
    focus_area: str = rephraser_output.get("focus_area") or ""
    atomic_rephrased: List[Dict[str, Any]] = rephraser_output.get("atomic_rephrased_questions") or []

    plan_summary: str = state.get("csod_plan_summary") or ""
    execution_plan: List[Dict[str, Any]] = state.get("csod_execution_plan") or []

    logger.info(
        "[csod_direct_sql_gateway] mode=%s planning_mode=%s question_type=%s atomic_count=%d",
        "FAKE" if settings.DEMO_FAKE_SQL_AND_INSIGHTS else "REAL",
        planning_mode, question_type, len(atomic_rephrased),
    )

    try:
        # ── Multi-question dispatch ─────────────────────────────────────────
        atomic_results: List[Dict[str, Any]] = []
        if atomic_rephrased and planning_mode in ("multi_question", "causal_rca", "compare_segments"):
            for aq in atomic_rephrased:
                aq_question = aq.get("rephrased_question") or rephrased_question
                aq_ids = list(aq.get("project_ids") or project_ids)
                aq_tables = list(aq.get("source_tables") or source_tables)
                aq_type = aq.get("question_type") or question_type
                try:
                    dispatched = _dispatch_one(
                        run_async, settings,
                        rephrased_question=aq_question,
                        question_type=aq_type,
                        project_ids=aq_ids,
                        source_tables=aq_tables,
                        focus_area=aq.get("focus_area") or focus_area,
                        plan_summary=plan_summary,
                        execution_plan=execution_plan,
                    )
                    atomic_results.append({
                        "question_id": aq.get("question_id", ""),
                        "analysis_type": aq.get("analysis_type", ""),
                        "target_metric": aq.get("target_metric", ""),
                        "rephrased_question": aq_question,
                        "project_ids": aq_ids,
                        **dispatched,
                    })
                    logger.info(
                        "[csod_direct_sql_gateway] atomic %s dispatched | status=%s",
                        aq.get("question_id", "?"),
                        dispatched["response"].get("status", "?"),
                    )
                except Exception as aqe:
                    logger.warning("[csod_direct_sql_gateway] atomic dispatch failed: %s", aqe)
                    atomic_results.append({
                        "question_id": aq.get("question_id", ""),
                        "rephrased_question": aq_question,
                        "project_ids": aq_ids,
                        "query": aq_question,
                        "response": None,
                        "error": str(aqe),
                    })

        # ── Primary question dispatch ───────────────────────────────────────
        primary = _dispatch_one(
            run_async, settings,
            rephrased_question=rephrased_question,
            question_type=question_type,
            project_ids=project_ids,
            source_tables=source_tables,
            focus_area=focus_area,
            plan_summary=plan_summary,
            execution_plan=execution_plan,
        )

        state["csod_gateway_sql_result"] = {
            "status": "success",
            "query": primary["query"],
            "project_ids": project_ids,
            "question_type": question_type,
            "planning_mode": planning_mode,
            "demo": settings.DEMO_FAKE_SQL_AND_INSIGHTS,
            "response": primary["response"],
            "atomic_results": atomic_results,
        }
        logger.info(
            "[csod_direct_sql_gateway] done | primary_status=%s atomic=%d",
            primary["response"].get("status", "?"), len(atomic_results),
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "[csod_direct_sql_gateway] HTTP %s: %s",
            exc.response.status_code, exc.response.text[:500],
        )
        state["csod_gateway_sql_result"] = {
            "status": "error",
            "query": rephrased_question,
            "project_ids": project_ids,
            "question_type": question_type,
            "planning_mode": planning_mode,
            "demo": False,
            "error": f"Gateway HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            "response": None,
            "atomic_results": [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("[csod_direct_sql_gateway] failed: %s", exc, exc_info=True)
        state["csod_gateway_sql_result"] = {
            "status": "error",
            "query": rephrased_question,
            "project_ids": project_ids,
            "question_type": question_type,
            "planning_mode": planning_mode,
            "demo": settings.DEMO_FAKE_SQL_AND_INSIGHTS,
            "error": str(exc),
            "response": None,
            "atomic_results": [],
        }

    _csod_log_step(
        state,
        "csod_direct_sql_gateway",
        "csod_direct_sql_gateway",
        inputs={
            "planning_mode": planning_mode,
            "question_type": question_type,
            "project_ids": project_ids,
            "atomic_count": len(atomic_rephrased),
            "demo": settings.DEMO_FAKE_SQL_AND_INSIGHTS,
        },
        outputs={
            "gateway_status": state["csod_gateway_sql_result"]["status"],
            "atomic_dispatched": len(state["csod_gateway_sql_result"].get("atomic_results", [])),
        },
    )

    return state
