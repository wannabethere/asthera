# Tableau Chart Generation Agent

A comprehensive system for automatically generating Tableau visualizations using LangChain and LLM agents.

## Features

- **Intelligent Chart Type Selection**: Automatically chooses the most appropriate Tableau chart type based on data and query intent
- **Data Preprocessing**: Analyzes data structure, infers data types, and generates metadata
- **Multiple Export Formats**: Supports JSON, TWB (Tableau Workbook), TDS (Tableau Data Source), and VQL formats
- **Comprehensive Chart Types**: Supports all major Tableau visualization types
- **Error Handling**: Robust error handling and validation

## Supported Chart Types

- **Bar Chart**: Comparing categories, rankings
- **Line Chart**: Trends over time, continuous data
- **Area Chart**: Cumulative trends, stacked composition
- **Scatter Plot**: Correlations, relationships
- **Pie Chart**: Part-to-whole relationships
- **Treemap**: Hierarchical data, proportional relationships
- **Heatmap**: Pattern analysis, correlation matrices
- **Histogram**: Distribution analysis
- **Box Plot**: Statistical distributions
- **Map Visualizations**: Geographic data
- **Dual Axis**: Multiple measures with different scales
- **Combined Charts**: Multiple chart types in one view

## Installation & Setup

```python
# Install required dependencies
pip install langchain orjson

# Import the main components
from tableau_chart_generation import (
    create_tableau_chart_generation_pipeline,
    generate_tableau_chart
)
```

## Basic Usage

```python
import asyncio
from langchain.llms import OpenAI

async def generate_chart_example():
    # Initialize your LLM
    llm = OpenAI(temperature=0.1)
    
    # Prepare your data
    sample_data = {
        "columns": ["Region", "Sales", "Date", "Category"],
        "data": [
            ["North", 100000, "2023-01-01", "Electronics"],
            ["South", 150000, "2023-01-01", "Clothing"],
            ["East", 120000, "2023-01-01", "Electronics"],
            ["West", 180000, "2023-01-01", "Furniture"]
        ]
    }
    
    # Generate the chart
    result = await generate_tableau_chart(
        llm=llm,
        query="Show me sales by region",
        sql="SELECT Region, SUM(Sales) as Sales FROM sales_data GROUP BY Region",
        data=sample_data,
        language="English",
        export_format="all"  # Exports to all formats
    )
    
    # Access the results
    print("Chart Type:", result["chart_type"])
    print("Reasoning:", result["reasoning"])
    print("Success:", result["success"])
    
    if result["success"]:
        # Access different export formats
        tableau_config = result["chart_config"]
        twb_workbook = result.get("twb_workbook")
        tds_datasource = result.get("tds_datasource")
        vql_query = result.get("vql_query")

# Run the example
asyncio.run(generate_chart_example())
```

## Example Chart Configurations

### Bar Chart Configuration
```json
{
    "datasource": {
        "name": "Sales Data",
        "connection": "extract",
        "fields": [
            {
                "name": "Region",
                "type": "dimension",
                "datatype": "string",
                "role": "dimension"
            },
            {
                "name": "Sales",
                "type": "measure",
                "datatype": "real",
                "role": "measure",
                "aggregation": "sum"
            }
        ]
    },
    "worksheet": {
        "name": "Sales by Region",
        "view": {
            "datasource": "Sales Data",
            "shelf": {
                "columns": [
                    {
                        "field": "Region",
                        "type": "nominal"
                    }
                ],
                "rows": [
                    {
                        "field": "Sales",
                        "type": "quantitative",
                        "aggregation": "sum"
                    }
                ],
                "color": {
                    "field": "Region",
                    "type": "nominal"
                }
            },
            "mark": {
                "type": "bar",
                "size": 5,
                "opacity": 1.0
            },
            "axes": {
                "x": {
                    "title": "Region",
                    "visible": true
                },
                "y": {
                    "title": "Sales",
                    "visible": true,
                    "format": "currency"
                }
            }
        }
    },
    "formatting": {
        "title": "Sales by Region",
        "background_color": "#ffffff"
    }
}
```

### Line Chart Configuration
```json
{
    "datasource": {
        "name": "Time Series Data",
        "connection": "extract",
        "fields": [
            {
                "name": "Date",
                "type": "dimension",
                "datatype": "date",
                "role": "dimension"
            },
            {
                "name": "Revenue",
                "type": "measure",
                "datatype": "real",
                "role": "measure",
                "aggregation": "sum"
            }
        ]
    },
    "worksheet": {
        "name": "Revenue Trend",
        "view": {
            "datasource": "Time Series Data",
            "shelf": {
                "columns": [
                    {
                        "field": "Date",
                        "type": "temporal"
                    }
                ],
                "rows": [
                    {
                        "field": "Revenue",
                        "type": "quantitative",
                        "aggregation": "sum"
                    }
                ]
            },
            "mark": {
                "type": "line",
                "size": 3,
                "opacity": 1.0
            },
            "axes": {
                "x": {
                    "title": "Date",
                    "visible": true,
                    "format": "date"
                },
                "y": {
                    "title": "Revenue",
                    "visible": true,
                    "format": "currency"
                }
            }
        }
    },
    "formatting": {
        "title": "Revenue Trend Over Time"
    }
}
```

## Advanced Usage

### Custom Pipeline Configuration
```python
from tableau_chart_generation import TableauChartGenerationPipeline

# Create a custom pipeline
pipeline = TableauChartGenerationPipeline(
    llm=your_llm,
    # Add any custom configuration here
)

# Run with specific parameters
result = await pipeline.run(
    query="Complex analytical question",
    sql="Complex SQL query",
    data=your_data,
    language="English",
    remove_data_from_chart_config=True,
    export_format="twb"  # Export as Tableau Workbook
)
```

### Data Preprocessing Only
```python
from tableau_chart_utils import TableauChartDataPreprocessor

preprocessor = TableauChartDataPreprocessor()
processed_data = preprocessor.run(your_raw_data)

print("Column Metadata:", processed_data["column_metadata"])
print("Sample Values:", processed_data["sample_column_values"])
```

### Export to Different Formats
```python
from tableau_chart_utils import TableauChartExporter

exporter = TableauChartExporter()

# Export to Tableau Workbook XML
twb_content = exporter.to_tableau_workbook(chart_config)

# Export to Tableau Data Source
tds_content = exporter.to_tableau_datasource(chart_config)

# Export to VQL
vql_query = exporter.to_tableau_vql(chart_config)

# Export to JSON
json_config = exporter.to_tableau_json(chart_config)
```

## Error Handling

The system includes comprehensive error handling:

```python
result = await generate_tableau_chart(llm, query, sql, data)

if not result["success"]:
    print("Error:", result["error"])
    print("Reasoning:", result["reasoning"])
else:
    # Process successful result
    chart_config = result["chart_config"]
    validation = result.get("validation", {})
    
    if not validation.get("is_valid", True):
        print("Validation errors:", validation["errors"])
        print("Validation warnings:", validation["warnings"])
```

## Customization

### Adding Custom Chart Types
You can extend the system by adding custom chart types in the instructions:

```python
# Modify tableau_chart_generation_instructions to include custom types
custom_instructions = tableau_chart_generation_instructions + """
## Custom Chart Types:
- **Custom Type**: Description and use cases
"""
```

### Custom Data Preprocessing
```python
class CustomTableauDataPreprocessor(TableauChartDataPreprocessor):
    def run(self, data):
        # Add custom preprocessing logic
        result = super().run(data)
        # Add custom fields
        result["custom_field"] = self.custom_analysis(data)
        return result
```

## Best Practices

1. **Data Quality**: Ensure your data is clean and properly structured
2. **Query Clarity**: Provide clear, specific questions for better chart selection
3. **Data Types**: Ensure proper data type inference by formatting your data consistently
4. **Performance**: For large datasets, consider sampling or aggregation before chart generation
5. **Validation**: Always check the validation results before using the generated configuration

## Integration with Tableau

The generated configurations can be used with:

- **Tableau Server**: Upload TWB files directly
- **Tableau Desktop**: Import TDS data sources and workbooks
- **Tableau Public**: Use JSON configurations for web-based visualizations
- **Tableau API**: Programmatically create visualizations using the generated configs

## Troubleshooting

### Common Issues

1. **Field Validation Errors**: Ensure all field names in your data match the SQL column names
2. **Data Type Mismatches**: Check that numeric fields are properly formatted
3. **Empty Results**: Verify that your data contains sufficient non-null values
4. **Export Failures**: Check that the chart configuration is valid before exporting

### Debug Mode

Enable verbose logging for debugging:

```python
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)
```