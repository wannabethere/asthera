"""
ECharts Intent Spec v1 — Pydantic Models
==========================================
Canonical Intermediate Representation (IR) for chart specifications.

Design:
  - Semantically stable (intent + encodings + measures/dimensions)
  - Renderer-agnostic (compiles to ECharts, Vega-Lite, PowerBI, etc.)
  - LLM-friendly (small, constrained enums, validatable)
  - Composable (multi-series, dual axis, multi-grid)
  - Auditable (provenance, warnings, lossiness)

Pipeline position:
  LLM / Agent → IntentSpec (this) → Compiler → ECharts option
                                             → Vega-Lite spec
                                             → PowerBI visual config
"""

from __future__ import annotations
from typing import Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════

class Intent(str, Enum):
    """What the user is trying to understand."""
    TREND_OVER_TIME     = "trend_over_time"
    COMPARE_CATEGORIES  = "compare_categories"
    DISTRIBUTION        = "distribution"
    RELATIONSHIP        = "relationship"
    PART_TO_WHOLE       = "part_to_whole"
    RANKING             = "ranking"
    GEO                 = "geo"
    FLOW                = "flow"
    HIERARCHY           = "hierarchy"
    COMPOSITION         = "composition"
    DEVIATION           = "deviation"
    CORRELATION         = "correlation"
    STATUS_KPI          = "status_kpi"
    TABLE               = "table"


class ChartFamily(str, Enum):
    """Visual chart type — maps to renderer series types."""
    # Cartesian
    LINE            = "line"
    AREA            = "area"
    BAR             = "bar"
    SCATTER         = "scatter"
    HEATMAP         = "heatmap"
    BOXPLOT         = "boxplot"
    CANDLESTICK     = "candlestick"
    # Polar / Radial
    PIE             = "pie"
    DONUT           = "donut"
    RADAR           = "radar"
    GAUGE           = "gauge"
    FUNNEL          = "funnel"
    # Hierarchical
    TREE            = "tree"
    TREEMAP         = "treemap"
    SUNBURST        = "sunburst"
    # Relational / Flow
    SANKEY          = "sankey"
    GRAPH           = "graph"
    # Geo
    MAP             = "map"
    # Specialized
    PICTORIAL_BAR   = "pictorial_bar"
    THEME_RIVER     = "theme_river"
    PARALLEL        = "parallel"
    WATERFALL       = "waterfall"
    BULLET          = "bullet"
    # Composite
    DUAL_AXIS       = "dual_axis"
    COMBO           = "combo"
    # Fallback
    CUSTOM          = "custom"
    KPI_CARD        = "kpi_card"


class AxisType(str, Enum):
    TIME        = "time"
    CATEGORY    = "category"
    VALUE       = "value"
    LOG         = "log"


class Aggregation(str, Enum):
    SUM             = "sum"
    AVG             = "avg"
    MIN             = "min"
    MAX             = "max"
    COUNT           = "count"
    COUNT_DISTINCT  = "count_distinct"
    MEDIAN          = "median"
    NONE            = "none"


class TimeGrain(str, Enum):
    MINUTE  = "minute"
    HOUR    = "hour"
    DAY     = "day"
    WEEK    = "week"
    MONTH   = "month"
    QUARTER = "quarter"
    YEAR    = "year"


class SortOrder(str, Enum):
    ASC     = "asc"
    DESC    = "desc"
    NONE    = "none"


class CoordinateSystem(str, Enum):
    CARTESIAN2D = "cartesian2d"
    POLAR       = "polar"
    GEO         = "geo"
    SINGLE      = "single"
    PARALLEL    = "parallel"
    NONE        = "none"


class FilterOp(str, Enum):
    EQ          = "="
    NEQ         = "!="
    GT          = ">"
    GTE         = ">="
    LT          = "<"
    LTE         = "<="
    IN          = "in"
    NOT_IN      = "not_in"
    BETWEEN     = "between"
    CONTAINS    = "contains"
    IS_NULL     = "is_null"
    IS_NOT_NULL = "is_not_null"


class GoodDirection(str, Enum):
    """For KPI/metric semantics — which direction is 'good'."""
    UP      = "up"
    DOWN    = "down"
    NEUTRAL = "neutral"


class LegendPosition(str, Enum):
    TOP     = "top"
    BOTTOM  = "bottom"
    LEFT    = "left"
    RIGHT   = "right"


class TooltipTrigger(str, Enum):
    AXIS    = "axis"
    ITEM    = "item"
    NONE    = "none"


class StackMode(str, Enum):
    NONE        = "none"
    STACKED     = "stacked"
    PERCENT     = "percent"


class Orientation(str, Enum):
    VERTICAL    = "vertical"
    HORIZONTAL  = "horizontal"


# ═══════════════════════════════════════════════════════════════════════
# ENCODING MODELS
# ═══════════════════════════════════════════════════════════════════════

class FieldEncoding(BaseModel):
    """Single field encoding — dimension or measure."""
    field: str = Field(..., description="Column/field name from the dataset")
    type: AxisType = Field(AxisType.CATEGORY, description="Axis type for this field")
    time_grain: Optional[TimeGrain] = Field(None, description="Time granularity if type=time")
    sort: SortOrder = Field(SortOrder.NONE, description="Sort order for this field")
    label: Optional[str] = Field(None, description="Display label override")


class MeasureEncoding(BaseModel):
    """Measure encoding — a numeric field with aggregation."""
    field: str = Field(..., description="Metric/measure field name")
    aggregate: Aggregation = Field(Aggregation.NONE, description="Aggregation function")
    axis: Optional[str] = Field(None, description="Axis binding: 'left', 'right', or None")
    format: Optional[str] = Field(None, description="Number format string, e.g. ',.0f' or '.1%'")
    label: Optional[str] = Field(None, description="Display label override")
    color: Optional[str] = Field(None, description="Explicit color hex for this measure")


class SeriesEncoding(BaseModel):
    """Grouping / series split field."""
    field: str = Field(..., description="Dimension field that creates series groups")
    label: Optional[str] = Field(None, description="Display label")


class SizeEncoding(BaseModel):
    """Size encoding — for scatter/bubble charts."""
    field: str
    min_size: int = Field(4, description="Minimum symbol size")
    max_size: int = Field(40, description="Maximum symbol size")


class ColorEncoding(BaseModel):
    """Color encoding — continuous or categorical."""
    field: str
    type: str = Field("dimension", description="'dimension' for categorical, 'measure' for continuous")
    palette: Optional[str] = Field(None, description="Named palette or list of hex colors")


class Encoding(BaseModel):
    """
    Complete encoding specification.
    Maps data fields to visual channels.
    """
    x: Optional[FieldEncoding] = Field(None, description="X-axis / primary dimension")
    y: list[MeasureEncoding] = Field(default_factory=list, description="Y-axis measures (supports multi)")
    series: Optional[SeriesEncoding] = Field(None, description="Series grouping field")
    color: Optional[ColorEncoding] = Field(None, description="Color encoding")
    size: Optional[SizeEncoding] = Field(None, description="Size encoding (scatter/bubble)")
    label_field: Optional[str] = Field(None, description="Field for data labels")
    tooltip_fields: list[str] = Field(default_factory=list, description="Extra fields in tooltip")

    # Hierarchical chart encodings
    source_field: Optional[str] = Field(None, description="Source node (sankey/graph)")
    target_field: Optional[str] = Field(None, description="Target node (sankey/graph)")
    value_field: Optional[str] = Field(None, description="Edge weight / node value")
    parent_field: Optional[str] = Field(None, description="Parent reference (tree/treemap)")
    children_field: Optional[str] = Field(None, description="Children array field")

    # Geo encodings
    lat_field: Optional[str] = Field(None, description="Latitude field")
    lng_field: Optional[str] = Field(None, description="Longitude field")
    region_field: Optional[str] = Field(None, description="Geographic region name/code")


# ═══════════════════════════════════════════════════════════════════════
# DATA SOURCE
# ═══════════════════════════════════════════════════════════════════════

class DataSource(BaseModel):
    """Where the data comes from."""
    source: str = Field("ref", description="'inline' for embedded rows, 'ref' for dataset reference")
    ref: Optional[str] = Field(None, description="Dataset reference ID (e.g. 'risk_timeseries_gold')")
    rows: Optional[list[dict[str, Any]]] = Field(None, description="Inline data rows")
    time_field: Optional[str] = Field(None, description="Primary time column for time-series data")
    row_count: Optional[int] = Field(None, description="Expected row count (for validation)")


# ═══════════════════════════════════════════════════════════════════════
# FILTER
# ═══════════════════════════════════════════════════════════════════════

class Filter(BaseModel):
    """Data filter expression."""
    field: str
    op: FilterOp
    value: Any = None


# ═══════════════════════════════════════════════════════════════════════
# VISUAL OPTIONS
# ═══════════════════════════════════════════════════════════════════════

class VisualOptions(BaseModel):
    """Visual styling and behavior options."""
    chart_family: ChartFamily = Field(..., description="Primary chart type")
    coordinate: CoordinateSystem = Field(CoordinateSystem.CARTESIAN2D)
    orientation: Orientation = Field(Orientation.VERTICAL)
    stack: StackMode = Field(StackMode.NONE)
    smooth: bool = Field(False, description="Smooth curves for line/area")
    show_area: bool = Field(False, description="Fill area under line")
    show_labels: bool = Field(False, description="Show data labels on chart")
    show_values: bool = Field(False, description="Show values on bars/points")
    palette: Optional[str] = Field(None, description="Named color palette")
    colors: Optional[list[str]] = Field(None, description="Explicit color list")
    inner_radius: Optional[str] = Field(None, description="Donut inner radius, e.g. '40%'")
    outer_radius: Optional[str] = Field(None, description="Pie/donut outer radius, e.g. '70%'")
    rose_type: Optional[str] = Field(None, description="'radius' or 'area' for nightingale charts")
    symbol_size: Optional[int] = Field(None, description="Default symbol size for scatter")
    bar_width: Optional[str] = Field(None, description="Bar width, e.g. '60%' or '20px'")
    bar_gap: Optional[str] = Field(None, description="Gap between bar groups")
    border_radius: Optional[int] = Field(None, description="Bar border radius")
    gradient: Optional[bool] = Field(None, description="Apply gradient fills")


# ═══════════════════════════════════════════════════════════════════════
# SERIES DEFINITION
# ═══════════════════════════════════════════════════════════════════════

class SeriesSpec(BaseModel):
    """
    Individual series within a chart.
    For multi-series or combo charts, you define one per visual layer.
    """
    id: Optional[str] = None
    type: ChartFamily = Field(..., description="Series chart type")
    y_field: Optional[str] = Field(None, description="Measure field for this series")
    x_field: Optional[str] = Field(None, description="Override x field")
    group_by: Optional[str] = Field(None, description="Grouping field")
    stack: Optional[str] = Field(None, description="Stack group name")
    axis_index: int = Field(0, description="Which y-axis (0=left, 1=right)")
    smooth: Optional[bool] = None
    show_area: Optional[bool] = None
    color: Optional[str] = Field(None, description="Explicit color for this series")
    label: Optional[str] = Field(None, description="Series name in legend")
    options: Optional[dict[str, Any]] = Field(None, description="Renderer-specific overrides")


# ═══════════════════════════════════════════════════════════════════════
# CHART BLOCK (for multi-grid / multi-chart layouts)
# ═══════════════════════════════════════════════════════════════════════

class ChartBlock(BaseModel):
    """
    A chart block within a composite layout.
    Single-chart specs have one block; multi-grid layouts have multiple.
    """
    id: str = Field("main", description="Block ID for grid reference")
    coordinate: CoordinateSystem = Field(CoordinateSystem.CARTESIAN2D)
    grid_index: int = Field(0)
    series: list[SeriesSpec] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# INTERACTIONS
# ═══════════════════════════════════════════════════════════════════════

class InteractionConfig(BaseModel):
    """User interaction configuration."""
    tooltip: TooltipTrigger = Field(TooltipTrigger.AXIS)
    legend: bool = Field(True)
    data_zoom: bool = Field(False, description="Enable slider/inside zoom")
    data_zoom_type: Optional[str] = Field(None, description="'slider', 'inside', or 'both'")
    brush: bool = Field(False, description="Enable brush selection")
    toolbox: bool = Field(False, description="Show ECharts toolbox")
    animation: bool = Field(True)


# ═══════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════

class GridConfig(BaseModel):
    """Grid positioning for multi-chart layouts."""
    id: str = "main"
    top: Optional[str] = None
    bottom: Optional[str] = None
    left: Optional[str] = None
    right: Optional[str] = None
    height: Optional[str] = None
    width: Optional[str] = None


class LayoutConfig(BaseModel):
    """Chart layout settings."""
    grids: list[GridConfig] = Field(default_factory=lambda: [GridConfig()])
    legend_position: LegendPosition = Field(LegendPosition.TOP)
    title_position: Optional[str] = Field(None)
    margin: Optional[dict[str, str]] = None


# ═══════════════════════════════════════════════════════════════════════
# SEMANTIC METADATA
# ═══════════════════════════════════════════════════════════════════════

class SemanticMeta(BaseModel):
    """
    Semantic metadata for governance, auto-formatting, and audit.
    Enables deterministic threshold coloring, title generation, etc.
    """
    metric_id: Optional[str] = Field(None, description="Canonical metric ID from your catalog")
    dataset_id: Optional[str] = Field(None, description="Source dataset reference")
    unit: Optional[str] = Field(None, description="Unit of measure: 'count', 'pct', 'usd', 'score_0_100', 'days'")
    good_direction: GoodDirection = Field(GoodDirection.NEUTRAL)
    thresholds: Optional[dict[str, float]] = Field(
        None,
        description="Named thresholds, e.g. {'critical': 90, 'warning': 70, 'good': 50}",
    )
    domain: Optional[str] = Field(None, description="Business domain: 'security', 'compliance', 'hr', 'finance'")
    control_id: Optional[str] = Field(None, description="Compliance control reference, e.g. 'CC7.1'")


# ═══════════════════════════════════════════════════════════════════════
# OVERRIDES (escape hatch)
# ═══════════════════════════════════════════════════════════════════════

class RendererOverrides(BaseModel):
    """
    Renderer-specific overrides. Controlled escape hatch.
    Only allowed keys are merged; everything else is rejected.
    """
    echarts_option: Optional[dict[str, Any]] = Field(
        None, description="Raw ECharts option keys to merge (use sparingly)"
    )
    vegalite_option: Optional[dict[str, Any]] = Field(None)
    powerbi_option: Optional[dict[str, Any]] = Field(None)


# ═══════════════════════════════════════════════════════════════════════
# THE SPEC — top-level model
# ═══════════════════════════════════════════════════════════════════════

class EChartsIntentSpec(BaseModel):
    """
    ECharts Intent Spec v1 — The canonical chart IR.
    
    LLMs generate this. Compilers consume it.
    
    Usage:
        spec = EChartsIntentSpec(
            intent=Intent.TREND_OVER_TIME,
            encoding=Encoding(
                x=FieldEncoding(field="date", type=AxisType.TIME),
                y=[MeasureEncoding(field="risk_score", aggregate=Aggregation.AVG)],
                series=SeriesEncoding(field="department"),
            ),
            visual=VisualOptions(chart_family=ChartFamily.LINE),
        )
        
        # Compile to ECharts
        from compiler_echarts import compile_to_echarts
        option = compile_to_echarts(spec, data=rows)
    """
    # Identity
    version: str = Field("eps/1.0", description="Spec version")
    title: Optional[str] = Field(None, description="Chart title")
    description: Optional[str] = Field(None, description="What this chart shows")
    
    # Semantic intent
    intent: Intent = Field(..., description="Analytical intent")
    
    # Data
    dataset: Optional[DataSource] = Field(None)
    filters: list[Filter] = Field(default_factory=list)
    
    # Encoding
    encoding: Encoding = Field(...)
    
    # Visual
    visual: VisualOptions = Field(...)
    
    # Series (for multi-series / combo charts)
    charts: list[ChartBlock] = Field(
        default_factory=list,
        description="Chart blocks — empty means auto-generate from encoding + visual",
    )
    
    # Interactions
    interactions: InteractionConfig = Field(default_factory=InteractionConfig)
    
    # Layout
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    
    # Semantic metadata
    semantics: Optional[SemanticMeta] = Field(None)
    
    # Overrides
    overrides: Optional[RendererOverrides] = Field(None)

    @model_validator(mode="after")
    def validate_encoding_for_intent(self) -> "EChartsIntentSpec":
        """Cross-field validation: ensure encoding matches intent."""
        intent = self.intent
        enc = self.encoding
        vis = self.visual

        # Cartesian charts need x + y
        cartesian_families = {
            ChartFamily.LINE, ChartFamily.AREA, ChartFamily.BAR,
            ChartFamily.SCATTER, ChartFamily.HEATMAP, ChartFamily.BOXPLOT,
            ChartFamily.CANDLESTICK, ChartFamily.WATERFALL,
        }
        if vis.chart_family in cartesian_families:
            if not enc.x:
                raise ValueError(f"chart_family={vis.chart_family.value} requires encoding.x")
            if not enc.y:
                raise ValueError(f"chart_family={vis.chart_family.value} requires encoding.y")

        # Flow charts need source + target
        if vis.chart_family in (ChartFamily.SANKEY, ChartFamily.GRAPH):
            if not enc.source_field or not enc.target_field:
                raise ValueError(f"chart_family={vis.chart_family.value} requires source_field + target_field")

        # Hierarchy charts need parent or children
        if vis.chart_family in (ChartFamily.TREE, ChartFamily.TREEMAP, ChartFamily.SUNBURST):
            if not enc.parent_field and not enc.children_field and not enc.value_field:
                raise ValueError(f"chart_family={vis.chart_family.value} requires parent_field or children_field")

        # Geo charts need lat/lng or region
        if vis.chart_family == ChartFamily.MAP:
            if not enc.lat_field and not enc.region_field:
                raise ValueError("chart_family=map requires lat_field+lng_field or region_field")

        return self

    class Config:
        use_enum_values = True


# ═══════════════════════════════════════════════════════════════════════
# COMPILATION RESULT
# ═══════════════════════════════════════════════════════════════════════

class WarningItem(BaseModel):
    code: str
    message: str
    severity: str = Field("info", description="'info', 'warning', 'error'")


class Lossiness(BaseModel):
    score: float = Field(0.0, ge=0.0, le=1.0, description="0=lossless, 1=total loss")
    dropped_features: list[str] = Field(default_factory=list)
    approximated_features: list[str] = Field(default_factory=list)


class CompileResult(BaseModel):
    """Output of any compiler (ECharts, Vega-Lite, PowerBI, etc.)."""
    status: str = Field(..., description="'compiled', 'approximated', 'unsupported'")
    renderer: str = Field(..., description="Target renderer name")
    intent_spec: EChartsIntentSpec
    option: Optional[dict[str, Any]] = Field(None, description="Compiled renderer-native option")
    warnings: list[WarningItem] = Field(default_factory=list)
    lossiness: Lossiness = Field(default_factory=Lossiness)
    provenance: Optional[dict[str, Any]] = Field(None, description="Audit trail")
