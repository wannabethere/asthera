"""
CCE Chart Engine — ECharts Intent Spec System
===============================================
Renderer-agnostic chart specification IR with compilers.

Usage:
    from cce_chart_engine import EChartsIntentSpec, compile_to_echarts
    from cce_chart_engine import CHART_CATALOG, CompilationPlanner
"""

from intent_spec_models import (
    EChartsIntentSpec, CompileResult, WarningItem, Lossiness,
    Encoding, FieldEncoding, MeasureEncoding, SeriesEncoding,
    SizeEncoding, ColorEncoding, VisualOptions, DataSource,
    Filter, InteractionConfig, LayoutConfig, SemanticMeta,
    RendererOverrides, ChartBlock, SeriesSpec,
    Intent, ChartFamily, AxisType, Aggregation, TimeGrain,
    CoordinateSystem, GoodDirection, StackMode, Orientation,
)
from chart_catalog import CHART_CATALOG, INTENT_CHART_MAP
from compiler_echarts import compile_to_echarts
from compiler_base import (
    BaseChartCompiler, EChartsCompiler,
    CompilationPlanner, RendererCapabilities, RENDERER_REGISTRY,
)
from spec_store import ChartSpecJsonStore, ChartSpecVectorStore

__all__ = [
    "EChartsIntentSpec", "CompileResult",
    "CHART_CATALOG", "INTENT_CHART_MAP",
    "compile_to_echarts",
    "CompilationPlanner", "RENDERER_REGISTRY",
    "ChartSpecJsonStore", "ChartSpecVectorStore",
]
