import logging
from typing import Any, Dict, Literal, Optional, List, Union
import json
import orjson
import pandas as pd
from langchain.agents import Tool
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel, Field
from app.agents.nodes.sql.utils.chart_models import ChartGenerationResults

logger = logging.getLogger("lexy-ai-service")

# Enhanced chart generation instructions with additional chart types
enhanced_chart_generation_instructions = """
### INSTRUCTIONS ###

- Chart types: Bar chart, Line chart, Multi line chart, Area chart, Pie chart, Stacked bar chart, Grouped bar chart, Scatter plot, Heatmap, Box plot, Histogram, Point plot, Circle plot, Square plot, Text plot, Tick plot, Trail plot, Rect plot, Rule plot, Image plot, Geoshape plot
- You can only use the chart types provided in the instructions
- Generated chart should answer the user's question and based on the semantics of the SQL query, and the sample data, sample column values are used to help you generate the suitable chart type
- If the sample data is not suitable for visualization, you must return an empty string for the schema and chart type
- If the sample data is empty, you must return an empty string for the schema and chart type
- The language for the chart and reasoning must be the same language provided by the user
- Please use the current time provided by the user to generate the chart

### CHART TYPE SELECTION GUIDELINES ###

1. **Bar Chart** (mark: "bar")
   - Use When: Comparing quantities across different categories
   - Data Requirements: One categorical variable (x-axis), One quantitative variable (y-axis)
   - Example: Sales by region, customer counts by category

2. **Line Chart** (mark: "line")
   - Use When: Displaying trends over continuous data, especially time
   - Data Requirements: One temporal or ordinal variable (x-axis), One quantitative variable (y-axis)
   - Example: Monthly revenue trends, user growth over time

3. **Area Chart** (mark: "area")
   - Use When: Similar to line charts but emphasizing volume of change over time
   - Data Requirements: Same as Line Chart
   - Example: Cumulative sales, market share over time

4. **Scatter Plot** (mark: "point" or "circle")
   - Use When: Showing relationship between two continuous variables
   - Data Requirements: Two quantitative variables (x and y)
   - Example: Sales vs profit correlation, age vs income

5. **Heatmap** (mark: "rect")
   - Use When: Showing correlation or density between two categorical variables
   - Data Requirements: Two categorical variables (x and y), One quantitative variable (color)
   - Example: Sales by month and region, user activity by hour and day

6. **Box Plot** (mark: "boxplot")
   - Use When: Showing distribution and outliers of a variable
   - Data Requirements: One quantitative variable (y), One categorical variable (x, optional)
   - Example: Salary distribution by department, test scores by class

7. **Histogram** (mark: "bar" with bin transform)
   - Use When: Showing distribution of a continuous variable
   - Data Requirements: One quantitative variable
   - Example: Age distribution, income distribution

8. **Pie Chart** (mark: "arc")
   - Use When: Showing parts of a whole as percentages
   - Data Requirements: One categorical variable, One quantitative variable
   - Example: Market share distribution, budget allocation

9. **Grouped Bar Chart** (mark: "bar" with xOffset)
   - Use When: Comparing sub-categories within main categories
   - Data Requirements: Two categorical variables, One quantitative variable
   - Example: Sales by product across regions

10. **Stacked Bar Chart** (mark: "bar" with stack)
    - Use When: Showing composition within categories
    - Data Requirements: Two categorical variables, One quantitative variable
    - Example: Sales breakdown by product type within regions

11. **Multi Line Chart** (mark: "line" with transform)
    - Use When: Displaying multiple trends over time
    - Data Requirements: One temporal variable, Multiple quantitative variables
    - Example: Multiple metrics over time

12. **Bubble Chart** (mark: "circle" with size encoding)
    - Use When: Showing relationship between three variables
    - Data Requirements: Two quantitative variables (x, y), One quantitative variable (size)
    - Example: Sales vs profit vs market size

13. **Text Plot** (mark: "text")
    - Use When: Displaying text labels or annotations
    - Data Requirements: Text data with positioning
    - Example: Labels on scatter plots, annotations

14. **Tick Plot** (mark: "tick")
    - Use When: Showing distribution of a single variable
    - Data Requirements: One quantitative variable
    - Example: Distribution of values, jittered points

15. **Rule Plot** (mark: "rule")
    - Use When: Drawing reference lines or connecting points
    - Data Requirements: Start and end points
    - Example: Reference lines, connecting lines

### VEGA-LITE SPECIFIC INSTRUCTIONS ###

- For grouped bar charts: Use xOffset encoding with stack: null
- For stacked bar charts: Use color encoding with stack: "zero"
- For pie charts: Use theta encoding for values, color for categories
- For heatmaps: Use rect mark with x, y, and color encodings
- For scatter plots: Use point or circle mark with x and y encodings
- For box plots: Use boxplot mark with y encoding and optional x encoding
- For histograms: Use bar mark with bin transform on x encoding
- For temporal data: Use appropriate timeUnit (year, yearmonth, yearmonthdate)
- For all charts: Include proper titles and axis labels in the user's language

### DATA TRANSFORMATION GUIDELINES ###

- Use "transform" section for data reshaping (fold, aggregate, bin, etc.)
- Use "fold" transform to combine multiple columns into key-value pairs
- Use "bin" transform for histograms and discretization
- Use "aggregate" transform for summarizing data
- Use "filter" transform to subset data when needed

### EXAMPLES ###

1. **Scatter Plot**
- Sample Data: [{"Sales": 100000, "Profit": 25000, "Region": "North"}, ...]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "circle"},
    "encoding": {
        "x": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Profit", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "color": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

2. **Heatmap**
- Sample Data: [{"Month": "Jan", "Region": "North", "Sales": 100000}, ...]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "rect"},
    "encoding": {
        "x": {"field": "Month", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "color": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

3. **Box Plot**
- Sample Data: [{"Department": "Sales", "Salary": 50000}, ...]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "boxplot"},
    "encoding": {
        "x": {"field": "Department", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Salary", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

4. **Histogram**
- Sample Data: [{"Age": 25}, {"Age": 30}, ...]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "bar"},
    "encoding": {
        "x": {"field": "Age", "type": "quantitative", "bin": true, "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"aggregate": "count", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

5. **Bubble Chart**
- Sample Data: [{"Sales": 100000, "Profit": 25000, "Market_Size": 1000000}, ...]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "circle"},
    "encoding": {
        "x": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Profit", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "size": {"field": "Market_Size", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

6. **Multi Line Chart with Transform**
- Sample Data: [{"Date": "2023-01-01", "Revenue": 100000, "Costs": 80000}, ...]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "line"},
    "transform": [
        {
            "fold": ["Revenue", "Costs"],
            "as": ["Metric", "Value"]
        }
    ],
    "encoding": {
        "x": {"field": "Date", "type": "temporal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Value", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "color": {"field": "Metric", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}
"""


class EnhancedChartDataPreprocessor:
    """Enhanced data preprocessor for Vega-Lite chart generation"""
    
    def __init__(self):
        self.name = "enhanced_chart_data_preprocessor"
        self.description = "Preprocesses data for enhanced Vega-Lite chart generation"
    
    def run(
        self,
        data: Dict[str, Any],
        sample_data_count: int = 15,
        sample_column_size: int = 5,
    ) -> Dict[str, Any]:
        """Process data and return sample data and column values with enhanced analysis"""
        try:
            columns = [
                column.get("name", "") if isinstance(column, dict) else column
                for column in data.get("columns", [])
            ]
            data_rows = data.get("data", [])

            df = pd.DataFrame(data_rows, columns=columns)
            
            # Enhanced column analysis
            column_analysis = self._analyze_columns(df)
            
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
                "column_analysis": column_analysis,
                "data_shape": {"rows": len(df), "columns": len(df.columns)},
                "suggested_chart_types": self._suggest_chart_types(column_analysis, df)
            }
        except Exception as e:
            logger.error(f"Error in enhanced data preprocessing: {e}")
            return {
                "sample_data": [],
                "sample_column_values": {},
                "column_analysis": {},
                "data_shape": {"rows": 0, "columns": 0},
                "suggested_chart_types": []
            }
    
    def _analyze_columns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze column types and characteristics"""
        analysis = {}
        
        for col in df.columns:
            col_analysis = {
                "name": col,
                "dtype": str(df[col].dtype),
                "unique_count": df[col].nunique(),
                "null_count": df[col].isnull().sum(),
                "sample_values": df[col].dropna().head(3).tolist()
            }
            
            # Determine column type
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                col_analysis["type"] = "temporal"
            elif pd.api.types.is_numeric_dtype(df[col]):
                col_analysis["type"] = "quantitative"
                col_analysis["min"] = df[col].min()
                col_analysis["max"] = df[col].max()
                col_analysis["mean"] = df[col].mean()
            else:
                col_analysis["type"] = "nominal"
            
            analysis[col] = col_analysis
        
        return analysis
    
    def _suggest_chart_types(self, column_analysis: Dict[str, Any], df: pd.DataFrame) -> List[str]:
        """Suggest appropriate chart types based on data analysis"""
        suggestions = []
        
        temporal_cols = [col for col, analysis in column_analysis.items() if analysis["type"] == "temporal"]
        quantitative_cols = [col for col, analysis in column_analysis.items() if analysis["type"] == "quantitative"]
        nominal_cols = [col for col, analysis in column_analysis.items() if analysis["type"] == "nominal"]
        
        # Basic chart type suggestions
        if temporal_cols and quantitative_cols:
            suggestions.extend(["line", "area"])
        
        if nominal_cols and quantitative_cols:
            suggestions.extend(["bar", "pie"])
            if len(nominal_cols) >= 2:
                suggestions.extend(["grouped_bar", "stacked_bar", "heatmap"])
        
        if len(quantitative_cols) >= 2:
            suggestions.extend(["scatter", "bubble"])
        
        if len(quantitative_cols) >= 1:
            suggestions.extend(["histogram", "boxplot", "tick"])
        
        # Remove duplicates and return
        return list(set(suggestions))


class EnhancedChartGenerationPostProcessor:
    """Enhanced post-processor for Vega-Lite chart generation results"""
    
    def __init__(self):
        self.name = "enhanced_chart_generation_postprocessor"
        self.description = "Post-processes enhanced Vega-Lite chart generation results"
    
    def run(
        self,
        generation_result: str,
        vega_schema: Dict[str, Any],
        sample_data: list[dict],
        remove_data_from_chart_schema: Optional[bool] = True,
    ) -> Dict[str, Any]:
        """Process LLM output and validate Vega-Lite schema with enhanced features"""
        
        if isinstance(generation_result, list) and generation_result:
            result_str = generation_result[0]
        else:
            result_str = generation_result
        
        logger.info(f"Enhanced post-processor input: {result_str}")
        
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

            # Enhanced Vega-Lite configuration fixes
            chart_schema = self._fix_enhanced_vega_lite_errors(chart_schema, sample_data)

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
            logger.info(f"Enhanced post-processor success result: {result}")
            return result

        logger.warning("No chart_schema found in parsed result")
        result = {
            "chart_schema": {},
            "reasoning": reasoning,
            "chart_type": chart_type,
            "success": False
        }
        logger.info(f"Enhanced post-processor failure result: {result}")
        return result
    
    def _fix_enhanced_vega_lite_errors(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fix common Vega-Lite configuration errors with enhanced support"""
        try:
            encoding = chart_schema.get("encoding", {})
            mark = chart_schema.get("mark", {})
            
            # Fix 0: Clean up invalid nested structures and comments
            self._clean_invalid_structures(chart_schema)
            
            # Fix 1: Ensure proper mark types for different chart types
            self._fix_mark_types(chart_schema, sample_data)
            
            # Fix 2: Handle special chart types
            if mark.get("type") == "boxplot":
                self._fix_boxplot_config(chart_schema, sample_data)
            elif mark.get("type") == "rect":
                self._fix_heatmap_config(chart_schema, sample_data)
            elif mark.get("type") in ["point", "circle"]:
                self._fix_scatter_config(chart_schema, sample_data)
            elif mark.get("type") == "bar" and any("bin" in enc for enc in encoding.values() if isinstance(enc, dict)):
                self._fix_histogram_config(chart_schema, sample_data)
            
            # Fix 3: Ensure proper data types
            self._fix_data_types(encoding, sample_data)
            
            # Fix 4: Handle transforms properly
            self._fix_transforms(chart_schema, sample_data)
            
            # Fix 5: Clean up color scales and remove invalid properties
            self._fix_color_scales(encoding)
            
            return chart_schema
        except Exception as e:
            logger.warning(f"Error fixing enhanced Vega-Lite errors: {e}")
            return chart_schema
    
    def _fix_mark_types(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix mark types for different chart types"""
        mark = chart_schema.get("mark", {})
        encoding = chart_schema.get("encoding", {})
        
        # Ensure mark is a dict
        if not isinstance(mark, dict):
            chart_schema["mark"] = {"type": str(mark)}
        
        # Fix specific mark types
        mark_type = mark.get("type", "")
        
        # For scatter plots, use point or circle
        if mark_type == "scatter":
            chart_schema["mark"] = {"type": "circle"}
        
        # For heatmaps, ensure rect mark
        if mark_type == "heatmap":
            chart_schema["mark"] = {"type": "rect"}
    
    def _fix_boxplot_config(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix boxplot configuration"""
        encoding = chart_schema.get("encoding", {})
        
        # Ensure y encoding exists for boxplot
        if "y" not in encoding and sample_data:
            # Find a quantitative column
            for col in sample_data[0].keys():
                if sample_data and any(isinstance(row.get(col), (int, float)) for row in sample_data):
                    encoding["y"] = {"field": col, "type": "quantitative"}
                    break
    
    def _fix_heatmap_config(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix heatmap configuration"""
        encoding = chart_schema.get("encoding", {})
        
        # Ensure x, y, and color encodings exist
        required_encodings = ["x", "y", "color"]
        available_cols = list(sample_data[0].keys()) if sample_data else []
        
        for i, encoding_name in enumerate(required_encodings):
            if encoding_name not in encoding and i < len(available_cols):
                col = available_cols[i]
                if encoding_name == "color":
                    # Color should be quantitative for heatmap
                    encoding[encoding_name] = {"field": col, "type": "quantitative"}
                else:
                    # X and Y can be nominal or quantitative
                    encoding[encoding_name] = {"field": col, "type": "nominal"}
    
    def _fix_scatter_config(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix scatter plot configuration"""
        encoding = chart_schema.get("encoding", {})
        
        # Ensure x and y encodings exist for scatter
        required_encodings = ["x", "y"]
        available_cols = list(sample_data[0].keys()) if sample_data else []
        
        for i, encoding_name in enumerate(required_encodings):
            if encoding_name not in encoding and i < len(available_cols):
                col = available_cols[i]
                encoding[encoding_name] = {"field": col, "type": "quantitative"}
    
    def _fix_histogram_config(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix histogram configuration"""
        encoding = chart_schema.get("encoding", {})
        
        # Ensure proper bin configuration for histogram
        if "x" in encoding and "bin" not in encoding["x"]:
            encoding["x"]["bin"] = True
        
        # Ensure y encoding has count aggregate
        if "y" not in encoding:
            encoding["y"] = {"aggregate": "count", "type": "quantitative"}
    
    def _fix_data_types(self, encoding: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix data types in encoding"""
        for channel in ["x", "y", "color", "xOffset", "size", "text", "theta"]:
            if channel in encoding and isinstance(encoding[channel], dict):
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
    
    def _fix_transforms(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]):
        """Fix transform configurations"""
        if "transform" in chart_schema:
            transform = chart_schema["transform"]
            if transform and isinstance(transform, list):
                for t in transform:
                    if isinstance(t, dict):
                        # Fix fold transform
                        if t.get("fold"):
                            if "as" not in t:
                                t["as"] = ["key", "value"]
                        
                        # Fix bin transform
                        if t.get("bin"):
                            if isinstance(t["bin"], bool) and t["bin"]:
                                t["bin"] = True
    
    def _clean_invalid_structures(self, chart_schema: Dict[str, Any]):
        """Clean up invalid nested structures in the chart schema"""
        try:
            encoding = chart_schema.get("encoding", {})
            
            # Remove invalid nested structures
            for channel in list(encoding.keys()):
                if channel not in ["x", "y", "color", "xOffset", "theta", "size", "shape", "text", "tooltip", "facet", "row", "column"]:
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
                    
                    # Remove any properties that might contain comments or invalid syntax
                    if isinstance(scale, dict):
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


# Enhanced Langchain Tools for Vega-Lite Chart Generation
def create_enhanced_chart_data_preprocessor_tool() -> Tool:
    """Create Langchain tool for enhanced data preprocessing"""
    preprocessor = EnhancedChartDataPreprocessor()
    
    def preprocess_data_func(data_json: str) -> str:
        """Preprocess data for enhanced Vega-Lite chart generation"""
        try:
            data = orjson.loads(data_json)
            result = preprocessor.run(data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in enhanced data preprocessing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="enhanced_chart_data_preprocessor",
        description="Preprocesses data for enhanced Vega-Lite chart generation with advanced analysis. Input should be JSON string with 'columns' and 'data' fields.",
        func=preprocess_data_func
    )


def create_enhanced_chart_postprocessor_tool() -> Tool:
    """Create Langchain tool for enhanced chart post-processing"""
    postprocessor = EnhancedChartGenerationPostProcessor()
    
    def postprocess_chart_func(input_json: str) -> str:
        """Post-process enhanced Vega-Lite chart generation results"""
        try:
            input_data = orjson.loads(input_json)
            generation_result = input_data.get("generation_result", "")
            vega_schema = input_data.get("vega_schema", {})
            sample_data = input_data.get("sample_data", [])
            remove_data = input_data.get("remove_data_from_chart_schema", True)
            
            result = postprocessor.run(generation_result, vega_schema, sample_data, remove_data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in enhanced chart post-processing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="enhanced_chart_postprocessor",
        description="Post-processes enhanced Vega-Lite chart generation results. Input should be JSON with 'generation_result', 'vega_schema', 'sample_data', and 'remove_data_from_chart_schema' fields.",
        func=postprocess_chart_func
    )


# Enhanced utility functions for Vega-Lite integration
class EnhancedVegaLiteChartExporter:
    """Enhanced utility class to export Vega-Lite chart configurations"""
    
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
// Enhanced Vega-Lite Chart
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
                    elif channel == "size":
                        encoding_parts.append(f"size=alt.Size('{field}:{data_type[0].upper()}')")
            
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
            "has_transforms": "transform" in chart_schema,
            "encoding_channels": list(chart_schema.get("encoding", {}).keys())
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


def fix_and_prepare_enhanced_chart_schema(
    chart_schema: Dict[str, Any], 
    data: List[Dict[str, Any]], 
    remove_data_from_schema: bool = False
) -> Dict[str, Any]:
    """
    Fix common Vega-Lite configuration errors and prepare enhanced chart schema with data.
    
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
        
        # Fix common errors using the enhanced post-processor
        post_processor = EnhancedChartGenerationPostProcessor()
        fixed_schema = post_processor._fix_enhanced_vega_lite_errors(fixed_schema, data)
        
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
            elif encoding.get("x", {}).get("bin"):
                chart_type = "histogram"
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
        elif mark_type in ["point", "circle"]:
            if "size" in encoding:
                chart_type = "bubble"
            else:
                chart_type = "scatter"
        elif mark_type == "rect":
            chart_type = "heatmap"
        elif mark_type == "boxplot":
            chart_type = "boxplot"
        elif mark_type == "text":
            chart_type = "text"
        elif mark_type == "tick":
            chart_type = "tick"
        elif mark_type == "rule":
            chart_type = "rule"
        
        return {
            "chart_schema": fixed_schema,
            "chart_type": chart_type,
            "reasoning": f"Enhanced chart schema fixed and prepared with {len(data)} data points",
            "success": True,
            "data_count": len(data)
        }
        
    except Exception as e:
        logger.error(f"Error fixing enhanced chart schema: {e}")
        return {
            "chart_schema": chart_schema,
            "chart_type": "",
            "reasoning": f"Error fixing enhanced chart schema: {str(e)}",
            "success": False,
            "error": str(e)
        }


def create_enhanced_chart_from_existing_schema(
    chart_schema: Dict[str, Any],
    data: List[Dict[str, Any]],
    language: str = "English"
) -> Dict[str, Any]:
    """
    Create an enhanced chart result from an existing chart schema and data.
    
    Args:
        chart_schema: The existing chart schema
        data: The data to visualize
        language: The language for titles and labels
    
    Returns:
        Dict containing the enhanced chart result
    """
    try:
        # Fix and prepare the chart schema
        result = fix_and_prepare_enhanced_chart_schema(chart_schema, data, remove_data_from_schema=False)
        
        # Add language-specific metadata
        result["language"] = language
        result["chart_format"] = "vega_lite_enhanced"
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating enhanced chart from existing schema: {e}")
        return {
            "chart_schema": chart_schema,
            "chart_type": "",
            "reasoning": f"Error creating enhanced chart: {str(e)}",
            "success": False,
            "error": str(e)
        } 