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


enhanced_chart_generation_instructions = """
### INSTRUCTIONS ###

- Chart types: Bar chart, Line chart, Multi line chart, Area chart, Pie chart, Stacked bar chart, Grouped bar chart, Scatter chart, Heatmap, Boxplot, Histogram, Bubble chart, Text chart, Tick chart, Rule chart, KPI chart
- You can only use the chart types provided in the instructions
- Generated chart should answer the user's question and based on the semantics of the SQL query, and the sample data, sample column values are used to help you generate the suitable chart type
- If the sample data is not suitable for visualization, you must return an empty string for the schema and chart type
- If the sample data is empty, you must return an empty string for the schema and chart type
- The language for the chart and reasoning must be the same language provided by the user
- Please use the current time provided by the user to generate the chart

### ENHANCED CHART TYPE INSTRUCTIONS ###

- For Scatter Chart:
    - Use mark type "circle" or "point"
    - Requires two quantitative variables (x and y)
    - Optional: color encoding for categorical data, size encoding for third quantitative variable
    - Example: {"mark": {"type": "circle"}, "encoding": {"x": {"field": "x_field", "type": "quantitative"}, "y": {"field": "y_field", "type": "quantitative"}}}

- For Heatmap:
    - Use mark type "rect"
    - Requires two categorical or temporal variables (x and y) and one quantitative variable (color)
    - Example: {"mark": {"type": "rect"}, "encoding": {"x": {"field": "x_field", "type": "nominal"}, "y": {"field": "y_field", "type": "nominal"}, "color": {"field": "value_field", "type": "quantitative"}}}

- For Boxplot:
    - Use mark type "boxplot"
    - Requires one quantitative variable (y) and optional categorical variable (x)
    - Example: {"mark": {"type": "boxplot"}, "encoding": {"y": {"field": "value_field", "type": "quantitative"}, "x": {"field": "category_field", "type": "nominal"}}}

- For Histogram:
    - Use mark type "bar"
    - Requires one quantitative variable (x) and count aggregation (y)
    - Example: {"mark": {"type": "bar"}, "encoding": {"x": {"field": "value_field", "type": "quantitative", "bin": true}, "y": {"aggregate": "count", "type": "quantitative"}}}

- For Bubble Chart:
    - Use mark type "circle"
    - Requires three quantitative variables (x, y, size)
    - Optional: color encoding for categorical data
    - Example: {"mark": {"type": "circle"}, "encoding": {"x": {"field": "x_field", "type": "quantitative"}, "y": {"field": "y_field", "type": "quantitative"}, "size": {"field": "size_field", "type": "quantitative"}}}

- For Text Chart:
    - Use mark type "text"
    - Requires text field and positioning (x, y)
    - Example: {"mark": {"type": "text"}, "encoding": {"x": {"field": "x_field", "type": "nominal"}, "y": {"field": "y_field", "type": "quantitative"}, "text": {"field": "text_field", "type": "nominal"}}}

- For Tick Chart:
    - Use mark type "tick"
    - Requires one quantitative variable (x or y)
    - Example: {"mark": {"type": "tick"}, "encoding": {"x": {"field": "value_field", "type": "quantitative"}}}

- For Rule Chart:
    - Use mark type "rule"
    - Requires positioning (x or y)
    - Example: {"mark": {"type": "rule"}, "encoding": {"x": {"field": "category_field", "type": "nominal"}}}

- For KPI Chart:
    - Use mark type "text" (dummy implementation)
    - This is a special case for KPI metrics that don't fit standard chart types
    - Returns a dummy chart schema since Vega-Lite doesn't support KPI charts natively
    - IMPORTANT: KPI charts are ONLY appropriate when:
        * Data has AT MOST 2 columns (1 for single value, 2 for key-value pairs)
        * Data has AT MOST 5 rows
    - DO NOT use KPI chart when data has more than 2 columns - use bar, grouped_bar, line, or other appropriate chart instead
    - Example: {"mark": {"type": "text"}, "encoding": {"text": {"field": "kpi_value", "type": "quantitative"}}}

### GUIDELINES TO PLOT CHART ###

1. Understanding Your Data Types
- Nominal (Categorical): Names or labels without a specific order (e.g., types of fruits, countries).
- Ordinal: Categorical data with a meaningful order but no fixed intervals (e.g., rankings, satisfaction levels).
- Quantitative: Numerical values representing counts or measurements (e.g., sales figures, temperatures).
- Temporal: Date or time data (e.g., timestamps, dates).

2. Enhanced Chart Types and When to Use Them

- Scatter Chart
    - Use When: Showing relationship between two continuous variables, identifying patterns, clusters, or outliers.
    - Data Requirements:
        - Two quantitative variables (x and y axes).
        - Optional: One categorical variable (color), one quantitative variable (size).
    - Example: Sales vs. profit by product, age vs. income by region.

- Heatmap
    - Use When: Showing correlation or density between two variables, displaying matrix data.
    - Data Requirements:
        - Two categorical or temporal variables (x and y axes).
        - One quantitative variable (color intensity).
    - Example: Sales by month and region, correlation matrix.

- Boxplot
    - Use When: Showing distribution and outliers, comparing distributions across categories.
    - Data Requirements:
        - One quantitative variable (y-axis).
        - Optional: One categorical variable (x-axis for grouping).
    - Example: Sales distribution by region, salary distribution by department.

- Histogram
    - Use When: Showing distribution of a continuous variable, identifying patterns in data.
    - Data Requirements:
        - One quantitative variable (x-axis with binning).
        - Count aggregation (y-axis).
    - Example: Age distribution of customers, sales amount distribution.

- Bubble Chart
    - Use When: Showing relationship between three variables, emphasizing size differences.
    - Data Requirements:
        - Three quantitative variables (x, y, size).
        - Optional: One categorical variable (color).
    - Example: Sales vs. profit vs. market size by region.

- Text Chart
    - Use When: Displaying text labels with positioning, annotations.
    - Data Requirements:
        - Text field for labels.
        - Positioning variables (x, y).
    - Example: Product names positioned by sales and profit.

- Tick Chart
    - Use When: Showing distribution of values, simple frequency plots.
    - Data Requirements:
        - One quantitative variable (x or y axis).
    - Example: Distribution of customer ratings, frequency of events.

- Rule Chart
    - Use When: Drawing reference lines, showing thresholds or boundaries.
    - Data Requirements:
        - Positioning variable (x or y).
    - Example: Target lines on charts, reference values.

- KPI Chart
    - Use When: Displaying key performance indicators, single metrics, or summary statistics.
    - Data Requirements:
        - MAXIMUM of 2 columns (1 column for single value, or 2 columns for key-value pairs)
        - MAXIMUM of 5 rows
        - One or more quantitative values representing KPIs.
        - Optional: comparison values, targets, or thresholds.
    - DO NOT USE when:
        - Data has more than 2 columns - use bar, grouped_bar, or other appropriate chart
        - Data has more than 5 rows with multiple dimensions - use line, bar, or scatter chart
    - Example: Total sales, conversion rate, customer satisfaction score.
    - Note: This returns a dummy chart schema since Vega-Lite doesn't support KPI charts natively.

3. Guidelines for Selecting Chart Types
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
    - Showing Relationships:
        - Scatter Chart: Best for showing correlation between two variables.
        - Bubble Chart: Use when you have a third variable to represent as size.
    - Displaying Distributions:
        - Histogram: Best for showing distribution of a single variable.
        - Boxplot: Use for comparing distributions across categories.
    - Showing Correlations:
        - Heatmap: Best for showing correlation matrices or two-dimensional data.
    - Annotations and Labels:
        - Text Chart: Use for adding labels or annotations.
        - Tick Chart: Use for simple frequency displays.
        - Rule Chart: Use for reference lines or thresholds.
    - Key Performance Indicators:
        - KPI Chart: Use ONLY when data has at most 2 columns and 5 rows. For data with more columns, use bar or grouped_bar charts instead.

### EXAMPLES ###

1. Scatter Chart
- Sample Data:
[
    {"Sales": 100000, "Profit": 25000, "Region": "North"},
    {"Sales": 150000, "Profit": 30000, "Region": "South"},
    {"Sales": 120000, "Profit": 20000, "Region": "East"},
    {"Sales": 180000, "Profit": 35000, "Region": "West"}
]
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

2. Heatmap
- Sample Data:
[
    {"Month": "Jan", "Region": "North", "Sales": 100000},
    {"Month": "Jan", "Region": "South", "Sales": 120000},
    {"Month": "Feb", "Region": "North", "Sales": 110000},
    {"Month": "Feb", "Region": "South", "Sales": 130000}
]
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

3. Boxplot
- Sample Data:
[
    {"Region": "North", "Sales": 100000},
    {"Region": "North", "Sales": 105000},
    {"Region": "North", "Sales": 95000},
    {"Region": "South", "Sales": 150000},
    {"Region": "South", "Sales": 145000},
    {"Region": "South", "Sales": 155000}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "boxplot"},
    "encoding": {
        "x": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

4. Histogram
- Sample Data:
[
    {"Sales": 50000},
    {"Sales": 75000},
    {"Sales": 100000},
    {"Sales": 125000},
    {"Sales": 150000}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "bar"},
    "encoding": {
        "x": {"field": "Sales", "type": "quantitative", "bin": true, "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"aggregate": "count", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

5. Bubble Chart
- Sample Data:
[
    {"Sales": 100000, "Profit": 25000, "Market_Size": 5000000, "Region": "North"},
    {"Sales": 150000, "Profit": 30000, "Market_Size": 8000000, "Region": "South"},
    {"Sales": 120000, "Profit": 20000, "Market_Size": 6000000, "Region": "East"}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "circle"},
    "encoding": {
        "x": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Profit", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "size": {"field": "Market_Size", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "color": {"field": "Region", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

6. Text Chart
- Sample Data:
[
    {"Product": "Product A", "Sales": 100000, "Profit": 25000},
    {"Product": "Product B", "Sales": 150000, "Profit": 30000},
    {"Product": "Product C", "Sales": 120000, "Profit": 20000}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "text"},
    "encoding": {
        "x": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Profit", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "text": {"field": "Product", "type": "nominal"}
    }
}

7. Tick Chart
- Sample Data:
[
    {"Rating": 1},
    {"Rating": 2},
    {"Rating": 3},
    {"Rating": 4},
    {"Rating": 5}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "tick"},
    "encoding": {
        "x": {"field": "Rating", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

8. Rule Chart
- Sample Data:
[
    {"Category": "Low", "Threshold": 50000},
    {"Category": "Medium", "Threshold": 100000},
    {"Category": "High", "Threshold": 150000}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "rule"},
    "encoding": {
        "x": {"field": "Category", "type": "nominal", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
        "y": {"field": "Threshold", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}
    }
}

9. KPI Chart
- Sample Data:
[
    {"Metric": "Total Sales", "Value": 1500000, "Target": 2000000, "Unit": "USD"},
    {"Metric": "Conversion Rate", "Value": 0.15, "Target": 0.20, "Unit": "%"},
    {"Metric": "Customer Satisfaction", "Value": 4.2, "Target": 4.5, "Unit": "stars"}
]
- Chart Schema:
{
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "mark": {"type": "text"},
    "encoding": {
        "text": {"field": "Value", "type": "quantitative"},
        "color": {"field": "Metric", "type": "nominal"}
    },
    "kpi_metadata": {
        "chart_type": "kpi",
        "is_dummy": true,
        "description": "KPI chart - templates will be created elsewhere",
        "kpi_data": {
            "metrics": ["Total Sales", "Conversion Rate", "Customer Satisfaction"],
            "values": [1500000, 0.15, 4.2],
            "targets": [2000000, 0.20, 4.5],
            "units": ["USD", "%", "stars"]
        }
    }
}
"""


class EnhancedChartDataPreprocessor:
    """Enhanced data preprocessor for chart generation with support for additional chart types"""
    
    def __init__(self):
        self.logger = logger
    
    def run(
        self,
        data: Dict[str, Any],
        sample_data_count: int = 15,
        sample_column_size: int = 5,
    ) -> Dict[str, Any]:
        """Preprocess data for enhanced chart generation"""
        try:
            if not data or "data" not in data or not data["data"]:
                return {
                    "sample_data": [],
                    "sample_column_values": {},
                    "data_analysis": {
                        "column_count": 0,
                        "row_count": 0,
                        "data_types": {},
                        "suggested_charts": []
                    }
                }
            
            # Extract data and columns
            raw_data = data["data"]
            columns = data.get("columns", [])
            
            # Validate data structure - ensure each row is a dictionary
            if raw_data and not isinstance(raw_data[0], dict):
                logger.warning(f"Data rows are not dictionaries. Converting from {type(raw_data[0])} to dict format")
                # Convert list of lists to list of dicts if needed
                if isinstance(raw_data[0], list):
                    raw_data = [dict(zip(columns, row)) for row in raw_data]
                else:
                    logger.error(f"Unexpected data format: {type(raw_data[0])}")
                    return {
                        "sample_data": [],
                        "sample_column_values": {},
                        "data_analysis": {
                            "column_count": 0,
                            "row_count": 0,
                            "data_types": {},
                            "suggested_charts": []
                        }
                    }
            
            # Create sample data
            sample_data = raw_data[:sample_data_count] if len(raw_data) > sample_data_count else raw_data
            
            # Add debugging information
            logger.info(f"Data preprocessing - Raw data type: {type(raw_data)}, Sample data type: {type(sample_data)}")
            if sample_data:
                logger.info(f"First row type: {type(sample_data[0])}, First row: {sample_data[0]}")
            
            # Analyze sample column values
            sample_column_values = {}
            data_types = {}
            suggested_charts = []
            
            if columns and sample_data:
                for col in columns:
                    col_values = [row.get(col, "") for row in sample_data if col in row]
                    sample_column_values[col] = col_values[:sample_column_size]
                    
                    # Determine data type
                    data_type = self._determine_data_type(col_values)
                    data_types[col] = data_type
                
                # Suggest chart types based on data analysis
                suggested_charts = self._suggest_chart_types(columns, data_types, sample_data)
                logger.info(f"Suggested chart types: {suggested_charts}")
                logger.info(f"Columns: {columns}")
                logger.info(f"Data types: {data_types}")
                logger.info(f"Sample data length: {len(sample_data)}")
            
            return {
                "sample_data": sample_data,
                "sample_column_values": sample_column_values,
                "data_analysis": {
                    "column_count": len(columns),
                    "row_count": len(raw_data),
                    "data_types": data_types,
                    "suggested_charts": suggested_charts
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in enhanced data preprocessing: {e}")
            return {
                "sample_data": [],
                "sample_column_values": {},
                "data_analysis": {
                    "column_count": 0,
                    "row_count": 0,
                    "data_types": {},
                    "suggested_charts": []
                }
            }
    
    def _determine_data_type(self, values: List[Any]) -> str:
        """Determine the data type of a column"""
        if not values:
            return "unknown"
        
        # Check if all values are numeric
        numeric_count = 0
        for val in values:
            if val is not None and str(val).replace('.', '').replace('-', '').isdigit():
                numeric_count += 1
        
        if numeric_count == len(values):
            return "quantitative"
        
        # Check if values look like dates
        date_patterns = ['-', '/', 'T', 'Z']
        date_count = 0
        for val in values:
            if val is not None and any(pattern in str(val) for pattern in date_patterns):
                date_count += 1
        
        if date_count > len(values) * 0.7:
            return "temporal"
        
        # Check if values are categorical (limited unique values)
        unique_values = set(str(v) for v in values if v is not None)
        if len(unique_values) <= min(10, len(values) * 0.5):
            return "nominal"
        
        return "ordinal"
    
    def _suggest_chart_types(self, columns: List[str], data_types: Dict[str, str], sample_data: List[Dict[str, Any]]) -> List[str]:
        """Suggest appropriate chart types based on data analysis"""
        suggestions = []
        
        # Count data types
        type_counts = {}
        for col_type in data_types.values():
            type_counts[col_type] = type_counts.get(col_type, 0) + 1
        
        # PRIORITY: Check for single values or small KPI datasets first
        logger.info(f"Checking for single values: columns={len(columns)}, quantitative_count={type_counts.get('quantitative', 0)}")
        
        # Check for all zero values
        all_zero_values = False
        if sample_data:
            numeric_values = []
            for row in sample_data:
                for key, value in row.items():
                    if data_types.get(key) == "quantitative":
                        try:
                            if isinstance(value, str):
                                clean_value = value.replace(',', '').replace('$', '').replace('%', '')
                                numeric_values.append(float(clean_value))
                            else:
                                numeric_values.append(float(value))
                        except (ValueError, TypeError):
                            continue
            
            # Check if all numeric values are zero
            if numeric_values and all(val == 0.0 for val in numeric_values):
                all_zero_values = True
                logger.info(f"All zero values detected, prioritizing KPI chart")
        
        if len(columns) <= 3 and type_counts.get("quantitative", 0) >= 1:
            # For single values or small datasets with quantitative data, prioritize KPI
            suggestions.extend(["kpi"])
            logger.info(f"Added KPI to suggestions for small dataset")
            
            # If it's a single value or all zero values, KPI is the primary choice
            if (len(columns) == 1 and type_counts.get("quantitative", 0) == 1) or all_zero_values:
                logger.info(f"Single value or all zero values detected, returning only KPI")
                return ["kpi"]  # Return only KPI for single values or all zero values
        
        # Suggest based on data type combinations for larger datasets
        if type_counts.get("quantitative", 0) >= 2:
            suggestions.extend(["scatter", "bubble"])
        
        if type_counts.get("temporal", 0) >= 1 and type_counts.get("quantitative", 0) >= 1:
            suggestions.extend(["line", "area", "multi_line"])
        
        if type_counts.get("nominal", 0) >= 1 and type_counts.get("quantitative", 0) >= 1:
            suggestions.extend(["bar", "grouped_bar", "stacked_bar", "pie"])
        
        if type_counts.get("nominal", 0) >= 2 and type_counts.get("quantitative", 0) >= 1:
            suggestions.extend(["heatmap"])
        
        if type_counts.get("quantitative", 0) >= 1:
            suggestions.extend(["histogram", "boxplot", "tick"])
        
        if type_counts.get("nominal", 0) >= 1:
            suggestions.extend(["text", "rule"])
        
        return list(set(suggestions))  # Remove duplicates


class EnhancedChartGenerationPostProcessor:
    """Enhanced post-processor for chart generation with support for additional chart types"""
    
    def __init__(self):
        self.logger = logger
    
    def run(
        self,
        generation_result: str,
        vega_schema: Dict[str, Any],
        sample_data: list[dict],
        remove_data_from_chart_schema: Optional[bool] = True,
    ) -> Dict[str, Any]:
        """Post-process enhanced chart generation results"""
        try:
            # Parse the generation result
            if isinstance(generation_result, str):
                try:
                    parsed_result = orjson.loads(generation_result)
                except Exception as e:
                    self.logger.error(f"Error parsing generation result: {e}")
                    return {
                        "chart_schema": {},
                        "reasoning": f"Error parsing result: {str(e)}",
                        "chart_type": "",
                        "success": False,
                        "error": str(e)
                    }
            else:
                parsed_result = generation_result
            
            # Extract components
            reasoning = parsed_result.get("reasoning", "")
            chart_type = parsed_result.get("chart_type", "")
            chart_schema = parsed_result.get("chart_schema", {})
            
            # Handle KPI charts specially (they don't need Vega-Lite validation)
            if chart_type == "kpi":
                chart_schema = self._create_kpi_dummy_schema(chart_schema, sample_data)
            else:
                # Validate and fix the chart schema
                if chart_schema:
                    chart_schema = self._fix_enhanced_vega_lite_errors(chart_schema, sample_data)
                    
                    # Validate against Vega-Lite schema
                    try:
                        validate(instance=chart_schema, schema=vega_schema)
                    except ValidationError as e:
                        self.logger.warning(f"Vega-Lite validation error: {e}")
                        # Try to fix common validation errors
                        chart_schema = self._fix_validation_errors(chart_schema, e)
            
            # Remove data from chart schema if requested
            if remove_data_from_chart_schema and "data" in chart_schema:
                del chart_schema["data"]
            
            return {
                "chart_schema": chart_schema,
                "reasoning": reasoning,
                "chart_type": chart_type,
                "success": True,
                "error": None
            }
            
        except Exception as e:
            self.logger.error(f"Error in enhanced post-processing: {e}")
            # Return a default chart instead of error for UI handling
            return {
                "chart_schema": {
                    "title": "Post-Processing Error",
                    "mark": {"type": "text"},
                    "encoding": {
                        "text": {"value": "Unable to process chart due to an error"}
                    }
                },
                "reasoning": f"Post-processing failed: {str(e)}",
                "chart_type": "text",
                "success": True,  # Return success so UI can handle gracefully
                "error": str(e)
            }
    
    def _fix_enhanced_vega_lite_errors(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fix common Vega-Lite errors for enhanced chart types"""
        try:
            # Ensure mark type is valid
            if "mark" in chart_schema:
                mark = chart_schema["mark"]
                if isinstance(mark, dict) and "type" in mark:
                    mark_type = mark["type"]
                    # Validate mark type for enhanced charts
                    valid_marks = ["bar", "line", "area", "arc", "point", "circle", "rect", "boxplot", "text", "tick", "rule"]
                    if mark_type not in valid_marks:
                        # Map invalid marks to valid ones
                        mark_mapping = {
                            "scatter": "circle",
                            "heatmap": "rect",
                            "histogram": "bar"
                        }
                        if mark_type in mark_mapping:
                            mark["type"] = mark_mapping[mark_type]
                        else:
                            mark["type"] = "bar"  # Default fallback
            
            # Fix encoding for enhanced chart types
            if "encoding" in chart_schema:
                encoding = chart_schema["encoding"]
                
                # Fix scatter chart encoding
                if chart_schema.get("mark", {}).get("type") in ["circle", "point"]:
                    if "x" in encoding and "y" in encoding:
                        # Ensure x and y are quantitative for scatter
                        for axis in ["x", "y"]:
                            if axis in encoding and "type" not in encoding[axis]:
                                encoding[axis]["type"] = "quantitative"
                
                # Fix heatmap encoding
                if chart_schema.get("mark", {}).get("type") == "rect":
                    if "x" in encoding and "y" in encoding and "color" in encoding:
                        # Ensure x and y are nominal for heatmap
                        for axis in ["x", "y"]:
                            if axis in encoding and "type" not in encoding[axis]:
                                encoding[axis]["type"] = "nominal"
                        # Ensure color is quantitative
                        if "color" in encoding and "type" not in encoding["color"]:
                            encoding["color"]["type"] = "quantitative"
                
                # Fix histogram encoding
                if chart_schema.get("mark", {}).get("type") == "bar":
                    if "x" in encoding and "y" in encoding:
                        # Check if this looks like a histogram
                        x_encoding = encoding.get("x", {})
                        y_encoding = encoding.get("y", {})
                        if (x_encoding.get("type") == "quantitative" and 
                            y_encoding.get("aggregate") == "count"):
                            # Add binning to x-axis
                            if "bin" not in x_encoding:
                                x_encoding["bin"] = True
                
                # Fix boxplot encoding
                if chart_schema.get("mark", {}).get("type") == "boxplot":
                    if "y" in encoding and "type" not in encoding["y"]:
                        encoding["y"]["type"] = "quantitative"
                
                # Fix text chart encoding
                if chart_schema.get("mark", {}).get("type") == "text":
                    if "text" not in encoding:
                        # Try to find a suitable text field
                        for field in ["name", "label", "title", "category"]:
                            if field in encoding:
                                encoding["text"] = encoding[field].copy()
                                break
            
            # Add data if not present
            if "data" not in chart_schema and sample_data:
                chart_schema["data"] = {"values": sample_data}
            
            return chart_schema
            
        except Exception as e:
            self.logger.error(f"Error fixing enhanced Vega-Lite errors: {e}")
            return chart_schema
    
    def _create_kpi_dummy_schema(self, chart_schema: Dict[str, Any], sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a dummy KPI chart schema since Vega-Lite doesn't support KPI charts natively"""
        try:
            # Extract KPI data from sample data
            kpi_data = self._extract_kpi_data(sample_data)
            
            # Try to find the actual field name from sample data
            encoding_field = "value"  # Default fallback
            if sample_data and len(sample_data) > 0:
                first_item = sample_data[0]
                if isinstance(first_item, dict):
                    # Find numeric fields in the data
                    for field_name, val in first_item.items():
                        if val is not None:
                            try:
                                if isinstance(val, (int, float)):
                                    encoding_field = field_name
                                    break
                                elif isinstance(val, str):
                                    clean_val = val.replace(',', '').replace('$', '').replace('%', '').strip()
                                    if clean_val and clean_val.lower() not in ["none", "null", ""]:
                                        float(clean_val)  # Test if numeric
                                        encoding_field = field_name
                                        break
                            except (ValueError, TypeError):
                                continue
            
            # Create dummy schema with KPI metadata
            dummy_schema = {
                "title": chart_schema.get("title", "KPI Dashboard"),
                "mark": {"type": "text"},  # Dummy mark type
                "encoding": {
                    "text": {"field": encoding_field, "type": "quantitative"},
                    "color": {"field": "metric", "type": "nominal"}
                },
                "kpi_metadata": {
                    "chart_type": "kpi",
                    "is_dummy": True,
                    "description": "KPI chart - templates will be created elsewhere",
                    "kpi_data": kpi_data,
                    "vega_lite_compatible": False,
                    "requires_custom_template": True
                }
            }
            
            return dummy_schema
            
        except Exception as e:
            self.logger.error(f"Error creating KPI dummy schema: {e}")
            return chart_schema
    
    def _extract_kpi_data(self, sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract KPI data from sample data"""
        try:
            if not sample_data:
                return {"metrics": [], "values": [], "targets": [], "units": []}
            
            # Try to identify KPI structure
            first_row = sample_data[0]
            metrics = []
            values = []
            targets = []
            units = []
            
            # Look for common KPI field patterns
            for key, value in first_row.items():
                key_lower = key.lower()
                
                # Identify metric names
                if any(word in key_lower for word in ["metric", "kpi", "indicator", "measure"]):
                    metrics = [row.get(key, "") for row in sample_data]
                
                # Identify values
                elif any(word in key_lower for word in ["value", "amount", "total", "count", "sum"]):
                    values = [row.get(key, 0) for row in sample_data]
                
                # Identify targets
                elif any(word in key_lower for word in ["target", "goal", "budget", "expected"]):
                    targets = [row.get(key, 0) for row in sample_data]
                
                # Identify units
                elif any(word in key_lower for word in ["unit", "currency", "format"]):
                    units = [row.get(key, "") for row in sample_data]
            
            # If no specific fields found, use all numeric columns as values
            if not values:
                for key, value in first_row.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        values = [row.get(key, 0) for row in sample_data]
                        metrics = [key] * len(sample_data)
                        break
            
            return {
                "metrics": metrics,
                "values": values,
                "targets": targets,
                "units": units
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting KPI data: {e}")
            return {"metrics": [], "values": [], "targets": [], "units": []}
    
    def _fix_validation_errors(self, chart_schema: Dict[str, Any], validation_error: ValidationError) -> Dict[str, Any]:
        """Fix common validation errors"""
        try:
            # Handle common validation issues
            error_path = validation_error.path
            error_message = validation_error.message
            
            # Fix encoding type errors
            if "encoding" in error_path:
                encoding = chart_schema.get("encoding", {})
                for channel in encoding:
                    if isinstance(encoding[channel], dict) and "type" in encoding[channel]:
                        # Ensure type is valid
                        valid_types = ["nominal", "ordinal", "quantitative", "temporal"]
                        if encoding[channel]["type"] not in valid_types:
                            encoding[channel]["type"] = "nominal"  # Default fallback
            
            return chart_schema
            
        except Exception as e:
            self.logger.error(f"Error fixing validation errors: {e}")
            return chart_schema


def create_enhanced_chart_data_preprocessor_tool() -> Tool:
    """Create a tool for enhanced chart data preprocessing"""
    
    def preprocess_data_func(data_json: str) -> str:
        try:
            data = orjson.loads(data_json)
            preprocessor = EnhancedChartDataPreprocessor()
            result = preprocessor.run(data)
            return orjson.dumps(result).decode('utf-8')
        except Exception as e:
            logger.error(f"Error in enhanced data preprocessing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode('utf-8')
    
    return Tool(
        name="enhanced_preprocess_data",
        func=preprocess_data_func,
        description="Enhanced preprocessing of chart data with support for additional chart types"
    )


def create_enhanced_chart_postprocessor_tool() -> Tool:
    """Create a tool for enhanced chart post-processing"""
    
    def postprocess_chart_func(input_json: str) -> str:
        try:
            # Parse input
            input_data = orjson.loads(input_json)
            generation_result = input_data.get("generation_result", "")
            vega_schema = input_data.get("vega_schema", {})
            sample_data = input_data.get("sample_data", [])
            remove_data = input_data.get("remove_data", True)
            
            # Post-process
            postprocessor = EnhancedChartGenerationPostProcessor()
            result = postprocessor.run(generation_result, vega_schema, sample_data, remove_data)
            
            return orjson.dumps(result).decode('utf-8')
        except Exception as e:
            logger.error(f"Error in enhanced chart post-processing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode('utf-8')
    
    return Tool(
        name="enhanced_postprocess_chart",
        func=postprocess_chart_func,
        description="Enhanced post-processing of chart schemas with support for additional chart types"
    ) 