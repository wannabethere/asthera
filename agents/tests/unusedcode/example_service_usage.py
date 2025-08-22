#!/usr/bin/env python3
"""
Example showing how other services can use the integrated dashboard pipelines.
This demonstrates the integration is working correctly.
"""

import asyncio
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from app.agents.pipelines.pipeline_container import PipelineContainer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExampleDashboardService:
    """Example service that uses the integrated dashboard pipelines"""
    
    def __init__(self):
        """Initialize the service with pipeline container access"""
        self.pipeline_container = PipelineContainer.initialize()
        
        # Get the dashboard orchestrator pipeline
        self.dashboard_orchestrator = self.pipeline_container.get_pipeline("dashboard_orchestrator")
        
        # Get individual pipelines if needed
        self.conditional_formatting_pipeline = self.pipeline_container.get_pipeline("conditional_formatting_generation")
        self.enhanced_streaming_pipeline = self.pipeline_container.get_pipeline("enhanced_dashboard_streaming")
        self.basic_streaming_pipeline = self.pipeline_container.get_pipeline("dashboard_streaming")
        
        print("✅ ExampleDashboardService initialized with all dashboard pipelines")
    
    async def process_dashboard_request(
        self,
        dashboard_queries: list,
        natural_language_query: str = None,
        dashboard_context: dict = None,
        project_id: str = "example_project"
    ):
        """Process a dashboard request using the integrated pipelines"""
        
        print(f"\n🚀 Processing dashboard request for project: {project_id}")
        print(f"   - Queries: {len(dashboard_queries)}")
        print(f"   - Conditional formatting: {'Yes' if natural_language_query else 'No'}")
        
        try:
            # Use the dashboard orchestrator pipeline for complete workflow
            result = await self.dashboard_orchestrator.run(
                dashboard_queries=dashboard_queries,
                natural_language_query=natural_language_query,
                dashboard_context=dashboard_context or self._create_sample_context(),
                project_id=project_id,
                status_callback=self._status_callback
            )
            
            print("✅ Dashboard processing completed successfully!")
            return result
            
        except Exception as e:
            print(f"❌ Dashboard processing failed: {e}")
            logger.error(f"Dashboard processing failed: {e}", exc_info=True)
            raise
    
    async def generate_conditional_formatting_only(
        self,
        natural_language_query: str,
        dashboard_context: dict,
        project_id: str = "example_project"
    ):
        """Generate conditional formatting rules without applying them"""
        
        print(f"\n🔧 Generating conditional formatting rules for project: {project_id}")
        
        try:
            result = await self.conditional_formatting_pipeline.run(
                natural_language_query=natural_language_query,
                dashboard_context=dashboard_context,
                project_id=project_id,
                status_callback=self._status_callback
            )
            
            print("✅ Conditional formatting rules generated successfully!")
            return result
            
        except Exception as e:
            print(f"❌ Conditional formatting generation failed: {e}")
            logger.error(f"Conditional formatting generation failed: {e}", exc_info=True)
            raise
    
    async def apply_rules_and_stream(
        self,
        dashboard_queries: list,
        enhanced_dashboard: dict,
        project_id: str = "example_project"
    ):
        """Apply conditional formatting rules and stream results"""
        
        print(f"\n📊 Applying rules and streaming results for project: {project_id}")
        
        try:
            result = await self.enhanced_streaming_pipeline.run(
                dashboard_queries=dashboard_queries,
                enhanced_dashboard=enhanced_dashboard,
                project_id=project_id,
                status_callback=self._status_callback
            )
            
            print("✅ Rules applied and results streamed successfully!")
            return result
            
        except Exception as e:
            print(f"❌ Rule application and streaming failed: {e}")
            logger.error(f"Rule application and streaming failed: {e}", exc_info=True)
            raise
    
    def _create_sample_context(self):
        """Create sample dashboard context"""
        return {
            "charts": [
                {
                    "chart_id": "sample_chart",
                    "type": "bar",
                    "columns": ["category", "value"],
                    "query": "Show sample data"
                }
            ],
            "available_columns": ["category", "value", "date"],
            "data_types": {
                "category": "categorical",
                "value": "numeric",
                "date": "datetime"
            }
        }
    
    def _status_callback(self, status: str, details: dict = None):
        """Status callback for monitoring pipeline progress"""
        print(f"   📊 Status: {status}")
        if details:
            for key, value in details.items():
                if key != "project_id":  # Skip project_id to reduce noise
                    print(f"      {key}: {value}")


async def example_usage():
    """Example of how to use the integrated dashboard pipelines"""
    
    print("🚀 Dashboard Pipeline Integration Example")
    print("=" * 50)
    
    try:
        # Step 1: Create the example service
        print("1. Creating example dashboard service...")
        service = ExampleDashboardService()
        print("   ✅ Service created successfully")
        
        # Step 2: Sample data
        print("\n2. Preparing sample data...")
        
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
                    "columns": ["date", "performance_score"],
                    "query": "Show performance over time"
                }
            ],
            "available_columns": ["region", "sales_amount", "date", "performance_score"],
            "data_types": {
                "sales_amount": "numeric",
                "performance_score": "numeric",
                "date": "datetime",
                "region": "categorical"
            }
        }
        
        natural_language_query = "Highlight sales amounts greater than $10,000 in green"
        
        print("   ✅ Sample data prepared")
        
        # Step 3: Test complete workflow
        print("\n3. Testing complete dashboard workflow...")
        complete_result = await service.process_dashboard_request(
            dashboard_queries=dashboard_queries,
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="complete_workflow_example"
        )
        
        print(f"   ✅ Complete workflow result keys: {list(complete_result.keys())}")
        
        # Step 4: Test individual pipeline usage
        print("\n4. Testing individual pipeline usage...")
        
        # Generate conditional formatting only
        cf_result = await service.generate_conditional_formatting_only(
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="individual_pipeline_example"
        )
        
        print(f"   ✅ Conditional formatting result keys: {list(cf_result.keys())}")
        
        # Extract enhanced dashboard
        enhanced_dashboard = cf_result.get("post_process", {}).get("enhanced_dashboard", {})
        
        # Apply rules and stream
        streaming_result = await service.apply_rules_and_stream(
            dashboard_queries=dashboard_queries,
            enhanced_dashboard=enhanced_dashboard,
            project_id="individual_pipeline_example"
        )
        
        print(f"   ✅ Streaming result keys: {list(streaming_result.keys())}")
        
        # Step 5: Summary
        print("\n🎉 Integration Example Completed Successfully!")
        print("\n📋 What was demonstrated:")
        print("   ✅ Dashboard orchestrator pipeline (complete workflow)")
        print("   ✅ Conditional formatting generation pipeline (rule generation)")
        print("   ✅ Enhanced dashboard streaming pipeline (rule application)")
        print("   ✅ All pipelines accessible via PipelineContainer")
        print("\n🔗 Other services can now use these pipelines easily!")
        
        return {
            "complete_workflow": complete_result,
            "conditional_formatting": cf_result,
            "streaming": streaming_result
        }
        
    except Exception as e:
        print(f"❌ Example failed: {e}")
        logger.error(f"Example failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run the example
    result = asyncio.run(example_usage())
    
    print("\n✅ Example completed successfully!")
    print("The dashboard pipelines are now fully integrated and available for other services!")
