# Layout Spec → ECharts Rendering Gap Analysis

## TL;DR

The current spec is **not renderable as-is**. It is a structural skeleton — it names
what exists but omits everything a renderer needs to actually draw anything.
There are 8 categories of gaps. Most are data that exists upstream in
`metric_recommendations` and `metric_gold_model_bindings` but was never promoted
into the spec.

---

## What the Chasma dashboard (reference image) requires vs what the spec provides

| Requirement | Reference Image | Current Spec | Gap |
|---|---|---|---|
| Grid layout | 2×3 grid, exact row/col spans | `panels: {left, center, right}` strings | No positions |
| KPI tile values | "4 Assigned", "20 Completed", "0 Missed", "11.538 Hours" | `strip_kpis: [{metric_id, display_name: "None"}]` | No labels, no values |
| Chart types | bar_horizontal, line_multi, bar_vertical | all `line_basic` | Wrong types for 4/5 charts |
| Axis config | labeled axes, formatted ticks | no axis config | Nothing |
| Color palette | orange/teal/green/red per status | no colors | Nothing |
| Learner profile panel | name/org/manager/email/emp# | `card_anatomy: {badge, title, subtitle, score}` | Wrong fields entirely |
| Data field mapping | `status → y`, `count → x` | no field mapping | Nothing |
| Chart-to-panel placement | which chart goes in which cell | all `panel: "center"` | No cell assignment |

---

## Gap 1 — Wrong Template Selected (`_fallback: true`)

The spec itself flags this:
```json
"_fallback": true,
"template_id": "risk-register"
```

The metrics are **vulnerability management** (Qualys, CVE counts, host snapshots).
The selected template is **GRC Risk Register** — designed for risk items with owners,
treatment plans, and residual risk scores.

**Scoring evidence**: top-3 had scores of 33, 32, 32. The only reason `risk-register`
won was `strip_cell_count_match`. Domain/focus/category signals scored zero because
`decisions_applied: {}` — the decision tree produced no decisions.

**Root cause**: `_fallback: true` means `spec_generation_node` ran its deterministic
fallback path because no LLM call succeeded. The LLM would have selected a template
like `command-center` or `vuln-management` based on the metric content.

**Fix**: Ensure the LLM `spec_generation_node` call runs, or add a deterministic
fallback that picks template by `metric_recommendations[*].data_source_required`
(here: `qualys` → security/vuln domain → `command-center` or `threat-intel`).

---

## Gap 2 — All `display_name: "None"` in strip_kpis and charts

Every KPI cell and chart entry has:
```json
"display_name": "None"
```

The source data (`metric_recommendations`) has the actual names:
```json
"name": "Vulnerabilities by Asset Criticality - by Host"
"kpis_covered": ["Critical vuln count (per host)", "30-day trend of critical vulnerabilities"]
```

**What a renderer needs:**
```json
{
  "metric_id": "vuln_by_asset_criticality:by_host",
  "display_name": "Critical Vulns by Host",    ← human label for the tile
  "subtitle": "30-day trend",                  ← secondary label
  "unit": "vulns",                             ← suffix for value display
  "icon": "shield-alert",                      ← icon key
  "value_format": "integer"                    ← how to format the number
}
```

**Fix in `spec_generation_node`**: When building `strip_kpis` and `charts`, join on
`metric_id` back to `resolution_payload.metric_recommendations` and pull
`name`, `kpis_covered`, `kpi_value_type`, `available_filters`.

---

## Gap 3 — All Charts Typed as `line_basic`

Every chart in the spec:
```json
"chart_type": "line_basic"
```

But `map_metric_widget_to_chart()` in `taxonomy_matcher.py` already maps widget types
to chart types. The issue is the bindings use `widget_type` from `metric_recommendations`,
but the spec's `charts[]` array ignores those bindings — it was built by the fallback
path which defaults everything to `line_basic`.

**What a renderer needs per chart:**

| Metric | Correct chart_type | ECharts series type |
|---|---|---|
| Activity by Status (horizontal bars) | `bar_horizontal` | `bar` with `encode.x=count, encode.y=status` |
| Activity by Type (horizontal bars) | `bar_horizontal` | same |
| YOY Activity Launch/Completions (dual line) | `line_multi` | two `line` series |
| YOY Training Hours (vertical bars) | `bar_vertical` | `bar` with `encode.x=year` |
| KPI tiles (Assigned / Completed / etc.) | `stat_tile` | not a chart — plain HTML/ECharts gauge |

**Fix**: `spec_generation_node` must read `metric_gold_model_bindings[*].chart_type`
(already correctly computed by `map_metric_widget_to_chart`) when building `charts[]`.

---

## Gap 4 — No Grid Layout Positions

The spec has:
```json
"panels": {
  "left":   "filter_bar + risk_cards",
  "center": "detail_sections + treatment_plan + heatmap",
  "right":  "chat_panel"
}
```

These are template description strings, not panel specifications. A renderer has no
idea where to place anything on the page.

**What ECharts / a layout engine needs:**

```json
"grid": {
  "rows": 2,
  "cols": 3,
  "cells": [
    {
      "cell_id": "learner_profile",
      "row": 0, "col": 0, "row_span": 1, "col_span": 1,
      "component_type": "profile_card",
      "metric_ids": []
    },
    {
      "cell_id": "activity_by_status",
      "row": 0, "col": 1, "row_span": 1, "col_span": 1,
      "component_type": "chart",
      "chart_type": "bar_horizontal",
      "metric_ids": ["activity_status_counts"]
    },
    {
      "cell_id": "kpi_strip",
      "row": 0, "col": 2, "row_span": 1, "col_span": 1,
      "component_type": "stat_grid",
      "metric_ids": ["assigned", "completed", "missed_deadline", "training_hours"]
    },
    ...
  ]
}
```

The current `primitives: ["topbar", "posture_strip", "three_panel"]` tell us the
abstract structure, but not the per-cell dimensions or what content goes in each.

**Fix**: The `spec_generation_node` needs a `grid_builder` that translates
`primitives + charts[] + strip_kpis[]` into positioned grid cells.

---

## Gap 5 — No Axis, Series, or Data Field Mapping

Every chart entry has:
```json
"axis_label": "",
"aggregation": "",
"gold_table": "gold_qualys_vulnerabilities_daily_snapshot"
```

A renderer cannot draw an ECharts instance from this. It needs:

```json
{
  "chart_type": "bar_horizontal",
  "gold_table": "gold_qualys_vulnerabilities_daily_snapshot",
  "x_field": "count",
  "y_field": "status",
  "group_by": null,
  "series_field": null,
  "aggregation": "sum",
  "filter_fields": ["severity", "status"],
  "time_field": null,
  "axis": {
    "x": {"label": "Count", "type": "value"},
    "y": {"label": "Activity Status", "type": "category"}
  },
  "tooltip_fields": ["status", "count"],
  "color_mapping": {
    "Attended": "#F5A623",
    "Cancelled": "#E05A5A",
    "In Progress": "#00BCD4",
    "No-Show": "#00BCD4"
  }
}
```

The `available_filters` and `available_groups` fields on each `metric_recommendation`
carry this — they just aren't promoted into the spec.

**Fix**: `spec_generation_node` must expand each chart entry with fields from the
corresponding `metric_recommendation`.

---

## Gap 6 — No Color Palette or Theme Tokens

The spec has:
```json
"theme": "light"
```

Nothing else. The reference image uses a consistent dark theme with:
- Background: `#1A1F2E`
- Card surface: `#252B3B`
- Accent colors: `#F5A623` (orange), `#00BCD4` (teal), `#E05A5A` (red), `#4CAF50` (green)
- Text: `#FFFFFF` primary, `#8E9AB5` secondary

**What the spec needs:**

```json
"theme_tokens": {
  "background": "#1A1F2E",
  "surface": "#252B3B",
  "border": "#2E3650",
  "text_primary": "#FFFFFF",
  "text_secondary": "#8E9AB5",
  "accent": ["#00BCD4", "#4CAF50", "#F5A623", "#E05A5A"],
  "severity_colors": {
    "critical": "#E05A5A",
    "high": "#F5A623",
    "medium": "#4FC3F7",
    "low": "#4CAF50"
  }
}
```

The `filters` array already has `["All", "Critical", "High", "Medium", "Low"]` — the
theme tokens should map directly to those filter values.

**Fix**: Add a `theme_token_registry` keyed by `(theme, domain)` in the template
registry, and emit the right tokens into the spec at `spec_generation_node`.

---

## Gap 7 — KPI Strip Has No Values, Labels, Thresholds, or Icons

Current:
```json
{
  "metric_id": "vuln_by_asset_criticality:by_host",
  "display_name": "None",
  "unit": "",
  "good_direction": "neutral",
  "threshold_warning": null,
  "threshold_critical": null
}
```

The reference image shows tiles like:
- **"4"** with label "Assigned" and a user icon
- **"20"** with label "Completed" and a green checkmark
- **"0"** with label "Missed Deadline" and a warning icon (orange)
- **"11.538"** with label "Training Hours" and a clock icon

**What a renderer needs:**

```json
{
  "metric_id": "assigned_count",
  "display_name": "Assigned",
  "icon": "user-plus",
  "icon_color": "#F5A623",
  "unit": "",
  "value_format": "integer",
  "good_direction": "down",
  "threshold_warning": 10,
  "threshold_critical": 25,
  "color_when_zero": "#4CAF50",
  "color_when_critical": "#E05A5A"
}
```

`sla_or_threshold` in `metric_recommendations` carries threshold data — it's `null`
here because the source metrics don't define SLAs. Icons need a mapping table
keyed by `kpi_value_type` (`count` → user icon, `percentage` → percent icon, etc.).

**Fix**: Add `kpi_icon_registry` and `kpi_color_registry` keyed by
`(kpi_value_type, good_direction)` and emit into strip_kpis at spec generation time.

---

## Gap 8 — `card_anatomy` is for the Wrong Template

Current:
```json
"card_anatomy": {
  "badge": "risk_level",
  "title": "risk_title",
  "subtitle": "owner + category",
  "score": "residual_risk_score"
}
```

This is the Risk Register template's card anatomy — `risk_level`, `residual_risk_score`
are GRC fields. The actual metrics are Qualys vulnerability data, so a card would need:

```json
"card_anatomy": {
  "badge": "severity",
  "title": "vulnerability_title",
  "subtitle": "host_id + os",
  "score": "cvss_score",
  "status": "remediation_status"
}
```

This cascades from the wrong template selection (Gap 1). Once the template is corrected,
the `card_anatomy` from the right template in the registry will be correct.

---

## What the Spec DOES Have That Is Useful

These fields are correct and usable today:

- `output_format: "echarts"` — renderer target is clear
- `destination_type: "embedded"` — no destination gate issues
- `filters: ["All", "Critical", "High", "Medium", "Low"]` — correct for vuln domain
- `gold_table` on every chart — data source is correctly identified
- `metric_gold_model_bindings` in state — has the right chart_type, strip_cell, panel_slot
- `compliance_context.focus_areas` — describes the dashboard intent accurately
- `pipeline_audit` — full traceability of how the spec was produced
- `has_chat: true` — correct structural flag

---

## Prioritized Fix Roadmap

### Priority 1 — `spec_generation_node` enrichment (unblocks rendering immediately)

| Change | What to do |
|---|---|
| Promote `display_name` | Join `strip_kpis[]` and `charts[]` back to `metric_recommendations` on `metric_id`, pull `name` |
| Promote `chart_type` | Use `metric_gold_model_bindings[*].chart_type` instead of defaulting to `line_basic` |
| Promote axis config | Pull `available_filters` → `filter_fields`, `available_groups` → `group_by`, `metrics_intent` → `x/y` orientation |
| Fix template selection | When `_fallback=True`, override with domain-keyed default (`qualys → command-center`) |

### Priority 2 — New spec fields (enables full visual fidelity)

| Field | How to populate |
|---|---|
| `grid.cells[]` | Build from `primitives + chart count + strip_cells` in a `GridBuilder` class |
| `theme_tokens{}` | Keyed registry in `templates_registry.json` by `(theme, domain)` |
| `strip_kpis[*].icon` | `kpi_icon_registry` keyed by `kpi_value_type` |
| `strip_kpis[*].threshold_*` | From `metric_recommendations[*].sla_or_threshold` |

### Priority 3 — ECharts adapter layer (new module)

Rather than making ECharts spec generation the spec itself, add an adapter:

```
layout_spec.json
    ↓
EChartsSpecAdapter.build(spec, data_sample)
    ↓
{
  "grid": [...],          ← ECharts grid array
  "xAxis": [...],         ← per-chart axis
  "yAxis": [...],
  "series": [...],        ← typed series with field mappings
  "color": [...],         ← palette from theme_tokens
  "tooltip": {...},
  "legend": {...}
}
```

This keeps the layout spec renderer-agnostic and puts ECharts-specific logic
in the adapter — so the same spec can produce Power BI or Tableau output later.

---

## Summary

The spec is a **correct structural intent document** but it is missing three layers:

1. **Display layer** — human-readable labels, icons, thresholds, colors (all derivable from existing upstream data)
2. **Grid layer** — exact row/col placement for each component (derivable from primitives + chart count)
3. **Data binding layer** — x/y fields, group_by, series, aggregation (derivable from metric_recommendations)

None of these require new data sources. Everything needed is already present in
`metric_recommendations`, `metric_gold_model_bindings`, and the template registry —
it just needs to be joined and promoted into the spec at `spec_generation_node`.