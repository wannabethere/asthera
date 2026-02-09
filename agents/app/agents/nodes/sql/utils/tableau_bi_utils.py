import logging
from typing import Any, Dict, List, Optional, Union
import orjson
import xml.etree.ElementTree as ET
from datetime import datetime
import re
from dataclasses import dataclass


from langchain_core.tools import BaseTool, Tool
# Import BaseMessage using modern LangChain paths
try:
    from langchain_core.messages import BaseMessage
except ImportError:
    from langchain.schema import BaseMessage

logger = logging.getLogger("lexy-ai-service")


# Tableau chart generation instructions
tableau_chart_generation_instructions = """
### TABLEAU VISUALIZATION GUIDELINES ###

## Chart Type Selection:
- **Bar Chart**: Comparing categories, rankings, parts of a whole
- **Line Chart**: Trends over time, continuous data progression
- **Area Chart**: Cumulative trends, stacked composition over time
- **Scatter Plot**: Correlations, relationships between two measures
- **Pie Chart**: Part-to-whole relationships (max 7 categories)
- **Treemap**: Hierarchical data, proportional relationships
- **Heatmap**: Patterns in matrix data, correlation matrices
- **Histogram**: Distribution of continuous data
- **Box Plot**: Statistical distribution, outliers
- **Bullet Chart**: Performance against targets
- **Gantt Chart**: Timeline and project management
- **Map**: Geographical data visualization
- **Symbol Map**: Geographic points with measures
- **Filled Map**: Geographic regions with measures
- **Dual Axis**: Two related measures with different scales
- **Combined**: Multiple chart types in one view

## Tableau Configuration Structure:
```json
{
    "datasource": {
        "name": "Data Source Name",
        "connection": "extract|live",
        "fields": [
            {
                "name": "field_name",
                "type": "dimension|measure",
                "datatype": "string|integer|real|date|datetime|boolean",
                "role": "dimension|measure",
                "aggregation": "sum|avg|count|min|max|countd|median|stdev|var"
            }
        ]
    },
    "worksheet": {
        "name": "Sheet Name",
        "view": {
            "datasource": "Data Source Name",
            "aggregation": {
                "value": "true|false",
                "user-aggregation": "sum|avg|count|min|max|countd|median|stdev|var"
            },
            "filter": [
                {
                    "column": "field_name",
                    "function": "eq|ne|gt|lt|ge|le|in|range",
                    "value": "filter_value"
                }
            ],
            "datasource-dependencies": {
                "datasource": [
                    {
                        "name": "field_name",
                        "type": "column"
                    }
                ]
            },
            "shelf": {
                "columns": [
                    {
                        "field": "field_name",
                        "type": "quantitative|ordinal|nominal|temporal",
                        "aggregation": "sum|avg|count|min|max|countd|median|stdev|var"
                    }
                ],
                "rows": [
                    {
                        "field": "field_name",
                        "type": "quantitative|ordinal|nominal|temporal",
                        "aggregation": "sum|avg|count|min|max|countd|median|stdev|var"
                    }
                ],
                "color": {
                    "field": "field_name",
                    "type": "quantitative|ordinal|nominal|temporal"
                },
                "size": {
                    "field": "field_name",
                    "type": "quantitative|ordinal|nominal|temporal"
                },
                "shape": {
                    "field": "field_name",
                    "type": "nominal|ordinal"
                },
                "label": {
                    "field": "field_name",
                    "type": "quantitative|ordinal|nominal|temporal"
                },
                "detail": {
                    "field": "field_name",
                    "type": "quantitative|ordinal|nominal|temporal"
                },
                "tooltip": [
                    {
                        "field": "field_name",
                        "type": "quantitative|ordinal|nominal|temporal"
                    }
                ]
            },
            "mark": {
                "type": "bar|line|area|circle|square|text|pie|gantt|polygon|filled_map|symbol_map",
                "size": 5,
                "opacity": 1.0,
                "color": "#1f77b4"
            },
            "axes": {
                "x": {
                    "title": "X Axis Title",
                    "visible": true,
                    "scale": "linear|log|sqrt|ordinal",
                    "format": "number|currency|percentage|date"
                },
                "y": {
                    "title": "Y Axis Title", 
                    "visible": true,
                    "scale": "linear|log|sqrt|ordinal",
                    "format": "number|currency|percentage|date"
                }
            },
            "legends": {
                "color": {
                    "visible": true,
                    "title": "Legend Title",
                    "position": "right|left|top|bottom"
                }
            },
            "reference_lines": [
                {
                    "type": "constant|average|median|trend",
                    "value": 100,
                    "axis": "x|y",
                    "label": "Reference Line Label"
                }
            ]
        }
    },
    "formatting": {
        "title": "Chart Title",
        "subtitle": "Chart Subtitle",
        "caption": "Chart Caption",
        "background_color": "#ffffff",
        "font_family": "Tableau Book",
        "font_size": 12
    }
}
```

## Best Practices:
1. Use appropriate aggregations for different data types
2. Include proper titles and labels for clarity
3. Choose colors that are accessible and meaningful
4. Apply filters to focus on relevant data
5. Use reference lines for context when needed
6. Consider dual-axis for related but different scale measures
7. Use calculated fields for complex metrics
8. Apply proper formatting for dates and numbers
"""


@dataclass
class TableauChartGenerationResults:
    """Results from Tableau chart generation"""
    chart_config: Dict[str, Any]
    reasoning: str
    chart_type: str
    success: bool
    error: Optional[str] = None


class TableauChartDataPreprocessor:
    """Preprocesses data for Tableau chart generation"""
    
    def __init__(self):
        self.max_sample_rows = 100
        self.max_unique_values = 50
    
    def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess data for chart generation"""
        try:
            columns = data.get("columns", [])
            rows = data.get("data", [])
            
            # Generate sample data
            sample_data = self._generate_sample_data(columns, rows)
            
            # Generate column metadata
            column_metadata = self._generate_column_metadata(columns, rows)
            
            # Generate sample column values
            sample_column_values = self._generate_sample_column_values(columns, rows)
            
            return {
                "sample_data": sample_data,
                "column_metadata": column_metadata,
                "sample_column_values": sample_column_values,
                "total_rows": len(rows),
                "total_columns": len(columns)
            }
            
        except Exception as e:
            logger.error(f"Error in data preprocessing: {e}")
            return {
                "sample_data": "Error preprocessing data",
                "column_metadata": {},
                "sample_column_values": {},
                "total_rows": 0,
                "total_columns": 0,
                "error": str(e)
            }
    
    def _generate_sample_data(self, columns: List[str], rows: List[List[Any]]) -> str:
        """Generate sample data preview"""
        if not columns or not rows:
            return "No data available"
        
        sample_rows = rows[:self.max_sample_rows]
        
        # Create formatted table
        result = f"Columns: {', '.join(columns)}\n\n"
        result += "Sample Data:\n"
        
        for i, row in enumerate(sample_rows[:10]):  # Show max 10 rows in preview
            row_str = " | ".join(str(cell) for cell in row)
            result += f"Row {i+1}: {row_str}\n"
        
        if len(rows) > 10:
            result += f"... and {len(rows) - 10} more rows"
        
        return result
    
    def _generate_column_metadata(self, columns: List[str], rows: List[List[Any]]) -> Dict[str, Dict[str, Any]]:
        """Generate metadata for each column"""
        metadata = {}
        
        if not columns or not rows:
            return metadata
        
        for i, column in enumerate(columns):
            column_data = [row[i] for row in rows if i < len(row)]
            
            # Determine data type
            data_type = self._infer_data_type(column_data)
            
            # Calculate statistics
            non_null_count = sum(1 for x in column_data if x is not None and x != "")
            null_count = len(column_data) - non_null_count
            unique_count = len(set(str(x) for x in column_data if x is not None))
            
            metadata[column] = {
                "data_type": data_type,
                "non_null_count": non_null_count,
                "null_count": null_count,
                "unique_count": unique_count,
                "total_count": len(column_data)
            }
            
            # Add type-specific metadata
            if data_type in ["integer", "real"]:
                numeric_data = [float(x) for x in column_data if self._is_numeric(x)]
                if numeric_data:
                    metadata[column].update({
                        "min_value": min(numeric_data),
                        "max_value": max(numeric_data),
                        "avg_value": sum(numeric_data) / len(numeric_data)
                    })
            
        return metadata
    
    def _generate_sample_column_values(self, columns: List[str], rows: List[List[Any]]) -> Dict[str, List[Any]]:
        """Generate sample values for each column"""
        sample_values = {}
        
        if not columns or not rows:
            return sample_values
        
        for i, column in enumerate(columns):
            column_data = [row[i] for row in rows if i < len(row)]
            unique_values = list(set(str(x) for x in column_data if x is not None and x != ""))
            
            # Limit number of sample values
            if len(unique_values) > self.max_unique_values:
                sample_values[column] = unique_values[:self.max_unique_values] + ["..."]
            else:
                sample_values[column] = unique_values
        
        return sample_values
    
    def _infer_data_type(self, column_data: List[Any]) -> str:
        """Infer the data type of a column"""
        if not column_data:
            return "string"
        
        # Sample non-null values
        non_null_data = [x for x in column_data if x is not None and x != ""]
        if not non_null_data:
            return "string"
        
        # Check for dates
        if self._is_date_column(non_null_data):
            return "date"
        
        # Check for numbers
        numeric_count = sum(1 for x in non_null_data if self._is_numeric(x))
        if numeric_count / len(non_null_data) > 0.8:  # 80% threshold
            # Check if all numbers are integers
            integer_count = sum(1 for x in non_null_data if self._is_integer(x))
            if integer_count == numeric_count:
                return "integer"
            else:
                return "real"
        
        # Check for booleans
        boolean_count = sum(1 for x in non_null_data if self._is_boolean(x))
        if boolean_count / len(non_null_data) > 0.8:
            return "boolean"
        
        return "string"
    
    def _is_numeric(self, value: Any) -> bool:
        """Check if value is numeric"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _is_integer(self, value: Any) -> bool:
        """Check if value is integer"""
        try:
            float_val = float(value)
            return float_val.is_integer()
        except (ValueError, TypeError):
            return False
    
    def _is_boolean(self, value: Any) -> bool:
        """Check if value is boolean"""
        if isinstance(value, bool):
            return True
        if isinstance(value, str):
            return value.lower() in ["true", "false", "yes", "no", "1", "0"]
        return False
    
    def _is_date_column(self, column_data: List[Any]) -> bool:
        """Check if column contains dates"""
        sample_size = min(10, len(column_data))
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
        ]
        
        date_count = 0
        for value in column_data[:sample_size]:
            value_str = str(value)
            for pattern in date_patterns:
                if re.match(pattern, value_str):
                    date_count += 1
                    break
        
        return date_count / sample_size > 0.6  # 60% threshold


class TableauChartGenerationPostProcessor:
    """Post-processes the generated chart configuration"""
    
    def run(
        self, 
        chart_result: str, 
        sample_data: str, 
        remove_data_from_chart_config: bool = True
    ) -> Dict[str, Any]:
        """Post-process the chart generation result"""
        try:
            # Parse the JSON result
            result_dict = orjson.loads(chart_result)
            
            # Validate required fields
            if not all(key in result_dict for key in ["reasoning", "chart_type", "chart_config"]):
                raise ValueError("Missing required fields in chart result")
            
            # Clean up chart config if requested
            if remove_data_from_chart_config:
                chart_config = result_dict["chart_config"]
                if isinstance(chart_config, dict) and "data" in chart_config:
                    del chart_config["data"]
            
            # Add success indicator
            result_dict["success"] = True
            
            # Validate chart configuration
            validation_result = self._validate_chart_config(result_dict["chart_config"])
            result_dict["validation"] = validation_result
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error in post-processing: {e}")
            return {
                "reasoning": f"Post-processing error: {str(e)}",
                "chart_type": "",
                "chart_config": {},
                "success": False,
                "error": str(e)
            }
    
    def _validate_chart_config(self, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the chart configuration"""
        validation = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check for required sections
            required_sections = ["datasource", "worksheet"]
            for section in required_sections:
                if section not in chart_config:
                    validation["errors"].append(f"Missing required section: {section}")
                    validation["is_valid"] = False
            
            # Validate datasource
            if "datasource" in chart_config:
                datasource = chart_config["datasource"]
                if not isinstance(datasource.get("fields"), list):
                    validation["errors"].append("Datasource fields must be a list")
                    validation["is_valid"] = False
            
            # Validate worksheet
            if "worksheet" in chart_config:
                worksheet = chart_config["worksheet"]
                if "view" not in worksheet:
                    validation["errors"].append("Worksheet must contain a view")
                    validation["is_valid"] = False
                elif "shelf" not in worksheet["view"]:
                    validation["warnings"].append("View should contain shelf configuration")
            
        except Exception as e:
            validation["errors"].append(f"Validation error: {str(e)}")
            validation["is_valid"] = False
        
        return validation


class TableauChartExporter:
    """Exports chart configurations to various Tableau formats"""
    
    def to_tableau_json(self, chart_config: Dict[str, Any]) -> str:
        """Export to Tableau JSON format"""
        try:
            return orjson.dumps(chart_config, option=orjson.OPT_INDENT_2).decode('utf-8')
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return "{}"
    
    def to_tableau_workbook(self, chart_config: Dict[str, Any]) -> str:
        """Export to Tableau Workbook XML format (.twb)"""
        try:
            # Create root workbook element
            workbook = ET.Element("workbook")
            workbook.set("version", "18.1")
            workbook.set("source-build", "2023.1.0 (20231.23.0630.1430)")
            
            # Add data sources
            if "datasource" in chart_config:
                datasource_elem = self._create_datasource_xml(chart_config["datasource"])
                workbook.append(datasource_elem)
            
            # Add worksheets
            worksheets_elem = ET.SubElement(workbook, "worksheets")
            if "worksheet" in chart_config:
                worksheet_elem = self._create_worksheet_xml(chart_config["worksheet"])
                worksheets_elem.append(worksheet_elem)
            
            # Add windows (required for Tableau)
            windows_elem = ET.SubElement(workbook, "windows")
            window_elem = ET.SubElement(windows_elem, "window")
            window_elem.set("class", "schema")
            
            # Convert to string
            return ET.tostring(workbook, encoding='unicode')
            
        except Exception as e:
            logger.error(f"Error creating Tableau workbook: {e}")
            return "<workbook></workbook>"
    
    def to_tableau_datasource(self, chart_config: Dict[str, Any]) -> str:
        """Export to Tableau Data Source format (.tds)"""
        try:
            # Create root datasource element
            if "datasource" not in chart_config:
                return "<datasource></datasource>"
            
            datasource_elem = self._create_datasource_xml(chart_config["datasource"])
            
            return ET.tostring(datasource_elem, encoding='unicode')
            
        except Exception as e:
            logger.error(f"Error creating Tableau data source: {e}")
            return "<datasource></datasource>"
    
    def to_tableau_vql(self, chart_config: Dict[str, Any]) -> str:
        """Export to Tableau VQL (Visual Query Language) format"""
        try:
            vql_queries = []
            
            if "worksheet" in chart_config and "view" in chart_config["worksheet"]:
                view = chart_config["worksheet"]["view"]
                shelf = view.get("shelf", {})
                
                # Generate SELECT statement
                select_fields = []
                
                # Add columns
                for col in shelf.get("columns", []):
                    field_name = col.get("field", "")
                    aggregation = col.get("aggregation", "")
                    if aggregation and aggregation != "none":
                        select_fields.append(f"{aggregation.upper()}([{field_name}])")
                    else:
                        select_fields.append(f"[{field_name}]")
                
                # Add rows
                for row in shelf.get("rows", []):
                    field_name = row.get("field", "")
                    aggregation = row.get("aggregation", "")
                    if aggregation and aggregation != "none":
                        select_fields.append(f"{aggregation.upper()}([{field_name}])")
                    else:
                        select_fields.append(f"[{field_name}]")
                
                # Add other shelf items
                for shelf_type in ["color", "size", "label"]:
                    shelf_item = shelf.get(shelf_type)
                    if shelf_item and isinstance(shelf_item, dict):
                        field_name = shelf_item.get("field", "")
                        if field_name:
                            select_fields.append(f"[{field_name}]")
                
                if select_fields:
                    vql_query = f"SELECT {', '.join(select_fields)} FROM [{view.get('datasource', 'Data Source')}]"
                    vql_queries.append(vql_query)
            
            return "\n".join(vql_queries) if vql_queries else "-- No VQL generated"
            
        except Exception as e:
            logger.error(f"Error creating VQL: {e}")
            return f"-- Error generating VQL: {str(e)}"
    
    def _create_datasource_xml(self, datasource_config: Dict[str, Any]) -> ET.Element:
        """Create XML element for datasource"""
        datasource_elem = ET.Element("datasource")
        datasource_elem.set("name", datasource_config.get("name", "Data Source"))
        datasource_elem.set("connection", datasource_config.get("connection", "extract"))
        
        # Add connection info
        connection_elem = ET.SubElement(datasource_elem, "connection")
        connection_elem.set("class", "extract")
        
        # Add fields/columns
        for field in datasource_config.get("fields", []):
            column_elem = ET.SubElement(datasource_elem, "column")
            column_elem.set("name", f"[{field.get('name', '')}]")
            column_elem.set("datatype", field.get("datatype", "string"))
            column_elem.set("role", field.get("role", "dimension"))
            column_elem.set("type", field.get("type", "nominal"))
        
        return datasource_elem
    
    def _create_worksheet_xml(self, worksheet_config: Dict[str, Any]) -> ET.Element:
        """Create XML element for worksheet"""
        worksheet_elem = ET.Element("worksheet")
        worksheet_elem.set("name", worksheet_config.get("name", "Sheet 1"))
        
        if "view" in worksheet_config:
            view_elem = ET.SubElement(worksheet_elem, "table")
            view_elem.set("name", worksheet_config["view"].get("datasource", "Data Source"))
            
            # Add view configuration
            view_config = worksheet_config["view"]
            
            # Add shelf configuration
            if "shelf" in view_config:
                shelf = view_config["shelf"]
                
                # Add columns
                for col in shelf.get("columns", []):
                    col_elem = ET.SubElement(view_elem, "pane-column")
                    col_elem.text = f"[{col.get('field', '')}]"
                
                # Add rows
                for row in shelf.get("rows", []):
                    row_elem = ET.SubElement(view_elem, "pane-row")
                    row_elem.text = f"[{row.get('field', '')}]"
        
        return worksheet_elem


# Tool creation functions
def create_tableau_data_preprocessor_tool() -> BaseTool:
    """Create a tool for data preprocessing"""
    
    class TableauDataPreprocessorTool(BaseTool):
        name: str = "tableau_data_preprocessor"
        description: str = "Preprocesses data for Tableau chart generation by analyzing structure and generating metadata"
        
        def _run(self, data: str) -> str:
            try:
                data_dict = orjson.loads(data)
                preprocessor = TableauChartDataPreprocessor()
                result = preprocessor.run(data_dict)
                return orjson.dumps(result).decode('utf-8')
            except Exception as e:
                return f"Error in data preprocessing: {str(e)}"
        
        async def _arun(self, data: str) -> str:
            return self._run(data)
    
    return TableauDataPreprocessorTool()


def create_tableau_chart_postprocessor_tool() -> Tool:
    """Create Langchain tool for chart post-processing"""
    postprocessor = TableauChartGenerationPostProcessor()
    
    def postprocess_chart_func(input_json: str) -> str:
        """Post-process Tableau chart generation results"""
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
        name="tableau_chart_postprocessor",
        description="Post-processes generated Tableau chart configurations to ensure validity and format",
        func=postprocess_chart_func
    )