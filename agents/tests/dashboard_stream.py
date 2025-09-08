import asyncio
import logging
from typing import Dict, Any

# Usage Example for Dashboard Streaming Pipeline

async def example_dashboard_streaming():
    """Example usage of the Dashboard Streaming Pipeline"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.agents.pipelines.pipeline_container import PipelineContainer
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
        print(f"   Engine Type: {settings.ENGINE_TYPE}")
        print(f"   Database: {settings.POSTGRES_DB} on {settings.POSTGRES_HOST}")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize pipeline container with proper dependencies
    pipeline_container = PipelineContainer.initialize()
    
    # Get the dashboard streaming pipeline from the container
    dashboard_pipeline = pipeline_container.get_pipeline("dashboard_streaming")
    
    # Check if dashboard pipeline is available
    if dashboard_pipeline is None:
        print("❌ Dashboard streaming pipeline is not available")
        print("🔍 Checking available pipelines...")
        
        all_pipelines = pipeline_container.get_all_pipelines()
        available_pipelines = [name for name, pipeline in all_pipelines.items() if pipeline is not None]
        print(f"   Available pipelines: {available_pipelines}")
        
        # Try to use an alternative pipeline or create a simple one
        print("🔄 Attempting to use alternative approach...")
        
        # Check if we can use the sql_execution pipeline instead
        sql_pipeline = pipeline_container.get_pipeline("sql_execution")
        if sql_pipeline:
            print("   ✅ Using sql_execution pipeline as fallback")
            # For now, we'll skip the dashboard streaming example
            print("   ⚠️  Dashboard streaming functionality not available")
            print("   💡 Try running the other examples instead")
            return {"status": "skipped", "reason": "dashboard_streaming_pipeline_not_available"}
        else:
            print("   ❌ No suitable fallback pipeline available")
            raise RuntimeError("Dashboard streaming pipeline and fallback pipelines are not available")
    
    print(f"✅ Dashboard streaming pipeline available: {type(dashboard_pipeline)}")
    
    # Configure for concurrent execution
    dashboard_pipeline.set_concurrent_execution(enabled=True, max_concurrent=3)
    dashboard_pipeline.set_streaming_options(stream_intermediate=True, continue_on_error=True)
    
    # Your input data (as provided in the requirement)
    queries = [
        {
            "sql": """WITH NotCompletedTraining AS (
                SELECT division, COUNT(*) AS not_completed_count
                FROM csod_training_records
                WHERE assigned_date >= CAST('2025-02-18 00:00:00' AS TIMESTAMP WITH TIME ZONE)
                  AND completed_date IS NULL
                GROUP BY division
            ),
            TotalEmployees AS (
                SELECT division, COUNT(*) AS total_count
                FROM csod_training_records
                GROUP BY division
            )
            SELECT 
                n.division,
                n.not_completed_count,
                t.total_count,
                (n.not_completed_count::FLOAT / t.total_count) AS proportion_not_completed
            FROM NotCompletedTraining n
            JOIN TotalEmployees t ON n.division = t.division;""",
            "query": "What are the proportions of employees by division who have not completed training in the last 6 months",
            "project_id": "cornerstone",
            "data_description": "Training completion analysis by division",
            "configuration": {
                "enable_pagination": True,
                "page_size": 1000
            }
        },
        {
            "sql": """SELECT 
                department,
                COUNT(*) as total_employees,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_employees,
                ROUND(COUNT(CASE WHEN status = 'active' THEN 1 END) * 100.0 / COUNT(*), 2) as active_percentage
            FROM employee_records 
            GROUP BY department
            ORDER BY active_percentage DESC;""",
            "query": "Employee status distribution by department",
            "project_id": "hr_analytics",
            "data_description": "HR dashboard metrics for employee status",
            "configuration": {
                "enable_pagination": False
            }
        },
        {
            "sql": """SELECT 
                DATE_TRUNC('month', order_date) as month,
                SUM(total_amount) as monthly_revenue,
                COUNT(*) as order_count,
                AVG(total_amount) as avg_order_value
            FROM sales_orders 
            WHERE order_date >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', order_date)
            ORDER BY month DESC;""",
            "query": "Monthly revenue trends for the last 12 months",
            "project_id": "sales_analytics",
            "data_description": "Sales performance dashboard data",
            "configuration": {
                "timeout": 45
            }
        }
    ]
    
    # Status callback for streaming updates
    def status_callback(status: str, details: Dict[str, Any]):
        """Handle status updates from the pipeline"""
        print(f"📊 Status Update: {status}")
        
        if status == "dashboard_streaming_started":
            print(f"   Starting processing {details['total_queries']} queries...")
            
        elif status == "query_execution_started":
            print(f"   ▶️  Query {details['query_index']}: {details['query'][:50]}...")
            
        elif status == "query_execution_completed":
            print(f"   ✅ Query {details['query_index']} completed in {details['execution_time']:.2f}s")
            print(f"      📈 Data rows: {details.get('data_rows', 'N/A')}")
            
        elif status == "query_execution_failed":
            print(f"   ❌ Query {details['query_index']} failed after {details['execution_time']:.2f}s")
            print(f"      Error: {details['error']}")
            
        elif status == "query_result_available":
            # This is where you would send results to your dashboard UI
            query_idx = details['query_index']
            result = details['result']
            print(f"   📤 Streaming result for query {query_idx} to dashboard")
            # send_to_dashboard_ui(query_idx, result)
            
        elif status == "dashboard_streaming_completed":
            print(f"🎉 Dashboard streaming completed!")
            print(f"   📊 {details['completed_queries']}/{details['total_queries']} queries successful")
            print(f"   ⏱️  Total time: {details['execution_time']:.2f}s")
            print(f"   📈 Success rate: {details['success_rate']:.1%}")
            
        elif status == "dashboard_streaming_error":
            print(f"💥 Dashboard streaming error: {details['error']}")
    
    # Execute the dashboard queries
    try:
        print("🚀 Starting Dashboard Streaming Pipeline...")
        
        result = await dashboard_pipeline.run(
            queries=queries,
            status_callback=status_callback,
            configuration={
                "concurrent_execution": True,
                "max_concurrent_queries": 3,
                "stream_intermediate_results": True,
                "continue_on_error": True
            },
            project_id="test_project"
        )
        
        # Process final results
        print("\n📋 Final Results Summary:")
        results = result["post_process"]["results"]
        execution_metadata = result["post_process"]["execution_metadata"]
        
        for query_key, query_result in results.items():
            query_idx = query_result["query_index"]
            success = query_result["success"]
            execution_time = query_result["execution_time_seconds"]
            
            print(f"   Query {query_idx}: {'✅ Success' if success else '❌ Failed'} ({execution_time:.2f}s)")
            
            if success:
                # Access the actual data
                exec_result = query_result["execution_result"]
                data = exec_result.get("post_process", {}).get("data", [])
                print(f"      📊 Returned {len(data)} rows")
                
                # Example: Print first few rows for verification
                if data and len(data) > 0:
                    print(f"      🔍 Sample data: {data[0] if isinstance(data, list) else 'Complex data structure'}")
            else:
                print(f"      ❌ Error: {query_result.get('error', 'Unknown error')}")
        
        # Print execution statistics
        print(f"\n📈 Execution Statistics:")
        print(f"   Total execution time: {execution_metadata['total_execution_time_seconds']:.2f}s")
        print(f"   Success rate: {execution_metadata['success_rate']:.1%}")
        print(f"   Completed queries: {execution_metadata['completed_queries']}")
        print(f"   Failed queries: {execution_metadata['failed_queries']}")
        
        return result
        
    except Exception as e:
        print(f"💥 Error running dashboard pipeline: {e}")
        raise


async def example_sequential_execution():
    """Example of sequential execution for cases where you need ordered processing"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.agents.pipelines.pipeline_container import PipelineContainer
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize pipeline container
    pipeline_container = PipelineContainer.initialize()
    
    # Get the dashboard streaming pipeline from the container
    dashboard_pipeline = pipeline_container.get_pipeline("dashboard_streaming")
    
    # Check if dashboard pipeline is available
    if dashboard_pipeline is None:
        print("❌ Dashboard streaming pipeline is not available")
        print("   💡 Skipping sequential execution example")
        return {"status": "skipped", "reason": "dashboard_streaming_pipeline_not_available"}
    
    # Configure for sequential execution
    dashboard_pipeline.set_concurrent_execution(enabled=False)
    
    # Simpler status callback for sequential processing
    def sequential_status_callback(status: str, details: Dict[str, Any]):
        if status == "query_execution_completed":
            query_idx = details['query_index']
            execution_time = details['execution_time']
            print(f"✅ Query {query_idx + 1} completed in {execution_time:.2f}s")
    
    # Your queries
    queries = [
        {
            "sql": "SELECT COUNT(*) as user_count FROM users",
            "query": "Total user count",
            "project_id": "analytics",
            "data_description": "User metrics"
        },
        {
            "sql": "SELECT AVG(session_duration) as avg_duration FROM user_sessions WHERE date >= CURRENT_DATE - 7",
            "query": "Average session duration last 7 days",
            "project_id": "analytics", 
            "data_description": "Session analytics"
        }
    ]
    
    # Execute sequentially
    result = await dashboard_pipeline.run(
        queries=queries,
        status_callback=sequential_status_callback,
        configuration={"concurrent_execution": False},
        project_id="test_project"
    )
    
    return result


async def example_using_dashboard_service():
    """Example using the refactored DashboardService with PipelineContainer"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.services.writers.dashboard_service import create_dashboard_service
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
        print(f"   Engine Type: {settings.ENGINE_TYPE}")
        print(f"   Database: {settings.POSTGRES_DB} on {settings.POSTGRES_HOST}")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Create dashboard service (automatically initializes PipelineContainer)
    dashboard_service = create_dashboard_service()
    
    # Sample dashboard queries
    dashboard_queries = [
        {
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "division", "type": "nominal", "axis": {"title": "Division"}},
                        "y": {"field": "total", "type": "quantitative", "axis": {"title": "Total Records"}}
                    }
                },
                "title": "Training Records by Division",
                "width": 400,
                "height": 300
            },
            "sql": "SELECT division, COUNT(*) as total FROM csod_training_records GROUP BY division",
            "query": "Training records by division",
            "data_description": "Training data analysis"
        },
        {
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "department", "type": "nominal", "axis": {"title": "Department"}},
                        "y": {"field": "count", "type": "quantitative", "axis": {"title": "Employee Count"}}
                    }
                },
                "title": "Employee Count by Department",
                "width": 400,
                "height": 300
            },
            "sql": "SELECT department, COUNT(*) as count FROM employee_records GROUP BY department",
            "query": "Employee count by department",
            "data_description": "Employee distribution"
        }
    ]
    
    # Dashboard context
    dashboard_context = {
        "charts": [
            {
                "chart_schema": {
                    "type": "vega_lite",
                    "spec": {
                        "mark": "bar",
                        "encoding": {
                            "x": {"field": "division", "type": "nominal"},
                            "y": {"field": "total", "type": "quantitative"}
                        }
                    },
                    "title": "Training Records by Division"
                },
                "type": "bar",
                "columns": ["division", "total"],
                "query": "Training records by division"
            },
            {
                "chart_schema": {
                    "type": "plotly",
                    "data": [{
                        "type": "pie",
                        "labels": ["HR", "IT", "Finance", "Operations"],
                        "values": [25, 30, 20, 25]
                    }],
                    "layout": {
                        "title": "Employee Count by Department"
                    }
                },
                "type": "pie",
                "columns": ["department", "count"],
                "query": "Employee count by department"
            }
        ],
        "available_columns": ["division", "department", "total", "count"],
        "data_types": {
            "division": "categorical",
            "department": "categorical",
            "total": "numeric",
            "count": "numeric"
        }
    }
    
    # Natural language formatting query
    natural_language_query = """
    Highlight divisions with more than 100 training records in green.
    Show departments with less than 50 employees in red.
    """
    
    # Status callback
    def status_callback(status: str, details: Dict[str, Any]):
        print(f"🔄 Dashboard Service Status: {status}")
        if details:
            print(f"   Details: {details}")
    
    try:
        print("🚀 Testing Dashboard Service with PipelineContainer...")
        
        # Process dashboard with conditional formatting
        result = await dashboard_service.process_dashboard_with_conditional_formatting(
            natural_language_query=natural_language_query,
            dashboard_queries=dashboard_queries,
            project_id="test_project",
            dashboard_context=dashboard_context,
            additional_context={"test_mode": True},
            status_callback=status_callback
        )
        
        print(f"\n✅ Dashboard Service Result:")
        print(f"   Success: {result['success']}")
        print(f"   Conditional formatting applied: {result['metadata']['conditional_formatting_applied']}")
        print(f"   Total queries: {result['metadata']['total_queries']}")
        
        return result
        
    except Exception as e:
        print(f"💥 Error in dashboard service: {e}")
        raise


async def example_service_container_integration():
    """Example showing integration with the service container"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.services.service_container import SQLServiceContainer
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize service container
    container = SQLServiceContainer()
    container.initialize_services(app_state=None)
    
    # Get dashboard service from container
    dashboard_service = container.get_service("dashboard_service")
    
    # Check service status
    status = dashboard_service.get_service_status()
    print(f"🔍 Dashboard Service Status: {status}")
    
    # Test basic dashboard execution
    queries = [
        {
            "chart_schema": {
                "type": "vega_lite",
                "spec": {
                    "mark": "bar",
                    "encoding": {
                        "x": {"field": "column1", "type": "nominal"},
                        "y": {"field": "column2", "type": "quantitative"}
                    }
                },
                "title": "Simple Test Chart"
            },
            "sql": "SELECT 'test' as column1, 42 as column2",
            "query": "Simple test query",
            "data_description": "Test data"
        }
    ]
    
    try:
        print("🚀 Testing Dashboard Service from Service Container...")
        
        result = await dashboard_service.execute_dashboard_only(
            dashboard_queries=queries,
            project_id="container_test"
        )
        
        print(f"✅ Container Dashboard Service Result:")
        print(f"   Success: {result.get('post_process', {}).get('success', False)}")
        
        return result
        
    except Exception as e:
        print(f"💥 Error in container dashboard service: {e}")
        raise


# Integration with existing SQL pipelines
async def integration_example():
    """Example showing integration with existing SQL execution pipeline"""
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.agents.pipelines.pipeline_container import PipelineContainer
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize pipeline container
    pipeline_container = PipelineContainer.initialize()
    
    # Get existing SQL execution pipeline
    sql_pipeline = pipeline_container.get_pipeline("sql_execution")
    
    # Get dashboard pipeline
    dashboard_pipeline = pipeline_container.get_pipeline("dashboard_streaming")
    
    # Check if dashboard pipeline is available
    if dashboard_pipeline is None:
        print("❌ Dashboard streaming pipeline is not available")
        print("   💡 Skipping pipeline integration example")
        return {"status": "skipped", "reason": "dashboard_streaming_pipeline_not_available"}
    
    # The rest works the same way...
    queries = [
        {
            "sql": "SELECT COUNT(*) as count FROM information_schema.tables",
            "query": "Table count",
            "project_id": "system_info",
            "data_description": "Database schema information"
        }
    ]
    
    result = await dashboard_pipeline.run(
        queries=queries,
        project_id="integration_test"
    )
    
    return result


async def example_available_pipelines():
    """Example showing what pipelines are available and testing basic functionality"""
    
    print("🔍 Testing Available Pipelines")
    print("=" * 50)
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.agents.pipelines.pipeline_container import PipelineContainer
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize pipeline container
    pipeline_container = PipelineContainer.initialize()
    
    # Check all available pipelines
    print("📋 Checking available pipelines...")
    all_pipelines = pipeline_container.get_all_pipelines()
    
    available_pipelines = []
    unavailable_pipelines = []
    
    for name, pipeline in all_pipelines.items():
        if pipeline is not None:
            available_pipelines.append(name)
        else:
            unavailable_pipelines.append(name)
    
    print(f"✅ Available pipelines ({len(available_pipelines)}):")
    for name in sorted(available_pipelines):
        print(f"   - {name}")
    
    if unavailable_pipelines:
        print(f"❌ Unavailable pipelines ({len(unavailable_pipelines)}):")
        for name in sorted(unavailable_pipelines):
            print(f"   - {name}")
    
    # Test a simple pipeline if available
    if "sql_execution" in available_pipelines:
        print("\n🧪 Testing SQL Execution Pipeline...")
        try:
            sql_pipeline = pipeline_container.get_pipeline("sql_execution")
            
            # Simple test query
            test_result = await sql_pipeline.run(
                sql="SELECT 1 as test_column",
                project_id="pipeline_test"
            )
            
            print(f"   ✅ SQL execution test successful")
            print(f"   📊 Result type: {type(test_result)}")
            
        except Exception as e:
            print(f"   ❌ SQL execution test failed: {e}")
    
    elif "data_summarization" in available_pipelines:
        print("\n🧪 Testing Data Summarization Pipeline...")
        try:
            data_pipeline = pipeline_container.get_pipeline("data_summarization")
            
            # Simple test
            print(f"   ✅ Data summarization pipeline available")
            print(f"   📊 Pipeline type: {type(data_pipeline)}")
            
        except Exception as e:
            print(f"   ❌ Data summarization test failed: {e}")
    
    else:
        print("\n⚠️  No suitable test pipelines available")
    
    return {
        "available_pipelines": available_pipelines,
        "unavailable_pipelines": unavailable_pipelines,
        "total_pipelines": len(all_pipelines)
    }


async def example_basic_sql_execution():
    """Example of basic SQL execution using available pipelines"""
    
    print("🔍 Basic SQL Execution Example")
    print("=" * 50)
    
    # Use proper settings and dependencies initialization
    from app.settings import init_environment, get_settings
    from app.core.dependencies import get_llm, get_doc_store_provider
    from app.agents.pipelines.pipeline_container import PipelineContainer
    
    # Initialize environment and settings
    try:
        init_environment()
        settings = get_settings()
        print(f"✅ Environment initialized successfully")
    except Exception as e:
        print(f"⚠️  Environment initialization warning: {e}")
        print("   Continuing with default settings...")
    
    # Get proper dependencies
    llm = get_llm(temperature=0.0, model="gpt-4o-mini")
    doc_store_provider = get_doc_store_provider()
    
    # Initialize pipeline container
    pipeline_container = PipelineContainer.initialize()
    
    # Try to use sql_execution pipeline
    sql_pipeline = pipeline_container.get_pipeline("sql_execution")
    if sql_pipeline is None:
        print("❌ SQL execution pipeline not available")
        return {"status": "failed", "reason": "sql_execution_pipeline_not_available"}
    
    print("✅ SQL execution pipeline available")
    
    # Simple test queries
    test_queries = [
        {
            "sql": "SELECT 1 as test_column, 'Hello World' as message",
            "description": "Simple test query"
        },
        {
            "sql": "SELECT CURRENT_TIMESTAMP as current_time",
            "description": "Current timestamp query"
        }
    ]
    
    results = []
    
    for i, query_info in enumerate(test_queries):
        print(f"\n🧪 Testing query {i+1}: {query_info['description']}")
        
        try:
            result = await sql_pipeline.run(
                sql=query_info["sql"],
                project_id="basic_sql_test"
            )
            
            print(f"   ✅ Query {i+1} successful")
            print(f"   📊 Result type: {type(result)}")
            
            if hasattr(result, 'get'):
                success = result.get('success', False)
                print(f"   📈 Success: {success}")
                
                if success and hasattr(result, 'get'):
                    data = result.get('data', [])
                    if data:
                        print(f"   📋 Data rows: {len(data)}")
                        print(f"   🔍 Sample data: {data[0] if isinstance(data, list) else 'Complex data'}")
            
            results.append({
                "query": query_info["description"],
                "success": True,
                "result": result
            })
            
        except Exception as e:
            print(f"   ❌ Query {i+1} failed: {e}")
            results.append({
                "query": query_info["description"],
                "success": False,
                "error": str(e)
            })
    
    # Summary
    successful_queries = sum(1 for r in results if r["success"])
    total_queries = len(results)
    
    print(f"\n📊 Summary:")
    print(f"   Total queries: {total_queries}")
    print(f"   Successful: {successful_queries}")
    print(f"   Failed: {total_queries - successful_queries}")
    
    return {
        "status": "completed",
        "total_queries": total_queries,
        "successful_queries": successful_queries,
        "results": results
    }


async def debug_dashboard_pipeline_import():
    """Debug function to test the specific import that's failing"""
    
    print("🔍 Debugging Dashboard Pipeline Import Issues")
    print("=" * 50)
    
    try:
        # Test 1: Import the module
        print("1. Testing dashboard_streaming_pipeline module import...")
        from app.agents.pipelines.writers import dashboard_streaming_pipeline
        print("   ✅ Module import successful")
        
        # Test 2: Import the factory function
        print("2. Testing create_dashboard_streaming_pipeline import...")
        from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
        print("   ✅ Factory function import successful")
        
        # Test 3: Import the class
        print("3. Testing DashboardStreamingPipeline class import...")
        from app.agents.pipelines.writers.dashboard_streaming_pipeline import DashboardStreamingPipeline
        print("   ✅ Class import successful")
        
        # Test 4: Test the specific import that might be failing
        print("4. Testing DataSummarizationPipeline import...")
        from app.agents.pipelines.sql_execution import DataSummarizationPipeline
        print("   ✅ DataSummarizationPipeline import successful")
        
        # Test 5: Test creating an instance
        print("5. Testing instance creation...")
        from app.core.dependencies import get_llm
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        from app.core.engine_provider import EngineProvider
        
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        engine = EngineProvider.get_engine()
        
        dashboard_pipeline = create_dashboard_streaming_pipeline(
            engine=engine,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        print("   ✅ Dashboard pipeline instance created successfully")
        print(f"   📊 Instance type: {type(dashboard_pipeline)}")
        print(f"   📊 Instance name: {dashboard_pipeline.name}")
        
        return {"status": "success", "pipeline": dashboard_pipeline}
        
    except Exception as e:
        print(f"   ❌ Import/creation failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # Run the examples
    print("Dashboard Streaming Pipeline Examples")
    print("=" * 50)
    
    try:
        # Example 0: Check available pipelines first
        print("\n0. Available Pipelines Check:")
        pipeline_info = asyncio.run(example_available_pipelines())
        
        # Example 1: Concurrent execution with streaming
        print("\n1. Concurrent Execution Example:")
        try:
            result1 = asyncio.run(example_dashboard_streaming())
            if result1.get("status") == "skipped":
                print("   ⏭️  Skipped due to missing dashboard streaming pipeline")
            else:
                print("   ✅ Completed successfully")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        # Example 2: Sequential execution  
        print("\n2. Sequential Execution Example:")
        try:
            result2 = asyncio.run(example_sequential_execution())
            if result2.get("status") == "skipped":
                print("   ⏭️  Skipped due to missing dashboard streaming pipeline")
            else:
                print("   ✅ Completed successfully")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        # Example 3: Using DashboardService
        print("\n3. Dashboard Service Example:")
        try:
            result3 = asyncio.run(example_using_dashboard_service())
            print("   ✅ Completed successfully")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        # Example 4: Service Container Integration
        print("\n4. Service Container Integration:")
        try:
            result4 = asyncio.run(example_service_container_integration())
            print("   ✅ Completed successfully")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        # Example 5: Pipeline Integration
        print("\n5. Pipeline Integration Example:")
        try:
            result5 = asyncio.run(integration_example())
            if result5.get("status") == "skipped":
                print("   ⏭️  Skipped due to missing dashboard streaming pipeline")
            else:
                print("   ✅ Completed successfully")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        # Example 6: Basic SQL Execution
        print("\n6. Basic SQL Execution Example:")
        try:
            result6 = asyncio.run(example_basic_sql_execution())
            if result6.get("status") == "failed":
                print("   ❌ Failed: SQL execution pipeline not available")
            else:
                print("   ✅ Completed successfully")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        # Example 7: Debug Dashboard Pipeline Import
        print("\n7. Debug Dashboard Pipeline Import:")
        try:
            debug_result = asyncio.run(debug_dashboard_pipeline_import())
            if debug_result.get("status") == "success":
                print("   ✅ Dashboard pipeline import debug successful")
            else:
                print("   ❌ Dashboard pipeline import debug failed")
        except Exception as e:
            print(f"   ❌ Debug failed: {e}")
        
        print("\n🎉 Examples completed!")
        print(f"📊 Pipeline Summary: {pipeline_info['total_pipelines']} total, {len(pipeline_info['available_pipelines'])} available, {len(pipeline_info['unavailable_pipelines'])} unavailable")
        
    except Exception as e:
        print(f"\n💥 Error running examples: {e}")
        import traceback
        traceback.print_exc()