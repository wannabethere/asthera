"""
ECharts Intent Spec — Example Usage & Tests
=============================================
Demonstrates the full pipeline:
  1. Create IntentSpec from the catalog examples
  2. Compile to ECharts option
  3. Multi-renderer planning
  4. Chart selection prompt generation

Run: python example_charts.py
"""

import json
from intent_spec_models import (
    EChartsIntentSpec, Encoding, FieldEncoding, MeasureEncoding,
    SeriesEncoding, SizeEncoding, VisualOptions, DataSource,
    InteractionConfig, SemanticMeta, RendererOverrides,
    ChartBlock, SeriesSpec,
    Intent, ChartFamily, AxisType, Aggregation, TimeGrain,
    CoordinateSystem, GoodDirection, StackMode,
)
from compiler_echarts import compile_to_echarts
from compiler_base import CompilationPlanner, RENDERER_REGISTRY
from chart_catalog import CHART_CATALOG, INTENT_CHART_MAP, get_charts_by_intent


# ═══════════════════════════════════════════════════════════════════════
# SAMPLE DATA
# ═══════════════════════════════════════════════════════════════════════

RISK_DATA = [
    {"date": "2024-01", "department": "Engineering", "risk_score": 72},
    {"date": "2024-02", "department": "Engineering", "risk_score": 68},
    {"date": "2024-03", "department": "Engineering", "risk_score": 65},
    {"date": "2024-01", "department": "Finance", "risk_score": 85},
    {"date": "2024-02", "department": "Finance", "risk_score": 82},
    {"date": "2024-03", "department": "Finance", "risk_score": 78},
    {"date": "2024-01", "department": "HR", "risk_score": 45},
    {"date": "2024-02", "department": "HR", "risk_score": 50},
    {"date": "2024-03", "department": "HR", "risk_score": 48},
]

TRAINING_DATA = [
    {"category": "Compliance", "hours": 450, "completions": 89},
    {"category": "Security", "hours": 320, "completions": 75},
    {"category": "Leadership", "hours": 180, "completions": 42},
    {"category": "Technical", "hours": 560, "completions": 112},
    {"category": "Onboarding", "hours": 210, "completions": 55},
]

COMPLIANCE_DONUT = [
    {"status": "Completed", "count": 85},
    {"status": "In Progress", "count": 10},
    {"status": "Overdue", "count": 3},
    {"status": "Assigned", "count": 32},
]

FLOW_DATA = [
    {"source_control": "CC7.1 Vuln Mgmt", "incident_type": "Data Breach", "incident_count": 5},
    {"source_control": "CC7.1 Vuln Mgmt", "incident_type": "Unauthorized Access", "incident_count": 12},
    {"source_control": "CC6.2 Access Control", "incident_type": "Unauthorized Access", "incident_count": 8},
    {"source_control": "CC6.2 Access Control", "incident_type": "Privilege Escalation", "incident_count": 3},
    {"source_control": "CC3.1 Risk Assess", "incident_type": "Compliance Gap", "incident_count": 7},
]


def demo_line_chart():
    """Example 1: Multi-series line chart (risk over time)."""
    print("=" * 60)
    print("  1. LINE CHART — Risk Score Over Time by Department")
    print("=" * 60)

    spec = EChartsIntentSpec(
        title="Risk Score Over Time by Department",
        intent=Intent.TREND_OVER_TIME,
        dataset=DataSource(source="ref", ref="risk_timeseries_gold", time_field="date"),
        encoding=Encoding(
            x=FieldEncoding(field="date", type=AxisType.TIME, time_grain=TimeGrain.MONTH),
            y=[MeasureEncoding(field="risk_score", aggregate=Aggregation.AVG, axis="left")],
            series=SeriesEncoding(field="department"),
        ),
        visual=VisualOptions(
            chart_family=ChartFamily.LINE,
            smooth=True,
        ),
        interactions=InteractionConfig(tooltip="axis", legend=True, data_zoom=True),
        semantics=SemanticMeta(
            metric_id="risk_score",
            unit="score_0_100",
            good_direction=GoodDirection.DOWN,
            domain="security",
        ),
    )

    result = compile_to_echarts(spec, data=RISK_DATA)
    _print_result(result)


def demo_bar_chart():
    """Example 2: Horizontal bar chart (training by category)."""
    print("\n" + "=" * 60)
    print("  2. BAR CHART — Training Hours by Category")
    print("=" * 60)

    spec = EChartsIntentSpec(
        title="Training Hours by Category",
        intent=Intent.COMPARE_CATEGORIES,
        encoding=Encoding(
            x=FieldEncoding(field="category", type=AxisType.CATEGORY),
            y=[MeasureEncoding(field="hours", aggregate=Aggregation.SUM)],
        ),
        visual=VisualOptions(
            chart_family=ChartFamily.BAR,
            orientation="horizontal",
            show_labels=True,
            bar_width="60%",
            border_radius=4,
        ),
    )

    result = compile_to_echarts(spec, data=TRAINING_DATA)
    _print_result(result)


def demo_donut_chart():
    """Example 3: Donut chart (compliance status)."""
    print("\n" + "=" * 60)
    print("  3. DONUT CHART — Training Compliance Status")
    print("=" * 60)

    spec = EChartsIntentSpec(
        title="Assigned Training Compliance",
        intent=Intent.PART_TO_WHOLE,
        encoding=Encoding(
            x=FieldEncoding(field="status", type=AxisType.CATEGORY),
            y=[MeasureEncoding(field="count", aggregate=Aggregation.SUM)],
        ),
        visual=VisualOptions(
            chart_family=ChartFamily.DONUT,
            inner_radius="45%",
            outer_radius="70%",
            show_labels=True,
        ),
    )

    result = compile_to_echarts(spec, data=COMPLIANCE_DONUT)
    _print_result(result)


def demo_sankey():
    """Example 4: Sankey (risk flow)."""
    print("\n" + "=" * 60)
    print("  4. SANKEY — Risk Flow: Controls → Incidents")
    print("=" * 60)

    spec = EChartsIntentSpec(
        title="Risk Flow: Control Failures → Incident Types",
        intent=Intent.FLOW,
        encoding=Encoding(
            source_field="source_control",
            target_field="incident_type",
            value_field="incident_count",
            x=FieldEncoding(field="source_control", type=AxisType.CATEGORY),
            y=[MeasureEncoding(field="incident_count", aggregate=Aggregation.SUM)],
        ),
        visual=VisualOptions(
            chart_family=ChartFamily.SANKEY,
            coordinate=CoordinateSystem.NONE,
        ),
        interactions=InteractionConfig(tooltip="item", legend=False),
    )

    result = compile_to_echarts(spec, data=FLOW_DATA)
    _print_result(result)


def demo_gauge():
    """Example 5: Gauge (posture score)."""
    print("\n" + "=" * 60)
    print("  5. GAUGE — Overall Compliance Posture")
    print("=" * 60)

    spec = EChartsIntentSpec(
        title="Overall Compliance Posture",
        intent=Intent.STATUS_KPI,
        encoding=Encoding(
            y=[MeasureEncoding(field="posture_score", aggregate=Aggregation.AVG, label="Score")],
        ),
        visual=VisualOptions(
            chart_family=ChartFamily.GAUGE,
            coordinate=CoordinateSystem.NONE,
        ),
        semantics=SemanticMeta(
            unit="score_0_100",
            good_direction=GoodDirection.UP,
            thresholds={"critical": 60, "warning": 80, "good": 90},
        ),
    )

    result = compile_to_echarts(spec, data=[{"posture_score": 84}])
    _print_result(result)


def demo_dual_axis():
    """Example 6: Dual-axis combo (bar + line)."""
    print("\n" + "=" * 60)
    print("  6. DUAL AXIS — Hours (bar) + Completions (line)")
    print("=" * 60)

    spec = EChartsIntentSpec(
        title="Training Hours vs Completions",
        intent=Intent.COMPARE_CATEGORIES,
        encoding=Encoding(
            x=FieldEncoding(field="category", type=AxisType.CATEGORY),
            y=[
                MeasureEncoding(field="hours", aggregate=Aggregation.SUM, axis="left", label="Hours"),
                MeasureEncoding(field="completions", aggregate=Aggregation.SUM, axis="right", label="Completions"),
            ],
        ),
        visual=VisualOptions(chart_family=ChartFamily.DUAL_AXIS),
        charts=[
            ChartBlock(id="c1", coordinate=CoordinateSystem.CARTESIAN2D, series=[
                SeriesSpec(type=ChartFamily.BAR, y_field="hours", axis_index=0, label="Hours"),
                SeriesSpec(type=ChartFamily.LINE, y_field="completions", axis_index=1, smooth=True, label="Completions"),
            ]),
        ],
    )

    result = compile_to_echarts(spec, data=TRAINING_DATA)
    _print_result(result)


def demo_multi_renderer():
    """Example 7: Multi-renderer planning."""
    print("\n" + "=" * 60)
    print("  7. MULTI-RENDERER PLANNING")
    print("=" * 60)

    planner = CompilationPlanner()

    # Sankey — ECharts supports, Vega-Lite doesn't
    sankey_spec = EChartsIntentSpec(
        title="Flow test",
        intent=Intent.FLOW,
        encoding=Encoding(
            source_field="src",
            target_field="tgt",
            value_field="val",
            x=FieldEncoding(field="src", type=AxisType.CATEGORY),
            y=[MeasureEncoding(field="val", aggregate=Aggregation.SUM)],
        ),
        visual=VisualOptions(chart_family=ChartFamily.SANKEY, coordinate=CoordinateSystem.NONE),
    )

    for renderer in ["echarts", "vegalite", "powerbi"]:
        plan = planner.plan(sankey_spec, target=renderer)
        status = "✓" if plan["can_compile"] else "✗"
        issues = plan["issues"] or ["none"]
        fallback = plan.get("fallback_family") or "—"
        print(f"  {status} {renderer:12s} issues={issues[0][:50]:50s} fallback={fallback}")


def demo_catalog_lookup():
    """Example 8: Chart catalog lookup."""
    print("\n" + "=" * 60)
    print("  8. CHART CATALOG LOOKUP")
    print("=" * 60)

    print(f"\n  Total chart types: {len(CHART_CATALOG)}")
    print(f"  Intent categories: {len(INTENT_CHART_MAP)}")

    for intent, charts in INTENT_CHART_MAP.items():
        if charts:
            print(f"\n  {intent}:")
            for cid in charts:
                c = CHART_CATALOG[cid]
                print(f"    → {c['name']:30s} ({c['family']})")


def demo_prompt_generation():
    """Example 9: LLM prompt generation."""
    print("\n" + "=" * 60)
    print("  9. LLM PROMPT GENERATION")
    print("=" * 60)

    from spec_store import build_chart_selection_prompt

    prompt = build_chart_selection_prompt(
        available_fields=["date", "department", "risk_score", "control_id", "status", "evidence_count"],
        data_description="Monthly risk scores by department with control compliance status",
        user_intent="Show me how risk trends differ across departments over time",
    )
    print(f"\n  Prompt length: {len(prompt)} chars")
    print(f"  First 300 chars:\n  {prompt[:300]}...")


def _print_result(result):
    """Pretty-print a CompileResult."""
    print(f"\n  Status: {result.status}")
    print(f"  Renderer: {result.renderer}")
    print(f"  Warnings: {len(result.warnings)}")
    for w in result.warnings:
        print(f"    [{w.severity}] {w.code}: {w.message}")
    print(f"  Lossiness: {result.lossiness.score}")
    if result.option:
        opt_str = json.dumps(result.option, indent=2, default=str)
        if len(opt_str) > 600:
            print(f"  Option (truncated):\n{opt_str[:600]}...")
        else:
            print(f"  Option:\n{opt_str}")


if __name__ == "__main__":
    demo_line_chart()
    demo_bar_chart()
    demo_donut_chart()
    demo_sankey()
    demo_gauge()
    demo_dual_axis()
    demo_multi_renderer()
    demo_catalog_lookup()
    demo_prompt_generation()
    print("\n✓ All demos complete.")
