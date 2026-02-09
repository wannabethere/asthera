import logging
from typing import Any, Dict, Literal, Optional, List, Union

import orjson
import pandas as pd
# Import Tool using modern LangChain paths
try:
    from langchain_core.tools import Tool
except ImportError:
    try:
        from langchain.tools import Tool
    except ImportError:
        from langchain.agents import Tool
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel, Field
from app.agents.nodes.sql.utils.chart_models import ChartGenerationResults

logger = logging.getLogger("lexy-ai-service")


chart_generation_instructions = """
### INSTRUCTIONS ###

- Chart types: Bar chart, Line chart, Multi line chart, Area chart, Pie chart, Stacked bar chart, Grouped bar chart
- You can only use the chart types provided in the instructions
- Generated chart should answer the user's question and based on the semantics of the SQL query, and the sample data, sample column values are used to help you generate the suitable chart type
- If the sample data is not suitable for visualization, you must return an empty string for the schema and chart type
- If the sample data is empty, you must return an empty string for the schema and chart type
- The language for the chart and reasoning must be the same language provided by the user
- Please use the current time provided by the user to generate the chart
- In order to generate the grouped bar chart, you need to follow the given instructions:
    - Disable Stacking: Add "stack": null to the y-encoding.
    - Use xOffset for subcategories to group bars.
    - If you have separate columns for different metrics (e.g., "Assigned_Trainings" and "Completed_Trainings"), use a "transform" section with "fold" to reshape the data.
    - The xOffset field must be categorical (nominal), not quantitative.
    - Example: For data with "Assigned" and "Completed" columns, use transform to create "Status" and "Count" fields.
- In order to generate the pie chart, you need to follow the given instructions:
    - Add {"type": "arc"} to the mark section.
    - Add "theta" encoding to the encoding section.
    - Add "color" encoding to the encoding section.
    - Don't add "innerRadius" to the mark section.
- If the x-axis of the chart is a temporal field, the time unit should be the same as the question user asked.
    - For yearly question, the time unit should be "year".
    - For monthly question, the time unit should be "yearmonth".
    - For weekly question, the time unit should be "yearmonthdate".
    - For daily question, the time unit should be "yearmonthdate".
    - Default time unit is "yearmonth".
- For each axis, generate the corresponding human-readable title based on the language provided by the user.
- Make sure all of the fields(x, y, xOffset, color, etc.) in the encoding section of the chart schema are present in the column names of the data.

### GUIDELINES TO PLOT CHART ###

1. Understanding Your Data Types
- Nominal (Categorical): Names or labels without a specific order (e.g., types of fruits, countries).
- Ordinal: Categorical data with a meaningful order but no fixed intervals (e.g., rankings, satisfaction levels).
- Quantitative: Numerical values representing counts or measurements (e.g., sales figures, temperatures).
- Temporal: Date or time data (e.g., timestamps, dates).

2. Chart Types and When to Use Them
- Bar Chart
    - Use When: Comparing quantities across different categories.
    - Data Requirements:
        - One categorical variable (x-axis).
        - One quantitative variable (y-axis).
    - Example: Comparing sales numbers for different product categories.
- Grouped Bar Chart
    - Use When: Comparing sub-categories within main categories.
    - Data Requirements:
        - Two categorical variables (x-axis grouped by one, color-coded by another).
        - One quantitative variable (y-axis).
        - Example: Sales numbers for different products across various regions.
- Line Chart
    - Use When: Displaying trends over continuous data, especially time.
    - Data Requirements:
        - One temporal or ordinal variable (x-axis).
        - One quantitative variable (y-axis).
    - Example: Tracking monthly revenue over a year.
- Multi Line Chart
    - Use When: Displaying trends over continuous data, especially time.
    - Data Requirements:
        - One temporal or ordinal variable (x-axis).
        - Two or more quantitative variables (y-axis and color).
    - Implementation Notes:
        - Uses `transform` with `fold` to combine multiple metrics into a single series
        - The folded metrics are distinguished using the color encoding
    - Example: Tracking monthly click rate and read rate over a year.
- Area Chart
    - Use When: Similar to line charts but emphasizing the volume of change over time.
    - Data Requirements:
        - Same as Line Chart.
    - Example: Visualizing cumulative rainfall over months.
- Pie Chart
    - Use When: Showing parts of a whole as percentages.
    - Data Requirements:
        - One categorical variable.
        - One quantitative variable representing proportions.
    - Example: Market share distribution among companies.
- Stacked Bar Chart
    - Use When: Showing composition and comparison across categories.
    - Data Requirements: Same as grouped bar chart.
    - Example: Sales by region and product type.
- Guidelines for Selecting Chart Types
    - Comparing Categories:
        - Bar Chart: Best for simple comparisons across categories.
        - Grouped Bar Chart: Use when you have sub-categories.
        - Stacked Bar Chart: Use to show composition within categories.
    - Showing Trends Over Time:
        - Line Chart: Ideal for continuous data over time.
        - Area Chart: Use when you want to emphasize volume or total value over time.
    - Displaying Proportions:
        - Pie Chart: Use for simple compositions at a single point in time.
        - Stacked Bar Chart (100%): Use for comparing compositions across multiple categories.
    
### EXAMPLES ###

1. Bar Chart
- Sample Data:
 [
    {"Region": "North", "Sales": 100},
    {"Region": "South", "Sales": 200},
    {"Region": "East", "Sales": 300},
    {"Region": "West", "Sales": 400}
]
- Chart Schema:
{
    "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>,
    "mark": {"type": "bar"},
    "encoding": {
        "x": {"field": "Region", "type": "nominal", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>},
        "y": {"field": "Sales", "type": "quantitative", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>},
        "color": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}
2. Line Chart
- Sample Data:
[
    {"Date": "2022-01-01", "Sales": 100},
    {"Date": "2022-01-02", "Sales": 200},
    {"Date": "2022-01-03", "Sales": 300},
    {"Date": "2022-01-04", "Sales": 400}
]
- Chart Schema:
{
    "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>,
    "mark": {"type": "line"},
    "encoding": {
        "x": {"field": "Date", "type": "temporal", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>},
        "y": {"field": "Sales", "type": "quantitative", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>}
    }
}
3. Pie Chart
- Sample Data:
[
    {"Company": "Company A", "Market Share": 0.4},
    {"Company": "Company B", "Market Share": 0.3},
    {"Company": "Company C", "Market Share": 0.2},
    {"Company": "Company D", "Market Share": 0.1}
]
- Chart Schema:
{
    "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>,
    "mark": {"type": "arc"},
    "encoding": {
        "theta": {"field": "Market Share", "type": "quantitative"},
        "color": {"field": "Company", "type": "nominal", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>}
    }
}
4. Area Chart
- Sample Data:
[
    {"Date": "2022-01-01", "Sales": 100},
    {"Date": "2022-01-02", "Sales": 200},
    {"Date": "2022-01-03", "Sales": 300},
    {"Date": "2022-01-04", "Sales": 400}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "area"},
    "encoding": {
        "x": {"field": "Date", "type": "temporal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}
5. Stacked Bar Chart
- Sample Data:
[
    {"Region": "North", "Product": "A", "Sales": 100},
    {"Region": "North", "Product": "B", "Sales": 150},
    {"Region": "South", "Product": "A", "Sales": 200},
    {"Region": "South", "Product": "B", "Sales": 250},
    {"Region": "East", "Product": "A", "Sales": 300},
    {"Region": "East", "Product": "B", "Sales": 350},
    {"Region": "West", "Product": "A", "Sales": 400},
    {"Region": "West", "Product": "B", "Sales": 450}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "bar"},
    "encoding": {
        "x": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "stack": "zero"},
        "color": {"field": "Product", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}
6. Grouped Bar Chart
- Sample Data (with separate columns):
[
    {"Region": "North", "Assigned": 100, "Completed": 80},
    {"Region": "South", "Assigned": 150, "Completed": 120},
    {"Region": "East", "Assigned": 200, "Completed": 180},
    {"Region": "West", "Assigned": 250, "Completed": 220}
]
- Chart Schema (using transform to reshape data):
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "bar"},
    "transform": [
        {
            "fold": ["Assigned", "Completed"],
            "as": ["Status", "Count"]
        }
    ],
    "encoding": {
        "x": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Count", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "stack": null},
        "xOffset": {"field": "Status", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "color": {"field": "Status", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

- Sample Data (already in long format):
[
    {"Region": "North", "Product": "A", "Sales": 100},
    {"Region": "North", "Product": "B", "Sales": 150},
    {"Region": "South", "Product": "A", "Sales": 200},
    {"Region": "South", "Product": "B", "Sales": 250},
    {"Region": "East", "Product": "A", "Sales": 300},
    {"Region": "East", "Product": "B", "Sales": 350},
    {"Region": "West", "Product": "A", "Sales": 400},
    {"Region": "West", "Product": "B", "Sales": 450}
]
- Chart Schema (for long format data):
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "bar"},
    "encoding": {
        "x": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "stack": null},
        "xOffset": {"field": "Product", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "color": {"field": "Product", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}
7. Multi Line Chart
- Sample Data:
[
    {"Date": "2022-01-01", "readCount": 100, "clickCount": 10},
    {"Date": "2022-01-02", "readCount": 200, "clickCount": 30},
    {"Date": "2022-01-03", "readCount": 300, "clickCount": 20},
    {"Date": "2022-01-04", "readCount": 400, "clickCount": 40}
]
- Chart Schema:
{
    "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>,
    "mark": {"type": "line"},
    "transform": [
        {
        "fold": ["readCount", "clickCount"],
        "as": ["Metric", "Value"]
        }
    ],
    "encoding": {
        "x": {"field": "Date", "type": "temporal", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>},
        "y": {"field": "Value", "type": "quantitative", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>},
        "color": {"field": "Metric", "type": "nominal", "title": <TITLE_IN_LANGUAGE_PROVIDED_BY_USER>}
    }
}
"""


class ChartDataPreprocessor:
    """Langchain tool for preprocessing data for Vega-Lite chart generation"""
    
    def __init__(self):
        self.name = "chart_data_preprocessor"
        self.description = "Preprocesses data for Vega-Lite chart generation"
    
    def run(
        self,
        data: Dict[str, Any],
        sample_data_count: int = 15,
        sample_column_size: int = 5,
    ) -> Dict[str, Any]:
        """Process data and return sample data and column values"""
        try:
            columns = [
                column.get("name", "") if isinstance(column, dict) else column
                for column in data.get("columns", [])
            ]
            data_rows = data.get("data", [])

            df = pd.DataFrame(data_rows, columns=columns)
            sample_column_values = {
                col: list(df[col].unique())[:sample_column_size] for col in df.columns
            }

            if len(df) > sample_data_count:
                sample_data = df.sample(n=sample_data_count).to_dict(orient="records")
            else:
                sample_data = df.to_dict(orient="records")

            return {
                "sample_data": sample_data,
                "sample_column_values": sample_column_values,
            }
        except Exception as e:
            logger.error(f"Error in data preprocessing: {e}")
            return {
                "sample_data": [],
                "sample_column_values": {},
            }


class ChartGenerationPostProcessor:
    """Langchain tool for post-processing Vega-Lite chart generation results"""
    
    def __init__(self):
        self.name = "chart_generation_postprocessor"
        self.description = "Post-processes Vega-Lite chart generation results"
    
    def run(
        self,
        generation_result: str,
        vega_schema: Dict[str, Any],
        sample_data: list[dict],
        remove_data_from_chart_schema: Optional[bool] = True,
    ) -> Dict[str, Any]:
        """Process LLM output and validate Vega-Lite schema"""
        
        if isinstance(generation_result, list) and generation_result:
            result_str = generation_result[0]
        else:
            result_str = generation_result
        
        logger.info(f"Post-processor input: {result_str}")
        
        parsed_result = orjson.loads(result_str)
        logger.info(f"Parsed result: {parsed_result}")
        
        reasoning = parsed_result.get("reasoning", "")
        chart_type = parsed_result.get("chart_type", "")
        chart_schema = parsed_result.get("chart_schema", {})
        
        logger.info(f"Extracted chart_schema: {chart_schema}")
        logger.info(f"Chart schema type: {type(chart_schema)}")
        
        if chart_schema:
            # Handle string format chart_schema
            if isinstance(chart_schema, str):
                logger.info("Chart schema is string, parsing...")
                chart_schema = orjson.loads(chart_schema)

            # Fix common Vega-Lite configuration errors
            chart_schema = self._fix_common_vega_lite_errors(chart_schema, sample_data)

            chart_schema["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"
            
            # Only set data if it doesn't already exist in the chart schema
            if "data" not in chart_schema:
                chart_schema["data"] = {"values": sample_data}
            else:
                # Ensure the data structure is correct
                if "values" not in chart_schema["data"]:
                    chart_schema["data"]["values"] = sample_data

            # Validate against Vega-Lite schema
            try:
                validate(chart_schema, schema=vega_schema)
                logger.info("Schema validation passed")
            except Exception as validation_error:
                logger.warning(f"Schema validation failed: {validation_error}")
                # Continue anyway, don't fail the entire process

            if remove_data_from_chart_schema:
                chart_schema["data"]["values"] = []

            result = {
                "chart_schema": chart_schema,
                "reasoning": reasoning,
                "chart_type": chart_type,
                "success": True
            }
            logger.info(f"Post-processor success result: {result}")
            return result

        logger.warning("No chart_schema found in parsed result")
        result = {
            "chart_schema": {},
            "reasoning": reasoning,
            "chart_type": chart_type,
            "success": False
        }
        logger.info(f"Post-processor failure result: {result}")
        return result
    
    def _fix_common_vega_lite_errors(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fix common Vega-Lite configuration errors"""
        try:
            encoding = chart_schema.get("encoding", {})
            
            # Fix 0: Clean up invalid nested structures and comments
            self._clean_invalid_structures(chart_schema)
            
            # Fix 1: Check if xOffset is used with quantitative data (should be categorical)
            if "xOffset" in encoding:
                xoffset_field = encoding["xOffset"].get("field", "")
                xoffset_type = encoding["xOffset"].get("type", "")
                
                # Check if the field exists in sample data and is quantitative
                if sample_data and xoffset_field:
                    sample_values = [row.get(xoffset_field) for row in sample_data if xoffset_field in row]
                    if sample_values and all(isinstance(val, (int, float)) or str(val).replace('.', '').replace('-', '').isdigit() for val in sample_values):
                        logger.warning(f"xOffset field '{xoffset_field}' appears to be quantitative, should be categorical")
                        
                        # Check if we have separate columns that could be folded
                        columns = list(sample_data[0].keys()) if sample_data else []
                        numeric_columns = []
                        categorical_columns = []
                        
                        for col in columns:
                            if col != encoding.get("x", {}).get("field", ""):
                                sample_values = [row.get(col) for row in sample_data if col in row]
                                if sample_values and all(isinstance(val, (int, float)) or str(val).replace('.', '').replace('-', '').isdigit() for val in sample_values):
                                    numeric_columns.append(col)
                                else:
                                    categorical_columns.append(col)
                        
                        # If we have multiple numeric columns, suggest using transform
                        if len(numeric_columns) >= 2:
                            logger.info(f"Detected multiple numeric columns: {numeric_columns}. Suggesting transform for grouped bar chart.")
                            
                            # Create a transform to fold the numeric columns
                            chart_schema["transform"] = [{
                                "fold": numeric_columns,
                                "as": ["Status", "Count"]
                            }]
                            
                            # Update encoding to use the transformed data
                            encoding["xOffset"] = {"field": "Status", "type": "nominal"}
                            encoding["y"] = {"field": "Count", "type": "quantitative"}
                            encoding["color"] = {"field": "Status", "type": "nominal"}
                            
                            # Add stack: null to disable stacking
                            if "y" in encoding:
                                encoding["y"]["stack"] = None
            
            # Fix 1.5: Preserve existing transforms and ensure encoding matches transformed data
            if "transform" in chart_schema:
                transform = chart_schema["transform"]
                if transform and isinstance(transform, list):
                    for t in transform:
                        if isinstance(t, dict) and t.get("fold"):
                            fold_columns = t.get("fold", [])
                            as_columns = t.get("as", ["Status", "Count"])
                            
                            if len(as_columns) >= 2:
                                status_field = as_columns[0]
                                count_field = as_columns[1]
                                
                                # Update encoding to use transformed fields
                                if "xOffset" in encoding:
                                    encoding["xOffset"]["field"] = status_field
                                    encoding["xOffset"]["type"] = "nominal"
                                
                                if "y" in encoding:
                                    encoding["y"]["field"] = count_field
                                    encoding["y"]["type"] = "quantitative"
                                
                                if "color" in encoding:
                                    encoding["color"]["field"] = status_field
                                    encoding["color"]["type"] = "nominal"
                                
                                logger.info(f"Updated encoding to use transformed fields: {status_field}, {count_field}")
                                
                                # Skip the automatic transform creation since we already have one
                                return chart_schema
            
            # Fix 2: Ensure stack: null is set for grouped bar charts
            if "xOffset" in encoding and "y" in encoding:
                if "stack" not in encoding["y"]:
                    encoding["y"]["stack"] = None
            
            # Fix 3: Ensure proper data types
            for channel in ["x", "y", "color", "xOffset"]:
                if channel in encoding:
                    field = encoding[channel].get("field", "")
                    if field and sample_data:
                        sample_values = [row.get(field) for row in sample_data if field in row]
                        if sample_values:
                            # Check if values are numeric
                            is_numeric = all(isinstance(val, (int, float)) or str(val).replace('.', '').replace('-', '').isdigit() for val in sample_values)
                            
                            # Set appropriate type if not already set
                            if "type" not in encoding[channel]:
                                if is_numeric:
                                    encoding[channel]["type"] = "quantitative"
                                else:
                                    encoding[channel]["type"] = "nominal"
            
            # Fix 4: Clean up color scales and remove invalid properties
            self._fix_color_scales(encoding)
            
            return chart_schema
        except Exception as e:
            logger.warning(f"Error fixing Vega-Lite errors: {e}")
            return chart_schema
    
    def _clean_invalid_structures(self, chart_schema: Dict[str, Any]):
        """Clean up invalid nested structures in the chart schema"""
        try:
            encoding = chart_schema.get("encoding", {})
            
            # Remove invalid nested xOffset within other encodings
            for channel in ["x", "y", "color"]:
                if channel in encoding and isinstance(encoding[channel], dict):
                    if "xOffset" in encoding[channel]:
                        logger.warning(f"Removing invalid nested xOffset from {channel} encoding")
                        del encoding[channel]["xOffset"]
            
            # Remove any other invalid nested structures
            for channel in list(encoding.keys()):
                if channel not in ["x", "y", "color", "xOffset", "theta", "size", "shape", "text", "tooltip"]:
                    logger.warning(f"Removing invalid encoding channel: {channel}")
                    del encoding[channel]
            
        except Exception as e:
            logger.warning(f"Error cleaning invalid structures: {e}")
    
    def _fix_color_scales(self, encoding: Dict[str, Any]):
        """Fix invalid color scale configurations"""
        try:
            if "color" in encoding and isinstance(encoding["color"], dict):
                color_encoding = encoding["color"]
                
                # Remove invalid scale configurations
                if "scale" in color_encoding:
                    scale = color_encoding["scale"]
                    
                    # Remove comments and invalid properties
                    if isinstance(scale, dict):
                        # Remove any properties that might contain comments or invalid syntax
                        invalid_keys = []
                        for key, value in scale.items():
                            if isinstance(value, str) and ("//" in value or "/*" in value):
                                invalid_keys.append(key)
                        
                        for key in invalid_keys:
                            del scale[key]
                        
                        # If scale is empty after cleaning, remove it entirely
                        if not scale:
                            del color_encoding["scale"]
                
                # Ensure color encoding has required fields
                if "field" not in color_encoding:
                    logger.warning("Color encoding missing field, removing color encoding")
                    del encoding["color"]
                elif "type" not in color_encoding:
                    # Set default type based on field name
                    color_encoding["type"] = "nominal"
                    
        except Exception as e:
            logger.warning(f"Error fixing color scales: {e}")


# Langchain Tools for Vega-Lite Chart Generation
def create_chart_data_preprocessor_tool() -> Tool:
    """Create Langchain tool for data preprocessing"""
    preprocessor = ChartDataPreprocessor()
    
    def preprocess_data_func(data_json: str) -> str:
        """Preprocess data for Vega-Lite chart generation"""
        try:
            data = orjson.loads(data_json)
            result = preprocessor.run(data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in data preprocessing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="chart_data_preprocessor",
        description="Preprocesses data for Vega-Lite chart generation. Input should be JSON string with 'columns' and 'data' fields.",
        func=preprocess_data_func
    )


def create_chart_postprocessor_tool() -> Tool:
    """Create Langchain tool for chart post-processing"""
    postprocessor = ChartGenerationPostProcessor()
    
    def postprocess_chart_func(input_json: str) -> str:
        """Post-process Vega-Lite chart generation results"""
        try:
            input_data = orjson.loads(input_json)
            generation_result = input_data.get("generation_result", "")
            vega_schema = input_data.get("vega_schema", {})
            sample_data = input_data.get("sample_data", [])
            remove_data = input_data.get("remove_data_from_chart_schema", True)
            
            result = postprocessor.run(generation_result, vega_schema, sample_data, remove_data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in chart post-processing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="chart_postprocessor",
        description="Post-processes Vega-Lite chart generation results. Input should be JSON with 'generation_result', 'vega_schema', 'sample_data', and 'remove_data_from_chart_schema' fields.",
        func=postprocess_chart_func
    )


# Utility functions for Vega-Lite integration
class VegaLiteChartExporter:
    """Utility class to export Vega-Lite chart configurations"""
    
    @staticmethod
    def to_vega_lite_json(chart_schema: dict) -> str:
        """Convert chart schema to Vega-Lite JSON format"""
        return orjson.dumps(chart_schema, option=orjson.OPT_INDENT_2).decode()
    
    @staticmethod
    def to_observable_notebook(chart_schema: dict, data: List[Dict[str, Any]]) -> str:
        """Generate Observable notebook code for the chart"""
        chart_with_data = chart_schema.copy()
        chart_with_data["data"] = {"values": data}
        
        notebook_code = f"""
// Vega-Lite Chart
vl = require("@observablehq/vega-lite")

chart = vl.render({orjson.dumps(chart_with_data, option=orjson.OPT_INDENT_2).decode()})
"""
        return notebook_code
    
    @staticmethod
    def to_altair_python(chart_schema: dict, data_variable: str = "data") -> str:
        """Generate Python Altair code for the chart"""
        mark_type = chart_schema.get("mark", {}).get("type", "bar")
        encoding = chart_schema.get("encoding", {})
        
        altair_code = f"""
import altair as alt
import pandas as pd

# Create the chart
chart = alt.Chart({data_variable}).mark_{mark_type}()"""
        
        if encoding:
            encoding_parts = []
            for channel, enc in encoding.items():
                if isinstance(enc, dict) and "field" in enc:
                    field = enc["field"]
                    data_type = enc.get("type", "nominal")
                    title = enc.get("title", field)
                    
                    if channel == "x":
                        encoding_parts.append(f"x=alt.X('{field}:{data_type[0].upper()}', title='{title}')")
                    elif channel == "y":
                        encoding_parts.append(f"y=alt.Y('{field}:{data_type[0].upper()}', title='{title}')")
                    elif channel == "color":
                        encoding_parts.append(f"color=alt.Color('{field}:{data_type[0].upper()}', title='{title}')")
                    elif channel == "theta":
                        encoding_parts.append(f"theta=alt.Theta('{field}:{data_type[0].upper()}')")
            
            if encoding_parts:
                altair_code += ".encode(\n    " + ",\n    ".join(encoding_parts) + "\n)"
        
        if "title" in chart_schema:
            altair_code += f".properties(title='{chart_schema['title']}')"
        
        return altair_code
    
    @staticmethod
    def get_chart_summary(chart_schema: dict) -> Dict[str, Any]:
        """Get a summary of the chart configuration"""
        summary = {
            "chart_type": chart_schema.get("mark", {}).get("type", "unknown"),
            "title": chart_schema.get("title", "Untitled Chart"),
            "fields_used": [],
            "data_types": {},
            "has_temporal_data": False,
            "has_transforms": "transform" in chart_schema
        }
        
        encoding = chart_schema.get("encoding", {})
        for channel, enc in encoding.items():
            if isinstance(enc, dict) and "field" in enc:
                field_name = enc["field"]
                data_type = enc.get("type", "nominal")
                
                summary["fields_used"].append(field_name)
                summary["data_types"][field_name] = data_type
                
                if data_type == "temporal":
                    summary["has_temporal_data"] = True
        
        return summary


def fix_and_prepare_chart_schema(
    chart_schema: Dict[str, Any], 
    data: List[Dict[str, Any]], 
    remove_data_from_schema: bool = False
) -> Dict[str, Any]:
    """
    Fix common Vega-Lite configuration errors and prepare chart schema with data.
    This function can be used to bypass the post-processing step and directly
    fix and prepare chart schemas.
    
    Args:
        chart_schema: The existing chart schema to fix
        data: The data to include in the chart
        remove_data_from_schema: Whether to remove data from the final schema
    
    Returns:
        Dict containing the fixed chart schema and metadata
    """
    try:
        # Create a copy to avoid modifying the original
        fixed_schema = chart_schema.copy()
        
        # Ensure $schema is set
        fixed_schema["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"
        
        # Add data
        fixed_schema["data"] = {"values": data}
        
        # Fix common errors using the same logic as the post-processor
        post_processor = ChartGenerationPostProcessor()
        fixed_schema = post_processor._fix_common_vega_lite_errors(fixed_schema, data)
        
        # Remove data if requested
        if remove_data_from_schema:
            fixed_schema["data"]["values"] = []
        
        # Determine chart type from the schema
        chart_type = ""
        mark_type = fixed_schema.get("mark", {}).get("type", "")
        encoding = fixed_schema.get("encoding", {})
        
        if mark_type == "bar":
            if "xOffset" in encoding:
                chart_type = "grouped_bar"
            elif encoding.get("y", {}).get("stack") == "zero":
                chart_type = "stacked_bar"
            else:
                chart_type = "bar"
        elif mark_type == "line":
            if "color" in encoding and "transform" in fixed_schema:
                chart_type = "multi_line"
            else:
                chart_type = "line"
        elif mark_type == "arc":
            chart_type = "pie"
        elif mark_type == "area":
            chart_type = "area"
        
        return {
            "chart_schema": fixed_schema,
            "chart_type": chart_type,
            "reasoning": f"Chart schema fixed and prepared with {len(data)} data points",
            "success": True,
            "data_count": len(data)
        }
        
    except Exception as e:
        logger.error(f"Error fixing chart schema: {e}")
        return {
            "chart_schema": chart_schema,
            "chart_type": "",
            "reasoning": f"Error fixing chart schema: {str(e)}",
            "success": False,
            "error": str(e)
        }


def create_chart_from_existing_schema(
    chart_schema: Dict[str, Any],
    data: List[Dict[str, Any]],
    language: str = "English"
) -> Dict[str, Any]:
    """
    Create a chart result from an existing chart schema and data.
    This bypasses the LLM generation and post-processing steps.
    
    Args:
        chart_schema: The existing chart schema
        data: The data to visualize
        language: The language for titles and labels
    
    Returns:
        Dict containing the chart result
    """
    try:
        # Fix and prepare the chart schema
        result = fix_and_prepare_chart_schema(chart_schema, data, remove_data_from_schema=False)
        
        # Add language-specific metadata
        result["language"] = language
        result["chart_format"] = "vega_lite"
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating chart from existing schema: {e}")
        return {
            "chart_schema": chart_schema,
            "chart_type": "",
            "reasoning": f"Error creating chart: {str(e)}",
            "success": False,
            "error": str(e)
        }


class ChartExecutionConfig:
    """Configuration for chart execution with pagination"""
    
    def __init__(
        self,
        page_size: int = 1000,
        max_rows: Optional[int] = None,
        enable_pagination: bool = True,
        sort_by: Optional[str] = None,
        sort_order: str = "ASC",
        timeout_seconds: int = 30,
        cache_results: bool = False,  # Disabled to fix empty results issue
        cache_ttl_seconds: int = 300
    ):
        self.page_size = page_size
        self.max_rows = max_rows
        self.enable_pagination = enable_pagination
        self.sort_by = sort_by
        self.sort_order = sort_order.upper()
        self.timeout_seconds = timeout_seconds
        self.cache_results = cache_results
        self.cache_ttl_seconds = cache_ttl_seconds


class ChartExecutor:
    """Execute chart schemas with data fetched from database"""
    
    def __init__(self, db_engine=None):
        self.db_engine = db_engine
        self.cache = {}  # Simple in-memory cache
    
    async def execute_chart(
        self,
        chart_schema: Dict[str, Any],
        sql_query: str,
        config: Optional[ChartExecutionConfig] = None,
        db_engine=None
    ) -> Dict[str, Any]:
        """
        Execute a chart schema with data fetched from database
        
        Args:
            chart_schema: Vega-Lite chart schema
            sql_query: SQL query to fetch data
            config: Execution configuration for pagination and limits
            db_engine: Database engine (overrides instance engine)
        
        Returns:
            Dict containing executed chart schema and metadata
        """
        try:
            # Use provided engine or instance engine
            engine = db_engine or self.db_engine
            if not engine:
                raise ValueError("Database engine is required")
            
            # Use default config if none provided
            if config is None:
                config = ChartExecutionConfig()
            
            # Check cache first
            cache_key = self._generate_cache_key(sql_query, config)
            if config.cache_results and cache_key in self.cache:
                cached_result = self.cache[cache_key]
                if self._is_cache_valid(cached_result, config.cache_ttl_seconds):
                    logger.info("Using cached chart execution result")
                    return cached_result
            
            # Fetch data from database
            data = await self._fetch_data(engine, sql_query, config)
            
            # Execute chart with fetched data
            result = self._execute_chart_with_data(chart_schema, data, config)
            
            # Cache result if enabled
            if config.cache_results:
                result["cached_at"] = pd.Timestamp.now().isoformat()
                self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing chart: {e}")
            return {
                "success": False,
                "error": str(e),
                "chart_schema": chart_schema,
                "data_count": 0
            }
    
    async def _fetch_data(
        self,
        engine,
        sql_query: str,
        config: ChartExecutionConfig
    ) -> List[Dict[str, Any]]:
        """Fetch data from database with pagination support"""
        try:
            # Check if SQL already has LIMIT clause - preserve it if present
            from app.core.engine import extract_limit_value
            original_limit = extract_limit_value(sql_query)
            
            # Modify SQL for pagination if enabled
            if config.enable_pagination and config.max_rows:
                # Only add LIMIT if SQL doesn't already have one
                if original_limit is None:
                    # No LIMIT in SQL, add one based on max_rows
                    sql_query += f" LIMIT {config.max_rows}"
                    effective_limit = config.max_rows
                    logger.info(f"No LIMIT in SQL, adding LIMIT {config.max_rows}")
                else:
                    # SQL already has LIMIT, preserve it (don't replace)
                    effective_limit = original_limit
                    logger.info(f"SQL already has LIMIT {original_limit}, preserving it (not replacing with max_rows {config.max_rows})")
            else:
                # Pagination not enabled, use original limit if present
                effective_limit = original_limit
            
            # Add sorting if specified
            if config.sort_by and "ORDER BY" not in sql_query.upper():
                sql_query += f" ORDER BY {config.sort_by} {config.sort_order}"
            
            logger.info(f"Executing SQL query: {sql_query}")
            
            # Always use execute_sql method since PandasEngine is a wrapper around other engines
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # Don't pass limit parameter if SQL already has LIMIT - let the SQL LIMIT be respected
                # Only pass limit if we added it ourselves or if no LIMIT in SQL
                limit_param = None if original_limit is not None else effective_limit
                success, result = await engine.execute_sql(
                    sql_query,
                    session,
                    dry_run=False,
                    limit=limit_param
                )
                
                if success and result and "data" in result:
                    data = result["data"]
                    logger.info(f"Fetched {len(data)} rows from database")
                    return data
                else:
                    error_msg = result.get("error", "Unknown error") if result else "No result returned"
                    logger.error(f"Database execution failed: {error_msg}")
                    raise Exception(f"Failed to execute query: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise
    
    def _execute_chart_with_data(
        self,
        chart_schema: Dict[str, Any],
        data: List[Dict[str, Any]],
        config: ChartExecutionConfig
    ) -> Dict[str, Any]:
        """Execute chart schema with provided data"""
        try:
            # Create a copy of the chart schema
            executed_schema = chart_schema.copy()
            
            # Add data to the schema
            executed_schema["data"] = {"values": data}
            
            # Create result without validation
            result = {
                "success": True,
                "chart_schema": executed_schema,
                "data_count": len(data),
                "execution_config": {
                    "page_size": config.page_size,
                    "max_rows": config.max_rows,
                    "enable_pagination": config.enable_pagination,
                    "sort_by": config.sort_by,
                    "sort_order": config.sort_order
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing chart with data: {e}")
            return {
                "success": False,
                "error": str(e),
                "chart_schema": chart_schema,
                "data_count": len(data) if data else 0
            }
    
    def _generate_cache_key(self, sql_query: str, config: ChartExecutionConfig) -> str:
        """Generate cache key for the query and config"""
        import hashlib
        key_data = f"{sql_query}_{config.page_size}_{config.max_rows}_{config.sort_by}_{config.sort_order}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cached_result: Dict[str, Any], ttl_seconds: int) -> bool:
        """Check if cached result is still valid"""
        if "cached_at" not in cached_result:
            return False
        
        cached_time = pd.Timestamp(cached_result["cached_at"])
        current_time = pd.Timestamp.now()
        return (current_time - cached_time).total_seconds() < ttl_seconds
    
    def clear_cache(self):
        """Clear the execution cache"""
        self.cache.clear()
        logger.info("Chart execution cache cleared")


# Convenience function for chart execution
async def execute_chart_with_sql(
    chart_schema: Dict[str, Any],
    sql_query: str,
    db_engine,
    config: Optional[ChartExecutionConfig] = None
) -> Dict[str, Any]:
    """
    Convenience function to execute a chart with SQL data
    
    Args:
        chart_schema: Vega-Lite chart schema
        sql_query: SQL query to fetch data
        db_engine: Database engine
        config: Execution configuration
    
    Returns:
        Dict containing executed chart schema and metadata
    """
    executor = ChartExecutor(db_engine)
    return await executor.execute_chart(chart_schema, sql_query, config)