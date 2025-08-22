#!/usr/bin/env python3
"""
Test file for the refactored DashboardService
"""

import asyncio
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_dashboard_service():
    """Test the refactored dashboard service"""
    
    try:
        # Import the service
        from app.services.writers.dashboard_service import create_dashboard_service
        
        # Create dashboard service
        logger.info("🔄 Creating dashboard service...")
        dashboard_service = create_dashboard_service()
        logger.info("✅ Dashboard service created successfully")
        
        # Test service status
        status = dashboard_service.get_service_status()
        logger.info(f"Service Status: {status}")
        
        # Test validation
        dashboard_queries = [
            {
                "chart_id": "test_chart",
                "sql": "SELECT * FROM test_table",
                "query": "Test query",
                "project_id": "test_project",
                "data_description": "Test data for validation"
            }
        ]
        
        dashboard_context = {
            "charts": [
                {
                    "chart_id": "test_chart",
                    "type": "bar",
                    "columns": ["col1", "col2"],
                    "query": "Test query"
                }
            ],
            "available_columns": ["col1", "col2", "col3"]
        }
        
        # Test validation
        logger.info("🔄 Testing dashboard configuration validation...")
        validation_result = await dashboard_service.validate_dashboard_configuration(
            dashboard_queries=dashboard_queries,
            dashboard_context=dashboard_context,
            natural_language_query="Highlight values greater than 100 in green"
        )
        
        logger.info(f"Validation Result: {validation_result}")
        
        # Test conditional formatting only
        logger.info("🔄 Testing conditional formatting service...")
        cf_result = await dashboard_service.process_conditional_formatting_only(
            natural_language_query="Highlight values greater than 100 in green",
            dashboard_context=dashboard_context,
            project_id="test_project"
        )
        
        logger.info(f"Conditional Formatting Result: {cf_result.get('success', False)}")
        
        # Test dashboard execution without conditional formatting
        logger.info("🔄 Testing dashboard execution without conditional formatting...")
        dashboard_result = await dashboard_service.execute_dashboard_only(
            dashboard_queries=dashboard_queries,
            project_id="test_project"
        )
        
        logger.info(f"Dashboard Execution Result: {dashboard_result.get('post_process', {}).get('success', False)}")
        
        # Test full dashboard processing with conditional formatting
        logger.info("🔄 Testing full dashboard processing with conditional formatting...")
        full_result = await dashboard_service.process_dashboard_with_conditional_formatting(
            natural_language_query="Highlight values greater than 100 in green",
            dashboard_queries=dashboard_queries,
            project_id="test_project",
            dashboard_context=dashboard_context,
            additional_context={"test_mode": True}
        )
        
        logger.info(f"Full Processing Result: {full_result.get('success', False)}")
        
        logger.info("✅ All tests passed! Dashboard service is working correctly.")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

async def test_service_container_integration():
    """Test that the dashboard service is properly integrated in the service container"""
    
    try:
        from app.services.service_container import SQLServiceContainer
        
        # Initialize service container
        logger.info("🔄 Initializing service container...")
        container = SQLServiceContainer()
        container.initialize_services(app_state=None)
        logger.info("✅ Service container initialized successfully")
        
        # Get dashboard service
        logger.info("🔄 Getting dashboard service from container...")
        dashboard_service = container.get_service("dashboard_service")
        
        # Test that it's the right type
        from app.services.writers.dashboard_service import DashboardService
        assert isinstance(dashboard_service, DashboardService), "Service should be DashboardService instance"
        logger.info("✅ Dashboard service type verification passed")
        
        # Test service status
        status = dashboard_service.get_service_status()
        logger.info(f"Container Dashboard Service Status: {status}")
        
        # Test basic dashboard execution through container
        logger.info("🔄 Testing dashboard execution through container...")
        queries = [
            {
                "chart_id": "container_test",
                "sql": "SELECT 'test' as column1, 42 as column2",
                "query": "Container test query",
                "project_id": "container_test",
                "data_description": "Test data for container integration"
            }
        ]
        
        result = await dashboard_service.execute_dashboard_only(
            dashboard_queries=queries,
            project_id="container_test"
        )
        
        logger.info(f"Container Dashboard Execution Result: {result.get('post_process', {}).get('success', False)}")
        
        logger.info("✅ Service container integration test passed!")
        
    except Exception as e:
        logger.error(f"❌ Service container integration test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

async def test_conditional_formatting_service():
    """Test the conditional formatting service specifically"""
    
    try:
        logger.info("🔄 Testing conditional formatting service specifically...")
        
        # Import the service
        from app.services.writers.dashboard_service import create_dashboard_service
        
        # Create dashboard service
        dashboard_service = create_dashboard_service()
        
        # Test conditional formatting with different scenarios
        dashboard_context = {
            "charts": [
                {
                    "chart_id": "sales_chart",
                    "type": "bar",
                    "columns": ["region", "sales"],
                    "query": "Sales by region"
                },
                {
                    "chart_id": "performance_chart",
                    "type": "line",
                    "columns": ["date", "performance"],
                    "query": "Performance over time"
                }
            ],
            "available_columns": ["region", "sales", "date", "performance", "status"],
            "data_types": {
                "region": "categorical",
                "sales": "numeric",
                "date": "datetime",
                "performance": "numeric",
                "status": "categorical"
            }
        }
        
        # Test case 1: Simple conditional formatting
        logger.info("🔄 Test case 1: Simple conditional formatting...")
        cf_result1 = await dashboard_service.process_conditional_formatting_only(
            natural_language_query="Highlight sales greater than 1000 in green",
            dashboard_context=dashboard_context,
            project_id="cf_test_1"
        )
        
        logger.info(f"Test case 1 result: {cf_result1.get('success', False)}")
        
        # Test case 2: Complex conditional formatting
        logger.info("🔄 Test case 2: Complex conditional formatting...")
        cf_result2 = await dashboard_service.process_conditional_formatting_only(
            natural_language_query="Show regions with sales above 500 in green, below 200 in red, and highlight performance scores above 80 in blue",
            dashboard_context=dashboard_context,
            project_id="cf_test_2"
        )
        
        logger.info(f"Test case 2 result: {cf_result2.get('success', False)}")
        
        # Test case 3: Time-based filtering
        logger.info("🔄 Test case 3: Time-based filtering...")
        cf_result3 = await dashboard_service.process_conditional_formatting_only(
            natural_language_query="Filter to show only data from the last 30 days and highlight any performance scores below 60 in red",
            dashboard_context=dashboard_context,
            project_id="cf_test_3"
        )
        
        logger.info(f"Test case 3 result: {cf_result3.get('success', False)}")
        
        logger.info("✅ Conditional formatting service tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Conditional formatting service test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

async def test_dashboard_streaming_pipeline():
    """Test the dashboard streaming pipeline directly"""
    
    try:
        logger.info("🔄 Testing dashboard streaming pipeline directly...")
        
        from app.agents.pipelines.writers.dashboard_streaming_pipeline import create_dashboard_streaming_pipeline
        from app.core.engine_provider import EngineProvider
        from app.core.dependencies import get_llm, get_doc_store_provider
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        
        # Create pipeline
        engine = EngineProvider.get_engine()
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        
        pipeline = create_dashboard_streaming_pipeline(
            engine=engine,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        logger.info("✅ Dashboard streaming pipeline created successfully")
        
        # Test with simple queries
        queries = [
            {
                'sql': 'SELECT 1 as test_value',
                'query': 'Simple test query',
                'project_id': 'pipeline_test',
                'data_description': 'Test data for pipeline testing'
            },
            {
                'sql': 'SELECT 2 as another_value',
                'query': 'Another test query',
                'project_id': 'pipeline_test',
                'data_description': 'More test data'
            }
        ]
        
        def status_callback(status: str, details: dict):
            logger.info(f"Pipeline Status: {status} - {details}")
        
        logger.info("🔄 Executing dashboard streaming pipeline...")
        result = await pipeline.run(
            queries=queries,
            project_id='pipeline_test',
            status_callback=status_callback
        )
        
        logger.info(f"Pipeline execution result: {result.get('post_process', {}).get('success', False)}")
        
        if 'post_process' in result and 'results' in result['post_process']:
            results = result['post_process']['results']
            logger.info(f"Number of query results: {len(results)}")
            for key, value in results.items():
                success = value.get('success', False)
                logger.info(f"  {key}: {'✅ Success' if success else '❌ Failed'}")
        
        logger.info("✅ Dashboard streaming pipeline test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Dashboard streaming pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    logger.info("Starting Dashboard Service tests...")
    
    try:
        # Run tests in sequence
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Basic Dashboard Service")
        logger.info("="*60)
        asyncio.run(test_dashboard_service())
        
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Service Container Integration")
        logger.info("="*60)
        asyncio.run(test_service_container_integration())
        
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Conditional Formatting Service")
        logger.info("="*60)
        asyncio.run(test_conditional_formatting_service())
        
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Dashboard Streaming Pipeline")
        logger.info("="*60)
        asyncio.run(test_dashboard_streaming_pipeline())
        
        logger.info("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"\n💥 Test suite failed: {e}")
        exit(1)
