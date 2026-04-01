"""
SQL Agent Placeholder Nodes — metric/KPI/table preview and adhoc/RCA query execution.

Two nodes:
  1. csod_sql_agent_preview_node — previews selected metrics, KPIs, and tables via
     LLM-generated dummy data, Vega-Lite chart specs, and explanations.
  2. csod_sql_agent_adhoc_node  — handles adhoc/RCA analysis by generating NL queries
     from causal graph context, sending to SQL agent (placeholder returns dummy results).

Both share a common _call_sql_agent_placeholder() that builds synthetic responses.
When a real SQL agent server is available, swap that function to HTTP call.
"""
from __future__ import annotations

import hashlib
import logging
import json
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _parse_json_response,
    logger,
)
from app.agents.csod.csod_nodes.narrative import append_csod_narrative
from app.core.dependencies import get_llm

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_PREVIEW_SUMMARY_PROMPT = """\
You are a data analyst. Given this item definition, generate a rich preview summary.

Item: {item_name}
Type: {item_type}
Description: {item_description}
Focus Area: {focus_area}
Intent: {intent}
Source Tables: {source_schemas}

Return JSON:
{{
  "summary": "2-sentence plain-English explanation of what this measures and why it matters",
  "insights": ["actionable insight 1", "actionable insight 2", "actionable insight 3"],
  "chart_type": "line|bar|gauge|table|area|pie",
  "trend_direction": "up|down|stable",
  "explanation": "Detailed 2-3 sentence explanation of methodology, data sources, and how to interpret this metric",
  "visualization": {{
    "title": "Chart title for display",
    "x_axis": "X-axis label",
    "y_axis": "Y-axis label (with unit)",
    "recommended_aggregation": "monthly|weekly|daily|quarterly"
  }}
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


# ---------------------------------------------------------------------------
# Async helper — creates a fresh event loop for thread-pool execution
# ---------------------------------------------------------------------------

def _run_async_in_new_loop(coro):
    """Run an async coroutine in a brand-new event loop (thread-safe)."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Dummy data generators
# ---------------------------------------------------------------------------

def _generate_dummy_preview_data(metric_name: str, idx: int) -> Dict[str, Any]:
    """Generate synthetic time-series tabular preview data for a metric."""
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


def _generate_dummy_kpi_data(kpi_name: str, idx: int) -> Dict[str, Any]:
    """Generate synthetic gauge-style data for a KPI."""
    seed = int(hashlib.md5(kpi_name.encode()).hexdigest()[:8], 16)
    current = round(55 + (seed % 40) + (idx * 1.3), 1)
    target = round(85 + (seed % 10), 1)
    threshold = round(target * 0.7, 1)
    delta = round(current - target, 1)
    return {
        "columns": ["current_value", "target", "threshold", "delta", "pct_of_target"],
        "rows": [{
            "current_value": current,
            "target": target,
            "threshold": threshold,
            "delta": delta,
            "pct_of_target": round((current / target) * 100, 1) if target else 0,
        }],
        "row_count": 1,
    }


def _generate_dummy_table_preview(table_name: str, columns: List[Any], idx: int) -> Dict[str, Any]:
    """Generate synthetic sample rows for a table recommendation (20 rows, max 6 cols)."""
    seed = int(hashlib.md5(table_name.encode()).hexdigest()[:8], 16)

    # Build column names from metadata — cap at 6 to keep payload small
    col_names = []
    for c in (columns or [])[:6]:
        if isinstance(c, dict):
            col_names.append(c.get("column_name") or c.get("name") or "col")
        elif isinstance(c, str):
            col_names.append(c)
    if not col_names:
        col_names = ["id", "name", "value", "created_at"]

    # Generate 20 sample rows
    sample_rows = []
    departments = ["Engineering", "Sales", "Operations", "Finance", "HR",
                    "Marketing", "Legal", "Support", "Product", "Research"]
    statuses = ["Active", "Pending", "Completed", "In Progress", "On Hold"]
    for row_idx in range(20):
        row = {}
        for ci, col in enumerate(col_names):
            cl = col.lower()
            if "id" in cl:
                row[col] = 1000 + row_idx + (seed % 100)
            elif "name" in cl or "department" in cl:
                row[col] = departments[row_idx % len(departments)]
            elif "status" in cl or "state" in cl:
                row[col] = statuses[row_idx % len(statuses)]
            elif "date" in cl or "created" in cl or "updated" in cl:
                row[col] = (datetime.now() - timedelta(days=row_idx * 3)).strftime("%Y-%m-%d")
            elif "rate" in cl or "pct" in cl or "score" in cl:
                row[col] = round(60 + (seed + row_idx + ci) % 35, 1)
            elif "count" in cl or "total" in cl:
                row[col] = 50 + (seed + row_idx) % 200
            else:
                row[col] = round(10 + (seed + row_idx + ci) % 90, 1)
        sample_rows.append(row)

    return {
        "columns": col_names,
        "rows": sample_rows,
        "row_count": 20,
        "estimated_total_rows": 500 + (seed % 10000),
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


# ---------------------------------------------------------------------------
# Vega-Lite spec builders
# ---------------------------------------------------------------------------

def _build_vega_lite_spec(
    chart_type: str,
    result_data: Dict[str, Any],
    title: str,
    x_label: str = "",
    y_label: str = "",
) -> Dict[str, Any]:
    """Build a minimal Vega-Lite JSON spec from preview data."""
    rows = result_data.get("rows", [])
    if not rows:
        return {}

    base = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "width": "container",
        "height": 200,
        "config": {
            "view": {"stroke": "transparent"},
            "axis": {"labelFontSize": 11, "titleFontSize": 12},
        },
    }

    if chart_type == "line":
        values = [{"period": r.get("period", ""), "value": r.get("value", 0)} for r in rows]
        return {
            **base,
            "data": {"values": values},
            "mark": {"type": "line", "point": True, "color": "#00e5c0"},
            "encoding": {
                "x": {"field": "period", "type": "ordinal", "title": x_label or "Period"},
                "y": {"field": "value", "type": "quantitative", "title": y_label or "Value"},
            },
        }

    if chart_type == "bar":
        # Use first two meaningful columns
        cols = result_data.get("columns", [])
        cat_col = cols[0] if cols else "category"
        val_col = cols[1] if len(cols) > 1 else "value"
        values = [{cat_col: r.get(cat_col, ""), val_col: r.get(val_col, 0)} for r in rows]
        return {
            **base,
            "data": {"values": values},
            "mark": {"type": "bar", "color": "#00e5c0", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
            "encoding": {
                "x": {"field": cat_col, "type": "nominal", "title": x_label or cat_col},
                "y": {"field": val_col, "type": "quantitative", "title": y_label or val_col},
            },
        }

    if chart_type == "gauge":
        row = rows[0] if rows else {}
        current = row.get("current_value", row.get("value", 0))
        target = row.get("target", 100)
        return {
            **base,
            "height": 120,
            "layer": [
                {
                    "data": {"values": [{"value": target}]},
                    "mark": {"type": "arc", "innerRadius": 50, "outerRadius": 70, "theta": 6.28, "color": "#2a2d35"},
                },
                {
                    "data": {"values": [{"value": current}]},
                    "mark": {"type": "arc", "innerRadius": 50, "outerRadius": 70,
                             "theta": {"expr": f"datum.value / {target} * 6.28"}, "color": "#00e5c0"},
                },
                {
                    "data": {"values": [{"label": f"{current}/{target}"}]},
                    "mark": {"type": "text", "fontSize": 18, "fontWeight": "bold", "color": "#e0e0e0"},
                    "encoding": {"text": {"field": "label", "type": "nominal"}},
                },
            ],
        }

    if chart_type == "area":
        values = [{"period": r.get("period", ""), "value": r.get("value", 0)} for r in rows]
        return {
            **base,
            "data": {"values": values},
            "mark": {"type": "area", "color": "#00e5c0", "opacity": 0.3, "line": {"color": "#00e5c0"}},
            "encoding": {
                "x": {"field": "period", "type": "ordinal", "title": x_label or "Period"},
                "y": {"field": "value", "type": "quantitative", "title": y_label or "Value"},
            },
        }

    if chart_type == "pie":
        cols = result_data.get("columns", [])
        cat_col = cols[0] if cols else "category"
        val_col = cols[1] if len(cols) > 1 else "value"
        values = [{cat_col: r.get(cat_col, ""), val_col: r.get(val_col, 0)} for r in rows]
        return {
            **base,
            "data": {"values": values},
            "mark": {"type": "arc", "innerRadius": 30},
            "encoding": {
                "theta": {"field": val_col, "type": "quantitative"},
                "color": {"field": cat_col, "type": "nominal"},
            },
        }

    # Default: table — no Vega-Lite spec (rendered as HTML table)
    return {}


# ---------------------------------------------------------------------------
# Placeholder SQL agent
# ---------------------------------------------------------------------------

async def _call_sql_agent_placeholder_stream(
    queries: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Placeholder SQL agent — yields LLM-generated summaries with dummy data
    one preview at a time.

    Tables skip the LLM call entirely (template-based summary) for speed.
    Metrics/KPIs use a 15-second per-item timeout to prevent cascading failures.

    When a real SQL agent server exists, replace this with HTTP call.
    """
    import asyncio as _aio

    llm = get_llm()

    for idx, q in enumerate(queries):
        item_type = q.get("item_type", "metric")
        nl_question = q.get("nl_question") or q.get("metric_name") or f"Query {idx+1}"
        name = q.get("name") or q.get("metric_name") or nl_question
        description = q.get("description") or q.get("metric_description") or nl_question
        focus = q.get("focus_area") or context.get("primary_focus_area", "compliance")
        intent = context.get("intent", "analysis")
        source_schemas = q.get("source_schemas") or []

        # Generate dummy tabular data based on type
        if item_type == "kpi":
            preview_data = _generate_dummy_kpi_data(name, idx)
            default_chart = "gauge"
        elif item_type == "table":
            preview_data = _generate_dummy_table_preview(
                name, q.get("columns") or [], idx
            )
            default_chart = "table"
        elif q.get("type") == "adhoc":
            preview_data = _generate_dummy_adhoc_result(nl_question, idx)
            default_chart = "bar"
        else:
            preview_data = _generate_dummy_preview_data(name, idx)
            default_chart = "line"

        # LLM-generated summary + insights + visualization hints
        # Tables skip the LLM call — template-based summary is sufficient
        # since table previews just show sample data, not charts.
        parsed = {}
        if item_type == "table":
            # Template-based summary for tables — no LLM needed
            raw_cols = (q.get("columns") or [])[:4]
            col_strs = []
            for _c in raw_cols:
                if isinstance(_c, dict):
                    col_strs.append(_c.get("column_name") or _c.get("name") or "col")
                elif isinstance(_c, str):
                    col_strs.append(_c)
            col_list = ", ".join(col_strs) if col_strs else "various columns"
            parsed = {
                "summary": f"Sample data from {name} showing {col_list}.",
                "insights": [],
                "chart_type": "table",
                "trend_direction": "stable",
                "explanation": f"Displaying 20 sample rows from {name}.",
            }
        else:
            try:
                prompt = _PREVIEW_SUMMARY_PROMPT.format(
                    item_name=name,
                    item_type=item_type,
                    item_description=description[:300],
                    focus_area=focus,
                    intent=intent,
                    source_schemas=", ".join(source_schemas[:5]) if source_schemas else "N/A",
                )
                resp = await _aio.wait_for(llm.ainvoke(prompt), timeout=15.0)
                content = resp.content if hasattr(resp, "content") else str(resp)
                parsed = _parse_json_response(content, {})
            except _aio.TimeoutError:
                logger.warning("SQL agent placeholder LLM call timed out for %s", name)
                parsed = {}
            except Exception as e:
                logger.warning("SQL agent placeholder LLM call failed: %s", e)
                parsed = {}

        chart_type = parsed.get("chart_type", default_chart)
        viz = parsed.get("visualization", {})

        # Build Vega-Lite spec
        vega_spec = _build_vega_lite_spec(
            chart_type=chart_type,
            result_data=preview_data,
            title=viz.get("title", name),
            x_label=viz.get("x_axis", ""),
            y_label=viz.get("y_axis", ""),
        )

        result = {
            "query_id": q.get("query_id") or f"q_{idx}",
            "item_type": item_type,
            "name": name,
            "nl_question": nl_question,
            "description": description,
            "result_data": preview_data,
            "summary": parsed.get("summary", f"Preview data for {name}"),
            "explanation": parsed.get("explanation", ""),
            "insights": parsed.get("insights", [f"Showing preview for {name}"]),
            "chart_type": chart_type,
            "trend_direction": parsed.get("trend_direction", "stable"),
            "vega_lite_spec": vega_spec,
            "source": "sql_agent_placeholder",
            "source_schemas": source_schemas,
        }

        # Include generated SQL if adhoc
        if "generated_sql" in preview_data:
            result["generated_sql"] = preview_data.pop("generated_sql")

        yield result


async def _call_sql_agent_placeholder(
    queries: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Accumulating wrapper for backward compatibility (used by adhoc node)."""
    return [r async for r in _call_sql_agent_placeholder_stream(queries, context)]


# ---------------------------------------------------------------------------
# Streaming preview generator (called directly by the service layer)
# ---------------------------------------------------------------------------

async def generate_previews_stream(
    metrics: List[Dict[str, Any]],
    kpis: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
    intent: str = "",
    primary_focus_area: str = "",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Async generator that yields one preview dict at a time.

    Accepts only the fields it needs (no full state object), builds queries,
    and streams results from the LLM placeholder. Each preview is yielded
    immediately so the caller can emit SSE events incrementally.
    """
    queries: List[Dict[str, Any]] = []

    for m in metrics[:10]:
        queries.append({
            "query_id": m.get("metric_id") or m.get("name"),
            "item_type": "metric",
            "name": m.get("name") or m.get("metric_id") or "",
            "nl_question": m.get("natural_language_question") or m.get("name") or "",
            "metric_name": m.get("name") or m.get("metric_id") or "",
            "description": m.get("description") or "",
            "focus_area": m.get("focus_area") or "",
            "source_schemas": m.get("source_schemas") or [],
            "type": "metric_preview",
        })

    for k in kpis[:5]:
        queries.append({
            "query_id": k.get("kpi_id") or k.get("name"),
            "item_type": "kpi",
            "name": k.get("name") or k.get("kpi_id") or "",
            "nl_question": k.get("name") or k.get("kpi_id") or "",
            "metric_name": k.get("name") or "",
            "description": k.get("description") or "",
            "focus_area": k.get("focus_area") or "",
            "source_schemas": k.get("source_schemas") or [],
            "type": "metric_preview",
        })

    for t in tables[:5]:
        table_name = t.get("table_name") or t.get("name") or ""
        queries.append({
            "query_id": f"table_{table_name}",
            "item_type": "table",
            "name": table_name,
            "nl_question": f"Sample data from {table_name}",
            "metric_name": table_name,
            "description": t.get("description") or t.get("purpose") or "",
            "focus_area": "",
            "source_schemas": [table_name] if table_name else [],
            "columns": t.get("columns") or t.get("column_metadata") or [],
            "type": "metric_preview",
        })

    if not queries:
        return

    context = {
        "intent": intent,
        "primary_focus_area": primary_focus_area,
    }

    async for preview in _call_sql_agent_placeholder_stream(queries, context):
        yield preview


# ---------------------------------------------------------------------------
# Node 1: Preview selected metrics, KPIs, and tables
# ---------------------------------------------------------------------------

def csod_sql_agent_preview_node(state: CSOD_State) -> CSOD_State:
    """
    Preview selected metrics, KPIs, and tables via SQL agent.

    Generates rich preview objects with dummy data, Vega-Lite chart specs,
    LLM summaries, insights, and explanations for the Analysis Dashboard.

    Reads: csod_metric_recommendations, csod_kpi_recommendations,
           csod_table_recommendations, csod_selected_metric_ids,
           csod_resolved_schemas, csod_intent
    Writes: csod_metric_previews (list of preview objects)
    """
    # Skip if already previewed
    if state.get("csod_metric_previews"):
        logger.info("Metric previews already populated — pass-through")
        return state

    metrics = state.get("csod_metric_recommendations") or []
    kpis = state.get("csod_kpi_recommendations") or []
    tables = state.get("csod_table_recommendations") or []

    if not metrics and not kpis and not tables:
        state["csod_metric_previews"] = []
        return state

    # Build queries for the SQL agent — metrics, KPIs, and tables
    queries = []

    for m in metrics[:10]:
        queries.append({
            "query_id": m.get("metric_id") or m.get("name"),
            "item_type": "metric",
            "name": m.get("name") or m.get("metric_id") or "",
            "nl_question": m.get("natural_language_question") or m.get("name") or "",
            "metric_name": m.get("name") or m.get("metric_id") or "",
            "description": m.get("description") or "",
            "focus_area": m.get("focus_area") or "",
            "source_schemas": m.get("source_schemas") or [],
            "type": "metric_preview",
        })

    for k in kpis[:5]:
        queries.append({
            "query_id": k.get("kpi_id") or k.get("name"),
            "item_type": "kpi",
            "name": k.get("name") or k.get("kpi_id") or "",
            "nl_question": k.get("name") or k.get("kpi_id") or "",
            "metric_name": k.get("name") or "",
            "description": k.get("description") or "",
            "focus_area": k.get("focus_area") or "",
            "source_schemas": k.get("source_schemas") or [],
            "type": "metric_preview",
        })

    for t in tables[:5]:
        table_name = t.get("table_name") or t.get("name") or ""
        queries.append({
            "query_id": f"table_{table_name}",
            "item_type": "table",
            "name": table_name,
            "nl_question": f"Sample data from {table_name}",
            "metric_name": table_name,
            "description": t.get("description") or t.get("purpose") or "",
            "focus_area": "",
            "source_schemas": [table_name] if table_name else [],
            "columns": t.get("columns") or t.get("column_metadata") or [],
            "type": "metric_preview",
        })

    context = {
        "intent": state.get("csod_intent", ""),
        "primary_focus_area": _extract_primary_focus(state),
    }

    # Call placeholder (sync wrapper for async)
    import asyncio
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                previews = pool.submit(
                    _run_async_in_new_loop, _call_sql_agent_placeholder(queries, context)
                ).result()
        else:
            # When called from asyncio.to_thread() or a plain thread,
            # there is no running loop.  Use _run_async_in_new_loop to
            # create a fresh loop instead of asyncio.run() which can
            # fail in some thread-pool contexts (Python 3.11+).
            previews = _run_async_in_new_loop(_call_sql_agent_placeholder(queries, context))
    except Exception as e:
        logger.error("SQL agent preview failed: %s", e, exc_info=True)
        # Fallback: generate previews without LLM
        previews = []
        for idx, q in enumerate(queries):
            item_type = q.get("item_type", "metric")
            name = q.get("name") or q.get("metric_name", "")
            if item_type == "kpi":
                data = _generate_dummy_kpi_data(name, idx)
                chart = "gauge"
            elif item_type == "table":
                data = _generate_dummy_table_preview(name, q.get("columns", []), idx)
                chart = "table"
            else:
                data = _generate_dummy_preview_data(name, idx)
                chart = "bar"
            previews.append({
                "query_id": q.get("query_id"),
                "item_type": item_type,
                "name": name,
                "nl_question": q.get("nl_question"),
                "description": q.get("description", ""),
                "result_data": data,
                "summary": f"Preview data for {name}",
                "explanation": "",
                "insights": [],
                "chart_type": chart,
                "trend_direction": "stable",
                "vega_lite_spec": _build_vega_lite_spec(chart, data, name),
                "source": "sql_agent_placeholder_fallback",
                "source_schemas": q.get("source_schemas", []),
            })

    state["csod_metric_previews"] = previews

    _csod_log_step(
        state, "csod_sql_agent_preview", "sql_agent_placeholder",
        inputs={
            "metric_count": len(metrics),
            "kpi_count": len(kpis),
            "table_count": len(tables),
            "query_count": len(queries),
        },
        outputs={"preview_count": len(previews)},
    )

    # ── Narrative for chat bubble ──
    n_metrics = len([p for p in previews if p.get("item_type") == "metric"])
    n_kpis = len([p for p in previews if p.get("item_type") == "kpi"])
    n_tables = len([p for p in previews if p.get("item_type") == "table"])
    parts = []
    if n_metrics:
        parts.append(f"{n_metrics} metric{'s' if n_metrics != 1 else ''}")
    if n_kpis:
        parts.append(f"{n_kpis} KPI{'s' if n_kpis != 1 else ''}")
    if n_tables:
        parts.append(f"{n_tables} table{'s' if n_tables != 1 else ''}")
    append_csod_narrative(
        state, "preview", "Analysis Preview Ready",
        f"Generated preview data for {', '.join(parts) or 'your analysis'}. "
        "Review the Analysis Dashboard to see values, charts, and explanations for each item. "
        "Click **Deploy** when ready, or ask a follow-up question to refine.",
        {"preview_count": len(previews)},
    )

    return state


# ---------------------------------------------------------------------------
# Node 2: Adhoc / RCA SQL agent
# ---------------------------------------------------------------------------

def _generate_queries_from_analysis_plan(
    analysis_plan: Dict[str, Any],
    user_query: str,
    intent: str,
) -> List[Dict[str, Any]]:
    """Generate NL queries from analysis plan steps (one query per step)."""
    queries = []
    for step in analysis_plan.get("steps", []):
        step_id = step.get("step_id", "")
        description = step.get("description", "")
        tables = step.get("required_tables", [])
        columns = step.get("required_columns", {})
        new_metrics = step.get("new_metrics", [])
        aggregation = step.get("aggregation", "")
        output_desc = step.get("output_description", "")

        # Build NL question from the step
        nl_parts = [description]
        if new_metrics:
            metric_names = [m.get("name", "") for m in new_metrics if m.get("name")]
            if metric_names:
                nl_parts.append(f"Compute: {', '.join(metric_names)}")
        if aggregation:
            nl_parts.append(f"Aggregation: {aggregation}")

        nl_question = ". ".join(nl_parts)

        queries.append({
            "nl_question": nl_question,
            "target_table": tables[0] if tables else "",
            "required_tables": tables,
            "required_columns": columns,
            "step_id": step_id,
            "step_type": step.get("step_type", ""),
            "new_metrics": new_metrics,
            "causal_path": "",
            "priority": "high" if step.get("dependencies") == [] else "medium",
            "type": "adhoc",
        })

    return queries


def csod_sql_agent_adhoc_node(state: CSOD_State) -> CSOD_State:
    """
    Generate and execute adhoc/RCA SQL queries from analysis plan + causal graph.

    If an analysis plan exists, generates one query per plan step. Otherwise falls
    back to generating queries from causal graph context.

    For adhoc: builds NL queries from analysis plan steps or user question + schemas.
    For RCA: traces causal paths and generates one query per relationship.

    After generating SQL results, this node does NOT replace csod_metric_recommendations.
    Instead it stores results in csod_sql_agent_results so the downstream metrics
    pipeline can use them alongside its own recommendations.

    Reads: user_query, csod_intent, csod_analysis_plan, csod_causal_nodes,
           csod_causal_edges, csod_resolved_schemas, causal_signals
    Writes: csod_sql_agent_results (SQL query results for downstream use)
    """
    user_query = state.get("user_query", "")
    intent = state.get("csod_intent", "")
    causal_nodes = state.get("csod_causal_nodes") or []
    causal_edges = state.get("csod_causal_edges") or []
    schemas = state.get("csod_resolved_schemas") or []
    analysis_plan = state.get("csod_analysis_plan") or {}

    schema_summary = _build_schema_summary(schemas)

    # Step 1: Generate NL queries — prefer analysis plan steps, fallback to causal graph
    nl_queries = []
    if analysis_plan.get("steps"):
        nl_queries = _generate_queries_from_analysis_plan(
            analysis_plan, user_query, intent,
        )
        logger.info(
            "[csod_sql_agent_adhoc] Generated %d queries from analysis plan steps",
            len(nl_queries),
        )

    if not nl_queries:
        nl_queries = _generate_nl_queries(
            user_query=user_query,
            intent=intent,
            causal_nodes=causal_nodes,
            causal_edges=causal_edges,
            schema_summary=schema_summary,
        )

    if not nl_queries:
        nl_queries = [{
            "nl_question": user_query,
            "target_table": "",
            "causal_path": "",
            "priority": "high",
        }]

    # ── Log generated NL queries ─────────────────────────────────────
    logger.info("=" * 80)
    logger.info("[CSOD pipeline] SQL AGENT ADHOC — NL QUERIES")
    logger.info("=" * 80)
    logger.info("  Intent: %s | Queries: %d | From analysis plan: %s",
                intent, len(nl_queries), bool(analysis_plan.get("steps")))
    for i, q in enumerate(nl_queries):
        logger.info(
            "    [%d] %s (priority=%s, step=%s, table=%s)",
            i + 1,
            q.get("nl_question", "")[:150],
            q.get("priority", "?"),
            q.get("step_id", "N/A"),
            q.get("target_table") or q.get("required_tables", ["?"])[0] if q.get("required_tables") else "?",
        )
        new_metrics = q.get("new_metrics", [])
        if new_metrics:
            for nm in new_metrics:
                logger.info("           metric: %s = %s", nm.get("name", "?"), nm.get("formula", "?"))
    logger.info("=" * 80)

    # Step 2: Execute via SQL agent placeholder
    context = {
        "intent": intent,
        "primary_focus_area": _extract_primary_focus(state),
    }

    import asyncio
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(
                    _run_async_in_new_loop, _call_sql_agent_placeholder(nl_queries, context)
                ).result()
        else:
            results = _run_async_in_new_loop(_call_sql_agent_placeholder(nl_queries, context))
    except Exception as e:
        logger.error("SQL agent adhoc failed: %s", e, exc_info=True)
        results = []
        for idx, q in enumerate(nl_queries):
            results.append({
                "query_id": f"adhoc_{idx}",
                "item_type": "metric",
                "name": q.get("nl_question", "")[:100],
                "nl_question": q.get("nl_question", ""),
                "result_data": _generate_dummy_adhoc_result(q.get("nl_question", ""), idx),
                "summary": f"Analysis for: {q.get('nl_question', '')[:80]}",
                "insights": [],
                "chart_type": "table",
                "source": "sql_agent_placeholder_fallback",
            })

    state["csod_sql_agent_results"] = results

    # Step 3: Convert SQL results to synthetic metric objects.
    # These are stored separately — the downstream metrics pipeline will merge them
    # with its own recommendations via the recommender node.
    synthetic_metrics = []
    for r in results:
        synthetic_metrics.append({
            "metric_id": r.get("query_id", ""),
            "name": r.get("name") or r.get("nl_question", "")[:100],
            "description": r.get("summary", ""),
            "natural_language_question": r.get("nl_question", ""),
            "source": "sql_agent_adhoc",
            "chart_type": r.get("chart_type", "table"),
            "insights": r.get("insights", []),
            "preview_data": r.get("result_data"),
            "step_id": r.get("step_id", ""),
        })

    state["csod_adhoc_synthetic_metrics"] = synthetic_metrics

    # ── Log SQL agent results ────────────────────────────────────────
    logger.info("=" * 80)
    logger.info("[CSOD pipeline] SQL AGENT ADHOC — RESULTS")
    logger.info("=" * 80)
    logger.info("  Results: %d | Synthetic metrics: %d", len(results), len(synthetic_metrics))
    for i, r in enumerate(results):
        logger.info(
            "    [%d] %s (chart=%s, rows=%d)",
            i + 1,
            r.get("name", r.get("nl_question", "?"))[:120],
            r.get("chart_type", "?"),
            r.get("result_data", {}).get("row_count", 0),
        )
        summary = r.get("summary", "")
        if summary:
            logger.info("         Summary: %s", summary[:150])
    logger.info("=" * 80)

    _csod_log_step(
        state, "csod_sql_agent_adhoc", "sql_agent_placeholder",
        inputs={"user_query": user_query[:100], "intent": intent,
                "causal_node_count": len(causal_nodes), "causal_edge_count": len(causal_edges),
                "analysis_plan_steps": len(analysis_plan.get("steps", []))},
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
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                resp = pool.submit(_run_async_in_new_loop, llm.ainvoke(prompt)).result()
        else:
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
