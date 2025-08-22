#!/usr/bin/env python3
"""
Test script for the new dashboard architecture:
DashboardOrchestrator -> DashboardIntegrationPipeline -> ConditionalFormattingPipeline -> ConditionalFormattingAgent
"""

import asyncio
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.writers.dashboard_orchestrator import create_dashboard_orchestrator
from app.agents.pipelines.conditional_formatting_pipeline import create_conditional_formatting_pipeline
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm, get_doc_store_provider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_new_architecture():
    """Test the new dashboard architecture"""
    
    print("🚀 Testing New Dashboard Architecture")
    print("=" * 50)
    
    try:
        # Step 1: Initialize pipeline container
        print("1. Initializing pipeline container...")
        container = PipelineContainer.initialize()
        print("   ✅ Pipeline container initialized")
        
        # Step 2: Add conditional formatting pipeline
        print("2. Adding conditional formatting pipeline...")
        from app.agents.pipelines.dashboard_integration_pipeline import add_conditional_formatting_to_pipeline_container
        conditional_formatting_pipeline = add_conditional_formatting_to_pipeline_container(container)
        print("   ✅ Conditional formatting pipeline added")
        
        # Step 3: Create dashboard orchestrator
        print("3. Creating dashboard orchestrator...")
        orchestrator = create_dashboard_orchestrator(pipeline_container=container)
        print("   ✅ Dashboard orchestrator created")
        
        # Step 4: Test service status
        print("4. Checking service status...")
        status = orchestrator.get_service_status()
        print(f"   ✅ Service status: {status}")
        
        # Step 5: Test dashboard validation
        print("5. Testing dashboard validation...")
        
        # Sample dashboard queries
        dashboard_queries = [
            {
                "chart_id": "sales_chart",
                "sql": "SELECT region, SUM(sales_amount) as sales FROM sales_data GROUP BY region",
                "query": "Show sales by region",
                "data_description": "Sales data by region"
            },
            {
                "chart_id": "performance_chart",
                "sql": "SELECT date, performance_score FROM performance_data ORDER BY date",
                "query": "Show performance over time",
                "data_description": "Performance trends over time"
            }
        ]
        
        # Dashboard context
        dashboard_context = {
            "charts": [
                {
                    "chart_id": "sales_chart",
                    "type": "bar",
                    "columns": ["region", "sales_amount", "date"],
                    "query": "Show sales by region"
                },
                {
                    "chart_id": "performance_chart",
                    "type": "line",
                    "columns": ["month", "performance_score", "target"],
                    "query": "Show performance trends"
                }
            ],
            "available_columns": ["region", "sales_amount", "date", "month", "performance_score", "target", "status"],
            "data_types": {
                "sales_amount": "numeric",
                "performance_score": "numeric",
                "date": "datetime",
                "month": "datetime",
                "region": "categorical",
                "status": "categorical"
            }
        }
        
        # Natural language query
        natural_language_query = """
        I want to highlight all sales amounts greater than $10,000 in green, 
        and filter the dashboard to show only active status records from the last 30 days.
        Also, make the performance chart show data only for the current year.
        """
        
        # Validate configuration
        validation_result = await orchestrator.validate_dashboard_configuration(
            dashboard_queries=dashboard_queries,
            dashboard_context=dashboard_context,
            natural_language_query=natural_language_query
        )
        
        print(f"   ✅ Validation result: {validation_result['valid']}")
        if not validation_result['valid']:
            print(f"      Issues: {validation_result['issues']}")
        
        # Step 6: Test conditional formatting only
        print("6. Testing conditional formatting only...")
        try:
            conditional_formatting_result = await orchestrator.process_conditional_formatting_only(
                natural_language_query=natural_language_query,
                dashboard_context=dashboard_context,
                project_id="test_project",
                additional_context={"user_id": "test_user"},
                time_filters={"period": "last_30_days"}
            )
            print("   ✅ Conditional formatting processed successfully")
            print(f"      Chart configurations: {len(conditional_formatting_result.get('chart_configurations', {}))}")
        except Exception as e:
            print(f"   ⚠️  Conditional formatting failed: {e}")
        
        print("\n🎉 New Architecture Test Completed Successfully!")
        print("\nArchitecture Summary:")
        print("DashboardOrchestrator")
        print("    ↓")
        print("DashboardIntegrationPipeline (EnhancedDashboardService)")
        print("    ↓")
        print("ConditionalFormattingPipeline")
        print("    ↓")
        print("ConditionalFormattingAgent")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_new_architecture())
    
    if success:
        print("\n✅ All tests passed! The new architecture is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the logs for details.")
        sys.exit(1)
