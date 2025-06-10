import logging
from typing import Any, Dict, Literal, Optional, List, Union

import orjson
import pandas as pd
from langchain.agents import Tool
from pydantic import BaseModel, Field

logger = logging.getLogger("lexy-ai-service")


plotly_chart_generation_instructions = """
### INSTRUCTIONS ###

- Chart types: Scatter plot, Line chart, Bar chart, Horizontal bar chart, Pie chart, Histogram, Box plot, Heatmap, Area chart, Violin plot, Bubble chart, Sunburst chart, Treemap, Waterfall chart, Funnel chart
- You can only use the chart types provided in the instructions
- Generated chart should answer the user's question and based on the semantics of the SQL query, and the sample data, sample column values are used to help you generate the suitable chart type
- If the sample data is not suitable for visualization, you must return an empty string for the config and chart type
- If the sample data is empty, you must return an empty string for the config and chart type
- The language for the chart and reasoning must be the same language provided by the user
- Please use the current time provided by the user to generate the chart
- For Plotly charts, configure traces with appropriate data mappings (x, y, z, color, size, etc.)
- Make sure all of the fields referenced in the chart configuration are present in the column names of the data
- Use appropriate color scales and styling for better visualization
- Configure layout properties (title, axis labels, legends, etc.) based on the data and user question

### GUIDELINES TO PLOT CHART ###

1. Understanding Your Data Types
- Text (Categorical): Names or labels without a specific order (e.g., product names, regions).
- Numeric: Numerical values representing counts or measurements (e.g., sales figures, quantities).
- Date/Time: Date or time data (e.g., order dates, timestamps).
- Boolean: True/false values.

2. Chart Types and When to Use Them
- Scatter Plot
    - Use When: Showing relationship between two continuous variables.
    - Data Requirements:
        - X: One numeric field
        - Y: One numeric field
        - Color: One categorical field (optional)
        - Size: One numeric field (optional)
    - Example: Sales vs. profit by product category.

- Line Chart
    - Use When: Showing trends over time or continuous data.
    - Data Requirements:
        - X: One date/time or numeric field
        - Y: One or more numeric fields
        - Color: One categorical field (for multiple lines)
    - Example: Monthly revenue trend.

- Bar Chart
    - Use When: Comparing values across categories.
    - Data Requirements:
        - X: One categorical field
        - Y: One numeric field
        - Color: One categorical field (optional)
    - Example: Sales by region.

- Horizontal Bar Chart
    - Use When: Comparing values across categories (horizontal layout).
    - Data Requirements:
        - Same as Bar Chart
    - Example: Top 10 products by sales.

- Pie Chart
    - Use When: Showing parts of a whole.
    - Data Requirements:
        - Labels: One categorical field
        - Values: One numeric field
    - Example: Market share distribution.

- Histogram
    - Use When: Showing distribution of a continuous variable.
    - Data Requirements:
        - X: One numeric field
        - Color: One categorical field (optional)
    - Example: Age distribution of customers.

- Box Plot
    - Use When: Showing distribution and outliers.
    - Data Requirements:
        - Y: One numeric field
        - X: One categorical field (optional)
    - Example: Sales distribution by region.

- Heatmap
    - Use When: Showing correlation or density between two variables.
    - Data Requirements:
        - X: One categorical or numeric field
        - Y: One categorical or numeric field
        - Z: One numeric field (intensity)
    - Example: Sales by month and region.

- Area Chart
    - Use When: Showing trends with emphasis on volume.
    - Data Requirements:
        - Same as Line Chart
    - Example: Cumulative sales over time.

- Bubble Chart
    - Use When: Showing relationship between three variables.
    - Data Requirements:
        - X: One numeric field
        - Y: One numeric field
        - Size: One numeric field
        - Color: One categorical field (optional)
    - Example: Sales vs. profit vs. market size by region.

### EXAMPLES ###

1. Scatter Plot
- Sample Data:
[
    {"Sales": 100000, "Profit": 25000, "Region": "North"},
    {"Sales": 150000, "Profit": 30000, "Region": "South"},
    {"Sales": 120000, "Profit": 20000, "Region": "East"},
    {"Sales": 180000, "Profit": 35000, "Region": "West"}
]
- Chart Config:
{
    "chart_type": "scatter",
    "data": [
        {
            "type": "scatter",
            "mode": "markers",
            "x": "Sales",
            "y": "Profit",
            "color": "Region",
            "marker": {
                "size": 10,
                "colorscale": "viridis"
            },
            "name": "Sales vs Profit"
        }
    ],
    "layout": {
        "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
        "xaxis": {"title": "<X_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "yaxis": {"title": "<Y_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "showlegend": true
    }
}

2. Line Chart
- Sample Data:
[
    {"Date": "2023-01-01", "Sales": 100000},
    {"Date": "2023-02-01", "Sales": 120000},
    {"Date": "2023-03-01", "Sales": 110000},
    {"Date": "2023-04-01", "Sales": 140000}
]
- Chart Config:
{
    "chart_type": "line",
    "data": [
        {
            "type": "scatter",
            "mode": "lines+markers",
            "x": "Date",
            "y": "Sales",
            "line": {"width": 2},
            "marker": {"size": 6},
            "name": "Sales Trend"
        }
    ],
    "layout": {
        "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
        "xaxis": {"title": "<X_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "yaxis": {"title": "<Y_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "showlegend": true
    }
}

3. Bar Chart
- Sample Data:
[
    {"Region": "North", "Sales": 100000},
    {"Region": "South", "Sales": 150000},
    {"Region": "East", "Sales": 120000},
    {"Region": "West", "Sales": 180000}
]
- Chart Config:
{
    "chart_type": "bar",
    "data": [
        {
            "type": "bar",
            "x": "Region",
            "y": "Sales",
            "marker": {
                "color": "lightblue",
                "line": {"color": "darkblue", "width": 1}
            },
            "name": "Sales by Region"
        }
    ],
    "layout": {
        "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
        "xaxis": {"title": "<X_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "yaxis": {"title": "<Y_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "showlegend": false
    }
}

4. Pie Chart
- Sample Data:
[
    {"Product": "Product A", "Sales": 250000},
    {"Product": "Product B", "Sales": 180000},
    {"Product": "Product C", "Sales": 120000},
    {"Product": "Product D", "Sales": 90000}
]
- Chart Config:
{
    "chart_type": "pie",
    "data": [
        {
            "type": "pie",
            "labels": "Product",
            "values": "Sales",
            "textinfo": "label+percent",
            "textposition": "auto",
            "marker": {
                "colors": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"]
            },
            "name": "Sales Distribution"
        }
    ],
    "layout": {
        "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
        "showlegend": true
    }
}

5. Heatmap
- Sample Data:
[
    {"Month": "Jan", "Region": "North", "Sales": 100000},
    {"Month": "Jan", "Region": "South", "Sales": 120000},
    {"Month": "Feb", "Region": "North", "Sales": 110000},
    {"Month": "Feb", "Region": "South", "Sales": 130000}
]
- Chart Config:
{
    "chart_type": "heatmap",
    "data": [
        {
            "type": "heatmap",
            "x": "Month",
            "y": "Region", 
            "z": "Sales",
            "colorscale": "Blues",
            "showscale": true,
            "name": "Sales Heatmap"
        }
    ],
    "layout": {
        "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
        "xaxis": {"title": "<X_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "yaxis": {"title": "<Y_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

6. Box Plot
- Sample Data:
[
    {"Region": "North", "Sales": 100000},
    {"Region": "North", "Sales": 105000},
    {"Region": "North", "Sales": 95000},
    {"Region": "South", "Sales": 150000},
    {"Region": "South", "Sales": 145000},
    {"Region": "South", "Sales": 155000}
]
- Chart Config:
{
    "chart_type": "box",
    "data": [
        {
            "type": "box",
            "x": "Region",
            "y": "Sales",
            "boxpoints": "outliers",
            "name": "Sales Distribution"
        }
    ],
    "layout": {
        "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
        "xaxis": {"title": "<X_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "yaxis": {"title": "<Y_AXIS_TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "showlegend": false
    }
}
"""


class PlotlyChartDataPreprocessor:
    """Langchain tool for preprocessing data for Plotly chart generation"""
    
    def __init__(self):
        self.name = "plotly_data_preprocessor"
        self.description = "Preprocesses data for Plotly chart generation"
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to Python native types"""
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        return obj
    
    def run(
        self,
        data: Dict[str, Any],
        sample_data_count: int = 15,
        sample_column_size: int = 5,
    ) -> Dict[str, Any]:
        """Process data and return sample data, column values, and metadata"""
        try:
            columns = [
                column.get("name", "") if isinstance(column, dict) else column
                for column in data.get("columns", [])
            ]
            data_rows = data.get("data", [])

            df = pd.DataFrame(data_rows, columns=columns)
            
            # Generate sample column values
            sample_column_values = {
                col: self._convert_numpy_types(list(df[col].unique())[:sample_column_size]) 
                for col in df.columns
            }

            # Analyze column metadata for Plotly
            column_metadata = {}
            for col in df.columns:
                dtype = str(df[col].dtype)
                if pd.api.types.is_numeric_dtype(df[col]):
                    column_metadata[col] = {
                        "type": "numeric", 
                        "aggregatable": True,
                        "min": float(df[col].min()),
                        "max": float(df[col].max()),
                        "mean": float(df[col].mean())
                    }
                elif pd.api.types.is_datetime64_any_dtype(df[col]):
                    column_metadata[col] = {
                        "type": "datetime", 
                        "aggregatable": False,
                        "min": str(df[col].min()),
                        "max": str(df[col].max())
                    }
                elif dtype == 'bool':
                    column_metadata[col] = {"type": "boolean", "aggregatable": False}
                else:
                    column_metadata[col] = {
                        "type": "categorical", 
                        "aggregatable": False,
                        "unique_count": df[col].nunique(),
                        "categories": list(df[col].unique())[:10]  # Limit to first 10 categories
                    }

            # Generate sample data
            if len(df) > sample_data_count:
                sample_data = df.sample(n=sample_data_count).to_dict(orient="records")
            else:
                sample_data = df.to_dict(orient="records")
            
            # Convert numpy types in sample data
            sample_data = self._convert_numpy_types(sample_data)

            return {
                "sample_data": sample_data,
                "sample_column_values": sample_column_values,
                "column_metadata": column_metadata,
            }
        except Exception as e:
            logger.error(f"Error in data preprocessing: {e}")
            return {
                "sample_data": [],
                "sample_column_values": {},
                "column_metadata": {},
            }


class PlotlyChartGenerationPostProcessor:
    """Langchain tool for post-processing chart generation results"""
    
    def __init__(self):
        self.name = "plotly_chart_postprocessor"
        self.description = "Post-processes Plotly chart generation results"
    
    def run(
        self,
        generation_result: str,
        sample_data: list[dict],
        remove_data_from_chart_config: Optional[bool] = True,
    ) -> Dict[str, Any]:
        """Process LLM output and validate chart configuration"""
        try:
            if isinstance(generation_result, list) and generation_result:
                result_str = generation_result[0]
            else:
                result_str = generation_result
            
            parsed_result = orjson.loads(result_str)
            reasoning = parsed_result.get("reasoning", "")
            chart_type = parsed_result.get("chart_type", "")
            
            if chart_config := parsed_result.get("chart_config", {}):
                # Handle string format chart_config
                if isinstance(chart_config, str):
                    chart_config = orjson.loads(chart_config)

                # Add sample data for validation
                chart_config["sample_data"] = sample_data

                # Basic validation - check if required fields exist
                self._validate_chart_config(chart_config, sample_data)

                # Process data references in traces
                chart_config = self._process_data_references(chart_config, sample_data)

                if remove_data_from_chart_config:
                    chart_config["sample_data"] = []

                return {
                    "chart_config": chart_config,
                    "reasoning": reasoning,
                    "chart_type": chart_type,
                    "success": True
                }

            return {
                "chart_config": {},
                "reasoning": reasoning,
                "chart_type": chart_type,
                "success": False
            }
            
        except Exception as e:
            logger.exception(f"Error in post-processing: {e}")
            return {
                "chart_config": {},
                "reasoning": "",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }
    
    def _validate_chart_config(self, chart_config: dict, sample_data: list) -> bool:
        """Basic validation of chart configuration"""
        required_fields = ["data", "layout"]
        
        for field in required_fields:
            if field not in chart_config:
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Validate data traces
        if "data" in chart_config and isinstance(chart_config["data"], list):
            for trace in chart_config["data"]:
                if not isinstance(trace, dict) or "type" not in trace:
                    logger.warning("Invalid trace definition")
                    return False
        
        return True
    
    def _process_data_references(self, chart_config: dict, sample_data: list) -> dict:
        """Process data field references in chart configuration"""
        if not sample_data:
            return chart_config
        
        # Get column names from sample data
        available_columns = list(sample_data[0].keys()) if sample_data else []
        
        # Process each trace
        if "data" in chart_config:
            for trace in chart_config["data"]:
                # Convert field references to actual data arrays
                for field in ["x", "y", "z", "labels", "values", "color"]:
                    if field in trace and isinstance(trace[field], str):
                        field_name = trace[field]
                        if field_name in available_columns:
                            # Extract data for this field
                            trace[field] = [row.get(field_name) for row in sample_data]
        
        return chart_config


# Pydantic Models for Plotly Chart Configuration
class PlotlyTrace(BaseModel):
    type: str
    x: Optional[Union[str, List[Any]]] = None
    y: Optional[Union[str, List[Any]]] = None
    z: Optional[Union[str, List[List[Any]]]] = None
    labels: Optional[Union[str, List[str]]] = None
    values: Optional[Union[str, List[float]]] = None
    mode: Optional[str] = None
    name: Optional[str] = None
    marker: Optional[Dict[str, Any]] = None
    line: Optional[Dict[str, Any]] = None
    colorscale: Optional[str] = None
    showscale: Optional[bool] = None
    textinfo: Optional[str] = None
    textposition: Optional[str] = None
    boxpoints: Optional[str] = None


class PlotlyAxis(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    range: Optional[List[float]] = None
    showgrid: Optional[bool] = None
    gridcolor: Optional[str] = None


class PlotlyLayout(BaseModel):
    title: Optional[str] = None
    xaxis: Optional[PlotlyAxis] = None
    yaxis: Optional[PlotlyAxis] = None
    showlegend: Optional[bool] = None
    template: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    margin: Optional[Dict[str, int]] = None


class PlotlyChartConfig(BaseModel):
    chart_type: str
    data: List[PlotlyTrace]
    layout: PlotlyLayout
    sample_data: Optional[List[Dict[str, Any]]] = []


class PlotlyChartGenerationResults(BaseModel):
    reasoning: str
    chart_type: Literal[
        "scatter", 
        "line", 
        "bar",
        "horizontal_bar", 
        "pie",
        "histogram", 
        "box",
        "heatmap",
        "area",
        "violin",
        "bubble",
        "sunburst",
        "treemap",
        "waterfall",
        "funnel",
        ""
    ]  # empty string for no chart
    chart_config: Union[PlotlyChartConfig, Dict[str, Any]]


# Langchain Tools for Plotly Chart Generation
def create_plotly_data_preprocessor_tool() -> Tool:
    """Create Langchain tool for data preprocessing"""
    preprocessor = PlotlyChartDataPreprocessor()
    
    def preprocess_data_func(data_json: str) -> str:
        """Preprocess data for Plotly chart generation"""
        try:
            data = orjson.loads(data_json)
            result = preprocessor.run(data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in data preprocessing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="plotly_data_preprocessor",
        description="Preprocesses data for Plotly chart generation. Input should be JSON string with 'columns' and 'data' fields.",
        func=preprocess_data_func
    )


def create_plotly_chart_postprocessor_tool() -> Tool:
    """Create Langchain tool for chart post-processing"""
    postprocessor = PlotlyChartGenerationPostProcessor()
    
    def postprocess_chart_func(input_json: str) -> str:
        """Post-process Plotly chart generation results"""
        try:
            input_data = orjson.loads(input_json)
            generation_result = input_data.get("generation_result", "")
            sample_data = input_data.get("sample_data", [])
            remove_data = input_data.get("remove_data_from_chart_config", True)
            
            result = postprocessor.run(generation_result, sample_data, remove_data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in chart post-processing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="plotly_chart_postprocessor",
        description="Post-processes Plotly chart generation results. Input should be JSON with 'generation_result', 'sample_data', and 'remove_data_from_chart_config' fields.",
        func=postprocess_chart_func
    )


# Utility functions for Plotly integration
class PlotlyChartExporter:
    """Utility class to export chart configurations to Plotly-compatible formats"""
    
    @staticmethod
    def to_plotly_json(chart_config: dict) -> str:
        """Convert chart configuration to Plotly JSON format"""
        return orjson.dumps(chart_config, option=orjson.OPT_INDENT_2).decode()
    
    @staticmethod
    def to_plotly_python(chart_config: dict, data_variable: str = "df") -> str:
        """Generate Python Plotly code for the chart"""
        chart_type = chart_config.get("chart_type", "scatter")
        traces = chart_config.get("data", [])
        layout = chart_config.get("layout", {})
        
        python_code = """
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Create figure
fig = go.Figure()

"""
        
        # Add traces
        for i, trace in enumerate(traces):
            trace_type = trace.get("type", "scatter")
            
            if trace_type == "scatter":
                mode = trace.get("mode", "markers")
                python_code += f"""
# Add trace {i+1}
fig.add_trace(go.Scatter(
    x={data_variable}['{trace.get('x', 'x')}'] if isinstance('{trace.get('x', 'x')}', str) else {trace.get('x', [])},
    y={data_variable}['{trace.get('y', 'y')}'] if isinstance('{trace.get('y', 'y')}', str) else {trace.get('y', [])},
    mode='{mode}',
    name='{trace.get('name', f'Trace {i+1}')}',
"""
                if trace.get("marker"):
                    python_code += f"    marker={trace['marker']},\n"
                python_code += "))\n"
            
            elif trace_type == "bar":
                python_code += f"""
# Add bar trace {i+1}
fig.add_trace(go.Bar(
    x={data_variable}['{trace.get('x', 'x')}'] if isinstance('{trace.get('x', 'x')}', str) else {trace.get('x', [])},
    y={data_variable}['{trace.get('y', 'y')}'] if isinstance('{trace.get('y', 'y')}', str) else {trace.get('y', [])},
    name='{trace.get('name', f'Trace {i+1}')}',
"""
                if trace.get("marker"):
                    python_code += f"    marker={trace['marker']},\n"
                python_code += "))\n"
            
            elif trace_type == "pie":
                python_code += f"""
# Add pie trace {i+1}
fig.add_trace(go.Pie(
    labels={data_variable}['{trace.get('labels', 'labels')}'] if isinstance('{trace.get('labels', 'labels')}', str) else {trace.get('labels', [])},
    values={data_variable}['{trace.get('values', 'values')}'] if isinstance('{trace.get('values', 'values')}', str) else {trace.get('values', [])},
    name='{trace.get('name', f'Trace {i+1}')}',
"""
                if trace.get("textinfo"):
                    python_code += f"    textinfo='{trace['textinfo']}',\n"
                python_code += "))\n"
        
        # Add layout
        python_code += f"""
# Update layout
fig.update_layout(
    title='{layout.get('title', 'Chart')}',
"""
        
        if layout.get("xaxis"):
            xaxis = layout["xaxis"]
            python_code += f"    xaxis=dict(title='{xaxis.get('title', 'X Axis')}'),\n"
        
        if layout.get("yaxis"):
            yaxis = layout["yaxis"]
            python_code += f"    yaxis=dict(title='{yaxis.get('title', 'Y Axis')}'),\n"
        
        if "showlegend" in layout:
            python_code += f"    showlegend={str(layout['showlegend']).lower()},\n"
        
        python_code += """
)

# Show figure
fig.show()
"""
        
        return python_code
    
    @staticmethod
    def to_plotly_express(chart_config: dict, data_variable: str = "df") -> str:
        """Generate Python Plotly Express code for the chart"""
        chart_type = chart_config.get("chart_type", "scatter")
        layout = chart_config.get("layout", {})
        
        if not chart_config.get("data"):
            return "# No data traces found"
        
        trace = chart_config["data"][0]  # Use first trace for Express
        
        express_code = """
import plotly.express as px
import pandas as pd

"""
        
        if chart_type == "scatter":
            express_code += f"""
# Create scatter plot
fig = px.scatter(
    {data_variable},
    x='{trace.get('x', 'x')}',
    y='{trace.get('y', 'y')}',
    title='{layout.get('title', 'Scatter Plot')}',
"""
            if trace.get("color"):
                express_code += f"    color='{trace.get('color')}',\n"
            express_code += ")\n"
        
        elif chart_type == "line":
            express_code += f"""
# Create line plot
fig = px.line(
    {data_variable},
    x='{trace.get('x', 'x')}',
    y='{trace.get('y', 'y')}',
    title='{layout.get('title', 'Line Plot')}',
)\n"""
        
        elif chart_type == "bar":
            express_code += f"""
# Create bar plot
fig = px.bar(
    {data_variable},
    x='{trace.get('x', 'x')}',
    y='{trace.get('y', 'y')}',
    title='{layout.get('title', 'Bar Plot')}',
)\n"""
        
        elif chart_type == "pie":
            express_code += f"""
# Create pie chart
fig = px.pie(
    {data_variable},
    names='{trace.get('labels', 'labels')}',
    values='{trace.get('values', 'values')}',
    title='{layout.get('title', 'Pie Chart')}',
)\n"""
        
        elif chart_type == "histogram":
            express_code += f"""
# Create histogram
fig = px.histogram(
    {data_variable},
    x='{trace.get('x', 'x')}',
    title='{layout.get('title', 'Histogram')}',
)\n"""
        
        elif chart_type == "box":
            express_code += f"""
# Create box plot
fig = px.box(
    {data_variable},
    y='{trace.get('y', 'y')}',
    title='{layout.get('title', 'Box Plot')}',
"""
            if trace.get("x"):
                express_code += f"    x='{trace.get('x')}',\n"
            express_code += ")\n"
        
        express_code += "\n# Show figure\nfig.show()\n"
        
        return express_code
    
    @staticmethod
    def to_javascript(chart_config: dict, div_id: str = "chart-div") -> str:
        """Generate JavaScript Plotly code for the chart"""
        js_code = f"""
// Plotly chart configuration
var data = {orjson.dumps(chart_config.get('data', []), option=orjson.OPT_INDENT_2).decode()};
var layout = {orjson.dumps(chart_config.get('layout', {}), option=orjson.OPT_INDENT_2).decode()};

// Create the plot
Plotly.newPlot('{div_id}', data, layout, {{responsive: true}});
"""
        return js_code
    
    @staticmethod
    def get_chart_summary(chart_config: dict) -> Dict[str, Any]:
        """Get a summary of the chart configuration"""
        summary = {
            "chart_type": chart_config.get("chart_type", "unknown"),
            "title": chart_config.get("layout", {}).get("title", "Untitled Chart"),
            "num_traces": len(chart_config.get("data", [])),
            "fields_used": [],
            "trace_types": [],
            "has_legend": chart_config.get("layout", {}).get("showlegend", True),
            "dimensions": {}
        }
        
        # Analyze traces
        for trace in chart_config.get("data", []):
            trace_type = trace.get("type", "unknown")
            summary["trace_types"].append(trace_type)
            
            # Collect field references
            for field in ["x", "y", "z", "labels", "values", "color"]:
                if field in trace and isinstance(trace[field], str):
                    summary["fields_used"].append(trace[field])
        
        # Get layout dimensions
        layout = chart_config.get("layout", {})
        if layout.get("width"):
            summary["dimensions"]["width"] = layout["width"]
        if layout.get("height"):
            summary["dimensions"]["height"] = layout["height"]
        
        # Remove duplicates
        summary["fields_used"] = list(set(summary["fields_used"]))
        summary["trace_types"] = list(set(summary["trace_types"]))
        
        return summary