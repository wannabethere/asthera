#!/usr/bin/env python3
"""
Test to verify chart schema consistency through the entire pipeline chain:
Dashboard → DataSummarization → Chart Generation

This test ensures that when a chart_schema is provided, it's used consistently
across multiple runs without regeneration.
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm


class ChartSchemaConsistencyTest:
    """Test chart schema consistency across pipeline runs"""
    
    @staticmethod
    def create_test_chart_schema() -> Dict[str, Any]:
        """Create a test chart schema for consistency testing"""
        return {
            "type": "vega_lite",
            "spec": {
                "mark": "bar",
                "encoding": {
                    "x": {"field": "region", "type": "nominal", "axis": {"title": "Region"}},
                    "y": {"field": "sales", "type": "quantitative", "axis": {"title": "Sales ($)"}},
                    "color": {"value": "#1f77b4"}
                }
            },
            "title": "Sales by Region - Consistent Chart",
            "width": 500,
            "height": 400,
            "description": "This chart should remain consistent across multiple runs"
        }
    
    @staticmethod
    def create_test_queries() -> List[Dict[str, Any]]:
        """Create test queries with chart schemas"""
        chart_schema = ChartSchemaConsistencyTest.create_test_chart_schema()
        
        return [
            {
                "chart_schema": chart_schema,
                "sql": "SELECT 'North' as region, 150000 as sales UNION ALL SELECT 'South' as region, 120000 as sales UNION ALL SELECT 'East' as region, 180000 as sales UNION ALL SELECT 'West' as region, 140000 as sales",
                "query": "Show sales by region with consistent chart",
                "data_description": "Sales data by region for consistency testing",
                "project_id": "consistency_test"
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
                    "title": "Revenue Trend - Consistent Line Chart",
                    "width": 600,
                    "height": 300
                },
                "sql": "SELECT '2024-01' as month, 100000 as revenue UNION ALL SELECT '2024-02' as month, 120000 as revenue UNION ALL SELECT '2024-03' as month, 110000 as revenue UNION ALL SELECT '2024-04' as month, 130000 as revenue",
                "query": "Show revenue trend over time",
                "data_description": "Revenue trend data for consistency testing",
                "project_id": "consistency_test"
            }
        ]


async def test_chart_schema_consistency():
    """Test that chart schemas remain consistent across multiple runs"""
    print("🧪 Testing Chart Schema Consistency")
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
        
        # Create test queries with chart schemas
        test_queries = ChartSchemaConsistencyTest.create_test_queries()
        
        print(f"📊 Created {len(test_queries)} test queries with chart schemas")
        
        # Status callback to track execution
        execution_log = []
        
        def status_callback(status: str, details: Dict[str, Any]):
            execution_log.append({
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "details": details
            })
            print(f"📈 Status: {status} - {details}")
        
        # Run the pipeline multiple times to test consistency
        results = []
        num_runs = 3
        
        for run_num in range(num_runs):
            print(f"\n🔄 Run {run_num + 1}/{num_runs}")
            print("-" * 30)
            
            # Execute pipeline
            result = await pipeline.run(
                queries=test_queries,
                status_callback=status_callback,
                configuration={
                    "concurrent_execution": True,
                    "max_concurrent_queries": 2,
                    "stream_intermediate_results": True,
                    "continue_on_error": True
                }
            )
            
            results.append(result)
            
            # Analyze results for chart schema consistency
            if result.get("post_process", {}).get("success"):
                print(f"✅ Run {run_num + 1} completed successfully")
                
                # Extract chart schemas from results
                chart_schemas = []
                for query_key, query_result in result["post_process"]["results"].items():
                    if query_result.get("success"):
                        execution_result = query_result.get("execution_result", {})
                        post_process = execution_result.get("post_process", {})
                        visualization = post_process.get("visualization", {})
                        chart_schema = visualization.get("chart_schema", {})
                        
                        if chart_schema:
                            chart_schemas.append({
                                "query_key": query_key,
                                "chart_schema": chart_schema,
                                "title": chart_schema.get("title", ""),
                                "type": chart_schema.get("type", ""),
                                "spec_keys": list(chart_schema.get("spec", {}).keys()) if chart_schema.get("spec") else []
                            })
                
                print(f"📊 Found {len(chart_schemas)} chart schemas in results")
                for i, chart_info in enumerate(chart_schemas):
                    print(f"  Chart {i+1}: {chart_info['title']} ({chart_info['type']})")
                    print(f"    Spec keys: {chart_info['spec_keys']}")
            else:
                print(f"❌ Run {run_num + 1} failed")
        
        # Analyze consistency across runs
        print(f"\n🔍 Consistency Analysis")
        print("=" * 30)
        
        if len(results) >= 2:
            # Compare chart schemas across runs
            first_run_schemas = []
            for query_key, query_result in results[0]["post_process"]["results"].items():
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    if chart_schema:
                        first_run_schemas.append({
                            "query_key": query_key,
                            "title": chart_schema.get("title", ""),
                            "type": chart_schema.get("type", ""),
                            "spec": chart_schema.get("spec", {})
                        })
            
            consistent_runs = 0
            for run_idx in range(1, len(results)):
                run_consistent = True
                for query_key, query_result in results[run_idx]["post_process"]["results"].items():
                    if query_result.get("success"):
                        execution_result = query_result.get("execution_result", {})
                        post_process = execution_result.get("post_process", {})
                        visualization = post_process.get("visualization", {})
                        chart_schema = visualization.get("chart_schema", {})
                        
                        # Find corresponding schema from first run
                        first_run_schema = next(
                            (s for s in first_run_schemas if s["query_key"] == query_key), 
                            None
                        )
                        
                        if first_run_schema:
                            # Compare key properties
                            if (chart_schema.get("title") != first_run_schema["title"] or
                                chart_schema.get("type") != first_run_schema["type"]):
                                run_consistent = False
                                print(f"⚠️  Inconsistency in run {run_idx + 1}, query {query_key}")
                                print(f"    Title: {chart_schema.get('title')} vs {first_run_schema['title']}")
                                print(f"    Type: {chart_schema.get('type')} vs {first_run_schema['type']}")
                
                if run_consistent:
                    consistent_runs += 1
                    print(f"✅ Run {run_idx + 1} is consistent with first run")
                else:
                    print(f"❌ Run {run_idx + 1} has inconsistencies")
            
            consistency_rate = consistent_runs / (len(results) - 1) * 100
            print(f"\n📊 Consistency Rate: {consistency_rate:.1f}% ({consistent_runs}/{len(results)-1} runs)")
            
            if consistency_rate == 100:
                print("🎉 Perfect consistency! Chart schemas remain identical across runs.")
            elif consistency_rate >= 80:
                print("✅ Good consistency! Most chart schemas remain consistent.")
            else:
                print("⚠️  Low consistency! Chart schemas are changing between runs.")
        
        # Show execution statistics
        print(f"\n📈 Execution Statistics")
        print("=" * 25)
        print(f"Total runs: {len(results)}")
        print(f"Successful runs: {sum(1 for r in results if r.get('post_process', {}).get('success'))}")
        print(f"Total status updates: {len(execution_log)}")
        
        # Show pipeline metrics
        pipeline_stats = pipeline.get_execution_statistics()
        print(f"\n🔧 Pipeline Metrics")
        print("=" * 20)
        print(f"Total executions: {pipeline_stats['pipeline_metrics'].get('total_executions', 0)}")
        print(f"Total queries processed: {pipeline_stats['pipeline_metrics'].get('total_queries_processed', 0)}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in consistency test: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_chart_schema_without_provided_schema():
    """Test chart generation without provided schema (should generate new schemas)"""
    print("\n🧪 Testing Chart Generation Without Provided Schema")
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
        
        # Create test queries WITHOUT chart schemas
        test_queries = [
            {
                "sql": "SELECT 'North' as region, 150000 as sales UNION ALL SELECT 'South' as region, 120000 as sales",
                "query": "Show sales by region (auto-generated chart)",
                "data_description": "Sales data for auto-generation testing",
                "project_id": "auto_generation_test"
            }
        ]
        
        print("📊 Created test query without chart schema (should auto-generate)")
        
        # Execute pipeline
        result = await pipeline.run(
            queries=test_queries,
            configuration={
                "concurrent_execution": False,
                "stream_intermediate_results": True
            }
        )
        
        if result.get("post_process", {}).get("success"):
            print("✅ Auto-generation test completed successfully")
            
            # Check if chart was generated
            for query_key, query_result in result["post_process"]["results"].items():
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    
                    if chart_schema:
                        print(f"📊 Auto-generated chart: {chart_schema.get('title', 'Untitled')}")
                        print(f"   Type: {chart_schema.get('type', 'Unknown')}")
                        print(f"   Spec keys: {list(chart_schema.get('spec', {}).keys())}")
                    else:
                        print("⚠️  No chart schema generated")
        else:
            print("❌ Auto-generation test failed")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in auto-generation test: {e}")
        return None


async def run_all_consistency_tests():
    """Run all chart schema consistency tests"""
    print("🚀 Starting Chart Schema Consistency Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Chart schema consistency with provided schemas
    results["consistency_with_schema"] = await test_chart_schema_consistency()
    
    # Test 2: Chart generation without provided schemas
    results["auto_generation"] = await test_chart_schema_without_provided_schema()
    
    print("\n" + "=" * 60)
    print("🎉 All consistency tests completed!")
    
    # Summary
    successful_tests = sum(1 for result in results.values() if result is not None)
    total_tests = len(results)
    
    print(f"\nSummary: {successful_tests}/{total_tests} tests successful")
    
    return results


if __name__ == "__main__":
    # Run all consistency tests
    asyncio.run(run_all_consistency_tests())
