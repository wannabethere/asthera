from typing import Literal, Optional, Union, Any, Dict, List
from pydantic import BaseModel, Field

class ChartAdjustmentOption(BaseModel):
    chart_type: Literal[
        "bar", "grouped_bar", "line", "pie", "stacked_bar", "area", "multi_line", 
        "scatter", "heatmap", "boxplot", "histogram", "bubble", "text", "tick", "rule", "kpi"
    ]
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    adjustment_option: Optional[str] = None
    x_offset: Optional[str] = None
    color: Optional[str] = None
    theta: Optional[str] = None 
    size: Optional[str] = None  # For bubble charts
    z_axis: Optional[str] = None  # For 3D plots


# Pydantic Models for Vega-Lite Chart Schemas
class ChartSchema(BaseModel):
    class ChartType(BaseModel):
        type: Literal["bar", "line", "area", "arc", "point", "circle", "rect", "boxplot", "text", "tick", "rule", "kpi"]

    class ChartEncoding(BaseModel):
        field: str
        type: Literal["ordinal", "quantitative", "nominal"]
        title: str

    title: str
    mark: ChartType
    encoding: ChartEncoding


class TemporalChartEncoding(ChartSchema.ChartEncoding):
    type: Literal["temporal"] = Field(default="temporal")
    timeUnit: str = Field(default="yearmonth")


class LineChartSchema(ChartSchema):
    class LineChartMark(BaseModel):
        type: Literal["line"] = Field(default="line")

    class LineChartEncoding(BaseModel):
        x: TemporalChartEncoding | ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        color: Optional[ChartSchema.ChartEncoding] = None

    mark: LineChartMark
    encoding: LineChartEncoding


class MultiLineChartSchema(ChartSchema):
    class MultiLineChartMark(BaseModel):
        type: Literal["line"] = Field(default="line")

    class MultiLineChartTransform(BaseModel):
        fold: list[str]
        as_: list[str] = Field(alias="as")

    class MultiLineChartEncoding(BaseModel):
        x: TemporalChartEncoding | ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        color: ChartSchema.ChartEncoding

    mark: MultiLineChartMark
    transform: list[MultiLineChartTransform]
    encoding: MultiLineChartEncoding


class BarChartSchema(ChartSchema):
    class BarChartMark(BaseModel):
        type: Literal["bar"] = Field(default="bar")

    class BarChartEncoding(BaseModel):
        x: TemporalChartEncoding | ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        color: ChartSchema.ChartEncoding

    mark: BarChartMark
    encoding: BarChartEncoding


class GroupedBarChartSchema(ChartSchema):
    class GroupedBarChartMark(BaseModel):
        type: Literal["bar"] = Field(default="bar")

    class GroupedBarChartEncoding(BaseModel):
        x: TemporalChartEncoding | ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        xOffset: ChartSchema.ChartEncoding
        color: ChartSchema.ChartEncoding

    mark: GroupedBarChartMark
    encoding: GroupedBarChartEncoding


class StackedBarChartYEncoding(ChartSchema.ChartEncoding):
    stack: Literal["zero"] = Field(default="zero")


class StackedBarChartSchema(ChartSchema):
    class StackedBarChartMark(BaseModel):
        type: Literal["bar"] = Field(default="bar")

    class StackedBarChartEncoding(BaseModel):
        x: TemporalChartEncoding | ChartSchema.ChartEncoding
        y: StackedBarChartYEncoding
        color: ChartSchema.ChartEncoding

    mark: StackedBarChartMark
    encoding: StackedBarChartEncoding


class PieChartSchema(ChartSchema):
    class PieChartMark(BaseModel):
        type: Literal["arc"] = Field(default="arc")

    class PieChartEncoding(BaseModel):
        theta: ChartSchema.ChartEncoding
        color: ChartSchema.ChartEncoding

    mark: PieChartMark
    encoding: PieChartEncoding


class AreaChartSchema(ChartSchema):
    class AreaChartMark(BaseModel):
        type: Literal["area"] = Field(default="area")

    class AreaChartEncoding(BaseModel):
        x: TemporalChartEncoding | ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding

    mark: AreaChartMark
    encoding: AreaChartEncoding


# New chart schemas for enhanced chart types
class ScatterChartSchema(ChartSchema):
    class ScatterChartMark(BaseModel):
        type: Literal["point", "circle"] = Field(default="circle")

    class ScatterChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        color: Optional[ChartSchema.ChartEncoding] = None
        size: Optional[ChartSchema.ChartEncoding] = None

    mark: ScatterChartMark
    encoding: ScatterChartEncoding


class HeatmapChartSchema(ChartSchema):
    class HeatmapChartMark(BaseModel):
        type: Literal["rect"] = Field(default="rect")

    class HeatmapChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        color: ChartSchema.ChartEncoding

    mark: HeatmapChartMark
    encoding: HeatmapChartEncoding


class BoxPlotChartSchema(ChartSchema):
    class BoxPlotChartMark(BaseModel):
        type: Literal["boxplot"] = Field(default="boxplot")

    class BoxPlotChartEncoding(BaseModel):
        y: ChartSchema.ChartEncoding
        x: Optional[ChartSchema.ChartEncoding] = None
        color: Optional[ChartSchema.ChartEncoding] = None

    mark: BoxPlotChartMark
    encoding: BoxPlotChartEncoding


class HistogramChartSchema(ChartSchema):
    class HistogramChartMark(BaseModel):
        type: Literal["bar"] = Field(default="bar")

    class HistogramChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding

    mark: HistogramChartMark
    encoding: HistogramChartEncoding


class BubbleChartSchema(ChartSchema):
    class BubbleChartMark(BaseModel):
        type: Literal["circle"] = Field(default="circle")

    class BubbleChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        size: ChartSchema.ChartEncoding
        color: Optional[ChartSchema.ChartEncoding] = None

    mark: BubbleChartMark
    encoding: BubbleChartEncoding


class TextChartSchema(ChartSchema):
    class TextChartMark(BaseModel):
        type: Literal["text"] = Field(default="text")

    class TextChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: ChartSchema.ChartEncoding
        text: ChartSchema.ChartEncoding

    mark: TextChartMark
    encoding: TextChartEncoding


class TickChartSchema(ChartSchema):
    class TickChartMark(BaseModel):
        type: Literal["tick"] = Field(default="tick")

    class TickChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: Optional[ChartSchema.ChartEncoding] = None
        color: Optional[ChartSchema.ChartEncoding] = None

    mark: TickChartMark
    encoding: TickChartEncoding


class RuleChartSchema(ChartSchema):
    class RuleChartMark(BaseModel):
        type: Literal["rule"] = Field(default="rule")

    class RuleChartEncoding(BaseModel):
        x: ChartSchema.ChartEncoding
        y: Optional[ChartSchema.ChartEncoding] = None
        color: Optional[ChartSchema.ChartEncoding] = None

    mark: RuleChartMark
    encoding: RuleChartEncoding


class KPIChartSchema(ChartSchema):
    class KPIChartMark(BaseModel):
        type: Literal["text"] = Field(default="text")  # Dummy mark type

    class KPIChartEncoding(BaseModel):
        text: ChartSchema.ChartEncoding
        color: Optional[ChartSchema.ChartEncoding] = None

    class KPIMetadata(BaseModel):
        chart_type: Literal["kpi"] = Field(default="kpi")
        is_dummy: bool = Field(default=True)
        description: str = Field(default="KPI chart - templates will be created elsewhere")
        kpi_data: Dict[str, Any] = Field(default_factory=dict)
        vega_lite_compatible: bool = Field(default=False)
        requires_custom_template: bool = Field(default=True)

    mark: KPIChartMark
    encoding: KPIChartEncoding
    kpi_metadata: KPIMetadata


class ChartGenerationResults(BaseModel):
    reasoning: str
    chart_type: Literal[
        "line", "multi_line", "bar", "pie", "grouped_bar", "stacked_bar", "area", 
        "scatter", "heatmap", "boxplot", "histogram", "bubble", "text", "tick", "rule", "kpi", ""
    ]  # empty string for no chart
    chart_schema: Union[
        LineChartSchema,
        MultiLineChartSchema,
        BarChartSchema,
        PieChartSchema,
        GroupedBarChartSchema,
        StackedBarChartSchema,
        AreaChartSchema,
        ScatterChartSchema,
        HeatmapChartSchema,
        BoxPlotChartSchema,
        HistogramChartSchema,
        BubbleChartSchema,
        TextChartSchema,
        TickChartSchema,
        RuleChartSchema,
        Dict[str, Any]  # For empty schema
    ]


# Enhanced chart generation results with additional metadata
class EnhancedChartGenerationResults(BaseModel):
    reasoning: str
    chart_type: Literal[
        "line", "multi_line", "bar", "pie", "grouped_bar", "stacked_bar", "area", 
        "scatter", "heatmap", "boxplot", "histogram", "bubble", "text", "tick", "rule", "kpi", ""
    ]
    chart_schema: Union[
        LineChartSchema,
        MultiLineChartSchema,
        BarChartSchema,
        PieChartSchema,
        GroupedBarChartSchema,
        StackedBarChartSchema,
        AreaChartSchema,
        ScatterChartSchema,
        HeatmapChartSchema,
        BoxPlotChartSchema,
        HistogramChartSchema,
        BubbleChartSchema,
        TextChartSchema,
        TickChartSchema,
        RuleChartSchema,
        KPIChartSchema,
        Dict[str, Any]
    ]
    enhanced_metadata: Optional[Dict[str, Any]] = None
    analysis_suggestions: Optional[List[str]] = None
    alternative_charts: Optional[List[Dict[str, Any]]] = None
    success: bool = True
    error: Optional[str] = None
