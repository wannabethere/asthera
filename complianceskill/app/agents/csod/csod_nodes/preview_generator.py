"""
Single-Item Preview Generator
=============================

Generates a complete preview card (summary, insights, chart spec, dummy data)
for ONE metric, KPI, or table at a time.  Called by the frontend per-card
via ``/workflow/preview_item`` — avoids loading 15+ LLM calls in a single
request and keeps memory bounded to one item at a time.

Input:  item metadata (name, type, description, NL question, source tables,
        focus area, intent, reasoning/plan context)
Output: preview dict ready for rendering (summary, insights, chart_type,
        vega_lite_spec, result_data, trend_direction, explanation)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM Prompt
# ---------------------------------------------------------------------------

_PREVIEW_PROMPT = """\
You are a data analyst generating a preview card for a compliance dashboard.

Item Name: {name}
Item Type: {item_type}
Description: {description}
Natural Language Question: {nl_question}
Focus Area: {focus_area}
Analysis Intent: {intent}
Source Tables: {source_tables}
{extra_context}
Return ONLY valid JSON (no markdown fences):
{{
  "summary": "2-sentence plain-English explanation of what this measures and why it matters",
  "insights": ["actionable insight 1", "actionable insight 2", "actionable insight 3"],
  "chart_type": "line|bar|gauge|table|area|pie",
  "trend_direction": "up|down|stable",
  "explanation": "2-3 sentence methodology explanation: data sources, how to interpret, caveats",
  "visualization": {{
    "title": "Chart title",
    "x_axis": "X-axis label",
    "y_axis": "Y-axis label (with unit)",
    "recommended_aggregation": "monthly|weekly|daily|quarterly"
  }}
}}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_single_preview(
    name: str,
    item_type: str,
    description: str = "",
    nl_question: str = "",
    focus_area: str = "",
    intent: str = "",
    source_tables: Optional[List[str]] = None,
    columns: Optional[List[Any]] = None,
    reasoning: str = "",
    plan_context: str = "",
    project_id: str = "",
    index: int = 0,
) -> Dict[str, Any]:
    """
    Generate a complete preview card for a single metric, KPI, or table.

    Args:
        name:           Item display name
        item_type:      "metric" | "kpi" | "table"
        description:    Item description / formula
        nl_question:    Natural language query this item answers
        focus_area:     Analytical focus area (e.g. "training_compliance")
        intent:         Analysis intent (e.g. "gap_analysis")
        source_tables:  List of source table names
        columns:        Column metadata (for tables)
        reasoning:      LLM reasoning / rationale for this recommendation
        plan_context:   Analysis plan context
        project_id:     Active project ID
        index:          Item index (for deterministic seed)

    Returns:
        Complete preview dict with summary, insights, chart_type,
        vega_lite_spec, result_data, trend_direction, explanation.
    """
    source_tables = source_tables or []

    # Generate dummy data based on type
    if item_type == "kpi":
        result_data = _dummy_kpi_data(name, index)
        default_chart = "gauge"
    elif item_type == "table":
        result_data = _dummy_table_data(name, columns or [], index)
        default_chart = "table"
    else:
        result_data = _dummy_metric_data(name, index)
        default_chart = "line"

    # LLM call for summary, insights, chart recommendation
    llm_result = await _call_llm_for_preview(
        name=name,
        item_type=item_type,
        description=description,
        nl_question=nl_question,
        focus_area=focus_area,
        intent=intent,
        source_tables=source_tables,
        reasoning=reasoning,
        plan_context=plan_context,
        default_chart=default_chart,
    )

    chart_type = llm_result.get("chart_type", default_chart)
    viz = llm_result.get("visualization", {})

    # Build Vega-Lite spec
    vega_spec = _build_vega_lite_spec(
        chart_type=chart_type,
        result_data=result_data,
        title=viz.get("title", name),
        x_label=viz.get("x_axis", ""),
        y_label=viz.get("y_axis", ""),
    )

    return {
        "name": name,
        "item_type": item_type,
        "description": description,
        "nl_question": nl_question,
        "summary": llm_result.get("summary", f"Preview for {name}"),
        "explanation": llm_result.get("explanation", ""),
        "insights": llm_result.get("insights", []),
        "chart_type": chart_type,
        "trend_direction": llm_result.get("trend_direction", "stable"),
        "vega_lite_spec": vega_spec,
        "result_data": result_data,
        "source_schemas": source_tables,
        "focus_area": focus_area,
        "source": "preview_generator",
    }


# ---------------------------------------------------------------------------
# LLM call (single item, isolated — no shared state)
# ---------------------------------------------------------------------------

async def _call_llm_for_preview(
    name: str,
    item_type: str,
    description: str,
    nl_question: str,
    focus_area: str,
    intent: str,
    source_tables: List[str],
    reasoning: str,
    plan_context: str,
    default_chart: str,
) -> Dict[str, Any]:
    """Call LLM for one preview item. Returns parsed JSON or template fallback."""
    import asyncio

    # Build extra context from reasoning/plan if provided
    extra_lines = []
    if reasoning:
        extra_lines.append(f"Reasoning: {reasoning[:300]}")
    if plan_context:
        extra_lines.append(f"Analysis Plan: {plan_context[:300]}")
    extra_context = "\n".join(extra_lines)

    prompt = _PREVIEW_PROMPT.format(
        name=name,
        item_type=item_type,
        description=description[:400],
        nl_question=nl_question[:300],
        focus_area=focus_area,
        intent=intent,
        source_tables=", ".join(source_tables[:5]) or "N/A",
        extra_context=extra_context,
    )

    try:
        from app.core.dependencies import get_llm
        llm = get_llm()
        resp = await asyncio.wait_for(llm.ainvoke(prompt), timeout=20.0)
        content = resp.content if hasattr(resp, "content") else str(resp)
        return _parse_json_safe(content)
    except asyncio.TimeoutError:
        logger.warning("Preview LLM timed out for %s", name)
    except Exception as e:
        logger.warning("Preview LLM failed for %s: %s", name, e)

    # Template fallback
    src = ", ".join(source_tables[:2]) or "available data"
    return {
        "summary": description[:200] if description else f"Analysis of {name}.",
        "insights": [f"Review {name} trends", f"Source: {src}"],
        "chart_type": default_chart,
        "trend_direction": "stable",
        "explanation": "",
        "visualization": {"title": name, "x_axis": "Period", "y_axis": "Value"},
    }


def _parse_json_safe(raw: str) -> Dict[str, Any]:
    """Parse LLM JSON response with fallback for common errors."""
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
# Dummy data generators (copied from node_sql_agent — no shared state)
# ---------------------------------------------------------------------------

def _dummy_metric_data(name: str, idx: int) -> Dict[str, Any]:
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    base = 60 + (seed % 35)
    rows = []
    for m in range(5):
        period = (datetime.now() - timedelta(days=30 * (4 - m))).strftime("%Y-%m")
        val = round(base + (m * 2.3) + ((seed + m) % 7), 1)
        rows.append({"period": period, "value": val, "delta_pct": round(((val - base) / base) * 100, 1)})
    return {"columns": ["period", "value", "delta_pct"], "rows": rows, "row_count": len(rows)}


def _dummy_kpi_data(name: str, idx: int) -> Dict[str, Any]:
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    cur = round(55 + (seed % 40) + (idx * 1.3), 1)
    tgt = round(85 + (seed % 10), 1)
    return {
        "columns": ["current_value", "target", "delta", "pct_of_target"],
        "rows": [{"current_value": cur, "target": tgt, "delta": round(cur - tgt, 1),
                  "pct_of_target": round((cur / tgt) * 100, 1) if tgt else 0}],
        "row_count": 1,
    }


def _dummy_table_data(name: str, columns: List[Any], idx: int) -> Dict[str, Any]:
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    col_names = []
    for c in (columns or [])[:6]:
        if isinstance(c, dict):
            col_names.append(c.get("column_name") or c.get("name") or "col")
        elif isinstance(c, str):
            col_names.append(c)
    if not col_names:
        col_names = ["id", "name", "value", "created_at"]

    depts = ["Engineering", "Sales", "Operations", "Finance", "HR",
             "Marketing", "Legal", "Support", "Product", "Research"]
    rows = []
    for r in range(20):
        row = {}
        for ci, col in enumerate(col_names):
            cl = col.lower()
            if "id" in cl:
                row[col] = 1000 + r + (seed % 100)
            elif "name" in cl or "department" in cl:
                row[col] = depts[r % len(depts)]
            elif "date" in cl or "created" in cl:
                row[col] = (datetime.now() - timedelta(days=r * 3)).strftime("%Y-%m-%d")
            elif "rate" in cl or "pct" in cl or "score" in cl:
                row[col] = round(60 + (seed + r + ci) % 35, 1)
            elif "count" in cl or "total" in cl:
                row[col] = 50 + (seed + r) % 200
            else:
                row[col] = round(10 + (seed + r + ci) % 90, 1)
        rows.append(row)
    return {"columns": col_names, "rows": rows, "row_count": 20,
            "estimated_total_rows": 500 + (seed % 10000)}


# ---------------------------------------------------------------------------
# Vega-Lite spec builder
# ---------------------------------------------------------------------------

def _build_vega_lite_spec(chart_type: str, result_data: Dict, title: str,
                          x_label: str = "", y_label: str = "") -> Dict[str, Any]:
    rows = result_data.get("rows", [])
    if not rows:
        return {}

    base = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title, "width": "container", "height": 200,
        "config": {"view": {"stroke": "transparent"},
                   "axis": {"labelFontSize": 11, "titleFontSize": 12}},
    }

    if chart_type == "line":
        vals = [{"period": r.get("period", ""), "value": r.get("value", 0)} for r in rows]
        return {**base, "data": {"values": vals},
                "mark": {"type": "line", "point": True, "color": "#00e5c0"},
                "encoding": {"x": {"field": "period", "type": "ordinal", "title": x_label or "Period"},
                             "y": {"field": "value", "type": "quantitative", "title": y_label or "Value"}}}

    if chart_type == "bar":
        cols = result_data.get("columns", [])
        c, v = (cols[0] if cols else "category"), (cols[1] if len(cols) > 1 else "value")
        vals = [{c: r.get(c, ""), v: r.get(v, 0)} for r in rows]
        return {**base, "data": {"values": vals},
                "mark": {"type": "bar", "color": "#00e5c0", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                "encoding": {"x": {"field": c, "type": "nominal", "title": x_label or c},
                             "y": {"field": v, "type": "quantitative", "title": y_label or v}}}

    if chart_type == "gauge":
        row = rows[0] if rows else {}
        cur = row.get("current_value", row.get("value", 0))
        tgt = row.get("target", 100)
        return {**base, "height": 120, "layer": [
            {"data": {"values": [{"value": tgt}]},
             "mark": {"type": "arc", "innerRadius": 50, "outerRadius": 70, "theta": 6.28, "color": "#2a2d35"}},
            {"data": {"values": [{"value": cur}]},
             "mark": {"type": "arc", "innerRadius": 50, "outerRadius": 70,
                      "theta": {"expr": f"datum.value / {tgt} * 6.28"}, "color": "#00e5c0"}},
            {"data": {"values": [{"label": f"{cur}/{tgt}"}]},
             "mark": {"type": "text", "fontSize": 18, "fontWeight": "bold", "color": "#e0e0e0"},
             "encoding": {"text": {"field": "label", "type": "nominal"}}},
        ]}

    if chart_type == "area":
        vals = [{"period": r.get("period", ""), "value": r.get("value", 0)} for r in rows]
        return {**base, "data": {"values": vals},
                "mark": {"type": "area", "color": "#00e5c0", "opacity": 0.3, "line": {"color": "#00e5c0"}},
                "encoding": {"x": {"field": "period", "type": "ordinal", "title": x_label or "Period"},
                             "y": {"field": "value", "type": "quantitative", "title": y_label or "Value"}}}

    if chart_type == "pie":
        cols = result_data.get("columns", [])
        c, v = (cols[0] if cols else "category"), (cols[1] if len(cols) > 1 else "value")
        vals = [{c: r.get(c, ""), v: r.get(v, 0)} for r in rows]
        return {**base, "data": {"values": vals}, "mark": {"type": "arc", "innerRadius": 30},
                "encoding": {"theta": {"field": v, "type": "quantitative"},
                             "color": {"field": c, "type": "nominal"}}}

    return {}  # table type — rendered as HTML, no chart spec
