"""
SQL Agent Placeholder Nodes — metric preview and adhoc/RCA query execution.

Two nodes:
  1. csod_sql_agent_preview_node — previews selected metrics via external SQL agent
     (placeholder returns LLM-generated dummy data/visuals/insights)
  2. csod_sql_agent_adhoc_node  — handles adhoc/RCA analysis by generating NL queries
     from causal graph context, sending to SQL agent (placeholder returns dummy results)

Both share a common _call_sql_agent_placeholder() that builds synthetic responses.
When a real SQL agent server is available, swap that function to HTTP call.
"""
from __future__ import annotations

import hashlib
import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _parse_json_response,
    logger,
)
from app.core.dependencies import get_llm

# ---------------------------------------------------------------------------
# Placeholder SQL agent (swap to HTTP client when real agent exists)
# ---------------------------------------------------------------------------

_PREVIEW_SUMMARY_PROMPT = """\
You are a data analyst. Given this metric definition, generate a brief 2-sentence summary
of what this metric measures and a realistic insight about its current state.

Metric: {metric_name}
Description: {metric_description}
Focus Area: {focus_area}
Intent: {intent}

Return JSON:
{{
  "summary": "2-sentence plain-English summary of what this metric shows",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "chart_type": "line|bar|gauge|table",
  "trend_direction": "up|down|stable"
}}
"""

_ADHOC_NL_QUERY_PROMPT = """\
You are a data analyst working with a causal graph of training/compliance metrics.

User question: {user_query}
Intent: {intent}

Causal graph context:
Nodes: {causal_nodes}
Edges: {causal_edges}

Available schemas:
{schema_summary}

Generate a list of natural-language SQL questions that would answer the user's question.
For RCA analysis, trace the causal paths and generate one question per causal relationship.
For adhoc analysis, generate 1-3 targeted questions.

Return JSON:
{{
  "queries": [
    {{
      "nl_question": "What is the average completion rate by department for Q4?",
      "target_table": "fact_training_completions",
      "causal_path": "assignment_volume → training_completion → compliance_posture",
      "priority": "high|medium|low"
    }}
  ]
}}
"""


def _generate_dummy_preview_data(metric_name: str, idx: int) -> Dict[str, Any]:
    """Generate synthetic tabular preview data for a metric."""
    # Deterministic seed for consistent dummy data
    seed = int(hashlib.md5(metric_name.encode()).hexdigest()[:8], 16)
    base_value = 60 + (seed % 35)
    rows = []
    for month_offset in range(5):
        period = (datetime.now() - timedelta(days=30 * (4 - month_offset))).strftime("%Y-%m")
        value = round(base_value + (month_offset * 2.3) + ((seed + month_offset) % 7), 1)
        delta = round(value - base_value, 1)
        rows.append({
            "period": period,
            "value": value,
            "delta_pct": round((delta / base_value) * 100, 1) if base_value else 0,
            "cohort_size": 100 + (seed % 500) + (month_offset * 20),
        })
    return {
        "columns": ["period", "value", "delta_pct", "cohort_size"],
        "rows": rows,
        "row_count": len(rows),
    }


def _generate_dummy_adhoc_result(nl_question: str, idx: int) -> Dict[str, Any]:
    """Generate synthetic query result for adhoc/RCA SQL question."""
    seed = int(hashlib.md5(nl_question.encode()).hexdigest()[:8], 16)
    rows = []
    segments = ["Engineering", "Sales", "Operations", "Finance", "HR"]
    for i, seg in enumerate(segments[:4]):
        rows.append({
            "segment": seg,
            "metric_value": round(65 + (seed + i) % 30 + (i * 1.7), 1),
            "target": 90.0,
            "gap": round(90.0 - (65 + (seed + i) % 30 + (i * 1.7)), 1),
            "record_count": 50 + (seed + i) % 200,
        })
    return {
        "columns": ["segment", "metric_value", "target", "gap", "record_count"],
        "rows": rows,
        "row_count": len(rows),
        "generated_sql": f"-- Placeholder SQL for: {nl_question[:80]}\nSELECT * FROM placeholder_table LIMIT 100;",
    }


async def _call_sql_agent_placeholder(
    queries: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Placeholder SQL agent — returns LLM-generated summaries with dummy data.

    When a real SQL agent server exists, replace this with:
        async with httpx.AsyncClient() as client:
            resp = await client.post(SQL_AGENT_URL, json={...})
            return resp.json()["results"]
    """
    results = []
    llm = get_llm()

    for idx, q in enumerate(queries):
        nl_question = q.get("nl_question") or q.get("metric_name") or f"Query {idx+1}"
        description = q.get("description") or q.get("metric_description") or nl_question
        focus = q.get("focus_area") or context.get("primary_focus_area", "compliance")
        intent = context.get("intent", "analysis")

        # Generate dummy tabular data
        if q.get("type") == "metric_preview":
            preview_data = _generate_dummy_preview_data(nl_question, idx)
        else:
            preview_data = _generate_dummy_adhoc_result(nl_question, idx)

        # LLM-generated summary + insights
        try:
            prompt = _PREVIEW_SUMMARY_PROMPT.format(
                metric_name=nl_question,
                metric_description=description[:300],
                focus_area=focus,
                intent=intent,
            )
            resp = await llm.ainvoke(prompt)
            content = resp.content if hasattr(resp, "content") else str(resp)
            parsed = _parse_json_response(content, {})
        except Exception as e:
            logger.warning("SQL agent placeholder LLM call failed: %s", e)
            parsed = {}

        result = {
            "query_id": q.get("query_id") or f"q_{idx}",
            "nl_question": nl_question,
            "description": description,
            "result_data": preview_data,
            "summary": parsed.get("summary", f"Preview data for {nl_question}"),
            "insights": parsed.get("insights", [f"Showing preview for {nl_question}"]),
            "chart_type": parsed.get("chart_type", "bar"),
            "trend_direction": parsed.get("trend_direction", "stable"),
            "source": "sql_agent_placeholder",
        }

        # Include generated SQL if adhoc
        if "generated_sql" in preview_data:
            result["generated_sql"] = preview_data.pop("generated_sql")

        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Node 1: Preview selected metrics
# ---------------------------------------------------------------------------

def csod_sql_agent_preview_node(state: CSOD_State) -> CSOD_State:
    """
    Preview selected metrics via SQL agent.

    Reads: csod_metric_recommendations, csod_selected_metric_ids, csod_resolved_schemas, csod_intent
    Writes: csod_metric_previews (list of preview objects per metric)
    """
    # Skip if already previewed or not in interactive mode
    if state.get("csod_metric_previews"):
        logger.info("Metric previews already populated — pass-through")
        return state

    metrics = state.get("csod_metric_recommendations") or []
    kpis = state.get("csod_kpi_recommendations") or []

    if not metrics and not kpis:
        state["csod_metric_previews"] = []
        return state

    # Build queries for the SQL agent
    queries = []
    for m in metrics[:10]:  # Cap preview at 10
        queries.append({
            "query_id": m.get("metric_id") or m.get("name"),
            "nl_question": m.get("natural_language_question") or m.get("name") or "",
            "metric_name": m.get("name") or m.get("metric_id") or "",
            "description": m.get("description") or "",
            "focus_area": m.get("focus_area") or "",
            "source_schemas": m.get("source_schemas") or [],
            "type": "metric_preview",
        })
    for k in kpis[:5]:  # Cap KPI preview at 5
        queries.append({
            "query_id": k.get("kpi_id") or k.get("name"),
            "nl_question": k.get("name") or k.get("kpi_id") or "",
            "metric_name": k.get("name") or "",
            "description": k.get("description") or "",
            "focus_area": k.get("focus_area") or "",
            "type": "metric_preview",
        })

    context = {
        "intent": state.get("csod_intent", ""),
        "primary_focus_area": _extract_primary_focus(state),
    }

    # Call placeholder (sync wrapper for async)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                previews = pool.submit(
                    asyncio.run, _call_sql_agent_placeholder(queries, context)
                ).result()
        else:
            previews = asyncio.run(_call_sql_agent_placeholder(queries, context))
    except Exception as e:
        logger.error("SQL agent preview failed: %s", e, exc_info=True)
        # Fallback: generate previews without LLM
        previews = []
        for idx, q in enumerate(queries):
            previews.append({
                "query_id": q.get("query_id"),
                "nl_question": q.get("nl_question"),
                "result_data": _generate_dummy_preview_data(q.get("metric_name", ""), idx),
                "summary": f"Preview data for {q.get('metric_name', 'metric')}",
                "insights": [],
                "chart_type": "bar",
                "source": "sql_agent_placeholder_fallback",
            })

    state["csod_metric_previews"] = previews

    _csod_log_step(
        state, "csod_sql_agent_preview", "sql_agent_placeholder",
        inputs={"query_count": len(queries)},
        outputs={"preview_count": len(previews)},
    )

    return state


# ---------------------------------------------------------------------------
# Node 2: Adhoc / RCA SQL agent
# ---------------------------------------------------------------------------

def csod_sql_agent_adhoc_node(state: CSOD_State) -> CSOD_State:
    """
    Generate and execute adhoc/RCA SQL queries from causal graph context.

    For adhoc: builds NL queries from user question + schemas.
    For RCA: traces causal paths and generates one query per relationship.

    Reads: user_query, csod_intent, csod_causal_nodes, csod_causal_edges,
           csod_resolved_schemas, causal_signals
    Writes: csod_sql_agent_results, csod_metric_recommendations (synthetic metrics
            from SQL results so metric_selection can present them)
    """
    user_query = state.get("user_query", "")
    intent = state.get("csod_intent", "")
    causal_nodes = state.get("csod_causal_nodes") or []
    causal_edges = state.get("csod_causal_edges") or []
    schemas = state.get("csod_resolved_schemas") or []

    # Build schema summary for the prompt
    schema_summary = _build_schema_summary(schemas)

    # Step 1: Generate NL queries from causal graph context
    nl_queries = _generate_nl_queries(
        user_query=user_query,
        intent=intent,
        causal_nodes=causal_nodes,
        causal_edges=causal_edges,
        schema_summary=schema_summary,
    )

    if not nl_queries:
        # Fallback: single direct query from user question
        nl_queries = [{
            "nl_question": user_query,
            "target_table": "",
            "causal_path": "",
            "priority": "high",
        }]

    # Step 2: Execute via SQL agent placeholder
    context = {
        "intent": intent,
        "primary_focus_area": _extract_primary_focus(state),
    }

    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(
                    asyncio.run, _call_sql_agent_placeholder(nl_queries, context)
                ).result()
        else:
            results = asyncio.run(_call_sql_agent_placeholder(nl_queries, context))
    except Exception as e:
        logger.error("SQL agent adhoc failed: %s", e, exc_info=True)
        results = []
        for idx, q in enumerate(nl_queries):
            results.append({
                "query_id": f"adhoc_{idx}",
                "nl_question": q.get("nl_question", ""),
                "result_data": _generate_dummy_adhoc_result(q.get("nl_question", ""), idx),
                "summary": f"Analysis for: {q.get('nl_question', '')[:80]}",
                "insights": [],
                "chart_type": "table",
                "source": "sql_agent_placeholder_fallback",
            })

    state["csod_sql_agent_results"] = results

    # Step 3: Convert SQL results to metric-like objects for metric_selection
    synthetic_metrics = []
    for r in results:
        synthetic_metrics.append({
            "metric_id": r.get("query_id", ""),
            "name": r.get("nl_question", "")[:100],
            "description": r.get("summary", ""),
            "natural_language_question": r.get("nl_question", ""),
            "source": "sql_agent_adhoc",
            "chart_type": r.get("chart_type", "table"),
            "insights": r.get("insights", []),
            "preview_data": r.get("result_data"),
        })

    # Set as metric recommendations so metric_selection can present them
    state["csod_metric_recommendations"] = synthetic_metrics

    _csod_log_step(
        state, "csod_sql_agent_adhoc", "sql_agent_placeholder",
        inputs={"user_query": user_query[:100], "intent": intent,
                "causal_node_count": len(causal_nodes), "causal_edge_count": len(causal_edges)},
        outputs={"query_count": len(nl_queries), "result_count": len(results)},
    )

    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_nl_queries(
    user_query: str,
    intent: str,
    causal_nodes: List[Any],
    causal_edges: List[Any],
    schema_summary: str,
) -> List[Dict[str, Any]]:
    """Use LLM to generate NL queries from causal graph context."""
    # Summarize causal context
    node_summary = json.dumps(
        [n.get("label") or n.get("id") or str(n) for n in causal_nodes[:20]]
        if isinstance(causal_nodes, list) else [],
        indent=None,
    )
    edge_summary = json.dumps(
        [
            {"from": e.get("source") or e.get("from_concept", ""),
             "to": e.get("target") or e.get("to_concept", ""),
             "weight": e.get("weight", "")}
            for e in (causal_edges[:20] if isinstance(causal_edges, list) else [])
        ],
        indent=None,
    )

    prompt = _ADHOC_NL_QUERY_PROMPT.format(
        user_query=user_query,
        intent=intent,
        causal_nodes=node_summary,
        causal_edges=edge_summary,
        schema_summary=schema_summary[:2000],
    )

    try:
        llm = get_llm()
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    resp = pool.submit(asyncio.run, llm.ainvoke(prompt)).result()
            else:
                resp = asyncio.run(llm.ainvoke(prompt))
        except RuntimeError:
            resp = asyncio.run(llm.ainvoke(prompt))

        content = resp.content if hasattr(resp, "content") else str(resp)
        parsed = _parse_json_response(content, {})
        queries = parsed.get("queries", [])
        if queries and isinstance(queries, list):
            return queries
    except Exception as e:
        logger.warning("NL query generation failed: %s", e)

    # Fallback: generate from causal edges directly
    queries = []
    if intent == "alert_rca" and causal_edges:
        for i, edge in enumerate(causal_edges[:8]):
            src = edge.get("source") or edge.get("from_concept", "unknown")
            tgt = edge.get("target") or edge.get("to_concept", "unknown")
            queries.append({
                "nl_question": f"How does {src} affect {tgt}? Show trend and deviation.",
                "causal_path": f"{src} → {tgt}",
                "priority": "high" if i < 3 else "medium",
            })
    else:
        queries.append({
            "nl_question": user_query,
            "priority": "high",
        })

    return queries


def _build_schema_summary(schemas: List[Any]) -> str:
    """Build a compact schema summary for the LLM prompt."""
    lines = []
    for s in (schemas[:10] if isinstance(schemas, list) else []):
        if not isinstance(s, dict):
            continue
        table = s.get("table_name") or s.get("name") or "unknown"
        desc = s.get("description") or ""
        cols = s.get("columns") or s.get("column_metadata") or []
        col_names = []
        if isinstance(cols, list):
            for c in cols[:8]:
                if isinstance(c, dict):
                    col_names.append(c.get("column_name") or c.get("name") or "")
                elif isinstance(c, str):
                    col_names.append(c)
        lines.append(f"  {table}: {desc[:80]} | cols: {', '.join(col_names[:8])}")
    return "\n".join(lines) if lines else "(no schemas available)"


def _extract_primary_focus(state: CSOD_State) -> str:
    """Extract primary focus area from state for context."""
    pa = state.get("csod_primary_area")
    if isinstance(pa, dict):
        return pa.get("area_name") or pa.get("name") or ""
    de = state.get("data_enrichment")
    if isinstance(de, dict):
        areas = de.get("suggested_focus_areas") or []
        if areas:
            return str(areas[0])
    return "compliance"
