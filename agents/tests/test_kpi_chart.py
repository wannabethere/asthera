#!/usr/bin/env python3
"""
Test script for KPI chart generation

This script demonstrates the KPI chart functionality including:
- Single KPI metrics
- Multiple KPI metrics with targets
- KPI data with units
- Edge cases for KPI identification

Usage:
    python test_kpi_chart.py
"""

import asyncio
import json
import logging
from typing import Dict, Any, List

from agents.app.agents.nodes.sql.enhanced_chart_generation import (
    EnhancedVegaLiteChartGenerationPipeline,
    generate_enhanced_chart
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Sample KPI data for different scenarios
KPI_SAMPLE_DATA = {
    "single_kpi": {
        "columns": ["Total_Sales"],
        "data": [
            {"Total_Sales": 1500000}
        ]
    },
    "multiple_kpis": {
        "columns": ["Metric", "Value", "Target", "Unit"],
        "data": [
            {"Metric": "Total Sales", "Value": 1500000, "Target": 2000000, "Unit": "USD"},
            {"Metric": "Conversion Rate", "Value": 0.15, "Target": 0.20, "Unit": "%"},
            {"Metric": "Customer Satisfaction", "Value": 4.2, "Target": 4.5, "Unit": "stars"},
            {"Metric": "Monthly Active Users", "Value": 50000, "Target": 60000, "Unit": "users"}
        ]
    },
    "kpi_without_targets": {
        "columns": ["KPI_Name", "Current_Value", "Unit"],
        "data": [
            {"KPI_Name": "Revenue", "Current_Value": 2500000, "Unit": "USD"},
            {"KPI_Name": "Profit Margin", "Current_Value": 0.25, "Unit": "%"},
            {"KPI_Name": "Customer Count", "Current_Value": 15000, "Unit": "customers"}
        ]
    },
    "simple_numeric": {
        "columns": ["Sales", "Profit"],
        "data": [
            {"Sales": 1000000, "Profit": 250000}
        ]
    },
    "mixed_data": {
        "columns": ["Department", "Budget", "Spent", "Efficiency"],
        "data": [
            {"Department": "Marketing", "Budget": 500000, "Spent": 450000, "Efficiency": 0.90},
            {"Department": "Sales", "Budget": 800000, "Spent": 750000, "Efficiency": 0.94},
            {"Department": "R&D", "Budget": 1200000, "Spent": 1100000, "Efficiency": 0.92}
        ]
    }
}


async def test_single_kpi():
    """Test single KPI chart generation"""
    print("\n" + "="*50)
    print("TESTING SINGLE KPI")
    print("="*50)
    
    query = "Show me the total sales"
    sql = "SELECT Total_Sales FROM sales_summary"
    data = KPI_SAMPLE_DATA["single_kpi"]
    
    result = await generate_enhanced_chart(
        query=query,
        sql=sql,
        data=data,
        language="English",
        include_reasoning=True
    )
    
    print(f"Chart Type: {result.get('chart_type', 'N/A')}")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    
    if result.get('chart_schema', {}).get('kpi_metadata'):
        kpi_meta = result['chart_schema']['kpi_metadata']
        print(f"KPI Metadata:")
        print(f"  - Is Dummy: {kpi_meta.get('is_dummy', 'N/A')}")
        print(f"  - Description: {kpi_meta.get('description', 'N/A')}")
        print(f"  - Vega-Lite Compatible: {kpi_meta.get('vega_lite_compatible', 'N/A')}")
        print(f"  - Requires Custom Template: {kpi_meta.get('requires_custom_template', 'N/A')}")
        
        kpi_data = kpi_meta.get('kpi_data', {})
        print(f"KPI Data:")
        print(f"  - Metrics: {kpi_data.get('metrics', [])}")
        print(f"  - Values: {kpi_data.get('values', [])}")
        print(f"  - Targets: {kpi_data.get('targets', [])}")
        print(f"  - Units: {kpi_data.get('units', [])}")
    
    if result.get('chart_schema'):
        print("Chart Schema:")
        print(json.dumps(result['chart_schema'], indent=2))


async def test_multiple_kpis():
    """Test multiple KPI chart generation"""
    print("\n" + "="*50)
    print("TESTING MULTIPLE KPIS")
    print("="*50)
    
    query = "Show me the key performance indicators with their targets"
    sql = "SELECT Metric, Value, Target, Unit FROM kpi_dashboard"
    data = KPI_SAMPLE_DATA["multiple_kpis"]
    
    result = await generate_enhanced_chart(
        query=query,
        sql=sql,
        data=data,
        language="English",
        include_reasoning=True
    )
    
    print(f"Chart Type: {result.get('chart_type', 'N/A')}")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    
    if result.get('chart_schema', {}).get('kpi_metadata'):
        kpi_meta = result['chart_schema']['kpi_metadata']
        kpi_data = kpi_meta.get('kpi_data', {})
        print(f"KPI Data Extracted:")
        print(f"  - Metrics: {kpi_data.get('metrics', [])}")
        print(f"  - Values: {kpi_data.get('values', [])}")
        print(f"  - Targets: {kpi_data.get('targets', [])}")
        print(f"  - Units: {kpi_data.get('units', [])}")
    
    if result.get('enhanced_metadata'):
        metadata = result['enhanced_metadata']
        print(f"Alternative Charts: {metadata.get('alternative_charts', [])}")
        print(f"Chart Selection Reasoning: {metadata.get('chart_selection_reasoning', 'N/A')}")


async def test_kpi_without_targets():
    """Test KPI chart generation without targets"""
    print("\n" + "="*50)
    print("TESTING KPI WITHOUT TARGETS")
    print("="*50)
    
    query = "Display the current KPI values"
    sql = "SELECT KPI_Name, Current_Value, Unit FROM current_kpis"
    data = KPI_SAMPLE_DATA["kpi_without_targets"]
    
    result = await generate_enhanced_chart(
        query=query,
        sql=sql,
        data=data,
        language="English",
        include_reasoning=True
    )
    
    print(f"Chart Type: {result.get('chart_type', 'N/A')}")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    
    if result.get('chart_schema', {}).get('kpi_metadata'):
        kpi_meta = result['chart_schema']['kpi_metadata']
        kpi_data = kpi_meta.get('kpi_data', {})
        print(f"KPI Data Extracted:")
        print(f"  - Metrics: {kpi_data.get('metrics', [])}")
        print(f"  - Values: {kpi_data.get('values', [])}")
        print(f"  - Targets: {kpi_data.get('targets', [])}")
        print(f"  - Units: {kpi_data.get('units', [])}")


async def test_simple_numeric():
    """Test KPI identification with simple numeric data"""
    print("\n" + "="*50)
    print("TESTING SIMPLE NUMERIC DATA")
    print("="*50)
    
    query = "What are the sales and profit numbers?"
    sql = "SELECT Sales, Profit FROM financial_summary"
    data = KPI_SAMPLE_DATA["simple_numeric"]
    
    result = await generate_enhanced_chart(
        query=query,
        sql=sql,
        data=data,
        language="English",
        include_reasoning=True
    )
    
    print(f"Chart Type: {result.get('chart_type', 'N/A')}")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    
    if result.get('enhanced_metadata'):
        metadata = result['enhanced_metadata']
        print(f"Data Analysis: {metadata.get('data_analysis', 'N/A')}")
        print(f"Alternative Charts: {metadata.get('alternative_charts', [])}")


async def test_mixed_data():
    """Test KPI identification with mixed data types"""
    print("\n" + "="*50)
    print("TESTING MIXED DATA")
    print("="*50)
    
    query = "Show department budgets and efficiency metrics"
    sql = "SELECT Department, Budget, Spent, Efficiency FROM department_metrics"
    data = KPI_SAMPLE_DATA["mixed_data"]
    
    result = await generate_enhanced_chart(
        query=query,
        sql=sql,
        data=data,
        language="English",
        include_reasoning=True
    )
    
    print(f"Chart Type: {result.get('chart_type', 'N/A')}")
    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    
    if result.get('enhanced_metadata'):
        metadata = result['enhanced_metadata']
        print(f"Data Analysis: {metadata.get('data_analysis', 'N/A')}")
        print(f"Alternative Charts: {metadata.get('alternative_charts', [])}")


async def test_kpi_edge_cases():
    """Test KPI chart edge cases"""
    print("\n" + "="*50)
    print("TESTING KPI EDGE CASES")
    print("="*50)
    
    # Test with empty data
    print("\n--- Empty Data Test ---")
    empty_data = {"columns": [], "data": []}
    result = await generate_enhanced_chart(
        query="Show KPIs",
        sql="SELECT * FROM empty_table",
        data=empty_data,
        language="English"
    )
    print(f"Empty Data Result: {result.get('chart_type', 'N/A')}")
    
    # Test with single row, multiple columns
    print("\n--- Single Row, Multiple Columns Test ---")
    single_row_data = {
        "columns": ["Metric1", "Metric2", "Metric3"],
        "data": [{"Metric1": 100, "Metric2": 200, "Metric3": 300}]
    }
    result = await generate_enhanced_chart(
        query="Show metrics",
        sql="SELECT Metric1, Metric2, Metric3 FROM metrics",
        data=single_row_data,
        language="English"
    )
    print(f"Single Row Result: {result.get('chart_type', 'N/A')}")
    
    # Test with non-numeric data
    print("\n--- Non-numeric Data Test ---")
    non_numeric_data = {
        "columns": ["Name", "Status", "Category"],
        "data": [
            {"Name": "Project A", "Status": "Active", "Category": "Development"},
            {"Name": "Project B", "Status": "Completed", "Category": "Testing"}
        ]
    }
    result = await generate_enhanced_chart(
        query="Show project status",
        sql="SELECT Name, Status, Category FROM projects",
        data=non_numeric_data,
        language="English"
    )
    print(f"Non-numeric Result: {result.get('chart_type', 'N/A')}")


async def test_pipeline_kpi():
    """Test KPI chart generation using the pipeline"""
    print("\n" + "="*50)
    print("TESTING PIPELINE KPI GENERATION")
    print("="*50)
    
    pipeline = EnhancedVegaLiteChartGenerationPipeline()
    
    query = "Display key performance indicators"
    sql = "SELECT Metric, Value, Target, Unit FROM kpi_dashboard"
    data = KPI_SAMPLE_DATA["multiple_kpis"]
    
    result = await pipeline.run(
        query=query,
        sql=sql,
        data=data,
        language="English",
        remove_data_from_chart_schema=True
    )
    
    print(f"Pipeline Result:")
    print(f"Chart Type: {result.get('chart_type', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    print(f"Error: {result.get('error', 'None')}")
    
    if result.get('chart_schema', {}).get('kpi_metadata'):
        kpi_meta = result['chart_schema']['kpi_metadata']
        print(f"KPI Metadata Present: {kpi_meta.get('chart_type') == 'kpi'}")


async def main():
    """Run all KPI chart tests"""
    print("KPI Chart Generation System Test")
    print("="*60)
    
    try:
        # Test different KPI scenarios
        await test_single_kpi()
        await test_multiple_kpis()
        await test_kpi_without_targets()
        await test_simple_numeric()
        await test_mixed_data()
        await test_kpi_edge_cases()
        await test_pipeline_kpi()
        
        print("\n" + "="*60)
        print("ALL KPI TESTS COMPLETED")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Error running KPI tests: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 