#!/usr/bin/env python3
"""
Comprehensive examples for using the enhanced dashboard system
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from app.agents.nodes.writers.dashboard_orchestrator import create_dashboard_orchestrator
from app.agents.nodes.writers.dashboard_factory import create_conditional_formatting_service
from app.agents.nodes.writers.enhanced_dashboard_pipeline import create_enhanced_dashboard_pipeline
from app.agents.nodes.writers.dashboard_models import (
    FilterOperator, FilterType, ActionType,
    ControlFilter, ConditionalFormat, DashboardConfiguration
)


class DashboardExamples:
    """Collection of dashboard usage examples"""
    
    @staticmethod
    def generate_sample_dashboard_context(
        chart_count: int = 3,
        columns: List[str] = None
    ) -> Dict[str, Any]:
        """Generate sample dashboard context for testing"""
        if columns is None:
            columns = ["date", "region", "sales", "quantity", "profit", "category", "status"]
        
        charts = []
        for i in range(chart_count):
            chart_types = ["bar", "line", "pie"]
            chart_type = chart_types[i % 3]
            
            # Create chart schema based on type
            if chart_type == "bar":
                chart_schema = {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": columns[0], "type": "nominal"},
                            "y": {"field": columns[1], "type": "quantitative"}
                        }
                    },
                    "title": f"Chart {i+1} - Bar Chart"
                }
            elif chart_type == "line":
                chart_schema = {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "line",
                        "encoding": {
                            "x": {"field": columns[0], "type": "temporal"},
                            "y": {"field": columns[1], "type": "quantitative"}
                        }
                    },
                    "title": f"Chart {i+1} - Line Chart"
                }
            else:  # pie
                chart_schema = {
                    "type": "plotly",
                    "data": [{
                        "type": "pie",
                        "labels": ["A", "B", "C", "D"],
                        "values": [25, 30, 20, 25]
                    }],
                    "layout": {
                        "title": f"Chart {i+1} - Pie Chart"
                    }
                }
            
            chart = {
                "chart_schema": chart_schema,
                "type": chart_type,
                "columns": columns[:4],  # Use first 4 columns
                "query": f"Sample query for chart {i+1}"
            }
            charts.append(chart)
        
        return {
            "charts": charts,
            "available_columns": columns,
            "data_types": {
                "date": "datetime",
                "region": "categorical",
                "sales": "numeric",
                "quantity": "numeric",
                "profit": "numeric",
                "category": "categorical",
                "status": "categorical"
            }
        }
    
    @staticmethod
    def generate_sample_dashboard_queries() -> List[Dict[str, Any]]:
        """Generate sample dashboard queries"""
        return [
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "region", "type": "nominal", "axis": {"title": "Region"}},
                            "y": {"field": "sales", "type": "quantitative", "axis": {"title": "Sales ($)"}}
                        }
                    },
                    "title": "Sales by Region",
                    "width": 400,
                    "height": 300
                },
                "sql": "SELECT region, SUM(sales_amount) as sales FROM sales_data GROUP BY region;",
                "query": "Show sales by region",
                "data_description": "Sales data by region",
                "project_id": "example_project"
            },
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "line",
                        "encoding": {
                            "x": {"field": "date", "type": "temporal", "axis": {"title": "Date"}},
                            "y": {"field": "performance_score", "type": "quantitative", "axis": {"title": "Performance Score"}},
                            "color": {"value": "#1f77b4"}
                        }
                    },
                    "title": "Performance Over Time",
                    "width": 600,
                    "height": 300
                },
                "sql": "SELECT date, performance_score FROM performance_data ORDER BY date;",
                "query": "Show performance over time",
                "data_description": "Performance trends over time",
                "project_id": "example_project"
            },
            {
                "chart_schema": {
                    "type": "plotly",
                    "data": [{
                        "type": "pie",
                        "labels": ["Electronics", "Clothing", "Books", "Home", "Sports"],
                        "values": [30, 25, 20, 15, 10],
                        "hole": 0.3
                    }],
                    "layout": {
                        "title": "Average Profit by Category",
                        "height": 400,
                        "showlegend": True
                    }
                },
                "sql": "SELECT category, AVG(profit) as avg_profit FROM sales_data GROUP BY category;",
                "query": "Show average profit by category",
                "data_description": "Profit analysis by category",
                "project_id": "example_project"
            }
        ]
    
    @staticmethod
    def generate_sample_natural_language_queries() -> List[str]:
        """Generate sample natural language queries for conditional formatting"""
        return [
            """
            Highlight all sales amounts greater than $50,000 in green and less than $10,000 in red.
            Filter to show only data from the last quarter.
            Make the performance chart show only scores above 80.
            """,
            
            """
            Apply conditional formatting to show high-performing regions in blue.
            Filter dashboard to show only active status records.
            Highlight profit margins above 20% in green.
            """,
            
            """
            Show sales data for the current year only.
            Highlight regions with sales growth above 15%.
            Apply red color to categories with declining performance.
            """
        ]


async def example_basic_conditional_formatting():
    """Example 1: Basic conditional formatting without dashboard execution"""
    print("\n=== Example 1: Basic Conditional Formatting ===")
    
    try:
        # Create conditional formatting service
        service = create_conditional_formatting_service()
        
        # Generate sample context and query
        dashboard_context = DashboardExamples.generate_sample_dashboard_context()
        natural_language_query = DashboardExamples.generate_sample_natural_language_queries()[0]
        
        print(f"Natural Language Query: {natural_language_query.strip()}")
        print(f"Dashboard Context: {len(dashboard_context['charts'])} charts")
        
        # Process conditional formatting
        result = await service.process_conditional_formatting_request(
            query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="example_project",
            additional_context={"user_id": "user123"},
            time_filters={"period": "last_quarter"}
        )
        
        if result.get("success"):
            print("✅ Conditional formatting processed successfully!")
            print(f"Total chart configurations: {len(result.get('chart_configurations', {}))}")
            print(f"Total filters: {len(result.get('configuration', {}).get('filters', []))}")
            
            # Show chart configurations
            for chart_id, config in result.get("chart_configurations", {}).items():
                print(f"\nChart {chart_id}:")
                print(f"  Actions: {config.get('actions', [])}")
                print(f"  SQL Expansions: {list(config.get('sql_expansion', {}).keys())}")
                print(f"  Chart Adjustments: {list(config.get('chart_adjustment', {}).keys())}")
        else:
            print(f"❌ Conditional formatting failed: {result.get('error')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in basic conditional formatting example: {e}")
        return None


async def example_enhanced_dashboard_pipeline():
    """Example 2: Using enhanced dashboard pipeline directly"""
    print("\n=== Example 2: Enhanced Dashboard Pipeline ===")
    
    try:
        # Create enhanced dashboard pipeline
        from app.core.engine_provider import EngineProvider
        
        engine = EngineProvider.get_engine()
        pipeline = create_enhanced_dashboard_pipeline(
            engine=engine,
            llm=None,  # Will use default
            retrieval_helper=None,  # Will create default
            conditional_formatting_service=None  # Will create default
        )
        
        # Generate sample data
        dashboard_queries = DashboardExamples.generate_sample_dashboard_queries()
        dashboard_context = DashboardExamples.generate_sample_dashboard_context()
        natural_language_query = DashboardExamples.generate_sample_natural_language_queries()[1]
        
        print(f"Pipeline: {pipeline.name} v{pipeline.version}")
        print(f"Total queries: {len(dashboard_queries)}")
        print(f"Natural language query: {natural_language_query.strip()[:100]}...")
        
        # Status callback for streaming updates
        def status_callback(status: str, details: Dict[str, Any]):
            print(f"📊 Status: {status} - {details}")
        
        # Execute pipeline
        result = await pipeline.run(
            queries=dashboard_queries,
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="example_project",
            additional_context={"user_id": "user123"},
            time_filters={"period": "current_year"},
            status_callback=status_callback,
            configuration={
                "concurrent_execution": True,
                "max_concurrent_queries": 3,
                "stream_intermediate_results": True,
                "enable_conditional_formatting": True,
                "enable_chart_adjustments": True
            }
        )
        
        print("✅ Enhanced dashboard pipeline completed!")
        print(f"Success: {result.get('post_process', {}).get('success', False)}")
        print(f"Total execution time: {result.get('post_process', {}).get('execution_metadata', {}).get('total_execution_time_seconds', 0):.2f}s")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in enhanced dashboard pipeline example: {e}")
        return None


async def example_dashboard_orchestrator():
    """Example 3: Using dashboard orchestrator for complete workflow"""
    print("\n=== Example 3: Dashboard Orchestrator ===")
    
    try:
        # Create dashboard orchestrator
        orchestrator = create_dashboard_orchestrator()
        
        # Generate sample data
        dashboard_queries = DashboardExamples.generate_sample_dashboard_queries()
        dashboard_context = DashboardExamples.generate_sample_dashboard_context()
        natural_language_query = DashboardExamples.generate_sample_natural_language_queries()[2]
        
        print(f"Orchestrator created successfully")
        print(f"Total queries: {len(dashboard_queries)}")
        print(f"Natural language query: {natural_language_query.strip()[:100]}...")
        
        # Validate configuration first
        validation_result = await orchestrator.validate_dashboard_configuration(
            dashboard_queries=dashboard_queries,
            dashboard_context=dashboard_context,
            natural_language_query=natural_language_query
        )
        
        print(f"\nConfiguration Validation:")
        print(f"  Valid: {validation_result['valid']}")
        print(f"  Issues: {len(validation_result['issues'])}")
        print(f"  Warnings: {len(validation_result['warnings'])}")
        print(f"  Recommendations: {len(validation_result['recommendations'])}")
        
        if not validation_result['valid']:
            print("❌ Configuration validation failed, cannot proceed")
            return None
        
        # Status callback for orchestration
        def orchestration_callback(status: str, details: Dict[str, Any]):
            print(f"🎯 Orchestration: {status} - {details}")
        
        # Execute complete workflow
        result = await orchestrator.execute_dashboard_with_conditional_formatting(
            dashboard_queries=dashboard_queries,
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="example_project",
            additional_context={"user_id": "user123", "session_id": "session456"},
            time_filters={"period": "current_year", "start_date": "2024-01-01"},
            status_callback=orchestration_callback,
            pipeline_configuration={
                "concurrent_execution": True,
                "max_concurrent_queries": 3,
                "stream_intermediate_results": True,
                "enable_conditional_formatting": True,
                "enable_chart_adjustments": True
            }
        )
        
        print("✅ Dashboard orchestration completed!")
        print(f"Success: {result.get('post_process', {}).get('success', False)}")
        print(f"Conditional formatting applied: {result.get('post_process', {}).get('execution_metadata', {}).get('conditional_formatting_applied', False)}")
        print(f"Chart adjustments applied: {result.get('post_process', {}).get('execution_metadata', {}).get('chart_adjustments_applied', False)}")
        
        # Get service status
        service_status = orchestrator.get_service_status()
        print(f"\nService Status:")
        print(f"  Conditional formatting service: {'✅' if service_status['conditional_formatting_service']['available'] else '❌'}")
        print(f"  Enhanced dashboard pipeline: {'✅' if service_status['enhanced_dashboard_pipeline']['available'] else '❌'}")
        print(f"  Pipeline container: {'✅' if service_status['pipeline_container']['available'] else '❌'}")
        print(f"  Execution history: {service_status['execution_history']['total_entries']} entries")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in dashboard orchestrator example: {e}")
        return None


async def example_conditional_formatting_only():
    """Example 4: Process conditional formatting without dashboard execution"""
    print("\n=== Example 4: Conditional Formatting Only ===")
    
    try:
        # Create orchestrator
        orchestrator = create_dashboard_orchestrator()
        
        # Generate sample data
        dashboard_context = DashboardExamples.generate_sample_dashboard_context()
        natural_language_query = DashboardExamples.generate_sample_natural_language_queries()[0]
        
        print(f"Processing conditional formatting only...")
        print(f"Natural language query: {natural_language_query.strip()[:100]}...")
        
        # Process conditional formatting
        result = await orchestrator.process_conditional_formatting_only(
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="example_project",
            additional_context={"user_id": "user123"},
            time_filters={"period": "last_30_days"}
        )
        
        if result.get("success"):
            print("✅ Conditional formatting processed successfully!")
            print(f"Total chart configurations: {len(result.get('chart_configurations', {}))}")
            
            # Show detailed configuration
            configuration = result.get("configuration", {})
            print(f"\nConfiguration Details:")
            print(f"  Dashboard ID: {configuration.get('dashboard_id', 'N/A')}")
            print(f"  Total filters: {len(configuration.get('filters', []))}")
            print(f"  Total conditional formats: {len(configuration.get('conditional_formats', []))}")
            
            # Show filters
            for i, filter_obj in enumerate(configuration.get("filters", [])[:3]):  # Show first 3
                print(f"  Filter {i+1}: {filter_obj.get('column_name')} {filter_obj.get('operator')} {filter_obj.get('value')}")
            
        else:
            print(f"❌ Conditional formatting failed: {result.get('error')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in conditional formatting only example: {e}")
        return None


async def example_dashboard_only():
    """Example 5: Execute dashboard without conditional formatting"""
    print("\n=== Example 5: Dashboard Only (No Conditional Formatting) ===")
    
    try:
        # Create orchestrator
        orchestrator = create_dashboard_orchestrator()
        
        # Generate sample data
        dashboard_queries = DashboardExamples.generate_sample_dashboard_queries()
        
        print(f"Executing dashboard without conditional formatting...")
        print(f"Total queries: {len(dashboard_queries)}")
        
        # Status callback
        def dashboard_callback(status: str, details: Dict[str, Any]):
            print(f"📊 Dashboard: {status} - {details}")
        
        # Execute dashboard only
        result = await orchestrator.execute_dashboard_only(
            dashboard_queries=dashboard_queries,
            project_id="example_project",
            status_callback=dashboard_callback,
            pipeline_configuration={
                "concurrent_execution": True,
                "max_concurrent_queries": 3,
                "stream_intermediate_results": True,
                "enable_conditional_formatting": False,
                "enable_chart_adjustments": False
            }
        )
        
        print("✅ Dashboard execution completed!")
        print(f"Success: {result.get('post_process', {}).get('success', False)}")
        print(f"Total queries executed: {len(result.get('post_process', {}).get('results', {}))}")
        
        # Show execution metadata
        metadata = result.get("post_process", {}).get("execution_metadata", {})
        print(f"Execution time: {metadata.get('total_execution_time_seconds', 0):.2f}s")
        print(f"Success rate: {metadata.get('success_rate', 0):.1%}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in dashboard only example: {e}")
        return None


async def run_all_examples():
    """Run all dashboard examples"""
    print("🚀 Starting Enhanced Dashboard Examples")
    print("=" * 50)
    
    results = {}
    
    try:
        # Run all examples
        results["basic_conditional_formatting"] = await example_basic_conditional_formatting()
        results["enhanced_dashboard_pipeline"] = await example_enhanced_dashboard_pipeline()
        results["dashboard_orchestrator"] = await example_dashboard_orchestrator()
        results["conditional_formatting_only"] = await example_conditional_formatting_only()
        results["dashboard_only"] = await example_dashboard_only()
        
        print("\n" + "=" * 50)
        print("🎉 All examples completed!")
        
        # Summary
        successful_examples = sum(1 for result in results.values() if result is not None)
        total_examples = len(results)
        
        print(f"\nSummary: {successful_examples}/{total_examples} examples successful")
        
        return results
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        return results


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())
