"""
ECharts Compiler — IntentSpec → ECharts Option
================================================
Deterministic compiler that transforms an EChartsIntentSpec
into a native ECharts `option` object.

No LLM calls. Pure rule-based transformation.

Supported chart families (v1):
  Cartesian: line, area, bar, scatter, heatmap, boxplot, candlestick, waterfall
  Polar:     pie, donut, radar, gauge, funnel
  Hierarchy: treemap, sunburst, tree
  Flow:      sankey, graph
  Composite: dual_axis, combo
  KPI:       kpi_card (renders metadata, not a chart)
  Geo:       map

Usage:
    from intent_spec_models import EChartsIntentSpec
    from compiler_echarts import compile_to_echarts

    result = compile_to_echarts(spec, data=rows)
    if result.status == "compiled":
        echarts_option = result.option
"""

from __future__ import annotations
from typing import Any, Optional
from copy import deepcopy

from intent_spec_models import (
    EChartsIntentSpec, CompileResult, WarningItem, Lossiness,
    ChartFamily, CoordinateSystem, StackMode, Orientation,
    Aggregation, AxisType, TooltipTrigger,
)


# ═══════════════════════════════════════════════════════════════════════
# MAIN COMPILER ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def compile_to_echarts(
    spec: EChartsIntentSpec,
    data: Optional[list[dict[str, Any]]] = None,
) -> CompileResult:
    """
    Compile an IntentSpec to an ECharts option.
    
    Args:
        spec: The intent spec to compile
        data: Optional inline data rows. If None, uses spec.dataset.rows
    
    Returns:
        CompileResult with status, option, warnings, lossiness
    """
    warnings: list[WarningItem] = []
    dropped: list[str] = []
    approximated: list[str] = []

    family = spec.visual.chart_family

    # Route to family-specific compiler
    compiler_map = {
        # Cartesian
        "line":         _compile_cartesian,
        "area":         _compile_cartesian,
        "bar":          _compile_cartesian,
        "scatter":      _compile_scatter,
        "heatmap":      _compile_heatmap,
        "boxplot":      _compile_boxplot,
        "candlestick":  _compile_candlestick,
        "waterfall":    _compile_waterfall,
        # Polar / Radial
        "pie":          _compile_pie,
        "donut":        _compile_pie,
        "radar":        _compile_radar,
        "gauge":        _compile_gauge,
        "funnel":       _compile_funnel,
        # Hierarchical
        "treemap":      _compile_treemap,
        "sunburst":     _compile_sunburst,
        "tree":         _compile_tree,
        # Flow
        "sankey":       _compile_sankey,
        "graph":        _compile_graph,
        # Specialized
        "theme_river":  _compile_theme_river,
        "parallel":     _compile_parallel,
        "pictorial_bar": _compile_cartesian,
        # Composite
        "dual_axis":    _compile_dual_axis,
        "combo":        _compile_dual_axis,
        # KPI
        "kpi_card":     _compile_kpi_card,
        # Geo
        "map":          _compile_geo,
    }

    compiler = compiler_map.get(family)
    if not compiler:
        return CompileResult(
            status="unsupported",
            renderer="echarts",
            intent_spec=spec,
            warnings=[WarningItem(code="UNSUPPORTED_FAMILY", message=f"chart_family='{family}' has no compiler.", severity="error")],
            lossiness=Lossiness(score=1.0, dropped_features=[family]),
        )

    try:
        option = compiler(spec, data or [])
    except Exception as e:
        return CompileResult(
            status="unsupported",
            renderer="echarts",
            intent_spec=spec,
            warnings=[WarningItem(code="COMPILE_ERROR", message=str(e), severity="error")],
            lossiness=Lossiness(score=1.0, dropped_features=["compilation"]),
        )

    # Apply overrides
    if spec.overrides and spec.overrides.echarts_option:
        option = _safe_merge(option, spec.overrides.echarts_option, warnings)

    # Apply common options
    option = _apply_common(spec, option)

    status = "compiled"
    if warnings:
        status = "approximated" if any(w.severity == "warning" for w in warnings) else "compiled"

    return CompileResult(
        status=status,
        renderer="echarts",
        intent_spec=spec,
        option=option,
        warnings=warnings,
        lossiness=Lossiness(
            score=len(dropped) * 0.2 + len(approximated) * 0.1,
            dropped_features=dropped,
            approximated_features=approximated,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# COMMON OPTIONS (title, tooltip, legend, animation)
# ═══════════════════════════════════════════════════════════════════════

def _apply_common(spec: EChartsIntentSpec, option: dict) -> dict:
    """Apply title, tooltip, legend, animation to any chart."""
    # Title
    if spec.title:
        option.setdefault("title", {})["text"] = spec.title

    # Tooltip
    trigger = spec.interactions.tooltip
    if trigger != "none":
        option["tooltip"] = {"trigger": trigger}

    # Legend
    if spec.interactions.legend:
        option["legend"] = {
            "show": True,
            "type": "scroll",
            **(_legend_position(spec.layout.legend_position)),
        }

    # DataZoom
    if spec.interactions.data_zoom:
        zoom_type = spec.interactions.data_zoom_type or "slider"
        zooms = []
        if zoom_type in ("slider", "both"):
            zooms.append({"type": "slider", "start": 0, "end": 100})
        if zoom_type in ("inside", "both"):
            zooms.append({"type": "inside"})
        if zooms:
            option["dataZoom"] = zooms

    # Toolbox
    if spec.interactions.toolbox:
        option["toolbox"] = {
            "feature": {
                "saveAsImage": {},
                "dataView": {"readOnly": True},
                "restore": {},
            }
        }

    # Animation
    option["animation"] = spec.interactions.animation

    # Grid margin defaults
    if "grid" not in option and spec.visual.chart_family in (
        "line", "area", "bar", "scatter", "heatmap", "boxplot",
        "candlestick", "waterfall", "pictorial_bar",
    ):
        option["grid"] = {"containLabel": True, "left": "3%", "right": "4%", "bottom": "3%"}

    return option


def _legend_position(pos: str) -> dict:
    if pos == "bottom":
        return {"bottom": 0}
    if pos == "left":
        return {"left": 0, "orient": "vertical"}
    if pos == "right":
        return {"right": 0, "orient": "vertical"}
    return {"top": 0}


# ═══════════════════════════════════════════════════════════════════════
# CARTESIAN COMPILER (line, area, bar)
# ═══════════════════════════════════════════════════════════════════════

def _compile_cartesian(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    vis = spec.visual
    family = vis.chart_family

    is_horizontal = vis.orientation == "horizontal"

    # Determine ECharts series type
    series_type = family
    if family == "area":
        series_type = "line"
    elif family == "pictorial_bar":
        series_type = "pictorialBar"

    # Axis types
    x_axis_type = enc.x.type if enc.x else "category"
    if x_axis_type == "time":
        x_axis = {"type": "time"}
    else:
        x_axis = {"type": "category"}
        if data and enc.x:
            categories = sorted(set(str(r.get(enc.x.field, "")) for r in data))
            x_axis["data"] = categories

    y_axis = {"type": "value"}

    # Build series
    series_list = []

    if enc.series and enc.series.field:
        # Multi-series: group by series field
        groups = _group_data(data, enc.series.field)
        for group_name, rows in groups.items():
            for y_enc in enc.y:
                s = {
                    "name": group_name,
                    "type": series_type,
                    "data": _extract_xy_data(rows, enc.x.field if enc.x else None, y_enc.field),
                }
                if family == "area" or vis.show_area:
                    s["areaStyle"] = {}
                if vis.smooth:
                    s["smooth"] = True
                if vis.stack != "none":
                    s["stack"] = "total"
                if vis.show_labels or vis.show_values:
                    s["label"] = {"show": True}
                series_list.append(s)
    else:
        # Single or multi-measure
        for y_enc in enc.y:
            s = {
                "name": y_enc.label or y_enc.field,
                "type": series_type,
                "data": _extract_values(data, y_enc.field),
            }
            if family == "area" or vis.show_area:
                s["areaStyle"] = {}
            if vis.smooth:
                s["smooth"] = True
            if vis.stack != "none":
                s["stack"] = "total"
            if vis.show_labels or vis.show_values:
                s["label"] = {"show": True}
            if y_enc.color:
                s["itemStyle"] = {"color": y_enc.color}
            if vis.bar_width:
                s["barWidth"] = vis.bar_width
            if vis.border_radius:
                s.setdefault("itemStyle", {})["borderRadius"] = vis.border_radius
            series_list.append(s)

    option = {"series": series_list}
    if is_horizontal:
        option["xAxis"] = y_axis
        option["yAxis"] = x_axis
    else:
        option["xAxis"] = x_axis
        option["yAxis"] = y_axis

    if vis.colors:
        option["color"] = vis.colors

    return option


# ═══════════════════════════════════════════════════════════════════════
# SCATTER COMPILER
# ═══════════════════════════════════════════════════════════════════════

def _compile_scatter(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    vis = spec.visual
    x_field = enc.x.field if enc.x else ""
    y_field = enc.y[0].field if enc.y else ""

    option = {
        "xAxis": {"type": "value", "name": enc.x.label or x_field if enc.x else ""},
        "yAxis": {"type": "value", "name": enc.y[0].label or y_field if enc.y else ""},
    }

    if enc.series and enc.series.field:
        groups = _group_data(data, enc.series.field)
        series_list = []
        for name, rows in groups.items():
            s = {
                "name": name,
                "type": "scatter",
                "data": [[r.get(x_field), r.get(y_field)] for r in rows],
            }
            if enc.size:
                s["symbolSize"] = _make_symbol_size_fn(enc.size, rows)
            elif vis.symbol_size:
                s["symbolSize"] = vis.symbol_size
            series_list.append(s)
        option["series"] = series_list
    else:
        s = {
            "type": "scatter",
            "data": [[r.get(x_field), r.get(y_field)] for r in data],
            "symbolSize": vis.symbol_size or 10,
        }
        option["series"] = [s]

    return option


def _make_symbol_size_fn(size_enc, rows):
    """Create scaled symbol sizes from a size encoding."""
    values = [r.get(size_enc.field, 0) for r in rows]
    if not values:
        return size_enc.min_size
    max_val = max(values) or 1
    return [
        size_enc.min_size + (v / max_val) * (size_enc.max_size - size_enc.min_size)
        for v in values
    ]


# ═══════════════════════════════════════════════════════════════════════
# HEATMAP COMPILER
# ═══════════════════════════════════════════════════════════════════════

def _compile_heatmap(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    x_field = enc.x.field if enc.x else ""
    y_field = enc.y[0].field if enc.y else ""
    color_field = enc.color.field if enc.color else (enc.y[0].field if enc.y else "")

    x_cats = sorted(set(str(r.get(x_field, "")) for r in data))
    y_cats = sorted(set(str(r.get(y_field, "")) for r in data))

    heatmap_data = []
    for r in data:
        xi = x_cats.index(str(r.get(x_field, ""))) if str(r.get(x_field, "")) in x_cats else 0
        yi = y_cats.index(str(r.get(y_field, ""))) if str(r.get(y_field, "")) in y_cats else 0
        heatmap_data.append([xi, yi, r.get(color_field, 0)])

    values = [d[2] for d in heatmap_data]
    min_val = min(values) if values else 0
    max_val = max(values) if values else 1

    return {
        "xAxis": {"type": "category", "data": x_cats},
        "yAxis": {"type": "category", "data": y_cats},
        "visualMap": {"min": min_val, "max": max_val, "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0},
        "series": [{"type": "heatmap", "data": heatmap_data, "label": {"show": True}}],
    }


# ═══════════════════════════════════════════════════════════════════════
# BOXPLOT / CANDLESTICK
# ═══════════════════════════════════════════════════════════════════════

def _compile_boxplot(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    return {
        "xAxis": {"type": "category"},
        "yAxis": {"type": "value"},
        "dataset": {"source": data},
        "series": [{"type": "boxplot", "encode": {"x": enc.x.field if enc.x else "", "y": enc.y[0].field if enc.y else ""}}],
    }


def _compile_candlestick(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    return {
        "xAxis": {"type": "category"},
        "yAxis": {"type": "value"},
        "dataset": {"source": data},
        "series": [{"type": "candlestick", "encode": {
            "x": enc.x.field if enc.x else "",
            "y": [e.field for e in enc.y[:4]],
        }}],
    }


def _compile_waterfall(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    x_field = enc.x.field if enc.x else ""
    y_field = enc.y[0].field if enc.y else ""

    categories = [str(r.get(x_field, "")) for r in data]
    values = [r.get(y_field, 0) for r in data]

    # Build waterfall as stacked bar (transparent base + colored delta)
    running = 0
    base_data = []
    positive_data = []
    negative_data = []
    for v in values:
        if v >= 0:
            base_data.append(running)
            positive_data.append(v)
            negative_data.append("-")
        else:
            base_data.append(running + v)
            positive_data.append("-")
            negative_data.append(abs(v))
        running += v

    return {
        "xAxis": {"type": "category", "data": categories},
        "yAxis": {"type": "value"},
        "series": [
            {"type": "bar", "stack": "waterfall", "data": base_data, "itemStyle": {"color": "transparent"}, "emphasis": {"itemStyle": {"color": "transparent"}}},
            {"name": "Increase", "type": "bar", "stack": "waterfall", "data": positive_data, "itemStyle": {"color": "#22c55e"}},
            {"name": "Decrease", "type": "bar", "stack": "waterfall", "data": negative_data, "itemStyle": {"color": "#ef4444"}},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# PIE / DONUT COMPILER
# ═══════════════════════════════════════════════════════════════════════

def _compile_pie(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    vis = spec.visual
    label_field = enc.x.field if enc.x else ""
    value_field = enc.y[0].field if enc.y else ""

    pie_data = [{"name": str(r.get(label_field, "")), "value": r.get(value_field, 0)} for r in data]

    s = {
        "type": "pie",
        "data": pie_data,
        "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}},
    }

    if vis.chart_family == "donut" or vis.inner_radius:
        s["radius"] = [vis.inner_radius or "40%", vis.outer_radius or "70%"]
    elif vis.outer_radius:
        s["radius"] = vis.outer_radius

    if vis.rose_type:
        s["roseType"] = vis.rose_type

    if vis.show_labels:
        s["label"] = {"show": True, "formatter": "{b}: {d}%"}
    else:
        s["label"] = {"show": False}

    return {"series": [s]}


# ═══════════════════════════════════════════════════════════════════════
# RADAR COMPILER
# ═══════════════════════════════════════════════════════════════════════

def _compile_radar(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    x_field = enc.x.field if enc.x else ""
    y_field = enc.y[0].field if enc.y else ""

    indicators = sorted(set(str(r.get(x_field, "")) for r in data))
    max_val = max((r.get(y_field, 0) for r in data), default=100)

    indicator_config = [{"name": ind, "max": max_val * 1.2} for ind in indicators]

    if enc.series and enc.series.field:
        groups = _group_data(data, enc.series.field)
        series_data = []
        for name, rows in groups.items():
            value_map = {str(r.get(x_field, "")): r.get(y_field, 0) for r in rows}
            series_data.append({"name": name, "value": [value_map.get(ind, 0) for ind in indicators]})
    else:
        value_map = {str(r.get(x_field, "")): r.get(y_field, 0) for r in data}
        series_data = [{"value": [value_map.get(ind, 0) for ind in indicators]}]

    return {
        "radar": {"indicator": indicator_config},
        "series": [{"type": "radar", "data": series_data}],
    }


# ═══════════════════════════════════════════════════════════════════════
# GAUGE COMPILER
# ═══════════════════════════════════════════════════════════════════════

def _compile_gauge(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    y_field = enc.y[0].field if enc.y else ""
    label = enc.y[0].label or y_field if enc.y else ""

    value = data[0].get(y_field, 0) if data else 0

    s: dict[str, Any] = {
        "type": "gauge",
        "data": [{"value": value, "name": label}],
        "detail": {"formatter": "{value}"},
    }

    # Apply semantic thresholds as axis line colors
    if spec.semantics and spec.semantics.thresholds:
        t = spec.semantics.thresholds
        colors = []
        sorted_t = sorted(t.items(), key=lambda x: x[1])
        for name, val in sorted_t:
            color = "#ef4444" if "critical" in name.lower() else "#f97316" if "warning" in name.lower() else "#22c55e"
            colors.append([val / 100, color])
        if colors and colors[-1][0] < 1:
            colors.append([1, "#22c55e"])
        s["axisLine"] = {"lineStyle": {"color": colors}}

    return {"series": [s]}


# ═══════════════════════════════════════════════════════════════════════
# FUNNEL COMPILER
# ═══════════════════════════════════════════════════════════════════════

def _compile_funnel(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    label_field = enc.x.field if enc.x else ""
    value_field = enc.y[0].field if enc.y else ""

    funnel_data = [{"name": str(r.get(label_field, "")), "value": r.get(value_field, 0)} for r in data]
    funnel_data.sort(key=lambda x: x["value"], reverse=True)

    return {
        "series": [{
            "type": "funnel",
            "data": funnel_data,
            "sort": "descending",
            "gap": 2,
            "label": {"show": True, "position": "inside"},
        }],
    }


# ═══════════════════════════════════════════════════════════════════════
# TREEMAP / SUNBURST / TREE
# ═══════════════════════════════════════════════════════════════════════

def _compile_treemap(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    return {
        "series": [{
            "type": "treemap",
            "data": data,
            "label": {"show": True},
        }],
    }


def _compile_sunburst(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    return {
        "series": [{
            "type": "sunburst",
            "data": data,
            "radius": [0, "90%"],
            "label": {"rotate": "radial"},
        }],
    }


def _compile_tree(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    orient = "LR" if spec.visual.orientation == "horizontal" else "TB"
    tree_data = data[0] if data and isinstance(data[0], dict) else {"name": "root", "children": data}
    return {
        "series": [{
            "type": "tree",
            "data": [tree_data],
            "orient": orient,
            "label": {"position": "left", "verticalAlign": "middle"},
            "expandAndCollapse": True,
        }],
    }


# ═══════════════════════════════════════════════════════════════════════
# SANKEY / GRAPH
# ═══════════════════════════════════════════════════════════════════════

def _compile_sankey(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    src = enc.source_field or ""
    tgt = enc.target_field or ""
    val = enc.value_field or ""

    nodes_set = set()
    links = []
    for r in data:
        s = str(r.get(src, ""))
        t = str(r.get(tgt, ""))
        v = r.get(val, 1)
        nodes_set.add(s)
        nodes_set.add(t)
        links.append({"source": s, "target": t, "value": v})

    nodes = [{"name": n} for n in sorted(nodes_set)]

    return {
        "series": [{
            "type": "sankey",
            "data": nodes,
            "links": links,
            "emphasis": {"focus": "adjacency"},
            "lineStyle": {"color": "gradient", "curveness": 0.5},
        }],
    }


def _compile_graph(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    src = enc.source_field or ""
    tgt = enc.target_field or ""

    nodes_set = set()
    links = []
    for r in data:
        s = str(r.get(src, ""))
        t = str(r.get(tgt, ""))
        nodes_set.add(s)
        nodes_set.add(t)
        links.append({"source": s, "target": t})

    nodes = [{"name": n, "symbolSize": 20} for n in sorted(nodes_set)]

    return {
        "series": [{
            "type": "graph",
            "layout": "force",
            "data": nodes,
            "links": links,
            "roam": True,
            "label": {"show": True},
            "force": {"repulsion": 100, "edgeLength": [50, 200]},
        }],
    }


# ═══════════════════════════════════════════════════════════════════════
# SPECIALIZED
# ═══════════════════════════════════════════════════════════════════════

def _compile_theme_river(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    x_field = enc.x.field if enc.x else ""
    y_field = enc.y[0].field if enc.y else ""
    series_field = enc.series.field if enc.series else ""

    river_data = [[str(r.get(x_field, "")), r.get(y_field, 0), str(r.get(series_field, ""))] for r in data]

    return {
        "singleAxis": {"type": "time", "top": 50, "bottom": 50},
        "series": [{"type": "themeRiver", "data": river_data}],
    }


def _compile_parallel(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    dims = [{"dim": i, "name": e.label or e.field} for i, e in enumerate(enc.y)]

    parallel_data = []
    for r in data:
        parallel_data.append([r.get(e.field, 0) for e in enc.y])

    return {
        "parallelAxis": dims,
        "series": [{"type": "parallel", "data": parallel_data}],
    }


# ═══════════════════════════════════════════════════════════════════════
# DUAL-AXIS / COMBO
# ═══════════════════════════════════════════════════════════════════════

def _compile_dual_axis(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    vis = spec.visual

    x_field = enc.x.field if enc.x else ""
    x_type = enc.x.type if enc.x else "category"

    categories = sorted(set(str(r.get(x_field, "")) for r in data)) if data and x_type != "time" else None

    x_axis = {"type": x_type}
    if categories:
        x_axis["data"] = categories

    y_axes = []
    series_list = []

    # Use charts blocks if defined, otherwise auto from encoding.y
    if spec.charts and spec.charts[0].series:
        for s_spec in spec.charts[0].series:
            axis_idx = s_spec.axis_index
            while len(y_axes) <= axis_idx:
                y_axes.append({"type": "value"})
            s: dict[str, Any] = {
                "name": s_spec.label or s_spec.y_field or "",
                "type": s_spec.type,
                "yAxisIndex": axis_idx,
                "data": _extract_values(data, s_spec.y_field or ""),
            }
            if s_spec.smooth:
                s["smooth"] = True
            if s_spec.show_area:
                s["areaStyle"] = {}
            series_list.append(s)
    else:
        for i, y_enc in enumerate(enc.y):
            axis_idx = 1 if y_enc.axis == "right" else 0
            while len(y_axes) <= axis_idx:
                y_axes.append({"type": "value"})
            s_type = "line" if i > 0 else "bar"
            series_list.append({
                "name": y_enc.label or y_enc.field,
                "type": s_type,
                "yAxisIndex": axis_idx,
                "data": _extract_values(data, y_enc.field),
            })

    if not y_axes:
        y_axes = [{"type": "value"}]

    return {
        "xAxis": x_axis,
        "yAxis": y_axes,
        "series": series_list,
    }


# ═══════════════════════════════════════════════════════════════════════
# KPI CARD (metadata only)
# ═══════════════════════════════════════════════════════════════════════

def _compile_kpi_card(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    y_field = enc.y[0].field if enc.y else ""
    label = enc.y[0].label or y_field if enc.y else ""
    value = data[0].get(y_field, 0) if data else 0

    return {
        "_type": "kpi_card",
        "label": label,
        "value": value,
        "format": enc.y[0].format if enc.y else None,
        "semantics": spec.semantics.model_dump() if spec.semantics else None,
    }


# ═══════════════════════════════════════════════════════════════════════
# GEO MAP
# ═══════════════════════════════════════════════════════════════════════

def _compile_geo(spec: EChartsIntentSpec, data: list[dict]) -> dict:
    enc = spec.encoding
    region = enc.region_field or ""
    value_field = enc.y[0].field if enc.y else ""

    map_data = [{"name": str(r.get(region, "")), "value": r.get(value_field, 0)} for r in data]

    return {
        "geo": {"map": "world", "roam": True},
        "series": [{"type": "map", "map": "world", "data": map_data}],
    }


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _group_data(data: list[dict], field: str) -> dict[str, list[dict]]:
    """Group data rows by a field value."""
    groups: dict[str, list[dict]] = {}
    for r in data:
        key = str(r.get(field, ""))
        groups.setdefault(key, []).append(r)
    return groups


def _extract_xy_data(rows: list[dict], x_field: str | None, y_field: str) -> list:
    """Extract [x, y] pairs from rows."""
    if x_field:
        return [[r.get(x_field), r.get(y_field)] for r in rows]
    return [r.get(y_field) for r in rows]


def _extract_values(data: list[dict], field: str) -> list:
    """Extract values for a single field."""
    return [r.get(field, 0) for r in data]


def _safe_merge(base: dict, overrides: dict, warnings: list[WarningItem]) -> dict:
    """Safely merge overrides into base option. Only allowed top-level keys."""
    ALLOWED_OVERRIDE_KEYS = {
        "series", "title", "color", "textStyle", "grid",
        "visualMap", "axisPointer", "graphic",
    }
    result = deepcopy(base)
    for key, value in overrides.items():
        if key in ALLOWED_OVERRIDE_KEYS:
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = {**result[key], **value}
            elif key in result and isinstance(result[key], list) and isinstance(value, list):
                result[key] = value  # replace list overrides
            else:
                result[key] = value
        else:
            warnings.append(WarningItem(
                code="OVERRIDE_BLOCKED",
                message=f"Override key '{key}' is not in the allowed list and was ignored.",
                severity="warning",
            ))
    return result
