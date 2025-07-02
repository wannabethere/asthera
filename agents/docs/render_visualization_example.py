"""
Example script demonstrating the usage of the render_visualization service.

This script shows how to use the new render_visualization service that combines
chart generation and execution to provide a complete visualization solution.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def example_render_visualization():
    """
    Example demonstrating how to use the render_visualization service
    """
    try:
        # Import required components
        from app.services.sql.sql_helper_services import SQLHelperService
        from app.agents.pipelines.pipeline_container import PipelineContainer
        from app.core.engine_provider import EngineProvider
        from app.core.dependencies import get_llm
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        from app.agents.nodes.sql.chart_generation import create_vega_lite_chart_generation_pipeline
        from app.agents.nodes.sql.plotly_chart_generation import create_plotly_chart_generation_pipeline
        from app.agents.nodes.sql.powerbi_chart_generation import create_powerbi_chart_generation_pipeline
        from app.agents.pipelines.sql_execution import ChartExecutionPipeline
        
        print("🚀 Starting Render Visualization Service Example")
        print("=" * 70)
        
        # Setup components
        llm = get_llm()
        engine = EngineProvider.get_engine()
        retrieval_helper = RetrievalHelper()
        
        # Create chart generation pipelines
        chart_generation_pipeline = create_vega_lite_chart_generation_pipeline()
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
        
        # Define status callback function
        def status_callback(status: str, details: Dict[str, Any] = None):
            """Example status callback function"""
            print(f"📊 Status Update: {status}")
            if details:
                for key, value in details.items():
                    print(f"   {key}: {value}")
            print()
        
        # Example 1: Basic visualization rendering
        print("📈 Example 1: Basic Visualization Rendering")
        print("-" * 50)
        
        query_id = "example_1_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        query = "Show me sales trends by region over time"
        sql = "SELECT date, region, sales_amount FROM sales_data ORDER BY date"
        project_id = "render_visualization_example_1"
        
        # Basic configuration
        configuration = {
            "chart_format": "vega_lite",
            "include_other_formats": False,
            "page_size": 500,
            "max_rows": 5000,
            "language": "English"
        }
        
        try:
            result = await sql_helper_service.render_visualization(
                query_id=query_id,
                query=query,
                sql=sql,
                project_id=project_id,
                configuration=configuration,
                status_callback=status_callback
            )
            
            if result.get("success"):
                data = result.get("data", {})
                print(f"✅ Visualization rendered successfully!")
                print(f"   Chart Type: {data.get('chart_type', 'Unknown')}")
                print(f"   Chart Format: {data.get('chart_format', 'Unknown')}")
                print(f"   Data Count: {data.get('data_count', 0)}")
                print(f"   Validation Success: {data.get('validation', {}).get('valid', False)}")
                print(f"   Reasoning: {data.get('reasoning', '')[:100]}...")
                
                # Check chart schema
                chart_schema = data.get('chart_schema', {})
                if chart_schema:
                    print(f"   Chart Schema Keys: {list(chart_schema.keys())}")
            else:
                print(f"❌ Visualization rendering failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error in basic example: {str(e)}")
        
        print("\n" + "=" * 70)
        
        # Example 2: Multi-format visualization rendering
        print("📊 Example 2: Multi-Format Visualization Rendering")
        print("-" * 50)
        
        query_id_2 = "example_2_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        query_2 = "Display customer purchase patterns by category"
        sql_2 = "SELECT customer_id, purchase_date, amount, product_category FROM customer_purchases ORDER BY purchase_date"
        project_id_2 = "render_visualization_example_2"
        
        # Multi-format configuration
        configuration_2 = {
            "chart_format": "vega_lite",
            "include_other_formats": True,
            "use_multi_format": True,
            "page_size": 1000,
            "max_rows": 10000,
            "enable_pagination": True,
            "sort_by": "purchase_date",
            "sort_order": "ASC",
            "timeout_seconds": 60,
            "cache_results": True,
            "cache_ttl_seconds": 600,
            "language": "English"
        }
        
        try:
            result_2 = await sql_helper_service.render_visualization(
                query_id=query_id_2,
                query=query_2,
                sql=sql_2,
                project_id=project_id_2,
                configuration=configuration_2,
                status_callback=status_callback
            )
            
            if result_2.get("success"):
                data_2 = result_2.get("data", {})
                print(f"✅ Multi-format visualization rendered successfully!")
                print(f"   Chart Type: {data_2.get('chart_type', 'Unknown')}")
                print(f"   Chart Format: {data_2.get('chart_format', 'Unknown')}")
                print(f"   Data Count: {data_2.get('data_count', 0)}")
                
                # Check for other format schemas
                if 'plotly_schema' in data_2:
                    print(f"   ✅ Plotly schema available")
                if 'powerbi_schema' in data_2:
                    print(f"   ✅ PowerBI schema available")
                if 'vega_lite_schema' in data_2:
                    print(f"   ✅ Vega-Lite schema available")
                    
                # Show execution config
                exec_config = data_2.get('execution_config', {})
                print(f"   Execution Config: {exec_config}")
                
            else:
                print(f"❌ Multi-format visualization rendering failed: {result_2.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error in multi-format example: {str(e)}")
        
        print("\n" + "=" * 70)
        
        # Example 3: Streaming visualization rendering
        print("🌊 Example 3: Streaming Visualization Rendering")
        print("-" * 50)
        
        query_id_3 = "example_3_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        query_3 = "Analyze revenue growth by quarter"
        sql_3 = "SELECT quarter, revenue, growth_rate FROM quarterly_revenue ORDER BY quarter"
        project_id_3 = "render_visualization_example_3"
        
        # Streaming configuration
        configuration_3 = {
            "chart_format": "plotly",
            "include_other_formats": True,
            "page_size": 200,
            "max_rows": 2000,
            "language": "English"
        }
        
        try:
            print("Starting streaming visualization rendering...")
            update_count = 0
            
            async for update in sql_helper_service.stream_visualization_rendering(
                query_id=query_id_3,
                query=query_3,
                sql=sql_3,
                project_id=project_id_3,
                configuration=configuration_3
            ):
                update_count += 1
                status = update.get("status", "unknown")
                print(f"📡 Stream Update {update_count}: {status}")
                
                if status == "completed":
                    data_3 = update.get("data", {})
                    print(f"   ✅ Streaming completed!")
                    print(f"   Chart Type: {data_3.get('chart_type', 'Unknown')}")
                    print(f"   Chart Format: {data_3.get('chart_format', 'Unknown')}")
                    print(f"   Data Count: {data_3.get('data_count', 0)}")
                    break
                elif status == "error":
                    print(f"   ❌ Streaming error: {update.get('error', 'Unknown error')}")
                    break
                elif status == "stopped":
                    print(f"   ⏹️ Streaming stopped")
                    break
                    
        except Exception as e:
            print(f"❌ Error in streaming example: {str(e)}")
        
        print("\n" + "=" * 70)
        
        # Example 4: Different chart formats
        print("🎨 Example 4: Different Chart Formats")
        print("-" * 50)
        
        formats_to_test = ["vega_lite", "plotly", "powerbi"]
        
        for i, chart_format in enumerate(formats_to_test, 1):
            print(f"\nTesting {chart_format.upper()} format:")
            
            query_id_format = f"example_4_{chart_format}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            query_format = f"Show sales distribution by {chart_format} format"
            sql_format = "SELECT product_category, sales_amount FROM sales_summary ORDER BY sales_amount DESC"
            project_id_format = f"render_visualization_example_4_{chart_format}"
            
            configuration_format = {
                "chart_format": chart_format,
                "include_other_formats": False,
                "page_size": 300,
                "max_rows": 3000,
                "language": "English"
            }
            
            try:
                result_format = await sql_helper_service.render_visualization(
                    query_id=query_id_format,
                    query=query_format,
                    sql=sql_format,
                    project_id=project_id_format,
                    configuration=configuration_format
                )
                
                if result_format.get("success"):
                    data_format = result_format.get("data", {})
                    print(f"   ✅ {chart_format.upper()} visualization successful")
                    print(f"   Chart Type: {data_format.get('chart_type', 'Unknown')}")
                    print(f"   Data Count: {data_format.get('data_count', 0)}")
                else:
                    print(f"   ❌ {chart_format.upper()} visualization failed: {result_format.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"   ❌ Error testing {chart_format}: {str(e)}")
        
        print("\n" + "=" * 70)
        print("🎉 Render Visualization Service Example Completed!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error in main example: {str(e)}")
        logger.exception("Error in render visualization example")


async def example_error_handling():
    """
    Example demonstrating error handling in the render_visualization service
    """
    try:
        from app.services.sql.sql_helper_services import SQLHelperService
        from app.agents.pipelines.pipeline_container import PipelineContainer
        
        print("\n🔧 Error Handling Example")
        print("=" * 50)
        
        # Create SQL helper service
        pipeline_container = PipelineContainer.get_instance()
        sql_helper_service = SQLHelperService(pipeline_container=pipeline_container)
        
        # Test with invalid SQL
        query_id = "error_example_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        query = "Show me invalid data"
        sql = "SELECT * FROM non_existent_table"  # Invalid SQL
        project_id = "error_handling_example"
        
        try:
            result = await sql_helper_service.render_visualization(
                query_id=query_id,
                query=query,
                sql=sql,
                project_id=project_id
            )
            
            if not result.get("success"):
                print(f"✅ Error properly handled: {result.get('error', 'Unknown error')}")
            else:
                print("❌ Expected error was not caught")
                
        except Exception as e:
            print(f"✅ Exception properly caught: {str(e)}")
        
        # Test with missing pipeline
        query_id_2 = "error_example_2_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Remove chart execution pipeline to test missing pipeline error
            if "chart_execution" in pipeline_container._pipelines:
                del pipeline_container._pipelines["chart_execution"]
            
            result_2 = await sql_helper_service.render_visualization(
                query_id=query_id_2,
                query="Test missing pipeline",
                sql="SELECT 1",
                project_id="missing_pipeline_test"
            )
            
            if not result_2.get("success"):
                print(f"✅ Missing pipeline error properly handled: {result_2.get('error', 'Unknown error')}")
            else:
                print("❌ Expected missing pipeline error was not caught")
                
        except Exception as e:
            print(f"✅ Missing pipeline exception properly caught: {str(e)}")
        
        print("✅ Error handling example completed")
        
    except Exception as e:
        print(f"❌ Error in error handling example: {str(e)}")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(example_render_visualization())
    asyncio.run(example_error_handling()) 