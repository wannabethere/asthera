"""
Base Compiler Interface
========================
Abstract compiler contract that all renderers implement.
This ensures ECharts, Vega-Lite, PowerBI, and future renderers
all follow the same pattern: IntentSpec → CompileResult.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional

from intent_spec_models import EChartsIntentSpec, CompileResult, ChartFamily


# ═══════════════════════════════════════════════════════════════════════
# CAPABILITY MAP
# ═══════════════════════════════════════════════════════════════════════

class RendererCapabilities:
    """
    Declares what a renderer can handle.
    Used by the planner to choose the right compiler or warn about limitations.
    """

    def __init__(
        self,
        name: str,
        supported_families: set[str],
        supports_dual_axis: bool = False,
        supports_animation: bool = True,
        supports_zoom: bool = False,
        supports_brush: bool = False,
        max_series: int = 50,
        notes: str = "",
    ):
        self.name = name
        self.supported_families = supported_families
        self.supports_dual_axis = supports_dual_axis
        self.supports_animation = supports_animation
        self.supports_zoom = supports_zoom
        self.supports_brush = supports_brush
        self.max_series = max_series
        self.notes = notes

    def can_render(self, family: str) -> bool:
        return family in self.supported_families

    def check_spec(self, spec: EChartsIntentSpec) -> list[str]:
        """Return list of issues with rendering this spec."""
        issues = []
        if not self.can_render(spec.visual.chart_family):
            issues.append(f"chart_family '{spec.visual.chart_family}' not supported by {self.name}")
        if spec.interactions.data_zoom and not self.supports_zoom:
            issues.append(f"dataZoom not supported by {self.name}")
        if spec.interactions.brush and not self.supports_brush:
            issues.append(f"brush not supported by {self.name}")
        return issues


# ═══════════════════════════════════════════════════════════════════════
# PRE-DEFINED CAPABILITIES
# ═══════════════════════════════════════════════════════════════════════

ECHARTS_CAPABILITIES = RendererCapabilities(
    name="echarts",
    supported_families={
        "line", "area", "bar", "scatter", "heatmap", "boxplot", "candlestick",
        "pie", "donut", "radar", "gauge", "funnel",
        "treemap", "sunburst", "tree",
        "sankey", "graph",
        "theme_river", "parallel", "pictorial_bar",
        "waterfall", "dual_axis", "combo",
        "kpi_card", "map",
    },
    supports_dual_axis=True,
    supports_animation=True,
    supports_zoom=True,
    supports_brush=True,
    max_series=100,
    notes="Full-featured; native support for all chart families in the catalog.",
)

VEGALITE_CAPABILITIES = RendererCapabilities(
    name="vegalite",
    supported_families={
        "line", "area", "bar", "scatter", "heatmap", "boxplot",
        "pie",  # via arc mark
    },
    supports_dual_axis=False,
    supports_animation=False,
    supports_zoom=False,
    supports_brush=True,  # via selections
    max_series=20,
    notes="Strong grammar but limited to cartesian + arc marks. No sankey/treemap/gauge.",
)

POWERBI_CAPABILITIES = RendererCapabilities(
    name="powerbi",
    supported_families={
        "line", "area", "bar", "scatter",
        "pie", "donut", "funnel", "gauge",
        "treemap", "map",
        "kpi_card",
    },
    supports_dual_axis=True,
    supports_animation=True,
    supports_zoom=False,
    supports_brush=False,
    max_series=50,
    notes="Covers common visuals; no sankey/sunburst/graph natively (needs custom visuals).",
)

RENDERER_REGISTRY: dict[str, RendererCapabilities] = {
    "echarts": ECHARTS_CAPABILITIES,
    "vegalite": VEGALITE_CAPABILITIES,
    "powerbi": POWERBI_CAPABILITIES,
}


# ═══════════════════════════════════════════════════════════════════════
# ABSTRACT COMPILER
# ═══════════════════════════════════════════════════════════════════════

class BaseChartCompiler(ABC):
    """
    Abstract base for chart compilers.
    
    Each renderer (ECharts, Vega-Lite, PowerBI) implements:
      - compile(spec, data) → CompileResult
      - capabilities property
      - can_compile(spec) check
    """

    @property
    @abstractmethod
    def renderer_name(self) -> str:
        ...

    @property
    @abstractmethod
    def capabilities(self) -> RendererCapabilities:
        ...

    @abstractmethod
    def compile(
        self,
        spec: EChartsIntentSpec,
        data: Optional[list[dict[str, Any]]] = None,
    ) -> CompileResult:
        ...

    def can_compile(self, spec: EChartsIntentSpec) -> tuple[bool, list[str]]:
        """Check if this renderer can handle the spec."""
        issues = self.capabilities.check_spec(spec)
        return len(issues) == 0, issues


# ═══════════════════════════════════════════════════════════════════════
# ECHARTS COMPILER (wraps the module)
# ═══════════════════════════════════════════════════════════════════════

class EChartsCompiler(BaseChartCompiler):
    """ECharts compiler using the full compile_to_echarts function."""

    @property
    def renderer_name(self) -> str:
        return "echarts"

    @property
    def capabilities(self) -> RendererCapabilities:
        return ECHARTS_CAPABILITIES

    def compile(self, spec, data=None) -> CompileResult:
        from compiler_echarts import compile_to_echarts
        return compile_to_echarts(spec, data)


# ═══════════════════════════════════════════════════════════════════════
# MULTI-RENDERER PLANNER
# ═══════════════════════════════════════════════════════════════════════

class CompilationPlanner:
    """
    Given an IntentSpec and a target renderer, decides:
      1. Can the renderer handle it directly?
      2. If not, can we approximate?
      3. If not, what's the closest supported chart?
    
    Usage:
        planner = CompilationPlanner()
        plan = planner.plan(spec, target="echarts")
    """

    def __init__(self, compilers: Optional[dict[str, BaseChartCompiler]] = None):
        self._compilers = compilers or {"echarts": EChartsCompiler()}

    def plan(
        self,
        spec: EChartsIntentSpec,
        target: str = "echarts",
    ) -> dict:
        """
        Plan compilation for a target renderer.
        
        Returns:
            {
                "can_compile": bool,
                "target": str,
                "issues": [...],
                "fallback_family": str | None,
                "fallback_renderer": str | None,
            }
        """
        caps = RENDERER_REGISTRY.get(target)
        if not caps:
            return {"can_compile": False, "target": target, "issues": [f"Unknown renderer: {target}"], "fallback_family": None, "fallback_renderer": None}

        issues = caps.check_spec(spec)
        if not issues:
            return {"can_compile": True, "target": target, "issues": [], "fallback_family": None, "fallback_renderer": None}

        # Try to find a fallback chart family
        fallback = self._find_fallback_family(spec.visual.chart_family, caps)

        # Try to find a renderer that CAN handle it
        fallback_renderer = None
        for name, other_caps in RENDERER_REGISTRY.items():
            if name != target and other_caps.can_render(spec.visual.chart_family):
                fallback_renderer = name
                break

        return {
            "can_compile": False,
            "target": target,
            "issues": issues,
            "fallback_family": fallback,
            "fallback_renderer": fallback_renderer,
        }

    def _find_fallback_family(self, family: str, caps: RendererCapabilities) -> Optional[str]:
        """Find the closest supported chart family."""
        FALLBACK_MAP = {
            "donut":         "pie",
            "area":          "line",
            "sankey":        "bar",
            "sunburst":      "treemap",
            "tree":          "treemap",
            "graph":         "scatter",
            "gauge":         "kpi_card",
            "theme_river":   "area",
            "parallel":      "radar",
            "pictorial_bar": "bar",
            "waterfall":     "bar",
            "candlestick":   "line",
            "heatmap":       "scatter",
            "boxplot":       "bar",
            "funnel":        "bar",
            "combo":         "bar",
            "dual_axis":     "line",
            "bullet":        "bar",
        }
        fallback = FALLBACK_MAP.get(family)
        if fallback and caps.can_render(fallback):
            return fallback
        return None

    def compile(
        self,
        spec: EChartsIntentSpec,
        target: str = "echarts",
        data: Optional[list[dict]] = None,
    ) -> CompileResult:
        """Plan + compile in one step."""
        compiler = self._compilers.get(target)
        if not compiler:
            from intent_spec_models import WarningItem, Lossiness
            return CompileResult(
                status="unsupported",
                renderer=target,
                intent_spec=spec,
                warnings=[WarningItem(code="NO_COMPILER", message=f"No compiler registered for '{target}'")],
                lossiness=Lossiness(score=1.0, dropped_features=["renderer"]),
            )
        return compiler.compile(spec, data)
