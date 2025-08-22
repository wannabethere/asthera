#!/usr/bin/env python3
"""
Clean example showing the new pipeline architecture without service layer:
DashboardOrchestrator -> DashboardIntegrationPipeline -> ConditionalFormattingPipeline -> ConditionalFormattingAgent
"""

import asyncio
import logging
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.services.writers.dashboard_orchestrator import create_dashboard_orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_clean_pipeline_usage():
    """Example of clean pipeline usage without service layer"""
    
    print("🚀 Clean Pipeline Architecture Example")
    print("=" * 50)
    
    try:
        # 1. Initialize pipeline container
        container = PipelineContainer.initialize()
        
        # 2. Add conditional formatting pipeline to container
        from app.agents.pipelines.dashboard_integration_pipeline import add_conditional_formatting_to_pipeline_container
        conditional_formatting_pipeline = add_conditional_formatting_to_pipeline_container(container)
        
        # 3. Create orchestrator (no service needed!)
        orchestrator = create_dashboard_orchestrator(pipeline_container=container)
        
        # 4. Sample data
        dashboard_queries = [
            {
                "chart_id": "sales_chart",
                "sql": "SELECT region, SUM(sales_amount) as sales FROM sales_data GROUP BY region",
                "query": "Show sales by region",
                "data_description": "Sales data by region"
            }
        ]
        
        dashboard_context = {
            "charts": [
                {
                    "chart_id": "sales_chart",
                    "type": "bar",
                    "columns": ["region", "sales_amount", "date"],
                    "query": "Show sales by region"
                }
            ],
            "available_columns": ["region", "sales_amount", "date", "status"],
            "data_types": {
                "sales_amount": "numeric",
                "date": "datetime",
                "region": "categorical",
                "status": "categorical"
            }
        }
        
        natural_language_query = "Highlight sales amounts greater than $10,000 in green"
        
        # 5. Execute with clean pipeline architecture
        result = await orchestrator.execute_dashboard_with_conditional_formatting(
            dashboard_queries=dashboard_queries,
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="clean_example"
        )
        
        print("✅ Success! Clean pipeline architecture working without service layer")
        print(f"Result keys: {list(result.keys())}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Example failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(example_clean_pipeline_usage())
