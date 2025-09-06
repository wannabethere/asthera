#!/usr/bin/env python3
"""
Chart Template Generation Example

This example demonstrates how to use the new chart template generation functionality
to create new charts based on existing chart configurations with new data.

The example shows:
1. Creating an initial chart with sample data
2. Using that chart as a template to generate new charts with different data
3. Automatic field mapping between old and new data columns
4. Manual field mapping for more control
5. Validation and error handling

Supported chart types:
- Vega-Lite charts
- Plotly charts  
- PowerBI charts
"""

import asyncio
import orjson
from typing import Dict, Any, Optional
from app.core.dependencies import get_llm
from app.agents.nodes.sql.chart_generation import (
    VegaLiteChartGenerationPipeline,
    AdvancedVegaLiteChartGeneration
)
from app.agents.nodes.sql.plotly_chart_generation import (
    PlotlyChartGenerationPipeline,
    AdvancedPlotlyChartGeneration
)
from app.agents.nodes.sql.powerbi_chart_generation import (
    PowerBIChartGenerationPipeline
)


async def example_vega_lite_template_generation():
    """Example of Vega-Lite chart template generation"""
    print("=== Vega-Lite Chart Template Generation Example ===\n")
    
    # Initialize the pipeline
    pipeline = VegaLiteChartGenerationPipeline()
    
    # Original data for creating the template chart
    original_data = {
        "columns": ["Date", "Sales", "Region"],
        "data": [
            ["2023-01-01", 100000, "North"],
            ["2023-02-01", 120000, "North"],
            ["2023-03-01", 110000, "North"],
            ["2023-01-01", 90000, "South"],
            ["2023-02-01", 95000, "South"],
            ["2023-03-01", 105000, "South"]
        ]
    }
    
    # Create the original chart (template)
    print("1. Creating original chart template...")
    original_chart = await pipeline.run(
        query="Show sales trends by region over time",
        sql="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
        data=original_data,
        language="English"
    )
    
    print(f"Original chart type: {original_chart.get('chart_type', 'unknown')}")
    print(f"Original chart success: {original_chart.get('success', False)}")
    print(f"Original chart reasoning: {original_chart.get('reasoning', 'N/A')}")
    print()
    
    # New data with different column names
    new_data = {
        "columns": ["Timestamp", "Revenue", "Area"],
        "data": [
            ["2024-01-01", 150000, "East"],
            ["2024-02-01", 170000, "East"],
            ["2024-03-01", 160000, "East"],
            ["2024-01-01", 130000, "West"],
            ["2024-02-01", 135000, "West"],
            ["2024-03-01", 145000, "West"]
        ]
    }
    
    # Generate new chart using automatic field mapping
    print("2. Generating new chart with automatic field mapping...")
    new_chart_auto = await pipeline.generate_chart_from_template(
        existing_chart=original_chart,
        new_data=new_data,
        language="English"
    )
    
    print(f"New chart type: {new_chart_auto.get('chart_type', 'unknown')}")
    print(f"New chart success: {new_chart_auto.get('success', False)}")
    print(f"Field mapping used: {new_chart_auto.get('field_mapping', {})}")
    print(f"Template info: {new_chart_auto.get('template_info', {})}")
    print()
    
    # Generate new chart with manual field mapping
    print("3. Generating new chart with manual field mapping...")
    manual_mapping = {
        "Date": "Timestamp",
        "Sales": "Revenue", 
        "Region": "Area"
    }
    
    new_chart_manual = await pipeline.generate_chart_from_template(
        existing_chart=original_chart,
        new_data=new_data,
        field_mapping=manual_mapping,
        language="English"
    )
    
    print(f"New chart type: {new_chart_manual.get('chart_type', 'unknown')}")
    print(f"New chart success: {new_chart_manual.get('success', False)}")
    print(f"Manual field mapping: {new_chart_manual.get('field_mapping', {})}")
    print()
    
    # Show the generated chart schema
    if new_chart_manual.get('success'):
        print("4. Generated chart schema:")
        chart_schema = new_chart_manual.get('chart_schema', {})
        print(orjson.dumps(chart_schema, option=orjson.OPT_INDENT_2).decode())
    print()


async def example_plotly_template_generation():
    """Example of Plotly chart template generation"""
    print("=== Plotly Chart Template Generation Example ===\n")
    
    # Initialize the pipeline
    llm = get_llm()
    pipeline = PlotlyChartGenerationPipeline(llm)
    
    # Original data for creating the template chart
    original_data = {
        "columns": ["Product", "Sales", "Profit"],
        "data": [
            ["Product A", 100000, 25000],
            ["Product B", 150000, 30000],
            ["Product C", 80000, 15000],
            ["Product D", 120000, 28000]
        ]
    }
    
    # Create the original chart (template)
    print("1. Creating original Plotly chart template...")
    original_chart = await pipeline.run(
        query="Show sales vs profit by product",
        sql="SELECT Product, Sales, Profit FROM products",
        data=original_data,
        language="English"
    )
    
    print(f"Original chart type: {original_chart.get('chart_type', 'unknown')}")
    print(f"Original chart success: {original_chart.get('success', False)}")
    print()
    
    # New data with different structure
    new_data = {
        "columns": ["Item", "Revenue", "Margin", "Category"],
        "data": [
            ["Item 1", 200000, 50000, "Electronics"],
            ["Item 2", 180000, 45000, "Electronics"],
            ["Item 3", 160000, 40000, "Clothing"],
            ["Item 4", 140000, 35000, "Clothing"]
        ]
    }
    
    # Generate new chart using automatic field mapping
    print("2. Generating new Plotly chart with automatic field mapping...")
    new_chart = await pipeline.generate_chart_from_template(
        existing_chart=original_chart,
        new_data=new_data,
        language="English"
    )
    
    print(f"New chart type: {new_chart.get('chart_type', 'unknown')}")
    print(f"New chart success: {new_chart.get('success', False)}")
    print(f"Field mapping used: {new_chart.get('field_mapping', {})}")
    print()
    
    # Show the generated chart config
    if new_chart.get('success'):
        print("3. Generated chart config:")
        chart_config = new_chart.get('chart_config', {})
        print(orjson.dumps(chart_config, option=orjson.OPT_INDENT_2).decode())
    print()


async def example_powerbi_template_generation():
    """Example of PowerBI chart template generation"""
    print("=== PowerBI Chart Template Generation Example ===\n")
    
    # Initialize the pipeline
    llm = get_llm()
    pipeline = PowerBIChartGenerationPipeline(llm)
    
    # Original data for creating the template chart
    original_data = {
        "columns": ["Department", "Budget", "Actual"],
        "data": [
            ["Sales", 500000, 520000],
            ["Marketing", 300000, 280000],
            ["Engineering", 800000, 750000],
            ["HR", 200000, 190000]
        ]
    }
    
    # Create the original chart (template)
    print("1. Creating original PowerBI chart template...")
    original_chart = await pipeline.run(
        query="Compare budget vs actual by department",
        sql="SELECT Department, Budget, Actual FROM budget_data",
        data=original_data,
        language="English"
    )
    
    print(f"Original chart type: {original_chart.get('chart_type', 'unknown')}")
    print(f"Original chart success: {original_chart.get('success', False)}")
    print()
    
    # New data with different column names
    new_data = {
        "columns": ["Division", "Planned", "Spent"],
        "data": [
            ["R&D", 1000000, 950000],
            ["Operations", 600000, 620000],
            ["Support", 400000, 380000],
            ["Management", 300000, 310000]
        ]
    }
    
    # Generate new chart using automatic field mapping
    print("2. Generating new PowerBI chart with automatic field mapping...")
    new_chart = await pipeline.generate_chart_from_template(
        existing_chart=original_chart,
        new_data=new_data,
        language="English"
    )
    
    print(f"New chart type: {new_chart.get('chart_type', 'unknown')}")
    print(f"New chart success: {new_chart.get('success', False)}")
    print(f"Field mapping used: {new_chart.get('field_mapping', {})}")
    print()
    
    # Show the generated chart config
    if new_chart.get('success'):
        print("3. Generated chart config:")
        chart_config = new_chart.get('chart_config', {})
        print(orjson.dumps(chart_config, option=orjson.OPT_INDENT_2).decode())
    print()


async def example_advanced_template_features():
    """Example of advanced template generation features"""
    print("=== Advanced Template Generation Features ===\n")
    
    # Initialize advanced pipeline
    advanced_pipeline = AdvancedVegaLiteChartGeneration()
    
    # Create a complex template chart
    template_data = {
        "columns": ["Year", "Q1", "Q2", "Q3", "Q4"],
        "data": [
            ["2020", 100000, 120000, 110000, 130000],
            ["2021", 110000, 130000, 120000, 140000],
            ["2022", 120000, 140000, 130000, 150000]
        ]
    }
    
    print("1. Creating complex template chart...")
    template_chart = await advanced_pipeline.run(
        query="Show quarterly sales trends over years",
        sql="SELECT Year, Q1, Q2, Q3, Q4 FROM quarterly_sales",
        data=template_data,
        language="English"
    )
    
    print(f"Template chart type: {template_chart.get('chart_type', 'unknown')}")
    print(f"Template chart success: {template_chart.get('success', False)}")
    print()
    
    # Test with completely different data structure
    new_data = {
        "columns": ["Period", "Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "data": [
            ["2023", 50000, 55000, 52000, 58000, 60000, 62000],
            ["2024", 60000, 65000, 62000, 68000, 70000, 72000]
        ]
    }
    
    print("2. Testing with different data structure...")
    new_chart = await advanced_pipeline.generate_chart_from_template(
        existing_chart=template_chart,
        new_data=new_data,
        language="English"
    )
    
    print(f"New chart type: {new_chart.get('chart_type', 'unknown')}")
    print(f"New chart success: {new_chart.get('success', False)}")
    print(f"Field mapping: {new_chart.get('field_mapping', {})}")
    print()
    
    # Test error handling with incompatible data
    print("3. Testing error handling with incompatible data...")
    incompatible_data = {
        "columns": ["ID", "Name"],
        "data": [
            [1, "Item 1"],
            [2, "Item 2"]
        ]
    }
    
    error_chart = await advanced_pipeline.generate_chart_from_template(
        existing_chart=template_chart,
        new_data=incompatible_data,
        language="English"
    )
    
    print(f"Error chart success: {error_chart.get('success', False)}")
    print(f"Error message: {error_chart.get('error', 'N/A')}")
    print()


async def example_field_mapping_strategies():
    """Example of different field mapping strategies"""
    print("=== Field Mapping Strategies Example ===\n")
    
    pipeline = VegaLiteChartGenerationPipeline()
    
    # Create a simple template
    template_data = {
        "columns": ["Category", "Value"],
        "data": [
            ["A", 100],
            ["B", 200],
            ["C", 300]
        ]
    }
    
    template_chart = await pipeline.run(
        query="Show values by category",
        sql="SELECT Category, Value FROM data",
        data=template_data,
        language="English"
    )
    
    # Test different mapping scenarios
    test_cases = [
        {
            "name": "Exact match",
            "data": {
                "columns": ["Category", "Value"],
                "data": [["X", 400], ["Y", 500]]
            },
            "expected_mapping": {"Category": "Category", "Value": "Value"}
        },
        {
            "name": "Case insensitive match",
            "data": {
                "columns": ["category", "value"],
                "data": [["X", 400], ["Y", 500]]
            },
            "expected_mapping": {"Category": "category", "Value": "value"}
        },
        {
            "name": "Partial match",
            "data": {
                "columns": ["Product_Category", "Sales_Value"],
                "data": [["X", 400], ["Y", 500]]
            },
            "expected_mapping": {"Category": "Product_Category", "Value": "Sales_Value"}
        },
        {
            "name": "Semantic match",
            "data": {
                "columns": ["Type", "Amount"],
                "data": [["X", 400], ["Y", 500]]
            },
            "expected_mapping": {"Category": "Type", "Value": "Amount"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. Testing {test_case['name']}...")
        
        result = await pipeline.generate_chart_from_template(
            existing_chart=template_chart,
            new_data=test_case["data"],
            language="English"
        )
        
        print(f"   Success: {result.get('success', False)}")
        print(f"   Field mapping: {result.get('field_mapping', {})}")
        print(f"   Expected: {test_case['expected_mapping']}")
        print()


async def main():
    """Run all examples"""
    print("Chart Template Generation Examples")
    print("=" * 50)
    print()
    
    try:
        # Run all examples
        await example_vega_lite_template_generation()
        await example_plotly_template_generation()
        await example_powerbi_template_generation()
        await example_advanced_template_features()
        await example_field_mapping_strategies()
        
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
