#!/usr/bin/env python3
"""
Test to demonstrate LLM-based chart schema reuse functionality.

This test shows how the LLM can intelligently reuse existing chart schemas
when appropriate, providing consistency while still allowing for adaptation
when needed.
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm


class LLMChartSchemaReuseTest:
    """Test LLM-based chart schema reuse functionality"""
    
    @staticmethod
    def create_reusable_chart_schema() -> Dict[str, Any]:
        """Create a chart schema that can be reused across similar queries"""
        return {
            "type": "vega_lite",
            "spec": {
                "mark": "bar",
                "encoding": {
                    "x": {"field": "category", "type": "nominal", "axis": {"title": "Category"}},
                    "y": {"field": "value", "type": "quantitative", "axis": {"title": "Value"}},
                    "color": {"value": "#1f77b4"}
                }
            },
            "title": "Category Analysis Chart",
            "width": 500,
            "height": 400,
            "description": "A reusable bar chart for category-based analysis"
        }
    
    @staticmethod
    def create_test_queries_with_existing_schema() -> List[Dict[str, Any]]:
        """Create test queries with existing chart schemas for LLM consideration"""
        existing_schema = LLMChartSchemaReuseTest.create_reusable_chart_schema()
        
        return [
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "department", "type": "nominal", "axis": {"title": "Department"}},
                            "y": {"field": "employee_count", "type": "quantitative", "axis": {"title": "Employee Count"}},
                            "color": {"value": "#2E8B57"}
                        }
                    },
                    "title": "Employee Count by Department",
                    "width": 500,
                    "height": 400
                },
                "existing_chart_schema": existing_schema,  # LLM will consider this for reuse
                "sql": "SELECT 'Engineering' as department, 45 as employee_count UNION ALL SELECT 'Sales' as department, 32 as employee_count UNION ALL SELECT 'Marketing' as department, 18 as employee_count",
                "query": "Show employee count by department (consider reusing existing chart style)",
                "data_description": "Employee distribution across departments",
                "project_id": "llm_reuse_test"
            },
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "line",
                        "encoding": {
                            "x": {"field": "month", "type": "temporal", "axis": {"title": "Month"}},
                            "y": {"field": "revenue", "type": "quantitative", "axis": {"title": "Revenue ($)"}},
                            "color": {"value": "#ff7f0e"}
                        }
                    },
                    "title": "Revenue Trend Over Time",
                    "width": 600,
                    "height": 300
                },
                "existing_chart_schema": existing_schema,  # LLM will consider this but likely won't reuse (different chart type)
                "sql": "SELECT '2024-01' as month, 100000 as revenue UNION ALL SELECT '2024-02' as month, 120000 as revenue UNION ALL SELECT '2024-03' as month, 110000 as revenue",
                "query": "Show revenue trend over time (consider reusing existing chart style)",
                "data_description": "Revenue trend data",
                "project_id": "llm_reuse_test"
            },
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "product", "type": "nominal", "axis": {"title": "Product"}},
                            "y": {"field": "sales", "type": "quantitative", "axis": {"title": "Sales ($)"}},
                            "color": {"value": "#1f77b4"}  # Same color as existing schema
                        }
                    },
                    "title": "Product Sales Analysis",
                    "width": 500,
                    "height": 400
                },
                "existing_chart_schema": existing_schema,  # LLM should reuse this (same structure)
                "sql": "SELECT 'Product A' as product, 50000 as sales UNION ALL SELECT 'Product B' as product, 75000 as sales UNION ALL SELECT 'Product C' as product, 60000 as sales",
                "query": "Show product sales (consider reusing existing chart style)",
                "data_description": "Product sales data",
                "project_id": "llm_reuse_test"
            }
        ]


async def test_llm_chart_schema_reuse():
    """Test LLM-based chart schema reuse functionality"""
    print("🧠 Testing LLM Chart Schema Reuse")
    print("=" * 50)
    
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
        
        # Create test queries with existing chart schemas
        test_queries = LLMChartSchemaReuseTest.create_test_queries_with_existing_schema()
        
        print(f"📊 Created {len(test_queries)} test queries with existing chart schemas")
        print("   Query 1: Employee count (should consider reusing existing bar chart)")
        print("   Query 2: Revenue trend (should generate new line chart)")
        print("   Query 3: Product sales (should reuse existing bar chart structure)")
        
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
        print(f"\n🚀 Executing pipeline with LLM chart schema reuse...")
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
            
            # Analyze results for chart schema reuse
            print(f"\n🔍 Analyzing Chart Schema Reuse Results")
            print("=" * 45)
            
            for i, (query_key, query_result) in enumerate(result["post_process"]["results"].items()):
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    reasoning = visualization.get("reasoning", "")
                    
                    print(f"\n📊 Query {i+1} Results:")
                    print(f"   Title: {chart_schema.get('title', 'Untitled')}")
                    print(f"   Type: {chart_schema.get('type', 'Unknown')}")
                    print(f"   Mark: {chart_schema.get('spec', {}).get('mark', 'Unknown')}")
                    print(f"   Reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else f"   Reasoning: {reasoning}")
                    
                    # Check if LLM mentioned reusing existing schema
                    if "reuse" in reasoning.lower() or "existing" in reasoning.lower():
                        print("   ✅ LLM considered reusing existing chart schema")
                    elif "new" in reasoning.lower() or "generate" in reasoning.lower():
                        print("   🔄 LLM generated new chart schema")
                    else:
                        print("   ❓ LLM reasoning unclear about schema reuse")
                    
                    # Check color consistency
                    color = chart_schema.get("spec", {}).get("encoding", {}).get("color", {}).get("value", "")
                    if color == "#1f77b4":
                        print("   🎨 Color matches existing schema (#1f77b4)")
                    else:
                        print(f"   🎨 Color: {color}")
                else:
                    print(f"\n❌ Query {i+1} failed: {query_result.get('error', 'Unknown error')}")
            
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
        print(f"❌ Error in LLM chart schema reuse test: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_without_existing_schema():
    """Test chart generation without existing schema (baseline)"""
    print(f"\n🧪 Testing Chart Generation Without Existing Schema")
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
        
        # Create test query without existing chart schema
        test_queries = [
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "region", "type": "nominal", "axis": {"title": "Region"}},
                            "y": {"field": "sales", "type": "quantitative", "axis": {"title": "Sales ($)"}},
                            "color": {"value": "#2E8B57"}
                        }
                    },
                    "title": "Sales by Region",
                    "width": 500,
                    "height": 400
                },
                # No existing_chart_schema - LLM will generate fresh
                "sql": "SELECT 'North' as region, 150000 as sales UNION ALL SELECT 'South' as region, 120000 as sales UNION ALL SELECT 'East' as region, 180000 as sales",
                "query": "Show sales by region (generate new chart)",
                "data_description": "Sales data by region",
                "project_id": "baseline_test"
            }
        ]
        
        print("📊 Created test query without existing chart schema (baseline)")
        
        # Execute pipeline
        result = await pipeline.run(
            queries=test_queries,
            configuration={
                "concurrent_execution": False,
                "stream_intermediate_results": True
            }
        )
        
        if result.get("post_process", {}).get("success"):
            print("✅ Baseline test completed successfully")
            
            # Show generated chart
            for query_key, query_result in result["post_process"]["results"].items():
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    reasoning = visualization.get("reasoning", "")
                    
                    print(f"📊 Generated chart:")
                    print(f"   Title: {chart_schema.get('title', 'Untitled')}")
                    print(f"   Type: {chart_schema.get('type', 'Unknown')}")
                    print(f"   Reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else f"   Reasoning: {reasoning}")
                    print("   💡 This chart was generated without existing schema consideration")
        else:
            print("❌ Baseline test failed")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in baseline test: {e}")
        return None


async def run_llm_reuse_tests():
    """Run all LLM chart schema reuse tests"""
    print("🚀 Starting LLM Chart Schema Reuse Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Chart generation with existing schema consideration
    results["with_existing_schema"] = await test_llm_chart_schema_reuse()
    
    # Test 2: Chart generation without existing schema (baseline)
    results["without_existing_schema"] = await test_without_existing_schema()
    
    print("\n" + "=" * 60)
    print("🎉 All LLM reuse tests completed!")
    
    # Summary
    successful_tests = sum(1 for result in results.values() if result is not None)
    total_tests = len(results)
    
    print(f"\nSummary: {successful_tests}/{total_tests} tests successful")
    
    return results


if __name__ == "__main__":
    # Run all LLM reuse tests
    asyncio.run(run_llm_reuse_tests())
