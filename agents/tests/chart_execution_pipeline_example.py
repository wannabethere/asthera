"""
Example demonstrating the ChartExecutionPipeline

This example shows how to use the ChartExecutionPipeline to:
1. Generate chart schemas using sample data
2. Execute charts with full SQL data
3. Configure pagination and execution parameters
4. Handle different chart formats
"""

import asyncio
import os
from typing import Dict, Any

# Set up environment
os.environ["OPENAI_API_KEY"] = "your-api-key-here"

from app.agents.pipelines.sql_execution import ChartExecutionPipeline
from app.agents.nodes.sql.utils.chart import ChartExecutionConfig
from app.core.engine import Engine
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm
from app.agents.nodes.sql.chart_generation import create_chart_generation_pipeline
from app.agents.nodes.sql.plotly_chart_generation import create_plotly_chart_generation_pipeline
from app.agents.nodes.sql.powerbi_chart_generation import create_powerbi_chart_generation_pipeline


class MockEngine:
    """Mock engine for demonstration purposes"""
    
    def __init__(self):
        self.sales_data = [
            {"date": "2023-01-01", "region": "North", "sales_amount": 100000, "product_category": "Electronics"},
            {"date": "2023-02-01", "region": "North", "sales_amount": 120000, "product_category": "Electronics"},
            {"date": "2023-03-01", "region": "North", "sales_amount": 110000, "product_category": "Electronics"},
            {"date": "2023-04-01", "region": "North", "sales_amount": 130000, "product_category": "Electronics"},
            {"date": "2023-05-01", "region": "North", "sales_amount": 140000, "product_category": "Electronics"},
            {"date": "2023-01-01", "region": "South", "sales_amount": 90000, "product_category": "Clothing"},
            {"date": "2023-02-01", "region": "South", "sales_amount": 95000, "product_category": "Clothing"},
            {"date": "2023-03-01", "region": "South", "sales_amount": 105000, "product_category": "Clothing"},
            {"date": "2023-04-01", "region": "South", "sales_amount": 115000, "product_category": "Clothing"},
            {"date": "2023-05-01", "region": "South", "sales_amount": 125000, "product_category": "Clothing"},
            {"date": "2023-01-01", "region": "East", "sales_amount": 80000, "product_category": "Books"},
            {"date": "2023-02-01", "region": "East", "sales_amount": 85000, "product_category": "Books"},
            {"date": "2023-03-01", "region": "East", "sales_amount": 90000, "product_category": "Books"},
            {"date": "2023-04-01", "region": "East", "sales_amount": 100000, "product_category": "Books"},
            {"date": "2023-05-01", "region": "East", "sales_amount": 110000, "product_category": "Books"},
        ]
    
    async def execute_sql(self, sql: str, session, dry_run: bool = False, **kwargs):
        """Mock SQL execution"""
        print(f"Executing SQL: {sql}")
        
        # Simple mock SQL parsing
        if "LIMIT" in sql.upper():
            import re
            limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
            if limit_match:
                limit = int(limit_match.group(1))
                return True, {"data": self.sales_data[:limit]}
        
        if "ORDER BY" in sql.upper():
            if "date" in sql.lower():
                sorted_data = sorted(self.sales_data, key=lambda x: x["date"])
                return True, {"data": sorted_data}
        
        return True, {"data": self.sales_data}


async def example_basic_chart_execution():
    """Basic example of chart execution"""
    
    print("=== Basic Chart Execution Example ===\n")
    
    # Setup
    llm = get_llm()
    engine = MockEngine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Define status callback
    def status_callback(status: str, details: Dict[str, Any]):
        print(f"📊 Status: {status}")
        if details:
            print(f"   Details: {details}")
    
    # Create the pipeline
    pipeline = ChartExecutionPipeline(
        name="Basic Chart Execution",
        version="1.0",
        description="Basic chart execution with SQL data",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Configure pipeline
    pipeline.set_chart_format("vega_lite")
    
    # Set execution configuration
    exec_config = ChartExecutionConfig(
        page_size=1000,
        max_rows=5000,
        enable_pagination=True,
        sort_by="date",
        sort_order="ASC",
        cache_results=True,
        cache_ttl_seconds=300
    )
    pipeline.set_execution_config(exec_config)
    
    try:
        result = await pipeline.run(
            query="Show me sales trends by region over time",
            sql="SELECT date, region, sales_amount FROM sales_data ORDER BY date",
            project_id="basic_example",
            status_callback=status_callback
        )
        
        print("\n✅ Chart execution completed successfully!")
        print(f"Chart Type: {result['post_process'].get('chart_type', 'Unknown')}")
        print(f"Data Count: {result['post_process'].get('data_count', 0)}")
        print(f"Chart Format: {result['post_process'].get('chart_format', 'Unknown')}")
        print(f"Validation: {result['post_process'].get('validation', {}).get('valid', False)}")
        
        # Print metrics
        metrics = pipeline.get_metrics()
        print(f"Metrics: {metrics}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


async def example_different_formats():
    """Example with different chart formats"""
    
    print("\n=== Different Chart Formats Example ===\n")
    
    # Setup
    llm = get_llm()
    engine = MockEngine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    formats = ["vega_lite", "plotly", "powerbi"]
    
    for chart_format in formats:
        print(f"\n--- Testing {chart_format.upper()} ---")
        
        # Create pipeline
        pipeline = ChartExecutionPipeline(
            name=f"Chart Execution - {chart_format}",
            version="1.0",
            description=f"Chart execution with {chart_format}",
            llm=llm,
            retrieval_helper=retrieval_helper,
            engine=engine,
            chart_generation_pipeline=chart_generation_pipeline,
            plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
            powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
        )
        
        # Configure for specific format
        pipeline.set_chart_format(chart_format)
        
        # Set execution configuration
        exec_config = ChartExecutionConfig(
            page_size=500,
            max_rows=2000,
            enable_pagination=True,
            sort_by="sales_amount",
            sort_order="DESC"
        )
        pipeline.set_execution_config(exec_config)
        
        try:
            result = await pipeline.run(
                query="Compare sales across regions",
                sql="SELECT region, SUM(sales_amount) as total_sales FROM sales_data GROUP BY region",
                project_id=f"format_test_{chart_format}"
            )
            
            if result['post_process'].get('chart_schema'):
                print(f"✅ {chart_format.upper()} chart executed successfully")
                print(f"   Chart Type: {result['post_process'].get('chart_type', 'Unknown')}")
                print(f"   Data Count: {result['post_process'].get('data_count', 0)}")
            else:
                print(f"❌ {chart_format.upper()} chart execution failed")
                
        except Exception as e:
            print(f"❌ Error with {chart_format}: {str(e)}")


async def example_with_pagination():
    """Example demonstrating pagination features"""
    
    print("\n=== Pagination Example ===\n")
    
    # Setup
    llm = get_llm()
    engine = MockEngine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Create pipeline
    pipeline = ChartExecutionPipeline(
        name="Pagination Chart Execution",
        version="1.0",
        description="Chart execution with pagination",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Configure with pagination
    exec_config = ChartExecutionConfig(
        page_size=5,  # Small page size to see pagination in action
        max_rows=10,  # Limit total rows
        enable_pagination=True,
        sort_by="date",
        sort_order="ASC",
        cache_results=False  # Disable cache for testing
    )
    pipeline.set_execution_config(exec_config)
    
    # Configure pipeline
    configuration = {
        "chart_format": "vega_lite",
        "include_other_formats": True,
        "use_multi_format": True
    }
    
    try:
        result = await pipeline.run(
            query="Show sales trends with pagination",
            sql="SELECT date, region, sales_amount FROM sales_data ORDER BY date",
            project_id="pagination_example",
            configuration=configuration
        )
        
        print("✅ Pagination example completed!")
        print(f"Data Count: {result['post_process'].get('data_count', 0)}")
        print(f"Execution Config: {result['post_process'].get('execution_config', {})}")
        
        # Check for other format schemas
        post_process = result['post_process']
        if 'plotly_schema' in post_process:
            print("✅ Plotly schema generated")
        if 'powerbi_schema' in post_process:
            print("✅ PowerBI schema generated")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


async def example_with_custom_configuration():
    """Example with custom configuration"""
    
    print("\n=== Custom Configuration Example ===\n")
    
    # Setup
    llm = get_llm()
    engine = MockEngine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Create pipeline
    pipeline = ChartExecutionPipeline(
        name="Custom Configuration Chart Execution",
        version="1.0",
        description="Chart execution with custom configuration",
        llm=llm,
        retrieval_helper=retrieval_helper,
        engine=engine,
        chart_generation_pipeline=chart_generation_pipeline,
        plotly_chart_generation_pipeline=plotly_chart_generation_pipeline,
        powerbi_chart_generation_pipeline=powerbi_chart_generation_pipeline
    )
    
    # Custom configuration
    custom_config = {
        "page_size": 100,
        "max_rows": 1000,
        "enable_pagination": True,
        "sort_by": "sales_amount",
        "sort_order": "DESC",
        "timeout_seconds": 60,
        "cache_results": True,
        "cache_ttl_seconds": 600,
        "chart_format": "plotly",
        "include_other_formats": True,
        "use_multi_format": True,
        "language": "English"
    }
    
    try:
        result = await pipeline.run(
            query="Analyze sales performance by product category",
            sql="SELECT product_category, SUM(sales_amount) as total_sales FROM sales_data GROUP BY product_category",
            project_id="custom_config_example",
            configuration=custom_config
        )
        
        print("✅ Custom configuration example completed!")
        print(f"Chart Format: {result['post_process'].get('chart_format', 'Unknown')}")
        print(f"Data Count: {result['post_process'].get('data_count', 0)}")
        print(f"Chart Type: {result['post_process'].get('chart_type', 'Unknown')}")
        
        # Print execution configuration
        exec_config = result['post_process'].get('execution_config', {})
        print(f"Execution Config: {exec_config}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")



# Example usage of the ChartExecutionPipeline
async def example_chart_execution_pipeline():
    """
    Example demonstrating how to use the ChartExecutionPipeline
    """
    import os
    from app.core.engine import Engine
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    # Setup
    llm = get_llm()
    engine = Engine()
    retrieval_helper = RetrievalHelper()
    
    # Create chart generation pipelines
    chart_generation_pipeline = create_chart_generation_pipeline()
    plotly_chart_generation_pipeline = create_plotly_chart_generation_pipeline()
    powerbi_chart_generation_pipeline = create_powerbi_chart_generation_pipeline()
    
    # Define status callback
    def status_callback(status: str, details: Dict[str, Any]):
        print(f"📊 Chart Execution Status: {status}")
        if details:
            print(f"   Details: {details}")
    
    # Create the pipeline
    pipeline = ChartExecutionPipeline(
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
    
    # Configure pipeline
    pipeline.set_chart_format("vega_lite")
    
    # Set execution configuration
    exec_config = ChartExecutionConfig(
        page_size=500,
        max_rows=5000,
        enable_pagination=True,
        sort_by="date",
        sort_order="ASC",
        cache_results=True,
        cache_ttl_seconds=300
    )
    pipeline.set_execution_config(exec_config)
    
    # Example configuration
    configuration = {
        "include_other_formats": True,
        "use_multi_format": True,
        "language": "English"
    }
    
    print("🚀 Starting Chart Execution Pipeline Example")
    print("=" * 60)
    
    try:
        result = await pipeline.run(
            query="Show me sales trends by region over time",
            sql="SELECT date, region, sales_amount FROM sales_data ORDER BY date",
            project_id="chart_execution_example",
            configuration=configuration,
            status_callback=status_callback
        )
        
        print("\n" + "=" * 60)
        print("🎯 FINAL RESULT")
        print("=" * 60)
        
        post_process = result["post_process"]
        print(f"Chart Type: {post_process.get('chart_type', 'Unknown')}")
        print(f"Chart Format: {post_process.get('chart_format', 'Unknown')}")
        print(f"Data Count: {post_process.get('data_count', 0)}")
        print(f"Validation Success: {post_process.get('validation', {}).get('valid', False)}")
        print(f"Reasoning: {post_process.get('reasoning', '')[:100]}...")
        
        # Check for other format schemas
        if 'plotly_schema' in post_process:
            print(f"✅ Plotly schema available")
        if 'powerbi_schema' in post_process:
            print(f"✅ PowerBI schema available")
        if 'vega_lite_schema' in post_process:
            print(f"✅ Vega-Lite schema available")
        
        # Print metrics
        metrics = pipeline.get_metrics()
        print(f"Final Metrics: {metrics}")
        
    except Exception as e:
        print(f"❌ Error in example: {str(e)}")

if __name__ == "__main__":
    async def run_all_examples():
        print("🚀 Running Chart Execution Pipeline Examples")
        print("=" * 60)
        
        await example_basic_chart_execution()
        await example_different_formats()
        await example_with_pagination()
        await example_with_custom_configuration()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed!")
    
    asyncio.run(run_all_examples()) 