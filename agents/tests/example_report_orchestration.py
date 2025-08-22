"""
Example usage of the Report Orchestrator Pipeline

This script demonstrates how to:
1. Create and configure the report orchestrator pipeline
2. Set up sample data for report generation
3. Execute the pipeline with different configurations
4. Handle the results and display them
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

from app.agents.pipelines.writers.report_orchestrator_pipeline import create_report_orchestrator_pipeline
from app.agents.nodes.writers.report_writing_agent import (
    ThreadComponentData, 
    WriterActorType, 
    BusinessGoal,
    ComponentType
)
from app.core.engine import Engine
from app.core.dependencies import get_llm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_report_data() -> Dict[str, Any]:
    """Create sample data for report generation"""
    
    # Sample SQL queries
    report_queries = [
        {
            "id": "query_1",
            "name": "Q4 Sales Performance",
            "sql": "SELECT department, SUM(sales_amount) as total_sales, COUNT(*) as transactions FROM sales WHERE quarter = 'Q4' GROUP BY department ORDER BY total_sales DESC"
        },
        {
            "id": "query_2", 
            "name": "Employee Training Completion",
            "sql": "SELECT employee_id, training_name, completion_date, score FROM training_records WHERE completion_date >= '2024-01-01' ORDER BY completion_date DESC"
        },
        {
            "id": "query_3",
            "name": "Customer Satisfaction Metrics",
            "sql": "SELECT month, AVG(satisfaction_score) as avg_score, COUNT(surveys) as total_surveys FROM customer_satisfaction WHERE year = 2024 GROUP BY month ORDER BY month"
        }
    ]
    
    # Sample report context
    report_context = {
        "title": "Q4 2024 Business Performance Report",
        "description": "Comprehensive analysis of Q4 business performance across sales, training, and customer satisfaction",
        "charts": [
            {
                "id": "chart_1",
                "type": "bar",
                "title": "Department Sales Performance",
                "data_source": "query_1"
            },
            {
                "id": "chart_2", 
                "type": "line",
                "title": "Training Completion Trends",
                "data_source": "query_2"
            },
            {
                "id": "chart_3",
                "type": "area",
                "title": "Customer Satisfaction Trends",
                "data_source": "query_3"
            }
        ],
        "tables": [
            {
                "id": "table_1",
                "title": "Sales Summary by Department",
                "data_source": "query_1"
            }
        ],
        "filters": {
            "date_range": "Q4 2024",
            "departments": ["Sales", "Marketing", "Engineering", "Support"]
        }
    }
    
    # Sample thread components for comprehensive report generation
    thread_components = [
        ThreadComponentData(
            id="comp_1",
            component_type=ComponentType.QUESTION,
            sequence_order=1,
            question="What are the key performance indicators for Q4 sales across all departments?",
            description="Analysis of Q4 sales performance metrics and trends"
        ),
        ThreadComponentData(
            id="comp_2",
            component_type=ComponentType.CHART,
            sequence_order=2,
            chart_config={
                "type": "bar",
                "title": "Department Sales Performance",
                "data_source": "query_1"
            },
            description="Visual representation of sales performance by department"
        ),
        ThreadComponentData(
            id="comp_3",
            component_type=ComponentType.INSIGHT,
            sequence_order=3,
            description="Key insights and trends from the sales data analysis"
        ),
        ThreadComponentData(
            id="comp_4",
            component_type=ComponentType.RECOMMENDATION,
            sequence_order=4,
            description="Strategic recommendations based on the performance analysis"
        )
    ]
    
    # Sample business goal
    business_goal = BusinessGoal(
        primary_objective="Improve Q4 sales performance and identify growth opportunities",
        target_audience=["Executives", "Department Heads", "Sales Managers"],
        decision_context="Q4 planning and resource allocation for next quarter",
        success_metrics=["Sales growth", "Department performance improvement", "Training effectiveness"],
        timeframe="Q4 2024 - Q1 2025",
        risk_factors=["Market volatility", "Resource constraints", "Competitive pressure"]
    )
    
    return {
        "report_queries": report_queries,
        "report_context": report_context,
        "thread_components": thread_components,
        "business_goal": business_goal
    }


def create_sample_conditional_formatting_query() -> str:
    """Create a sample natural language query for conditional formatting"""
    return """
    Apply conditional formatting to the sales data:
    - Highlight sales amounts above $100,000 in green
    - Highlight sales amounts below $50,000 in red
    - Format all currency values with 2 decimal places
    - Apply bold formatting to department names
    - Add color coding for satisfaction scores: 8+ (green), 6-7 (yellow), below 6 (red)
    """


async def run_basic_report_generation():
    """Run basic report generation without conditional formatting using PipelineContainer"""
    logger.info("Running basic report generation using PipelineContainer...")
    
    try:
        # Use proper settings and dependencies initialization
        from app.settings import init_environment, get_settings
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
        
        # Initialize pipeline container with proper dependencies
        pipeline_container = PipelineContainer.initialize()
        
        # Get the report orchestrator pipeline from the container
        pipeline = pipeline_container.get_pipeline("report_orchestrator")
        
        # Get sample data
        sample_data = create_sample_report_data()
        
        # Run the pipeline with basic configuration
        result = await pipeline.run(
            report_queries=sample_data["report_queries"],
            natural_language_query=None,  # No conditional formatting
            report_context=sample_data["report_context"],
            project_id="example_project_001",
            status_callback=lambda status, details: logger.info(f"Status: {status} - {details}")
        )
        
        logger.info("Basic report generation completed successfully!")
        logger.info(f"Generated report ID: {result['post_process']['report']['report_id']}")
        logger.info(f"Total queries processed: {result['post_process']['report']['summary']['total_queries']}")
        logger.info(f"Total rows processed: {result['post_process']['report']['summary']['total_rows_processed']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in basic report generation: {e}")
        raise


async def run_enhanced_report_generation():
    """Run enhanced report generation with conditional formatting using PipelineContainer"""
    logger.info("Running enhanced report generation with conditional formatting using PipelineContainer...")
    
    try:
        # Use proper settings and dependencies initialization
        from app.settings import init_environment, get_settings
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
        
        # Initialize pipeline container with proper dependencies
        pipeline_container = PipelineContainer.initialize()
        
        # Get the report orchestrator pipeline from the container
        pipeline = pipeline_container.get_pipeline("report_orchestrator")
        
        # Get sample data
        sample_data = create_sample_report_data()
        
        # Create conditional formatting query
        conditional_formatting_query = create_sample_conditional_formatting_query()
        
        # Run the pipeline with conditional formatting
        result = await pipeline.run(
            report_queries=sample_data["report_queries"],
            natural_language_query=conditional_formatting_query,
            report_context=sample_data["report_context"],
            project_id="example_project_002",
            status_callback=lambda status, details: logger.info(f"Status: {status} - {details}")
        )
        
        logger.info("Enhanced report generation completed successfully!")
        logger.info(f"Generated report ID: {result['post_process']['report']['report_id']}")
        logger.info(f"Conditional formatting applied: {result['post_process']['orchestration_metadata']['conditional_formatting_applied']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in enhanced report generation: {e}")
        raise


async def run_comprehensive_report_generation():
    """Run comprehensive report generation with all features enabled using PipelineContainer"""
    logger.info("Running comprehensive report generation with all features using PipelineContainer...")
    
    try:
        # Use proper settings and dependencies initialization
        from app.settings import init_environment, get_settings
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
        
        # Initialize pipeline container with proper dependencies
        pipeline_container = PipelineContainer.initialize()
        
        # Get the report orchestrator pipeline from the container
        pipeline = pipeline_container.get_pipeline("report_orchestrator")
        
        # Get sample data
        sample_data = create_sample_report_data()
        
        # Create conditional formatting query
        conditional_formatting_query = create_sample_conditional_formatting_query()
        
        # Run the pipeline with all features
        result = await pipeline.run(
            report_queries=sample_data["report_queries"],
            natural_language_query=conditional_formatting_query,
            report_context=sample_data["report_context"],
            project_id="example_project_003",
            thread_components=sample_data["thread_components"],
            writer_actor=WriterActorType.EXECUTIVE,
            business_goal=sample_data["business_goal"],
            status_callback=lambda status, details: logger.info(f"Status: {status} - {details}")
        )
        
        logger.info("Comprehensive report generation completed successfully!")
        logger.info(f"Generated report ID: {result['post_process']['report']['report_id']}")
        logger.info(f"Conditional formatting applied: {result['post_process']['orchestration_metadata']['conditional_formatting_applied']}")
        logger.info(f"Comprehensive report generated: {result['post_process']['orchestration_metadata']['comprehensive_report_generated']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in comprehensive report generation: {e}")
        raise


async def demonstrate_pipeline_configuration():
    """Demonstrate pipeline configuration options using PipelineContainer"""
    logger.info("Demonstrating pipeline configuration options using PipelineContainer...")
    
    try:
        # Use proper settings and dependencies initialization
        from app.settings import init_environment, get_settings
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
        
        # Initialize pipeline container with proper dependencies
        pipeline_container = PipelineContainer.initialize()
        
        # Get the report orchestrator pipeline from the container
        pipeline = pipeline_container.get_pipeline("report_orchestrator")
        
        # Show current configuration
        logger.info("Current configuration:")
        for key, value in pipeline.get_configuration().items():
            logger.info(f"  {key}: {value}")
        
        # Update configuration
        pipeline.update_configuration({
            "quality_threshold": 0.9,
            "max_report_iterations": 5
        })
        
        # Disable conditional formatting
        pipeline.enable_conditional_formatting(False)
        
        # Show updated configuration
        logger.info("Updated configuration:")
        for key, value in pipeline.get_configuration().items():
            logger.info(f"  {key}: {value}")
        
        # Get execution statistics
        stats = pipeline.get_execution_statistics()
        logger.info("Execution statistics:")
        logger.info(f"  Total executions: {stats['pipeline_metrics'].get('total_executions', 0)}")
        logger.info(f"  Configuration: {stats['configuration']}")
        
    except Exception as e:
        logger.error(f"Error in pipeline configuration demonstration: {e}")
        raise


async def main():
    """Main function to demonstrate the report orchestrator pipeline using PipelineContainer"""
    logger.info("Starting Report Orchestrator Pipeline demonstration using PipelineContainer...")
    
    try:
        # Run different scenarios
        logger.info("\n" + "="*50)
        logger.info("SCENARIO 1: Basic Report Generation")
        logger.info("="*50)
        await run_basic_report_generation()
        
        logger.info("\n" + "="*50)
        logger.info("SCENARIO 2: Enhanced Report Generation with Conditional Formatting")
        logger.info("="*50)
        await run_enhanced_report_generation()
        
        logger.info("\n" + "="*50)
        logger.info("SCENARIO 3: Comprehensive Report Generation with All Features")
        logger.info("="*50)
        await run_comprehensive_report_generation()
        
        logger.info("\n" + "="*50)
        logger.info("SCENARIO 4: Pipeline Configuration Demonstration")
        logger.info("="*50)
        await demonstrate_pipeline_configuration()
        
        logger.info("\n" + "="*50)
        logger.info("All demonstrations completed successfully!")
        logger.info("="*50)
        
        # Additional example: Using simple report generation pipeline directly
        logger.info("\n" + "="*50)
        logger.info("SCENARIO 5: Direct Simple Report Generation Pipeline Usage")
        logger.info("="*50)
        await run_direct_simple_report_generation()
        
        # Comparison example: PipelineContainer vs Direct Creation
        logger.info("\n" + "="*50)
        logger.info("SCENARIO 6: PipelineContainer vs Direct Creation Comparison")
        logger.info("="*50)
        await compare_pipeline_approaches()
        
        logger.info("\n" + "="*50)
        logger.info("All demonstrations completed successfully!")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Error in main demonstration: {e}")
        raise


async def run_direct_simple_report_generation():
    """Example of using the simple report generation pipeline directly from the container"""
    logger.info("Running direct simple report generation pipeline...")
    
    try:
        # Use proper settings and dependencies initialization
        from app.settings import init_environment, get_settings
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
        
        # Initialize pipeline container with proper dependencies
        pipeline_container = PipelineContainer.initialize()
        
        # Get the simple report generation pipeline directly from the container
        simple_pipeline = pipeline_container.get_pipeline("simple_report_generation")
        
        # Get sample data
        sample_data = create_sample_report_data()
        
        # Create a basic enhanced context (similar to what conditional formatting would generate)
        enhanced_context = {
            "project_id": "direct_test",
            "generated_at": datetime.now().isoformat(),
            "original_context": sample_data["report_context"],
            "conditional_formatting_rules": {
                "total_sales": {
                    "type": "conditional_color",
                    "conditions": [
                        {"operator": "greater_than", "threshold": 100000, "color": "green"},
                        {"operator": "less_than", "threshold": 50000, "color": "red"}
                    ]
                },
                "satisfaction_score": {
                    "type": "conditional_color",
                    "conditions": [
                        {"operator": "greater_than_or_equal", "threshold": 8, "color": "green"},
                        {"operator": "greater_than_or_equal", "threshold": 6, "color": "yellow"},
                        {"operator": "less_than", "threshold": 6, "color": "red"}
                    ]
                }
            },
            "execution_instructions": {},
            "basic_context": False
        }
        
        # Status callback for monitoring
        def status_callback(status: str, details: Dict[str, Any]):
            print(f"📊 Simple Report Pipeline Status: {status}")
            if details:
                print(f"   Details: {details}")
        
        # Run the simple report generation pipeline directly
        result = await simple_pipeline.run(
            report_queries=sample_data["report_queries"],
            enhanced_context=enhanced_context,
            project_id="direct_simple_test",
            status_callback=status_callback
        )
        
        logger.info("Direct simple report generation completed successfully!")
        logger.info(f"Generated report ID: {result['post_process']['report']['report_id']}")
        logger.info(f"Total queries processed: {result['post_process']['report']['summary']['total_queries']}")
        logger.info(f"Total rows processed: {result['post_process']['report']['summary']['total_rows_processed']}")
        logger.info(f"Insights generated: {result['post_process']['report']['summary']['insights_generated']}")
        logger.info(f"Recommendations generated: {result['post_process']['report']['summary']['recommendations_generated']}")
        
        # Show some insights and recommendations
        if result['post_process']['insights']:
            logger.info("\n📈 Generated Insights:")
            for insight in result['post_process']['insights']:
                logger.info(f"  - {insight['insight']}")
        
        if result['post_process']['recommendations']:
            logger.info("\n💡 Generated Recommendations:")
            for rec in result['post_process']['recommendations']:
                logger.info(f"  - {rec['recommendation']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in direct simple report generation: {e}")
        raise


async def compare_pipeline_approaches():
    """Compare using PipelineContainer vs direct pipeline creation"""
    logger.info("Comparing PipelineContainer vs Direct Pipeline Creation approaches...")
    
    try:
        # Use proper settings and dependencies initialization
        from app.settings import init_environment, get_settings
        from app.agents.pipelines.pipeline_container import PipelineContainer
        from app.agents.pipelines.writers import create_report_orchestrator_pipeline
        from app.core.dependencies import get_llm
        from app.agents.retrieval.retrieval_helper import RetrievalHelper
        from app.core.engine import Engine
        
        # Initialize environment and settings
        try:
            init_environment()
            settings = get_settings()
            print(f"✅ Environment initialized successfully")
        except Exception as e:
            print(f"⚠️  Environment initialization warning: {e}")
            print("   Continuing with default settings...")
        
        # Approach 1: Using PipelineContainer (recommended)
        logger.info("\n🔧 APPROACH 1: Using PipelineContainer (Recommended)")
        logger.info("-" * 50)
        
        start_time = datetime.now()
        pipeline_container = PipelineContainer.initialize()
        container_pipeline = pipeline_container.get_pipeline("report_orchestrator")
        container_init_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"  ✓ Pipeline retrieved from container in {container_init_time:.3f}s")
        logger.info(f"  ✓ Pipeline name: {container_pipeline.name}")
        logger.info(f"  ✓ Pipeline version: {container_pipeline.version}")
        logger.info(f"  ✓ Pipeline initialized: {container_pipeline.is_initialized}")
        
        # Approach 2: Direct creation (alternative)
        logger.info("\n🔧 APPROACH 2: Direct Pipeline Creation (Alternative)")
        logger.info("-" * 50)
        
        start_time = datetime.now()
        llm = get_llm()
        retrieval_helper = RetrievalHelper()
        engine = Engine()  # This might need proper configuration
        
        direct_pipeline = create_report_orchestrator_pipeline(
            engine=engine,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        direct_init_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"  ✓ Pipeline created directly in {direct_init_time:.3f}s")
        logger.info(f"  ✓ Pipeline name: {direct_pipeline.name}")
        logger.info(f"  ✓ Pipeline version: {direct_pipeline.version}")
        logger.info(f"  ✓ Pipeline initialized: {direct_pipeline.is_initialized}")
        
        # Comparison summary
        logger.info("\n📊 COMPARISON SUMMARY")
        logger.info("-" * 50)
        logger.info(f"  PipelineContainer approach:")
        logger.info(f"    ✅ Pros: Centralized management, dependency injection, consistent configuration")
        logger.info(f"    ✅ Pros: Automatic initialization, error handling, metrics collection")
        logger.info(f"    ✅ Pros: Faster subsequent access, shared resources")
        logger.info(f"    ⚠️  Cons: Slightly longer initial setup")
        
        logger.info(f"  Direct creation approach:")
        logger.info(f"    ✅ Pros: Full control over dependencies, isolated instances")
        logger.info(f"    ✅ Pros: No container dependencies, simpler for standalone usage")
        logger.info(f"    ⚠️  Cons: Manual dependency management, no shared resources")
        logger.info(f"    ⚠️  Cons: Each instance is independent, potential resource duplication")
        
        logger.info(f"\n  Recommendation: Use PipelineContainer for production applications")
        logger.info(f"  and direct creation for testing, prototyping, or standalone scripts.")
        
        return {
            "container_pipeline": container_pipeline,
            "direct_pipeline": direct_pipeline,
            "container_init_time": container_init_time,
            "direct_init_time": direct_init_time
        }
        
    except Exception as e:
        logger.error(f"Error comparing pipeline approaches: {e}")
        raise


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())
