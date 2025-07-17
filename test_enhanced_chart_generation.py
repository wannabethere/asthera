#!/usr/bin/env python3
"""
Test script for enhanced chart generation system
Demonstrates the new chart types and capabilities
"""

import asyncio
import json
from typing import Dict, Any, List

# Mock data for testing different chart types
TEST_DATA = {
    "scatter_data": {
        "columns": ["Sales", "Profit", "Region"],
        "data": [
            [100000, 25000, "North"],
            [150000, 30000, "South"],
            [120000, 20000, "East"],
            [180000, 35000, "West"],
            [90000, 15000, "North"],
            [200000, 40000, "South"]
        ]
    },
    "heatmap_data": {
        "columns": ["Month", "Region", "Sales"],
        "data": [
            ["Jan", "North", 100000],
            ["Jan", "South", 120000],
            ["Feb", "North", 110000],
            ["Feb", "South", 130000],
            ["Mar", "North", 105000],
            ["Mar", "South", 125000]
        ]
    },
    "boxplot_data": {
        "columns": ["Department", "Salary"],
        "data": [
            ["Sales", 50000],
            ["Sales", 55000],
            ["Sales", 45000],
            ["IT", 70000],
            ["IT", 75000],
            ["IT", 65000],
            ["HR", 45000],
            ["HR", 50000],
            ["HR", 40000]
        ]
    },
    "histogram_data": {
        "columns": ["Age"],
        "data": [
            [25], [30], [35], [28], [32], [27], [40], [33], [29], [31],
            [26], [34], [36], [38], [24], [39], [37], [41], [42], [23]
        ]
    },
    "bubble_data": {
        "columns": ["Sales", "Profit", "Market_Size", "Region"],
        "data": [
            [100000, 25000, 1000000, "North"],
            [150000, 30000, 1500000, "South"],
            [120000, 20000, 800000, "East"],
            [180000, 35000, 2000000, "West"]
        ]
    },
    "time_series_data": {
        "columns": ["Date", "Revenue", "Costs"],
        "data": [
            ["2023-01-01", 100000, 80000],
            ["2023-02-01", 120000, 90000],
            ["2023-03-01", 110000, 85000],
            ["2023-04-01", 140000, 100000],
            ["2023-05-01", 130000, 95000],
            ["2023-06-01", 160000, 110000]
        ]
    }
}

# Test queries for different chart types
TEST_QUERIES = {
    "scatter": "Show the relationship between sales and profit by region",
    "heatmap": "Create a heatmap showing sales by month and region",
    "boxplot": "Show the salary distribution by department",
    "histogram": "Display the age distribution of employees",
    "bubble": "Show sales vs profit vs market size by region",
    "time_series": "Show revenue and costs trends over time"
}

# Mock SQL queries
TEST_SQL = {
    "scatter": "SELECT Sales, Profit, Region FROM sales_data GROUP BY Region",
    "heatmap": "SELECT Month, Region, SUM(Sales) as Sales FROM sales_data GROUP BY Month, Region",
    "boxplot": "SELECT Department, Salary FROM employee_data",
    "histogram": "SELECT Age FROM employee_data",
    "bubble": "SELECT Sales, Profit, Market_Size, Region FROM market_data",
    "time_series": "SELECT Date, Revenue, Costs FROM financial_data ORDER BY Date"
}


async def test_enhanced_chart_generation():
    """Test the enhanced chart generation system"""
    
    print("🚀 Testing Enhanced Chart Generation System")
    print("=" * 50)
    
    # Import the enhanced chart generation functions
    try:
        from agents.app.agents.nodes.sql.enhanced_chart_generation import (
            generate_enhanced_chart,
            generate_chart_with_template
        )
        from agents.app.agents.nodes.sql.utils.enhanced_chart import (
            create_enhanced_chart_from_existing_schema,
            fix_and_prepare_enhanced_chart_schema
        )
        print("✅ Successfully imported enhanced chart generation modules")
    except ImportError as e:
        print(f"❌ Error importing modules: {e}")
        return
    
    # Test different chart types
    for chart_type, query in TEST_QUERIES.items():
        print(f"\n📊 Testing {chart_type.upper()} chart generation")
        print("-" * 30)
        
        try:
            # Get test data
            data = TEST_DATA[f"{chart_type}_data"]
            sql = TEST_SQL[chart_type]
            
            print(f"Query: {query}")
            print(f"SQL: {sql}")
            print(f"Data shape: {len(data['data'])} rows, {len(data['columns'])} columns")
            
            # Generate chart
            result = await generate_enhanced_chart(
                query=query,
                sql=sql,
                data=data,
                language="English",
                include_reasoning=True
            )
            
            if result.get("success", False):
                primary_chart = result.get("primary_chart", {})
                print(f"✅ Chart type: {primary_chart.get('chart_type', 'unknown')}")
                print(f"✅ Success: {primary_chart.get('success', False)}")
                
                if primary_chart.get("chart_schema"):
                    schema = primary_chart["chart_schema"]
                    mark_type = schema.get("mark", {}).get("type", "unknown")
                    print(f"✅ Mark type: {mark_type}")
                    
                    # Show encoding channels
                    encoding = schema.get("encoding", {})
                    channels = list(encoding.keys())
                    print(f"✅ Encoding channels: {channels}")
                
                # Show reasoning
                reasoning = result.get("reasoning", "No reasoning provided")
                print(f"📝 Reasoning: {reasoning[:100]}...")
                
                # Show analysis suggestions
                suggestions = result.get("analysis_suggestions", [])
                if suggestions:
                    print(f"💡 Analysis suggestions: {suggestions}")
                
                # Show alternative charts
                alternatives = result.get("alternative_charts", [])
                if alternatives:
                    print(f"🔄 Alternative charts: {len(alternatives)} available")
                
            else:
                print(f"❌ Failed to generate chart: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error testing {chart_type}: {e}")
    
    # Test template-based generation
    print(f"\n🎯 Testing template-based chart generation")
    print("-" * 40)
    
    try:
        # Test correlation analysis template
        result = await generate_chart_with_template(
            query="Show correlation between sales and profit",
            sql="SELECT Sales, Profit FROM sales_data",
            data=TEST_DATA["scatter_data"],
            template_name="correlation_analysis",
            language="English"
        )
        
        if result.get("success", False):
            print("✅ Template-based generation successful")
            print(f"📊 Used template: {result.get('used_template', 'unknown')}")
            print(f"📝 Template description: {result.get('template_description', 'No description')}")
        else:
            print(f"❌ Template-based generation failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing template-based generation: {e}")
    
    print(f"\n🎉 Enhanced chart generation testing completed!")


async def test_chart_schema_fixing():
    """Test the chart schema fixing functionality"""
    
    print(f"\n🔧 Testing Chart Schema Fixing")
    print("=" * 30)
    
    try:
        from agents.app.agents.nodes.sql.utils.enhanced_chart import (
            fix_and_prepare_enhanced_chart_schema
        )
        
        # Test with a basic chart schema that needs fixing
        test_schema = {
            "mark": "bar",  # Should be {"type": "bar"}
            "encoding": {
                "x": {"field": "Region"},  # Missing type
                "y": {"field": "Sales"}    # Missing type
            }
        }
        
        test_data = [
            {"Region": "North", "Sales": 100000},
            {"Region": "South", "Sales": 150000}
        ]
        
        print("Testing schema fixing with basic bar chart...")
        result = fix_and_prepare_enhanced_chart_schema(test_schema, test_data)
        
        if result.get("success", False):
            print("✅ Schema fixing successful")
            fixed_schema = result.get("chart_schema", {})
            print(f"📊 Chart type: {result.get('chart_type', 'unknown')}")
            print(f"🔧 Fixed mark: {fixed_schema.get('mark', {})}")
            
            encoding = fixed_schema.get("encoding", {})
            for channel, enc in encoding.items():
                if isinstance(enc, dict):
                    print(f"🔧 Fixed {channel}: {enc}")
        else:
            print(f"❌ Schema fixing failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing schema fixing: {e}")


def print_available_chart_types():
    """Print information about available chart types"""
    
    print(f"\n📋 Available Enhanced Chart Types")
    print("=" * 35)
    
    chart_types = {
        "bar": "Bar chart for comparing categories",
        "line": "Line chart for trends over time",
        "area": "Area chart emphasizing volume over time",
        "scatter": "Scatter plot for correlation analysis",
        "heatmap": "Heatmap for density visualization",
        "boxplot": "Box plot for statistical distribution",
        "histogram": "Histogram for frequency distribution",
        "bubble": "Bubble chart for 3-variable relationships",
        "pie": "Pie chart for proportions",
        "grouped_bar": "Grouped bar chart for sub-categories",
        "stacked_bar": "Stacked bar chart for composition",
        "multi_line": "Multi-line chart for multiple trends",
        "text": "Text plot for labels and annotations",
        "tick": "Tick plot for distribution visualization",
        "rule": "Rule plot for reference lines"
    }
    
    for chart_type, description in chart_types.items():
        print(f"• {chart_type:15} - {description}")


def print_available_templates():
    """Print information about available templates"""
    
    print(f"\n🎨 Available Analysis Templates")
    print("=" * 30)
    
    templates = {
        "correlation_analysis": "Shows correlation between two variables",
        "distribution_analysis": "Shows distribution of a variable",
        "statistical_comparison": "Shows statistical distribution and outliers",
        "density_visualization": "Shows density or correlation matrix",
        "multi_dimensional_analysis": "Shows relationship between three variables",
        "time_series_analysis": "Shows trends over time",
        "composition_analysis": "Shows composition within categories"
    }
    
    for template, description in templates.items():
        print(f"• {template:25} - {description}")


async def main():
    """Main test function"""
    
    print("🧪 Enhanced Chart Generation System Test Suite")
    print("=" * 55)
    
    # Print available chart types and templates
    print_available_chart_types()
    print_available_templates()
    
    # Test chart generation
    await test_enhanced_chart_generation()
    
    # Test schema fixing
    await test_chart_schema_fixing()
    
    print(f"\n✨ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main()) 