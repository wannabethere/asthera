import logging
from typing import Any, Dict, Literal, Optional, List, Union

import orjson
import pandas as pd
from langchain.agents import Tool
from pydantic import BaseModel, Field

logger = logging.getLogger("wren-ai-service")


powerbi_chart_generation_instructions = """
### INSTRUCTIONS ###

- Chart types: Column chart, Clustered column chart, Stacked column chart, Line chart, Area chart, Pie chart, Donut chart, Scatter chart, Bar chart, Clustered bar chart, Stacked bar chart, Combo chart
- You can only use the chart types provided in the instructions
- Generated chart should answer the user's question and based on the semantics of the SQL query, and the sample data, sample column values are used to help you generate the suitable chart type
- If the sample data is not suitable for visualization, you must return an empty string for the config and chart type
- If the sample data is empty, you must return an empty string for the config and chart type
- The language for the chart and reasoning must be the same language provided by the user
- Please use the current time provided by the user to generate the chart
- For PowerBI charts, configure data roles (axis, values, legend, etc.) based on data types
- Make sure all of the fields in the data roles are present in the column names of the data
- For time-based data, use appropriate date hierarchy (Year, Quarter, Month, Day)
- Configure appropriate aggregation methods (Sum, Average, Count, etc.) for numeric fields

### GUIDELINES TO PLOT CHART ###

1. Understanding Your Data Types
- Text (Categorical): Names or labels without a specific order (e.g., product names, regions).
- Number: Numerical values representing counts or measurements (e.g., sales figures, quantities).
- Date/Time: Date or time data (e.g., order dates, timestamps).
- Boolean: True/false values.

2. Chart Types and When to Use Them
- Column Chart
    - Use When: Comparing values across categories.
    - Data Requirements:
        - Axis: One categorical field
        - Values: One or more numeric fields
    - Example: Sales by product category.

- Clustered Column Chart
    - Use When: Comparing multiple series across categories.
    - Data Requirements:
        - Axis: One categorical field
        - Values: Multiple numeric fields or one numeric field with legend
        - Legend: One categorical field (optional)
    - Example: Sales and profit by region.

- Stacked Column Chart
    - Use When: Showing composition within categories.
    - Data Requirements:
        - Axis: One categorical field
        - Values: One numeric field
        - Legend: One categorical field for stacking
    - Example: Sales breakdown by product type within each region.

- Line Chart
    - Use When: Showing trends over time or continuous data.
    - Data Requirements:
        - Axis: One date/time or continuous numeric field
        - Values: One or more numeric fields
        - Legend: One categorical field (for multiple lines)
    - Example: Monthly revenue trend.

- Area Chart
    - Use When: Showing trends with emphasis on volume.
    - Data Requirements:
        - Same as Line Chart
    - Example: Cumulative sales over time.

- Pie Chart
    - Use When: Showing parts of a whole.
    - Data Requirements:
        - Legend: One categorical field
        - Values: One numeric field
    - Example: Market share by company.

- Donut Chart
    - Use When: Similar to pie chart with center space for additional info.
    - Data Requirements:
        - Same as Pie Chart
    - Example: Budget allocation by department.

- Scatter Chart
    - Use When: Showing correlation between two numeric variables.
    - Data Requirements:
        - X Axis: One numeric field
        - Y Axis: One numeric field
        - Legend: One categorical field (optional)
        - Size: One numeric field (optional)
    - Example: Sales vs. profit by product.

- Bar Chart
    - Use When: Comparing values across categories (horizontal orientation).
    - Data Requirements:
        - Axis: One categorical field
        - Values: One or more numeric fields
    - Example: Top 10 products by sales.

- Combo Chart
    - Use When: Showing different types of data together.
    - Data Requirements:
        - Axis: One categorical or date field
        - Column Values: Numeric fields for columns
        - Line Values: Numeric fields for lines
    - Example: Sales (columns) and growth rate (line) by month.

### EXAMPLES ###

1. Column Chart
- Sample Data:
[
    {"Region": "North", "Sales": 100000},
    {"Region": "South", "Sales": 150000},
    {"Region": "East", "Sales": 120000},
    {"Region": "West", "Sales": 180000}
]
- Chart Config:
{
    "visualType": "columnChart",
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "dataRoles": {
        "Category": [{"field": "Region", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}],
        "Y": [{"field": "Sales", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "aggregation": "Sum"}]
    },
    "formatting": {
        "general": {
            "responsive": true
        },
        "categoryAxis": {
            "show": true,
            "axisType": "Categorical"
        },
        "valueAxis": {
            "show": true,
            "axisType": "Linear"
        }
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
    "visualType": "lineChart",
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "dataRoles": {
        "Category": [{"field": "Date", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "dateHierarchy": "Month"}],
        "Y": [{"field": "Sales", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "aggregation": "Sum"}]
    },
    "formatting": {
        "general": {
            "responsive": true
        },
        "categoryAxis": {
            "show": true,
            "axisType": "Continuous"
        },
        "valueAxis": {
            "show": true,
            "axisType": "Linear"
        }
    }
}

3. Pie Chart
- Sample Data:
[
    {"Product": "Product A", "Sales": 250000},
    {"Product": "Product B", "Sales": 180000},
    {"Product": "Product C", "Sales": 120000},
    {"Product": "Product D", "Sales": 90000}
]
- Chart Config:
{
    "visualType": "pieChart",
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "dataRoles": {
        "Category": [{"field": "Product", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}],
        "Y": [{"field": "Sales", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "aggregation": "Sum"}]
    },
    "formatting": {
        "general": {
            "responsive": true
        },
        "legend": {
            "show": true,
            "position": "Right"
        }
    }
}

4. Clustered Column Chart
- Sample Data:
[
    {"Region": "North", "Product": "A", "Sales": 100000},
    {"Region": "North", "Product": "B", "Sales": 80000},
    {"Region": "South", "Product": "A", "Sales": 120000},
    {"Region": "South", "Product": "B", "Sales": 90000}
]
- Chart Config:
{
    "visualType": "clusteredColumnChart",
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "dataRoles": {
        "Category": [{"field": "Region", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}],
        "Y": [{"field": "Sales", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "aggregation": "Sum"}],
        "Series": [{"field": "Product", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}]
    },
    "formatting": {
        "general": {
            "responsive": true
        },
        "categoryAxis": {
            "show": true,
            "axisType": "Categorical"
        },
        "valueAxis": {
            "show": true,
            "axisType": "Linear"
        },
        "legend": {
            "show": true,
            "position": "Top"
        }
    }
}

5. Scatter Chart
- Sample Data:
[
    {"Product": "Product A", "Sales": 100000, "Profit": 25000},
    {"Product": "Product B", "Sales": 150000, "Profit": 30000},
    {"Product": "Product C", "Sales": 80000, "Profit": 15000}
]
- Chart Config:
{
    "visualType": "scatterChart",
    "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>",
    "dataRoles": {
        "X": [{"field": "Sales", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "aggregation": "Sum"}],
        "Y": [{"field": "Profit", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>", "aggregation": "Sum"}],
        "Details": [{"field": "Product", "displayName": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"}]
    },
    "formatting": {
        "general": {
            "responsive": true
        },
        "xAxis": {
            "show": true,
            "axisType": "Linear"
        },
        "yAxis": {
            "show": true,
            "axisType": "Linear"
        }
    }
}
"""


class PowerBIChartDataPreprocessor:
    """Langchain tool for preprocessing data for PowerBI chart generation"""
    
    def __init__(self):
        self.name = "powerbi_data_preprocessor"
        self.description = "Preprocesses data for PowerBI chart generation"
    
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

            # Analyze column metadata for PowerBI
            column_metadata = {}
            for col in df.columns:
                dtype = str(df[col].dtype)
                if pd.api.types.is_numeric_dtype(df[col]):
                    column_metadata[col] = {"type": "number", "aggregatable": True}
                elif pd.api.types.is_datetime64_any_dtype(df[col]):
                    column_metadata[col] = {"type": "datetime", "aggregatable": False}
                elif dtype == 'bool':
                    column_metadata[col] = {"type": "boolean", "aggregatable": False}
                else:
                    column_metadata[col] = {"type": "text", "aggregatable": False}

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


class PowerBIChartGenerationPostProcessor:
    """Langchain tool for post-processing chart generation results"""
    
    def __init__(self):
        self.name = "powerbi_chart_postprocessor"
        self.description = "Post-processes PowerBI chart generation results"
    
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
                chart_config["data"] = sample_data

                # Basic validation - check if required fields exist
                self._validate_chart_config(chart_config)

                if remove_data_from_chart_config:
                    chart_config["data"] = []

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
    
    def _validate_chart_config(self, chart_config: dict) -> bool:
        """Basic validation of chart configuration"""
        required_fields = ["visualType", "dataRoles"]
        
        for field in required_fields:
            if field not in chart_config:
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Validate data roles contain actual field references
        if "dataRoles" in chart_config:
            data_roles = chart_config["dataRoles"]
            for role_name, fields in data_roles.items():
                if not isinstance(fields, list):
                    logger.warning(f"Data role {role_name} should be a list")
                    return False
                
                for field in fields:
                    if not isinstance(field, dict) or "field" not in field:
                        logger.warning(f"Invalid field definition in role {role_name}")
                        return False
        
        return True


# Pydantic Models for PowerBI Chart Configuration
class DataRole(BaseModel):
    field: str
    displayName: str
    aggregation: Optional[str] = None
    dateHierarchy: Optional[str] = None


class FormattingGeneral(BaseModel):
    responsive: bool = True


class FormattingAxis(BaseModel):
    show: bool = True
    axisType: Literal["Categorical", "Linear", "Continuous"]


class FormattingLegend(BaseModel):
    show: bool = True
    position: Literal["Top", "Bottom", "Left", "Right"] = "Right"


class ChartFormatting(BaseModel):
    general: FormattingGeneral
    categoryAxis: Optional[FormattingAxis] = None
    valueAxis: Optional[FormattingAxis] = None
    xAxis: Optional[FormattingAxis] = None
    yAxis: Optional[FormattingAxis] = None
    legend: Optional[FormattingLegend] = None


class PowerBIChartConfig(BaseModel):
    visualType: str
    title: str
    dataRoles: Dict[str, List[DataRole]]
    formatting: ChartFormatting
    data: Optional[List[Dict[str, Any]]] = []


class ColumnChartConfig(PowerBIChartConfig):
    visualType: Literal["columnChart"] = "columnChart"


class ClusteredColumnChartConfig(PowerBIChartConfig):
    visualType: Literal["clusteredColumnChart"] = "clusteredColumnChart"


class StackedColumnChartConfig(PowerBIChartConfig):
    visualType: Literal["stackedColumnChart"] = "stackedColumnChart"


class LineChartConfig(PowerBIChartConfig):
    visualType: Literal["lineChart"] = "lineChart"


class AreaChartConfig(PowerBIChartConfig):
    visualType: Literal["areaChart"] = "areaChart"


class PieChartConfig(PowerBIChartConfig):
    visualType: Literal["pieChart"] = "pieChart"


class DonutChartConfig(PowerBIChartConfig):
    visualType: Literal["donutChart"] = "donutChart"


class ScatterChartConfig(PowerBIChartConfig):
    visualType: Literal["scatterChart"] = "scatterChart"


class BarChartConfig(PowerBIChartConfig):
    visualType: Literal["barChart"] = "barChart"


class ComboChartConfig(PowerBIChartConfig):
    visualType: Literal["comboChart"] = "comboChart"


class PowerBIChartGenerationResults(BaseModel):
    reasoning: str
    chart_type: Literal[
        "columnChart", 
        "clusteredColumnChart", 
        "stackedColumnChart",
        "lineChart", 
        "areaChart",
        "pieChart", 
        "donutChart",
        "scatterChart",
        "barChart",
        "clusteredBarChart",
        "stackedBarChart",
        "comboChart",
        ""
    ]  # empty string for no chart
    chart_config: Union[
        ColumnChartConfig,
        ClusteredColumnChartConfig,
        StackedColumnChartConfig,
        LineChartConfig,
        AreaChartConfig,
        PieChartConfig,
        DonutChartConfig,
        ScatterChartConfig,
        BarChartConfig,
        ComboChartConfig,
        Dict[str, Any]  # For empty config
    ]


# Langchain Tools for PowerBI Chart Generation
def create_powerbi_data_preprocessor_tool() -> Tool:
    """Create Langchain tool for data preprocessing"""
    preprocessor = PowerBIChartDataPreprocessor()
    
    def preprocess_data_func(data_json: str) -> str:
        """Preprocess data for PowerBI chart generation"""
        try:
            data = orjson.loads(data_json)
            result = preprocessor.run(data)
            return orjson.dumps(result).decode()
        except Exception as e:
            logger.error(f"Error in data preprocessing tool: {e}")
            return orjson.dumps({"error": str(e)}).decode()
    
    return Tool(
        name="powerbi_data_preprocessor",
        description="Preprocesses data for PowerBI chart generation. Input should be JSON string with 'columns' and 'data' fields.",
        func=preprocess_data_func
    )


def create_powerbi_chart_postprocessor_tool() -> Tool:
    """Create Langchain tool for chart post-processing"""
    postprocessor = PowerBIChartGenerationPostProcessor()
    
    def postprocess_chart_func(input_json: str) -> str:
        """Post-process PowerBI chart generation results"""
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
        name="powerbi_chart_postprocessor",
        description="Post-processes PowerBI chart generation results. Input should be JSON with 'generation_result', 'sample_data', and 'remove_data_from_chart_config' fields.",
        func=postprocess_chart_func
    )


# Utility functions for PowerBI integration
class PowerBIChartExporter:
    """Utility class to export chart configurations to PowerBI-compatible formats"""
    
    @staticmethod
    def to_powerbi_json(chart_config: dict) -> str:
        """Convert chart configuration to PowerBI JSON format"""
        return orjson.dumps(chart_config, option=orjson.OPT_INDENT_2).decode()
    
    @staticmethod
    def to_powerbi_dax_measures(chart_config: dict) -> List[str]:
        """Generate DAX measures based on chart configuration"""
        measures = []
        
        if "dataRoles" in chart_config:
            for role_name, fields in chart_config["dataRoles"].items():
                for field in fields:
                    if field.get("aggregation"):
                        field_name = field["field"]
                        aggregation = field["aggregation"]
                        display_name = field.get("displayName", field_name)
                        
                        if aggregation.lower() == "sum":
                            measures.append(f"{display_name} = SUM({field_name})")
                        elif aggregation.lower() == "average":
                            measures.append(f"{display_name} = AVERAGE({field_name})")
                        elif aggregation.lower() == "count":
                            measures.append(f"{display_name} = COUNT({field_name})")
                        elif aggregation.lower() == "min":
                            measures.append(f"{display_name} = MIN({field_name})")
                        elif aggregation.lower() == "max":
                            measures.append(f"{display_name} = MAX({field_name})")
        
        return measures
    
    @staticmethod
    def to_powerbi_visual_settings(chart_config: dict) -> dict:
        """Convert chart formatting to PowerBI visual settings"""
        settings = {}
        
        if "formatting" in chart_config:
            formatting = chart_config["formatting"]
            
            # General settings
            if "general" in formatting:
                settings["general"] = formatting["general"]
            
            # Axis settings
            if "categoryAxis" in formatting:
                settings["categoryAxis"] = formatting["categoryAxis"]
            if "valueAxis" in formatting:
                settings["valueAxis"] = formatting["valueAxis"]
            if "xAxis" in formatting:
                settings["xAxis"] = formatting["xAxis"]
            if "yAxis" in formatting:
                settings["yAxis"] = formatting["yAxis"]
            
            # Legend settings
            if "legend" in formatting:
                settings["legend"] = formatting["legend"]
        
        return settings