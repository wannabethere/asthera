#!/usr/bin/env python3
"""
Test to demonstrate LLM-based chart schema reuse functionality across all chart types:
Vega-Lite, PowerBI, Plotly, and Tableau

This test shows how the LLM can intelligently reuse existing chart schemas
across different chart libraries while maintaining consistency.
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm


class MultiChartTypeLLMReuseTest:
    """Test LLM-based chart schema reuse across multiple chart types"""
    
    @staticmethod
    def create_reusable_chart_schemas() -> Dict[str, Dict[str, Any]]:
        """Create reusable chart schemas for different chart types"""
        return {
            "vega_lite": {
                "type": "vega_lite",
                "spec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "category", "type": "nominal", "axis": {"title": "Category"}},
                        "y": {"field": "value", "type": "quantitative", "axis": {"title": "Value"}},
                        "color": {"value": "#1f77b4"}
                    }
                },
                "title": "Category Analysis - Consistent Style",
                "width": 500,
                "height": 400
            },
            "powerbi": {
                "type": "powerbi",
                "chart_type": "columnChart",
                "dataRoles": {
                    "Category": ["category"],
                    "Value": ["value"]
                },
                "fieldFormatting": {
                    "category": {"dataType": "string"},
                    "value": {"dataType": "whole", "format": "currency"}
                },
                "visualSettings": {
                    "title": "Category Analysis - Consistent Style",
                    "color": "#1f77b4"
                }
            },
            "plotly": {
                "type": "plotly",
                "data": [{
                    "type": "bar",
                    "x": "category",
                    "y": "value",
                    "marker": {"color": "#1f77b4"}
                }],
                "layout": {
                    "title": "Category Analysis - Consistent Style",
                    "xaxis": {"title": "Category"},
                    "yaxis": {"title": "Value"}
                }
            },
            "tableau": {
                "type": "tableau",
                "chart_type": "bar",
                "rows": ["category"],
                "columns": ["value"],
                "filters": {},
                "marks": {
                    "type": "bar",
                    "color": "#1f77b4"
                },
                "title": "Category Analysis - Consistent Style"
            }
        }
    
    @staticmethod
    def create_test_queries_for_chart_types() -> List[Dict[str, Any]]:
        """Create test queries for different chart types with existing schemas"""
        existing_schemas = MultiChartTypeLLMReuseTest.create_reusable_chart_schemas()
        
        return [
            {
                "chart_schema": existing_schemas["vega_lite"],
                "existing_chart_schema": existing_schemas["vega_lite"],
                "sql": "SELECT 'Product A' as category, 150000 as value UNION ALL SELECT 'Product B' as category, 200000 as value UNION ALL SELECT 'Product C' as category, 175000 as value",
                "query": "Show product sales (Vega-Lite with existing schema consideration)",
                "data_description": "Product sales data for Vega-Lite visualization",
                "project_id": "multi_chart_test",
                "chart_type": "vega_lite"
            },
            {
                "chart_schema": existing_schemas["powerbi"],
                "existing_chart_schema": existing_schemas["powerbi"],
                "sql": "SELECT 'Region North' as category, 300000 as value UNION ALL SELECT 'Region South' as category, 250000 as value UNION ALL SELECT 'Region East' as category, 275000 as value",
                "query": "Show regional revenue (PowerBI with existing schema consideration)",
                "data_description": "Regional revenue data for PowerBI visualization",
                "project_id": "multi_chart_test",
                "chart_type": "powerbi"
            },
            {
                "chart_schema": existing_schemas["plotly"],
                "existing_chart_schema": existing_schemas["plotly"],
                "sql": "SELECT 'Q1' as category, 100000 as value UNION ALL SELECT 'Q2' as category, 120000 as value UNION ALL SELECT 'Q3' as category, 110000 as value",
                "query": "Show quarterly performance (Plotly with existing schema consideration)",
                "data_description": "Quarterly performance data for Plotly visualization",
                "project_id": "multi_chart_test",
                "chart_type": "plotly"
            },
            {
                "chart_schema": existing_schemas["tableau"],
                "existing_chart_schema": existing_schemas["tableau"],
                "sql": "SELECT 'Department A' as category, 50 as value UNION ALL SELECT 'Department B' as category, 75 as value UNION ALL SELECT 'Department C' as category, 60 as value",
                "query": "Show department headcount (Tableau with existing schema consideration)",
                "data_description": "Department headcount data for Tableau visualization",
                "project_id": "multi_chart_test",
                "chart_type": "tableau"
            }
        ]


async def test_llm_reuse_across_chart_types():
    """Test LLM-based chart schema reuse across different chart types"""
    print("🧠 Testing LLM Chart Schema Reuse Across Chart Types")
    print("=" * 60)
    
    try:
        # Initialize components
        engine = EngineProvider.get_engine()
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        
        # Create dashboard streaming pipeline
        pipeline = create_dashboard_streaming_pipeline(
            engine=engine,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        # Create test queries for different chart types
        test_queries = MultiChartTypeLLMReuseTest.create_test_queries_for_chart_types()
        
        print(f"📊 Created {len(test_queries)} test queries across chart types:")
        for i, query in enumerate(test_queries):
            print(f"   {i+1}. {query['chart_type'].upper()}: {query['query']}")
        
        # Status callback to track execution
        execution_log = []
        
        def status_callback(status: str, details: Dict[str, Any]):
            execution_log.append({
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "details": details
            })
            print(f"📈 Status: {status} - {details}")
        
        # Execute the pipeline
        print(f"\n🚀 Executing pipeline with LLM chart schema reuse across chart types...")
        result = await pipeline.run(
            queries=test_queries,
            status_callback=status_callback,
            configuration={
                "concurrent_execution": False,  # Sequential for clearer analysis
                "stream_intermediate_results": True,
                "continue_on_error": True
            }
        )
        
        if result.get("post_process", {}).get("success"):
            print("✅ Pipeline execution completed successfully")
            
            # Analyze results for each chart type
            print(f"\n🔍 Analyzing Chart Schema Reuse Results by Chart Type")
            print("=" * 55)
            
            chart_type_results = {}
            
            for i, (query_key, query_result) in enumerate(result["post_process"]["results"].items()):
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    reasoning = visualization.get("reasoning", "")
                    
                    # Get the original query info
                    original_query = test_queries[i] if i < len(test_queries) else {}
                    chart_type = original_query.get("chart_type", "unknown")
                    
                    if chart_type not in chart_type_results:
                        chart_type_results[chart_type] = []
                    
                    chart_type_results[chart_type].append({
                        "query_key": query_key,
                        "title": chart_schema.get("title", "Untitled"),
                        "type": chart_schema.get("type", "Unknown"),
                        "reasoning": reasoning,
                        "original_query": original_query.get("query", "")
                    })
                    
                    print(f"\n📊 {chart_type.upper()} Chart Results:")
                    print(f"   Title: {chart_schema.get('title', 'Untitled')}")
                    print(f"   Type: {chart_schema.get('type', 'Unknown')}")
                    print(f"   Reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else f"   Reasoning: {reasoning}")
                    
                    # Check if LLM mentioned reusing existing schema
                    if "reuse" in reasoning.lower() or "existing" in reasoning.lower():
                        print("   ✅ LLM considered reusing existing chart schema")
                    elif "new" in reasoning.lower() or "generate" in reasoning.lower():
                        print("   🔄 LLM generated new chart schema")
                    else:
                        print("   ❓ LLM reasoning unclear about schema reuse")
                else:
                    print(f"\n❌ Query {i+1} failed: {query_result.get('error', 'Unknown error')}")
            
            # Summary by chart type
            print(f"\n📋 Summary by Chart Type")
            print("=" * 30)
            
            for chart_type, results in chart_type_results.items():
                print(f"\n{chart_type.upper()}:")
                print(f"   Total queries: {len(results)}")
                
                reuse_count = 0
                generate_count = 0
                
                for result in results:
                    reasoning = result["reasoning"].lower()
                    if "reuse" in reasoning or "existing" in reasoning:
                        reuse_count += 1
                    elif "new" in reasoning or "generate" in reasoning:
                        generate_count += 1
                
                print(f"   Reuse decisions: {reuse_count}")
                print(f"   Generate decisions: {generate_count}")
                print(f"   Reuse rate: {reuse_count / len(results) * 100:.1f}%" if results else "   Reuse rate: N/A")
            
            # Show execution statistics
            print(f"\n📈 Execution Statistics")
            print("=" * 25)
            print(f"Total queries: {len(test_queries)}")
            print(f"Successful queries: {sum(1 for r in result['post_process']['results'].values() if r.get('success'))}")
            print(f"Total status updates: {len(execution_log)}")
            
            # Show pipeline metrics
            pipeline_stats = pipeline.get_execution_statistics()
            print(f"\n🔧 Pipeline Metrics")
            print("=" * 20)
            print(f"Total executions: {pipeline_stats['pipeline_metrics'].get('total_executions', 0)}")
            print(f"Total queries processed: {pipeline_stats['pipeline_metrics'].get('total_queries_processed', 0)}")
            
        else:
            print("❌ Pipeline execution failed")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in multi-chart type LLM reuse test: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_chart_type_consistency():
    """Test consistency of chart schemas within the same chart type"""
    print(f"\n🔄 Testing Chart Type Consistency")
    print("=" * 40)
    
    try:
        # Initialize components
        engine = EngineProvider.get_engine()
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        
        # Create dashboard streaming pipeline
        pipeline = create_dashboard_streaming_pipeline(
            engine=engine,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        # Create multiple queries with the same chart type and existing schema
        existing_schema = MultiChartTypeLLMReuseTest.create_reusable_chart_schemas()["vega_lite"]
        
        consistency_queries = [
            {
                "chart_schema": existing_schema,
                "existing_chart_schema": existing_schema,
                "sql": "SELECT 'A' as category, 100 as value UNION ALL SELECT 'B' as category, 200 as value",
                "query": "Show data A (consistency test 1)",
                "data_description": "Test data A",
                "project_id": "consistency_test"
            },
            {
                "chart_schema": existing_schema,
                "existing_chart_schema": existing_schema,
                "sql": "SELECT 'X' as category, 300 as value UNION ALL SELECT 'Y' as category, 400 as value",
                "query": "Show data B (consistency test 2)",
                "data_description": "Test data B",
                "project_id": "consistency_test"
            },
            {
                "chart_schema": existing_schema,
                "existing_chart_schema": existing_schema,
                "sql": "SELECT 'P' as category, 500 as value UNION ALL SELECT 'Q' as category, 600 as value",
                "query": "Show data C (consistency test 3)",
                "data_description": "Test data C",
                "project_id": "consistency_test"
            }
        ]
        
        print("📊 Created 3 consistency test queries with same existing schema")
        
        # Execute pipeline
        result = await pipeline.run(
            queries=consistency_queries,
            configuration={
                "concurrent_execution": False,
                "stream_intermediate_results": True
            }
        )
        
        if result.get("post_process", {}).get("success"):
            print("✅ Consistency test completed successfully")
            
            # Analyze consistency
            chart_titles = []
            chart_types = []
            reasoning_patterns = []
            
            for query_key, query_result in result["post_process"]["results"].items():
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    reasoning = visualization.get("reasoning", "")
                    
                    chart_titles.append(chart_schema.get("title", ""))
                    chart_types.append(chart_schema.get("type", ""))
                    reasoning_patterns.append(reasoning)
            
            # Check consistency
            print(f"\n🔍 Consistency Analysis:")
            print(f"   Chart titles: {chart_titles}")
            print(f"   Chart types: {chart_types}")
            
            # Check if titles are consistent
            unique_titles = set(chart_titles)
            unique_types = set(chart_types)
            
            if len(unique_titles) == 1:
                print("   ✅ Chart titles are consistent")
            else:
                print(f"   ⚠️  Chart titles vary: {unique_titles}")
            
            if len(unique_types) == 1:
                print("   ✅ Chart types are consistent")
            else:
                print(f"   ⚠️  Chart types vary: {unique_types}")
            
            # Check reasoning patterns
            reuse_mentions = sum(1 for r in reasoning_patterns if "reuse" in r.lower() or "existing" in r.lower())
            print(f"   Reuse mentions: {reuse_mentions}/{len(reasoning_patterns)}")
            
        else:
            print("❌ Consistency test failed")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in consistency test: {e}")
        return None


async def run_multi_chart_type_tests():
    """Run all multi-chart type LLM reuse tests"""
    print("🚀 Starting Multi-Chart Type LLM Reuse Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: LLM reuse across different chart types
    results["multi_chart_reuse"] = await test_llm_reuse_across_chart_types()
    
    # Test 2: Consistency within same chart type
    results["consistency_test"] = await test_chart_type_consistency()
    
    print("\n" + "=" * 60)
    print("🎉 All multi-chart type tests completed!")
    
    # Summary
    successful_tests = sum(1 for result in results.values() if result is not None)
    total_tests = len(results)
    
    print(f"\nSummary: {successful_tests}/{total_tests} tests successful")
    
    return results


if __name__ == "__main__":
    # Run all multi-chart type tests
    asyncio.run(run_multi_chart_type_tests())
