"""
Single-Item Preview Generator
=============================

Generates a complete preview card (summary, insights, chart spec, dummy data)
for ONE metric, KPI, or table at a time.  Called by the frontend per-card
via ``/workflow/preview_item``.

When DEMO_FAKE_SQL_AND_INSIGHTS=False (default) uses LLM + dummy data.
When DEMO_FAKE_SQL_AND_INSIGHTS=True the same shape is returned — swap the
``_build_real_preview`` stub for live HTTP calls once the warehouse is ready.

Output shape is pre-aligned with:
  • POST /api/v1/combined/combined    (combined_ask)   — query + project_ids → sql + sql_execution_data
  • POST /sql-helper/summary          (sql_helper)     — sql + query + project_id → visualization/insights
  • POST /sql-helper/sql-expansion    (sql_helper)     — drill-down (expand SQL by sub-dimension)
  • POST /chart-adjustment/adjust     (chart_adj)      — chart type / axis re-configuration
  Annotations are handled locally (vega-lite layer injection, no upstream API).

Interactive operations (fake mode):
  • fake_chart_adjust(request_dict) → ChartAdjustmentResultResponse-shaped dict
  • fake_drill_down(request_dict)   → preview card dict (same shape as generate_single_preview)
  • fake_annotate(request_dict)     → {vega_lite_spec, annotations}
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
Generate a short preview card. Be concise.

Name: {name} | Type: {item_type} | Focus: {focus_area}
Question: {nl_question}

Return ONLY valid JSON, no markdown:
{{
  "summary": "One sentence.",
  "insights": ["insight 1", "insight 2"],
  "chart_type": "line|bar|gauge|table|area|pie",
  "trend_direction": "up|down|stable",
  "explanation": "One sentence.",
  "visualization": {{"title": "{name}", "x_axis": "Period", "y_axis": "Value", "recommended_aggregation": "monthly"}}
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
    project_ids: Optional[List[str]] = None,
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
        project_id:     Primary project ID
        project_ids:    Additional project IDs (union schema across projects)
        index:          Item index (for deterministic seed)

    Returns:
        Preview dict aligned with combined_ask + sql_helper/summary API shapes:
          sql, result_data (columns/rows/row_count), vega_lite_spec,
          summary, insights, explanation, chart_type, trend_direction.
    """
    from app.core.settings import get_settings
    settings = get_settings()

    source_tables = source_tables or []

    # When real warehouse data is available, swap this branch for live HTTP calls
    # to /api/v1/combined/combined and /sql-helper/summary.
    if not settings.DEMO_FAKE_SQL_AND_INSIGHTS:
        return await _demo_preview(
            name=name,
            item_type=item_type,
            description=description,
            nl_question=nl_question,
            focus_area=focus_area,
            intent=intent,
            source_tables=source_tables,
            columns=columns,
            reasoning=reasoning,
            plan_context=plan_context,
            project_id=project_id,
            project_ids=project_ids,
            index=index,
        )

    # DEMO_FAKE_SQL_AND_INSIGHTS=True: same output shape, future hook for real APIs
    return await _demo_preview(
        name=name,
        item_type=item_type,
        description=description,
        nl_question=nl_question,
        focus_area=focus_area,
        intent=intent,
        source_tables=source_tables,
        columns=columns,
        reasoning=reasoning,
        plan_context=plan_context,
        project_id=project_id,
        project_ids=project_ids,
        index=index,
    )


# ---------------------------------------------------------------------------
# Demo / dummy preview (LLM + synthetic data)
# ---------------------------------------------------------------------------

async def _demo_preview(
    name: str,
    item_type: str,
    description: str,
    nl_question: str,
    focus_area: str,
    intent: str,
    source_tables: List[str],
    columns: Optional[List[Any]],
    reasoning: str,
    plan_context: str,
    project_id: str,
    project_ids: Optional[List[str]],
    index: int,
) -> Dict[str, Any]:
    """LLM-generated summary/insights + deterministic dummy data."""

    if item_type == "kpi":
        result_data = _dummy_kpi_data(name, index)
        default_chart = "gauge"
    elif item_type == "table":
        result_data = _dummy_table_data(name, columns or [], index)
        default_chart = "table"
    else:
        result_data = _dummy_metric_data(name, index)
        default_chart = "line"

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
        # sql is empty in demo mode; populated by combined_ask when live
        "sql": "",
        "summary": llm_result.get("summary", f"Preview for {name}"),
        "explanation": llm_result.get("explanation", ""),
        "insights": llm_result.get("insights", []),
        "chart_type": chart_type,
        "trend_direction": llm_result.get("trend_direction", "stable"),
        "vega_lite_spec": vega_spec,
        # result_data mirrors sql_execution_data shape from combined_ask response
        "result_data": result_data,
        "source_schemas": source_tables,
        "focus_area": focus_area,
        "source": "preview_generator",
    }


# ---------------------------------------------------------------------------
# LLM call
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
    import asyncio

    extra_lines = []
    if reasoning:
        extra_lines.append(f"Reasoning: {reasoning[:300]}")
    if plan_context:
        extra_lines.append(f"Analysis Plan: {plan_context[:300]}")

    prompt = _PREVIEW_PROMPT.format(
        name=name,
        item_type=item_type,
        description=description[:400],
        nl_question=nl_question[:300],
        focus_area=focus_area,
        intent=intent,
        source_tables=", ".join(source_tables[:5]) or "N/A",
        extra_context="\n".join(extra_lines),
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
# Dummy data generators
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


# ===========================================================================
# Interactive preview operations (fake / demo mode)
# Request / response shapes mirror the real upstream APIs so astherabackend
# can use the same payload format for both fake and live calls.
# ===========================================================================

# ---------------------------------------------------------------------------
# Fake chart adjust
# Mirrors: POST /chart-adjustment/adjust  (ChartAdjustmentRequest)
# Returns shape matching ChartAdjustmentResultResponse
# ---------------------------------------------------------------------------

async def fake_chart_adjust(
    query: str,
    sql: str,
    chart_schema: Dict[str, Any],
    adjustment_option: Dict[str, Any],
    result_data: Optional[Dict[str, Any]] = None,
    project_id: str = "",
    project_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fake chart adjustment — rebuilds vega-lite spec in-process.

    Request fields match ChartAdjustmentRequest:
      query, sql, chart_schema (current spec), adjustment_option {chart_type, x_axis, y_axis, ...}

    Returns ChartAdjustmentResultResponse shape:
      {status, response: {reasoning, chart_type, chart_schema}}
    """
    chart_type = adjustment_option.get("chart_type", "bar")
    x_axis = adjustment_option.get("x_axis", "")
    y_axis = adjustment_option.get("y_axis", "")
    title = (chart_schema.get("title") or query or "Chart")

    # Use provided result_data or extract values from the existing spec
    data = result_data or {}
    if not data:
        existing_values = (
            chart_schema.get("data", {}).get("values")
            or (chart_schema.get("layer", [{}])[0].get("data", {}).get("values") if chart_schema.get("layer") else [])
        )
        cols = list(existing_values[0].keys()) if existing_values else ["category", "value"]
        data = {"columns": cols, "rows": existing_values or [], "row_count": len(existing_values or [])}

    new_spec = _build_vega_lite_spec(
        chart_type=chart_type,
        result_data=data,
        title=title,
        x_label=x_axis,
        y_label=y_axis,
    )

    return {
        "status": "finished",
        "response": {
            "reasoning": f"Chart type changed to {chart_type} with x={x_axis or 'auto'}, y={y_axis or 'auto'}.",
            "chart_type": chart_type,
            "chart_schema": new_spec,
        },
        "error": None,
        "trace_id": None,
    }


# ---------------------------------------------------------------------------
# Fake drill-down
# Mirrors: POST /sql-helper/sql-expansion  (SQLExpansionRequest)
# Returns a full preview card dict (same shape as generate_single_preview)
# ---------------------------------------------------------------------------

async def fake_drill_down(
    name: str,
    item_type: str,
    nl_question: str,
    drill_dimension: str = "",
    drill_value: str = "",
    parent_result_data: Optional[Dict[str, Any]] = None,
    source_tables: Optional[List[str]] = None,
    project_id: str = "",
    project_ids: Optional[List[str]] = None,
    index: int = 0,
) -> Dict[str, Any]:
    """
    Fake drill-down — generates a sub-level preview card.

    Maps to SQLExpansionRequest fields:
      query (= nl_question), sql (= ""), original_query (= name),
      project_id, project_ids

    drill_dimension / drill_value narrow the synthetic data so the
    card visually differs from the parent card.
    """
    sub_name = f"{name} — {drill_dimension}: {drill_value}" if drill_value else f"{name} (drill-down)"
    sub_question = (
        f"{nl_question} filtered by {drill_dimension}={drill_value}"
        if drill_value else f"Detailed breakdown of {nl_question}"
    )

    # Build narrowed synthetic data from parent rows or fresh dummy
    if parent_result_data and parent_result_data.get("rows"):
        parent_rows = parent_result_data["rows"]
        cols = parent_result_data.get("columns", list(parent_rows[0].keys()) if parent_rows else [])
        # Filter rows matching drill_value if possible
        if drill_dimension and drill_value:
            filtered = [r for r in parent_rows if str(r.get(drill_dimension, "")) == str(drill_value)]
            rows = filtered or parent_rows[:5]
        else:
            rows = parent_rows[:8]
        result_data: Dict[str, Any] = {"columns": cols, "rows": rows, "row_count": len(rows)}
    else:
        result_data = _dummy_metric_data(sub_name, index)

    chart_type = "bar" if item_type != "kpi" else "gauge"
    vega_spec = _build_vega_lite_spec(
        chart_type=chart_type,
        result_data=result_data,
        title=sub_name,
        x_label=drill_dimension or "Category",
        y_label="Value",
    )

    return {
        "name": sub_name,
        "item_type": item_type,
        "description": f"Drill-down view of {name}",
        "nl_question": sub_question,
        "sql": "",
        "summary": f"Detailed breakdown of {name} filtered by {drill_dimension}={drill_value}." if drill_value
                   else f"Detailed breakdown of {name}.",
        "explanation": "Drill-down showing a sub-set of the parent metric's data.",
        "insights": [
            f"Focused view on {drill_dimension}={drill_value}" if drill_value else "Sub-dimension detail",
            f"Parent metric: {name}",
        ],
        "chart_type": chart_type,
        "trend_direction": "stable",
        "vega_lite_spec": vega_spec,
        "result_data": result_data,
        "source_schemas": source_tables or [],
        "focus_area": "",
        "source": "preview_generator_drilldown",
    }


# ---------------------------------------------------------------------------
# Fake annotate
# No direct upstream API equivalent — annotations are vega-lite layer injections.
# The real path will call the LLM to generate the layer; fake does it locally.
# ---------------------------------------------------------------------------

def fake_annotate(
    vega_lite_spec: Dict[str, Any],
    annotation_text: str,
    annotation_type: str = "text",
    x_value: Optional[Any] = None,
    y_value: Optional[Any] = None,
    color: str = "#ff9800",
) -> Dict[str, Any]:
    """
    Inject an annotation layer into an existing vega-lite spec.

    annotation_type: "text" | "rule" | "point"
    x_value / y_value: data-space coordinates (optional; uses median if omitted).

    Returns:
      {vega_lite_spec: <updated spec>, annotations: [{text, x_value, y_value}]}
    """
    if not vega_lite_spec:
        return {"vega_lite_spec": vega_lite_spec, "annotations": []}

    spec = json.loads(json.dumps(vega_lite_spec))  # deep copy

    # Determine field names from existing encoding
    encoding = spec.get("encoding", {})
    x_field = encoding.get("x", {}).get("field", "period") if isinstance(encoding.get("x"), dict) else "period"
    y_field = encoding.get("y", {}).get("field", "value") if isinstance(encoding.get("y"), dict) else "value"

    # If caller didn't supply coords, pick the median row value
    if x_value is None or y_value is None:
        raw_vals = spec.get("data", {}).get("values", [])
        if raw_vals:
            mid = raw_vals[len(raw_vals) // 2]
            x_value = x_value if x_value is not None else mid.get(x_field)
            y_value = y_value if y_value is not None else mid.get(y_field)

    annotation_layer: Dict[str, Any] = {
        "data": {"values": [{"ax": x_value, "ay": y_value, "label": annotation_text}]},
        "encoding": {
            "x": {"field": "ax", "type": "ordinal"},
            "y": {"field": "ay", "type": "quantitative"},
        },
    }

    if annotation_type == "rule":
        annotation_layer["mark"] = {"type": "rule", "color": color, "strokeDash": [4, 4]}
    elif annotation_type == "point":
        annotation_layer["mark"] = {"type": "point", "color": color, "size": 120, "shape": "diamond"}
    else:
        annotation_layer["mark"] = {"type": "text", "color": color, "fontSize": 11, "dy": -10}
        annotation_layer["encoding"]["text"] = {"field": "label", "type": "nominal"}

    # Wrap bare spec into a layered spec if needed
    if "layer" in spec:
        spec["layer"].append(annotation_layer)
    else:
        spec = {
            "$schema": spec.get("$schema", "https://vega.github.io/schema/vega-lite/v5.json"),
            "title": spec.get("title", ""),
            "width": spec.get("width", "container"),
            "height": spec.get("height", 200),
            "config": spec.get("config", {}),
            "layer": [
                {k: v for k, v in spec.items()
                 if k not in ("$schema", "title", "width", "height", "config")},
                annotation_layer,
            ],
        }

    return {
        "vega_lite_spec": spec,
        "annotations": [{"text": annotation_text, "x_value": x_value, "y_value": y_value,
                         "type": annotation_type, "color": color}],
    }
