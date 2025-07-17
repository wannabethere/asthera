#!/usr/bin/env python3
"""
Test script for enhanced chart generation pipeline integration

This script demonstrates how to use the enhanced chart generation pipeline
with support for KPI charts and other advanced chart types.

Usage:
    python test_enhanced_chart_pipeline.py
"""

import asyncio
import json
import logging
from typing import Dict, Any

from app.agents.pipelines.sql_pipelines import ChartGenerationPipeline
from app.core.dependencies import get_llm
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.provider import DocumentStoreProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Sample data for different chart types
SAMPLE_DATA = {
    "kpi_data": {
        "columns": ["Metric", "Value", "Target", "Unit"],
        "data": [
            {"Metric": "Total Sales", "Value": 1500000, "Target": 2000000, "Unit": "USD"},
            {"Metric": "Conversion Rate", "Value": 0.15, "Target": 0.20, "Unit": "%"},
            {"Metric": "Customer Satisfaction", "Value": 4.2, "Target": 4.5, "Unit": "stars"}
        ]
    },
    "scatter_data": {
        "columns": ["Sales", "Profit", "Region"],
        "data": [
            {"Sales": 100000, "Profit": 25000, "Region": "North"},
            {"Sales": 150000, "Profit": 30000, "Region": "South"},
            {"Sales": 120000, "Profit": 20000, "Region": "East"},
            {"Sales": 180000, "Profit": 35000, "Region": "West"}
        ]
    },
    "heatmap_data": {
        "columns": ["Month", "Region", "Sales"],
        "data": [
            {"Month": "Jan", "Region": "North", "Sales": 100000},
            {"Month": "Jan", "Region": "South", "Sales": 120000},
            {"Month": "Feb", "Region": "North", "Sales": 110000},
            {"Month": "Feb", "Region": "South", "Sales": 130000}
        ]
    }
}


async def test_enhanced_chart_generation():
    """Test enhanced chart generation with KPI support"""
    print("\n" + "="*60)
    print("TESTING ENHANCED CHART GENERATION PIPELINE")
    print("="*60)
    
    # Initialize dependencies
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    document_store_provider = DocumentStoreProvider()
    
    # Create enhanced chart generation pipeline
    pipeline = ChartGenerationPipeline(
        llm=llm,
        retrieval_helper=retrieval_helper,
        document_store_provider=document_store_provider,
        chart_config={"type": "enhanced_vega_lite"}  # Use enhanced Vega-Lite
    )
    
    # Test KPI chart generation
    print("\n--- Testing KPI Chart Generation ---")
    kpi_result = await pipeline.run(
        query="Show me the key performance indicators",
        sql="SELECT Metric, Value, Target, Unit FROM kpi_dashboard",
        data=SAMPLE_DATA["kpi_data"],
        language="English"
    )
    
    print(f"KPI Chart Result:")
    print(f"  Success: {kpi_result.get('success', False)}")
    print(f"  Chart Type: {kpi_result.get('data', {}).get('chart_type', 'N/A')}")
    print(f"  Reasoning: {kpi_result.get('data', {}).get('reasoning', 'N/A')}")
    
    if kpi_result.get('data', {}).get('kpi_metadata'):
        kpi_meta = kpi_result['data']['kpi_metadata']
        print(f"  KPI Metadata:")
        print(f"    - Is Dummy: {kpi_meta.get('is_dummy', 'N/A')}")
        print(f"    - Description: {kpi_meta.get('description', 'N/A')}")
        print(f"    - Requires Custom Template: {kpi_meta.get('requires_custom_template', 'N/A')}")
    
    # Test scatter chart generation
    print("\n--- Testing Scatter Chart Generation ---")
    scatter_result = await pipeline.run(
        query="Show the relationship between sales and profit by region",
        sql="SELECT Sales, Profit, Region FROM sales_data",
        data=SAMPLE_DATA["scatter_data"],
        language="English"
    )
    
    print(f"Scatter Chart Result:")
    print(f"  Success: {scatter_result.get('success', False)}")
    print(f"  Chart Type: {scatter_result.get('data', {}).get('chart_type', 'N/A')}")
    print(f"  Reasoning: {scatter_result.get('data', {}).get('reasoning', 'N/A')}")
    
    if scatter_result.get('data', {}).get('enhanced_metadata'):
        enhanced_meta = scatter_result['data']['enhanced_metadata']
        print(f"  Enhanced Metadata:")
        print(f"    - Data Analysis: {enhanced_meta.get('data_analysis', 'N/A')}")
        print(f"    - Alternative Charts: {enhanced_meta.get('alternative_charts', [])}")
    
    # Test heatmap chart generation
    print("\n--- Testing Heatmap Chart Generation ---")
    heatmap_result = await pipeline.run(
        query="Show sales intensity across months and regions",
        sql="SELECT Month, Region, Sales FROM sales_data",
        data=SAMPLE_DATA["heatmap_data"],
        language="English"
    )
    
    print(f"Heatmap Chart Result:")
    print(f"  Success: {heatmap_result.get('success', False)}")
    print(f"  Chart Type: {heatmap_result.get('data', {}).get('chart_type', 'N/A')}")
    print(f"  Reasoning: {heatmap_result.get('data', {}).get('reasoning', 'N/A')}")


async def test_chart_config_options():
    """Test different chart configuration options"""
    print("\n" + "="*60)
    print("TESTING CHART CONFIGURATION OPTIONS")
    print("="*60)
    
    # Initialize dependencies
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    document_store_provider = DocumentStoreProvider()
    
    # Test with default config (should use enhanced Vega-Lite)
    print("\n--- Testing Default Config (Enhanced Vega-Lite) ---")
    default_pipeline = ChartGenerationPipeline(
        llm=llm,
        retrieval_helper=retrieval_helper,
        document_store_provider=document_store_provider
    )
    
    result = await default_pipeline.run(
        query="Show me the total sales",
        sql="SELECT Total_Sales FROM sales_summary",
        data={"columns": ["Total_Sales"], "data": [{"Total_Sales": 1500000}]},
        language="English"
    )
    
    print(f"Default Config Result:")
    print(f"  Success: {result.get('success', False)}")
    print(f"  Chart Type: {result.get('data', {}).get('chart_type', 'N/A')}")
    
    # Test with explicit enhanced Vega-Lite config
    print("\n--- Testing Explicit Enhanced Vega-Lite Config ---")
    enhanced_pipeline = ChartGenerationPipeline(
        llm=llm,
        retrieval_helper=retrieval_helper,
        document_store_provider=document_store_provider,
        chart_config={"type": "enhanced_vega_lite"}
    )
    
    result = await enhanced_pipeline.run(
        query="Show me the total sales",
        sql="SELECT Total_Sales FROM sales_summary",
        data={"columns": ["Total_Sales"], "data": [{"Total_Sales": 1500000}]},
        language="English"
    )
    
    print(f"Enhanced Config Result:")
    print(f"  Success: {result.get('success', False)}")
    print(f"  Chart Type: {result.get('data', {}).get('chart_type', 'N/A')}")


async def test_pipeline_integration():
    """Test pipeline integration with different data types"""
    print("\n" + "="*60)
    print("TESTING PIPELINE INTEGRATION")
    print("="*60)
    
    # Initialize dependencies
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    document_store_provider = DocumentStoreProvider()
    
    # Create pipeline
    pipeline = ChartGenerationPipeline(
        llm=llm,
        retrieval_helper=retrieval_helper,
        document_store_provider=document_store_provider,
        chart_config={"type": "enhanced_vega_lite"}
    )
    
    # Test with different query types
    test_cases = [
        {
            "name": "KPI Query",
            "query": "What are our key performance indicators?",
            "sql": "SELECT Metric, Value, Target, Unit FROM kpi_dashboard",
            "data": SAMPLE_DATA["kpi_data"]
        },
        {
            "name": "Relationship Query",
            "query": "Show sales vs profit correlation",
            "sql": "SELECT Sales, Profit, Region FROM sales_data",
            "data": SAMPLE_DATA["scatter_data"]
        },
        {
            "name": "Distribution Query",
            "query": "Show sales distribution by month and region",
            "sql": "SELECT Month, Region, Sales FROM sales_data",
            "data": SAMPLE_DATA["heatmap_data"]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing {test_case['name']} ---")
        
        result = await pipeline.run(
            query=test_case["query"],
            sql=test_case["sql"],
            data=test_case["data"],
            language="English"
        )
        
        print(f"  Success: {result.get('success', False)}")
        print(f"  Chart Type: {result.get('data', {}).get('chart_type', 'N/A')}")
        print(f"  Reasoning: {result.get('data', {}).get('reasoning', 'N/A')[:100]}...")
        
        # Check for enhanced features
        if result.get('data', {}).get('enhanced_metadata'):
            print(f"  Enhanced Metadata: Available")
        if result.get('data', {}).get('kpi_metadata'):
            print(f"  KPI Metadata: Available")


async def main():
    """Run all tests"""
    print("Enhanced Chart Generation Pipeline Integration Test")
    print("="*80)
    
    try:
        await test_enhanced_chart_generation()
        await test_chart_config_options()
        await test_pipeline_integration()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 