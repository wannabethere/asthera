"""
Simple test script for the render_visualization service.

This script provides a quick way to test the new render_visualization service
without running the full example.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_render_visualization_service():
    """
    Test the render_visualization service with a simple example
    """
    try:
        # Import required components
        from app.services.sql.sql_helper_services import SQLHelperService
        from app.agents.pipelines.pipeline_container import PipelineContainer
        from app.core.engine_provider import EngineProvider
        from app.core.dependencies import get_llm
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        from app.agents.nodes.sql.enhanced_chart_generation import create_enhanced_vega_lite_chart_generation_pipeline
        from app.agents.nodes.sql.plotly_chart_generation import create_plotly_chart_generation_pipeline
        from app.agents.nodes.sql.powerbi_chart_generation import create_powerbi_chart_generation_pipeline
        from app.agents.pipelines.sql_execution import ChartExecutionPipeline
        
        print("🧪 Testing Render Visualization Service")
        print("=" * 50)
        
        # Setup components
        llm = get_llm()
        engine = EngineProvider.get_engine()
        retrieval_helper = RetrievalHelper()
        
        # Create chart generation pipelines
        chart_generation_pipeline = create_enhanced_vega_lite_chart_generation_pipeline()
        plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline(llm)
        powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline(llm)
        
        # Create chart execution pipeline
        chart_execution_pipeline = ChartExecutionPipeline(
            name="Chart Execution Pipeline",
            version="1.0",
            description="Execute charts with SQL data using ChartExecutor",
            llm=llm,
            retrieval_helper=retrieval_helper,
            engine=engine,
            chart_generation_pipeline=chart_generation_pipeline,
            plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
            powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
        )
        
        # Get pipeline container and add chart execution pipeline
        pipeline_container = PipelineContainer.get_instance()
        pipeline_container.add_pipeline("chart_execution", chart_execution_pipeline)
        
        # Create SQL helper service
        sql_helper_service = SQLHelperService(
            pipeline_container=pipeline_container,
            enable_enhanced_sql=True
        )
        
        # Test parameters
        query_id = "test_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        query = "Show me a simple bar chart"
        sql = "SELECT category, value FROM test_data ORDER BY value DESC LIMIT 10"
        project_id = "test_render_visualization"
        
        # Test configuration
        configuration = {
            "chart_format": "vega_lite",
            "include_other_formats": False,
            "page_size": 100,
            "max_rows": 1000,
            "language": "English"
        }
        
        # Define simple status callback
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"📊 {status}")
        
        print(f"Query ID: {query_id}")
        print(f"Query: {query}")
        print(f"SQL: {sql}")
        print(f"Project ID: {project_id}")
        print(f"Configuration: {configuration}")
        print()
        
        # Test the service
        print("🚀 Starting render_visualization test...")
        
        result = await sql_helper_service.render_visualization(
            query_id=query_id,
            query=query,
            sql=sql,
            project_id=project_id,
            configuration=configuration,
            status_callback=status_callback
        )
        
        print("\n📋 Test Results:")
        print(f"Success: {result.get('success', False)}")
        
        if result.get("success"):
            data = result.get("data", {})
            print(f"✅ Test PASSED!")
            print(f"   Chart Type: {data.get('chart_type', 'Unknown')}")
            print(f"   Chart Format: {data.get('chart_format', 'Unknown')}")
            print(f"   Data Count: {data.get('data_count', 0)}")
            print(f"   Validation: {data.get('validation', {}).get('valid', False)}")
            
            # Check if chart schema exists
            chart_schema = data.get('chart_schema', {})
            if chart_schema:
                print(f"   Chart Schema: {len(chart_schema)} keys")
            else:
                print(f"   Chart Schema: Empty")
                
            # Check metadata
            metadata = result.get("metadata", {})
            print(f"   Metadata: {len(metadata)} keys")
            
        else:
            print(f"❌ Test FAILED!")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        
        print("\n" + "=" * 50)
        print("🧪 Test completed!")
        
        return result.get("success", False)
        
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        logger.exception("Error in test")
        return False


async def test_streaming():
    """
    Test the streaming version of the render_visualization service
    """
    try:
        from app.services.sql.sql_helper_services import SQLHelperService
        from app.agents.pipelines.pipeline_container import PipelineContainer
        
        print("\n🌊 Testing Streaming Render Visualization")
        print("=" * 50)
        
        # Get pipeline container
        pipeline_container = PipelineContainer.get_instance()
        
        # Create SQL helper service
        sql_helper_service = SQLHelperService(pipeline_container=pipeline_container)
        
        # Test parameters
        query_id = "stream_test_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        query = "Stream test visualization"
        sql = "SELECT id, name, value FROM stream_test_data LIMIT 5"
        project_id = "test_streaming"
        
        configuration = {
            "chart_format": "vega_lite",
            "page_size": 50,
            "max_rows": 500
        }
        
        print(f"Query ID: {query_id}")
        print(f"Query: {query}")
        print(f"SQL: {sql}")
        print()
        
        print("🚀 Starting streaming test...")
        
        update_count = 0
        async for update in sql_helper_service.stream_visualization_rendering(
            query_id=query_id,
            query=query,
            sql=sql,
            project_id=project_id,
            configuration=configuration
        ):
            update_count += 1
            status = update.get("status", "unknown")
            print(f"📡 Update {update_count}: {status}")
            
            if status in ["completed", "error", "stopped"]:
                if status == "completed":
                    print("✅ Streaming test PASSED!")
                else:
                    print(f"❌ Streaming test ended with status: {status}")
                break
        
        print(f"\n📊 Total updates received: {update_count}")
        print("🌊 Streaming test completed!")
        
        return update_count > 0
        
    except Exception as e:
        print(f"❌ Streaming test error: {str(e)}")
        logger.exception("Error in streaming test")
        return False


if __name__ == "__main__":
    # Run tests
    print("🧪 Running Render Visualization Service Tests")
    print("=" * 60)
    
    # Test basic functionality
    basic_success = asyncio.run(test_render_visualization_service())
    
    # Test streaming functionality
    streaming_success = asyncio.run(test_streaming())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Basic Test: {'✅ PASSED' if basic_success else '❌ FAILED'}")
    print(f"   Streaming Test: {'✅ PASSED' if streaming_success else '❌ FAILED'}")
    
    if basic_success and streaming_success:
        print("\n🎉 All tests PASSED! Render visualization service is working correctly.")
    else:
        print("\n⚠️ Some tests FAILED. Please check the implementation.")
    
    print("=" * 60) 