#!/usr/bin/env python3
"""
Example of the new two-step dashboard architecture:

Step 1: ConditionalFormattingGenerationPipeline - Generates enhanced dashboard JSON
Step 2: EnhancedDashboardStreamingPipeline - Applies rules and streams results

This creates a clean separation between rule generation and rule application.
"""

import asyncio
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from app.agents.pipelines.pipeline_container import PipelineContainer
from app.agents.pipelines.dashboard_orchestrator_pipeline import create_dashboard_orchestrator_pipeline
from app.core.engine_provider import EngineProvider
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_two_step_architecture():
    """Example of using the new two-step dashboard architecture"""
    
    print("🚀 Two-Step Dashboard Architecture Example")
    print("=" * 60)
    
    try:
        # Step 1: Initialize pipeline container
        print("1. Initializing pipeline container...")
        container = PipelineContainer.initialize()
        print("   ✅ Pipeline container initialized")
        
        # Step 2: Create dashboard orchestrator pipeline
        print("2. Creating dashboard orchestrator pipeline...")
        engine = EngineProvider.get_engine()
        orchestrator_pipeline = create_dashboard_orchestrator_pipeline(
            engine=engine,
            llm=get_llm(),
            retrieval_helper=RetrievalHelper()
        )
        print("   ✅ Dashboard orchestrator pipeline created")
        
        # Step 3: Sample data
        print("3. Preparing sample dashboard data...")
        
        # Dashboard queries
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
        
        # Natural language query for conditional formatting
        natural_language_query = """
        I want to highlight all sales amounts greater than $10,000 in green, 
        and filter the dashboard to show only active status records from the last 30 days.
        Also, make the performance chart show data only for the current year.
        """
        
        # Additional context
        additional_context = {
            "user_preferences": {
                "highlight_color": "green",
                "default_period": "last_30_days"
            }
        }
        
        # Time filters
        time_filters = {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "period": "current_year"
        }
        
        print("   ✅ Sample data prepared")
        
        # Step 4: Execute the two-step architecture
        print("4. Executing two-step dashboard architecture...")
        
        # Status callback to monitor progress
        def status_callback(status: str, details: Dict[str, Any] = None):
            print(f"   📊 Status: {status}")
            if details:
                for key, value in details.items():
                    if key != "project_id":  # Skip project_id to reduce noise
                        print(f"      {key}: {value}")
        
        # Execute the complete workflow
        result = await orchestrator_pipeline.run(
            dashboard_queries=dashboard_queries,
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="two_step_example",
            additional_context=additional_context,
            time_filters=time_filters,
            status_callback=status_callback
        )
        
        print("   ✅ Two-step architecture execution completed!")
        
        # Step 5: Analyze results
        print("5. Analyzing results...")
        
        # Check if conditional formatting was applied
        conditional_formatting_applied = result.get("post_process", {}).get("orchestration_metadata", {}).get("conditional_formatting_applied", False)
        print(f"   ✅ Conditional formatting applied: {conditional_formatting_applied}")
        
        # Check enhanced dashboard
        enhanced_dashboard = result.get("post_process", {}).get("enhanced_dashboard", {})
        if enhanced_dashboard:
            print(f"   ✅ Enhanced dashboard generated with {len(enhanced_dashboard.get('conditional_formatting_rules', {}))} chart configurations")
            
            # Show execution instructions
            execution_instructions = enhanced_dashboard.get("execution_instructions", {})
            for chart_id, instructions in execution_instructions.items():
                print(f"      Chart {chart_id}:")
                print(f"        - SQL expansions: {len(instructions.get('sql_expansions', []))}")
                print(f"        - Chart adjustments: {len(instructions.get('chart_adjustments', []))}")
                print(f"        - Conditional formats: {len(instructions.get('conditional_formats', []))}")
        
        # Check dashboard results
        dashboard_results = result.get("post_process", {}).get("dashboard_results", {})
        if dashboard_results:
            print(f"   ✅ Dashboard results generated")
        
        # Step 6: Show architecture summary
        print("\n🎉 Two-Step Architecture Summary:")
        print("=" * 40)
        print("Step 1: ConditionalFormattingGenerationPipeline")
        print("   ↓ Generates enhanced dashboard JSON with rules")
        print("Step 2: EnhancedDashboardStreamingPipeline")
        print("   ↓ Applies rules and streams results")
        print("Result: Clean separation of concerns!")
        
        return result
        
    except Exception as e:
        print(f"❌ Example failed: {e}")
        logger.error(f"Example failed: {e}", exc_info=True)
        raise


async def example_step_by_step():
    """Example showing each step separately for better understanding"""
    
    print("\n🔍 Step-by-Step Breakdown Example")
    print("=" * 50)
    
    try:
        # Initialize
        container = PipelineContainer.initialize()
        engine = EngineProvider.get_engine()
        
        # Step 1: Generate conditional formatting only
        print("Step 1: Generating conditional formatting...")
        from app.agents.pipelines.conditional_formatting_generation_pipeline import create_conditional_formatting_generation_pipeline
        
        conditional_formatting_pipeline = create_conditional_formatting_generation_pipeline(
            engine=engine,
            llm=get_llm(),
            retrieval_helper=RetrievalHelper()
        )
        
        # Sample data
        dashboard_context = {
            "charts": [{"chart_id": "test_chart", "type": "bar", "columns": ["region", "sales"]}],
            "available_columns": ["region", "sales", "date"]
        }
        
        natural_language_query = "Highlight sales greater than $5000 in green"
        
        # Generate conditional formatting
        conditional_formatting_result = await conditional_formatting_pipeline.run(
            natural_language_query=natural_language_query,
            dashboard_context=dashboard_context,
            project_id="step_by_step_example"
        )
        
        print("   ✅ Conditional formatting generated")
        
        # Extract enhanced dashboard
        enhanced_dashboard = conditional_formatting_result.get("post_process", {}).get("enhanced_dashboard", {})
        print(f"   📋 Enhanced dashboard created with {len(enhanced_dashboard.get('execution_instructions', {}))} chart instructions")
        
        # Step 2: Apply conditional formatting and stream results
        print("\nStep 2: Applying conditional formatting and streaming...")
        from app.agents.pipelines.enhanced_dashboard_streaming_pipeline import create_enhanced_dashboard_streaming_pipeline
        
        enhanced_streaming_pipeline = create_enhanced_dashboard_streaming_pipeline(
            engine=engine,
            llm=get_llm(),
            retrieval_helper=RetrievalHelper()
        )
        
        # Sample queries
        dashboard_queries = [
            {
                "chart_id": "test_chart",
                "sql": "SELECT region, SUM(sales) as total_sales FROM sales_data GROUP BY region",
                "query": "Show sales by region"
            }
        ]
        
        # Apply and stream
        streaming_result = await enhanced_streaming_pipeline.run(
            dashboard_queries=dashboard_queries,
            enhanced_dashboard=enhanced_dashboard,
            project_id="step_by_step_example"
        )
        
        print("   ✅ Conditional formatting applied and results streamed")
        
        # Show the complete flow
        print("\n🔄 Complete Flow:")
        print("   Natural Language Query → ConditionalFormattingAgent")
        print("   ↓")
        print("   Enhanced Dashboard JSON with Rules")
        print("   ↓")
        print("   EnhancedDashboardStreamingPipeline")
        print("   ↓")
        print("   Final Results with Rules Applied")
        
        return {
            "conditional_formatting": conditional_formatting_result,
            "streaming": streaming_result
        }
        
    except Exception as e:
        print(f"❌ Step-by-step example failed: {e}")
        logger.error(f"Step-by-step example failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run both examples
    print("Running Two-Step Architecture Examples...")
    
    # Example 1: Complete workflow
    result1 = asyncio.run(example_two_step_architecture())
    
    # Example 2: Step by step
    result2 = asyncio.run(example_step_by_step())
    
    print("\n✅ All examples completed successfully!")
    print("The new two-step architecture provides clean separation between:")
    print("1. Rule generation (ConditionalFormattingGenerationPipeline)")
    print("2. Rule application (EnhancedDashboardStreamingPipeline)")
