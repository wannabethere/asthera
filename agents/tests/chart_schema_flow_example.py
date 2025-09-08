#!/usr/bin/env python3
"""
Example demonstrating the complete flow of chart_schema through the pipeline chain:
Dashboard → DataSummarization → Chart Generation

This example shows how a provided chart_schema ensures consistency across runs.
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm


async def demonstrate_chart_schema_flow():
    """Demonstrate the complete chart schema flow through the pipeline"""
    print("🔄 Chart Schema Flow Demonstration")
    print("=" * 50)
    
    # Step 1: Define a consistent chart schema
    consistent_chart_schema = {
        "type": "vega_lite",
        "spec": {
            "mark": "bar",
            "encoding": {
                "x": {"field": "department", "type": "nominal", "axis": {"title": "Department"}},
                "y": {"field": "employee_count", "type": "quantitative", "axis": {"title": "Employee Count"}},
                "color": {"value": "#2E8B57"}
            }
        },
        "title": "Employee Count by Department - Consistent Visualization",
        "width": 500,
        "height": 400,
        "description": "This chart will remain identical across multiple runs"
    }
    
    print("📊 Step 1: Defined consistent chart schema")
    print(f"   Title: {consistent_chart_schema['title']}")
    print(f"   Type: {consistent_chart_schema['type']}")
    print(f"   Mark: {consistent_chart_schema['spec']['mark']}")
    
    # Step 2: Create dashboard queries with the chart schema
    dashboard_queries = [
        {
            "chart_schema": consistent_chart_schema,
            "sql": """
                SELECT 'Engineering' as department, 45 as employee_count
                UNION ALL SELECT 'Sales' as department, 32 as employee_count
                UNION ALL SELECT 'Marketing' as department, 18 as employee_count
                UNION ALL SELECT 'HR' as department, 12 as employee_count
                UNION ALL SELECT 'Finance' as department, 8 as employee_count
            """,
            "query": "Show employee count by department with consistent chart",
            "data_description": "Employee distribution across departments",
            "project_id": "flow_demonstration"
        }
    ]
    
    print(f"\n📋 Step 2: Created {len(dashboard_queries)} dashboard query with chart schema")
    
    # Step 3: Initialize pipeline components
    print("\n🔧 Step 3: Initializing pipeline components")
    engine = EngineProvider.get_engine()
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    
    # Create dashboard streaming pipeline
    pipeline = create_dashboard_streaming_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper
    )
    
    print("   ✅ Dashboard streaming pipeline created")
    print("   ✅ DataSummarizationPipeline will be used internally")
    print("   ✅ ChartExecutor will handle provided chart schema")
    
    # Step 4: Execute pipeline multiple times to show consistency
    print(f"\n🚀 Step 4: Executing pipeline multiple times to demonstrate consistency")
    
    execution_log = []
    results = []
    num_executions = 3
    
    def status_callback(status: str, details: Dict[str, Any]):
        execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "details": details
        })
        print(f"   📈 {status}: {details}")
    
    for execution_num in range(num_executions):
        print(f"\n   🔄 Execution {execution_num + 1}/{num_executions}")
        print("   " + "-" * 40)
        
        # Execute the pipeline
        result = await pipeline.run(
            queries=dashboard_queries,
            status_callback=status_callback,
            configuration={
                "concurrent_execution": False,  # Sequential for clearer logging
                "stream_intermediate_results": True,
                "continue_on_error": True
            }
        )
        
        results.append(result)
        
        # Analyze the result
        if result.get("post_process", {}).get("success"):
            print(f"   ✅ Execution {execution_num + 1} completed successfully")
            
            # Extract chart information from result
            for query_key, query_result in result["post_process"]["results"].items():
                if query_result.get("success"):
                    execution_result = query_result.get("execution_result", {})
                    post_process = execution_result.get("post_process", {})
                    visualization = post_process.get("visualization", {})
                    chart_schema = visualization.get("chart_schema", {})
                    
                    if chart_schema:
                        print(f"   📊 Generated chart: {chart_schema.get('title', 'Untitled')}")
                        print(f"      Type: {chart_schema.get('type', 'Unknown')}")
                        print(f"      Width: {chart_schema.get('width', 'N/A')}")
                        print(f"      Height: {chart_schema.get('height', 'N/A')}")
                        
                        # Check if it matches our original schema
                        if (chart_schema.get("title") == consistent_chart_schema["title"] and
                            chart_schema.get("type") == consistent_chart_schema["type"]):
                            print(f"      ✅ Chart schema matches original (consistent)")
                        else:
                            print(f"      ⚠️  Chart schema differs from original")
                    else:
                        print(f"   ⚠️  No chart schema found in result")
        else:
            print(f"   ❌ Execution {execution_num + 1} failed")
    
    # Step 5: Analyze consistency across executions
    print(f"\n🔍 Step 5: Analyzing consistency across {num_executions} executions")
    print("   " + "=" * 50)
    
    if len(results) >= 2:
        # Compare chart schemas across executions
        first_execution_schema = None
        for query_key, query_result in results[0]["post_process"]["results"].items():
            if query_result.get("success"):
                execution_result = query_result.get("execution_result", {})
                post_process = execution_result.get("post_process", {})
                visualization = post_process.get("visualization", {})
                chart_schema = visualization.get("chart_schema", {})
                if chart_schema:
                    first_execution_schema = chart_schema
                    break
        
        if first_execution_schema:
            consistent_executions = 0
            for exec_idx in range(1, len(results)):
                execution_consistent = True
                for query_key, query_result in results[exec_idx]["post_process"]["results"].items():
                    if query_result.get("success"):
                        execution_result = query_result.get("execution_result", {})
                        post_process = execution_result.get("post_process", {})
                        visualization = post_process.get("visualization", {})
                        chart_schema = visualization.get("chart_schema", {})
                        
                        if chart_schema:
                            # Compare key properties
                            if (chart_schema.get("title") != first_execution_schema.get("title") or
                                chart_schema.get("type") != first_execution_schema.get("type")):
                                execution_consistent = False
                                print(f"   ⚠️  Execution {exec_idx + 1} differs from first execution")
                                print(f"      Title: '{chart_schema.get('title')}' vs '{first_execution_schema.get('title')}'")
                                print(f"      Type: '{chart_schema.get('type')}' vs '{first_execution_schema.get('type')}'")
                
                if execution_consistent:
                    consistent_executions += 1
                    print(f"   ✅ Execution {exec_idx + 1} is consistent with first execution")
            
            consistency_rate = consistent_executions / (len(results) - 1) * 100
            print(f"\n   📊 Consistency Rate: {consistency_rate:.1f}% ({consistent_executions}/{len(results)-1} executions)")
            
            if consistency_rate == 100:
                print("   🎉 Perfect consistency! Chart schemas remain identical across executions.")
                print("   💡 This demonstrates that provided chart_schema ensures consistent visualizations.")
            elif consistency_rate >= 80:
                print("   ✅ Good consistency! Most chart schemas remain consistent.")
            else:
                print("   ⚠️  Low consistency! Chart schemas are changing between executions.")
    
    # Step 6: Show the complete flow summary
    print(f"\n📋 Step 6: Complete Flow Summary")
    print("   " + "=" * 30)
    print("   1. 📊 Chart schema defined with specific visualization properties")
    print("   2. 📋 Dashboard query created with embedded chart_schema")
    print("   3. 🔧 Dashboard streaming pipeline initialized")
    print("   4. 🚀 Pipeline executed multiple times")
    print("   5. 🔍 Chart schemas compared for consistency")
    print("   6. ✅ Result: Provided chart_schema ensures consistent visualizations")
    
    # Show pipeline flow details
    print(f"\n🔄 Pipeline Flow Details")
    print("   " + "=" * 25)
    print("   Dashboard Streaming Pipeline")
    print("   ├── Extracts chart_schema from query data")
    print("   ├── Passes chart_schema to DataSummarizationPipeline")
    print("   └── DataSummarizationPipeline")
    print("       ├── Receives chart_schema in kwargs")
    print("       ├── Passes chart_schema to _generate_chart_for_batch")
    print("       └── _generate_chart_for_batch")
    print("           ├── Detects provided chart_schema")
    print("           ├── Uses ChartExecutor instead of generating new schema")
    print("           ├── ChartExecutor executes provided schema with data")
    print("           └── Returns consistent chart visualization")
    
    print(f"\n🎯 Key Benefits of Chart Schema Flow")
    print("   " + "=" * 35)
    print("   ✅ Consistent visualizations across multiple runs")
    print("   ✅ No random chart generation variations")
    print("   ✅ Predictable chart appearance and behavior")
    print("   ✅ Better user experience with stable dashboards")
    print("   ✅ Reduced computational overhead (no chart generation)")
    
    return results


async def demonstrate_without_chart_schema():
    """Demonstrate what happens without provided chart schema (auto-generation)"""
    print(f"\n🔄 Chart Generation Without Provided Schema")
    print("=" * 50)
    
    # Create query without chart_schema
    dashboard_queries = [
        {
            "sql": "SELECT 'Q1' as quarter, 100000 as revenue UNION ALL SELECT 'Q2' as quarter, 120000 as revenue",
            "query": "Show quarterly revenue (auto-generated chart)",
            "data_description": "Quarterly revenue data for auto-generation",
            "project_id": "auto_generation_demo"
        }
    ]
    
    print("📋 Created query WITHOUT chart_schema (will auto-generate)")
    
    # Initialize pipeline
    engine = EngineProvider.get_engine()
    llm = get_llm()
    retrieval_helper = RetrievalHelper()
    
    pipeline = create_dashboard_streaming_pipeline(
        engine=engine,
        llm=llm,
        retrieval_helper=retrieval_helper
    )
    
    # Execute pipeline
    result = await pipeline.run(
        queries=dashboard_queries,
        configuration={
            "concurrent_execution": False,
            "stream_intermediate_results": True
        }
    )
    
    if result.get("post_process", {}).get("success"):
        print("✅ Auto-generation completed successfully")
        
        # Show generated chart
        for query_key, query_result in result["post_process"]["results"].items():
            if query_result.get("success"):
                execution_result = query_result.get("execution_result", {})
                post_process = execution_result.get("post_process", {})
                visualization = post_process.get("visualization", {})
                chart_schema = visualization.get("chart_schema", {})
                
                if chart_schema:
                    print(f"📊 Auto-generated chart:")
                    print(f"   Title: {chart_schema.get('title', 'Untitled')}")
                    print(f"   Type: {chart_schema.get('type', 'Unknown')}")
                    print(f"   Reasoning: {visualization.get('reasoning', 'No reasoning provided')}")
                    print("   💡 This chart was generated by the LLM and may vary between runs")
    
    return result


async def run_flow_demonstration():
    """Run the complete chart schema flow demonstration"""
    print("🚀 Chart Schema Flow Demonstration")
    print("=" * 60)
    
    # Demonstrate with provided chart schema
    results_with_schema = await demonstrate_chart_schema_flow()
    
    # Demonstrate without provided chart schema
    results_without_schema = await demonstrate_without_chart_schema()
    
    print(f"\n🎉 Flow Demonstration Complete!")
    print("=" * 40)
    print("✅ Demonstrated chart schema consistency with provided schemas")
    print("✅ Demonstrated auto-generation without provided schemas")
    print("✅ Showed complete pipeline flow from dashboard to chart execution")
    
    return {
        "with_schema": results_with_schema,
        "without_schema": results_without_schema
    }


if __name__ == "__main__":
    # Run the flow demonstration
    asyncio.run(run_flow_demonstration())
