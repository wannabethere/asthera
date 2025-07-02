import logging
from typing import Any, Dict, Literal, Optional, List, Union

import orjson
import pandas as pd
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
    - Don't use "transform" section.
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
        "y": {"field": "Sales", "type": "quantitative", "title": "<TITLE_IN_LANGUAGE_PROVIDED_BY_USER>"},
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
        try:
            if isinstance(generation_result, list) and generation_result:
                result_str = generation_result[0]
            else:
                result_str = generation_result
            
            parsed_result = orjson.loads(result_str)
            reasoning = parsed_result.get("reasoning", "")
            chart_type = parsed_result.get("chart_type", "")
            
            if chart_schema := parsed_result.get("chart_schema", {}):
                # Handle string format chart_schema
                if isinstance(chart_schema, str):
                    chart_schema = orjson.loads(chart_schema)

                chart_schema["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"
                chart_schema["data"] = {"values": sample_data}

                # Validate against Vega-Lite schema
                validate(chart_schema, schema=vega_schema)

                if remove_data_from_chart_schema:
                    chart_schema["data"]["values"] = []

                return {
                    "chart_schema": chart_schema,
                    "reasoning": reasoning,
                    "chart_type": chart_type,
                    "success": True
                }

            return {
                "chart_schema": {},
                "reasoning": reasoning,
                "chart_type": chart_type,
                "success": False
            }
            
        except ValidationError as e:
            logger.exception(f"Vega-lite schema is not valid: {e}")
            return {
                "chart_schema": {},
                "reasoning": "",
                "chart_type": "",
                "success": False,
                "error": f"Schema validation failed: {str(e)}"
            }
        except Exception as e:
            logger.exception(f"JSON deserialization failed: {e}")
            return {
                "chart_schema": {},
                "reasoning": "",
                "chart_type": "",
                "success": False,
                "error": str(e)
            }


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
        cache_results: bool = True,
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
            # Modify SQL for pagination if enabled
            if config.enable_pagination and config.max_rows:
                # Add LIMIT clause
                if "LIMIT" not in sql_query.upper():
                    sql_query += f" LIMIT {config.max_rows}"
                elif config.page_size:
                    # Replace existing LIMIT with our max_rows
                    import re
                    sql_query = re.sub(r'LIMIT\s+\d+', f'LIMIT {config.max_rows}', sql_query, flags=re.IGNORECASE)
            
            # Add sorting if specified
            if config.sort_by and "ORDER BY" not in sql_query.upper():
                sql_query += f" ORDER BY {config.sort_by} {config.sort_order}"
            
            logger.info(f"Executing SQL query: {sql_query}")
            
            # Always use execute_sql method since PandasEngine is a wrapper around other engines
            import aiohttp
            async with aiohttp.ClientSession() as session:
                success, result = await engine.execute_sql(
                    sql_query,
                    session,
                    dry_run=False,
                    limit=config.max_rows
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