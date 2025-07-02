"""
Example demonstrating separate chart execution with SQL data fetching

This example shows how to:
1. Generate a chart schema using the existing pipeline
2. Execute the chart with data fetched from a database using SQL
3. Configure pagination and other execution parameters
"""

import asyncio
import os
from typing import Dict, Any, List

# Set up environment
os.environ["OPENAI_API_KEY"] = "your-api-key-here"

from app.agents.nodes.sql.chart_generation import generate_vega_lite_chart
from app.agents.nodes.sql.utils.chart import ChartExecutor, ChartExecutionConfig, execute_chart_with_sql


class MockDatabaseEngine:
    """Mock database engine for demonstration purposes"""
    
    def __init__(self):
        # Mock data that would come from a real database
        self.sales_data = [
            {"Date": "2023-01-01", "Sales": 100000, "Region": "North", "Product": "A"},
            {"Date": "2023-02-01", "Sales": 120000, "Region": "North", "Product": "A"},
            {"Date": "2023-03-01", "Sales": 110000, "Region": "North", "Product": "A"},
            {"Date": "2023-04-01", "Sales": 130000, "Region": "North", "Product": "A"},
            {"Date": "2023-05-01", "Sales": 140000, "Region": "North", "Product": "A"},
            {"Date": "2023-06-01", "Sales": 150000, "Region": "North", "Product": "A"},
            {"Date": "2023-01-01", "Sales": 90000, "Region": "South", "Product": "A"},
            {"Date": "2023-02-01", "Sales": 95000, "Region": "South", "Product": "A"},
            {"Date": "2023-03-01", "Sales": 105000, "Region": "South", "Product": "A"},
            {"Date": "2023-04-01", "Sales": 115000, "Region": "South", "Product": "A"},
            {"Date": "2023-05-01", "Sales": 125000, "Region": "South", "Product": "A"},
            {"Date": "2023-06-01", "Sales": 135000, "Region": "South", "Product": "A"},
            {"Date": "2023-01-01", "Sales": 80000, "Region": "East", "Product": "B"},
            {"Date": "2023-02-01", "Sales": 85000, "Region": "East", "Product": "B"},
            {"Date": "2023-03-01", "Sales": 90000, "Region": "East", "Product": "B"},
            {"Date": "2023-04-01", "Sales": 100000, "Region": "East", "Product": "B"},
            {"Date": "2023-05-01", "Sales": 110000, "Region": "East", "Product": "B"},
            {"Date": "2023-06-01", "Sales": 120000, "Region": "East", "Product": "B"},
        ]
    
    async def execute(self, sql_query: str) -> List[Dict[str, Any]]:
        """Mock SQL execution - in real usage, this would connect to a database"""
        print(f"Executing SQL: {sql_query}")
        
        # Simple mock SQL parsing for demonstration
        if "LIMIT" in sql_query.upper():
            # Extract limit number
            import re
            limit_match = re.search(r'LIMIT\s+(\d+)', sql_query, re.IGNORECASE)
            if limit_match:
                limit = int(limit_match.group(1))
                return self.sales_data[:limit]
        
        if "ORDER BY" in sql_query.upper():
            # Simple sorting by Date
            if "Date" in sql_query:
                return sorted(self.sales_data, key=lambda x: x["Date"])
        
        return self.sales_data


async def example_chart_execution():
    """Example of generating and executing a chart with SQL data"""
    
    print("=== Chart Generation and Execution Example ===\n")
    
    # Step 1: Generate chart schema using sample data
    print("Step 1: Generating chart schema...")
    
    sample_data = {
        "columns": ["Date", "Sales", "Region"],
        "data": [
            ["2023-01-01", 100000, "North"],
            ["2023-02-01", 120000, "North"],
            ["2023-03-01", 110000, "North"],
            ["2023-01-01", 90000, "South"],
            ["2023-02-01", 95000, "South"],
            ["2023-03-01", 105000, "South"]
        ]
    }
    
    # Generate chart schema
    generation_result = await generate_vega_lite_chart(
        query="Show me sales trends by region over time",
        sql="SELECT Date, Sales, Region FROM sales_data ORDER BY Date",
        data=sample_data,
        language="English"
    )
    
    if not generation_result.get("success", False):
        print("Failed to generate chart schema")
        return
    
    chart_schema = generation_result.get("chart_schema", {})
    print(f"✓ Chart schema generated successfully")
    print(f"  Chart type: {generation_result.get('chart_type', 'unknown')}")
    print(f"  Reasoning: {generation_result.get('reasoning', '')[:100]}...")
    
    # Step 2: Execute chart with full database data
    print("\nStep 2: Executing chart with database data...")
    
    # Create mock database engine
    db_engine = MockDatabaseEngine()
    
    # Configure execution parameters
    config = ChartExecutionConfig(
        page_size=1000,           # Number of rows per page
        max_rows=10000,           # Maximum rows to fetch
        enable_pagination=True,   # Enable pagination
        sort_by="Date",           # Sort by Date column
        sort_order="ASC",         # Ascending order
        timeout_seconds=30,       # Query timeout
        cache_results=True,       # Enable caching
        cache_ttl_seconds=300     # Cache TTL (5 minutes)
    )
    
    # Execute chart with SQL data
    execution_result = await execute_chart_with_sql(
        chart_schema=chart_schema,
        sql_query="SELECT Date, Sales, Region FROM sales_data ORDER BY Date LIMIT 1000",
        db_engine=db_engine,
        config=config
    )
    
    if execution_result.get("success", False):
        print("✓ Chart executed successfully with database data")
        print(f"  Data count: {execution_result.get('data_count', 0)}")
        print(f"  Validation: {execution_result.get('validation', {}).get('valid', False)}")
        
        # Get the executed chart schema with data
        executed_schema = execution_result.get("chart_schema", {})
        print(f"  Chart schema ready for rendering")
        
        # Example: Export to different formats
        from app.agents.nodes.sql.utils.chart import VegaLiteChartExporter
        
        exporter = VegaLiteChartExporter()
        
        # Export to JSON
        json_export = exporter.to_vega_lite_json(executed_schema)
        print(f"  JSON export length: {len(json_export)} characters")
        
        # Get chart summary
        summary = exporter.get_chart_summary(executed_schema)
        print(f"  Chart summary: {summary}")
        
    else:
        print("✗ Chart execution failed")
        print(f"  Error: {execution_result.get('error', 'Unknown error')}")
    
    # Step 3: Demonstrate different execution configurations
    print("\nStep 3: Demonstrating different execution configurations...")
    
    # Configuration 1: Limited data for performance
    config_limited = ChartExecutionConfig(
        max_rows=10,
        enable_pagination=True,
        sort_by="Sales",
        sort_order="DESC"
    )
    
    result_limited = await execute_chart_with_sql(
        chart_schema=chart_schema,
        sql_query="SELECT Date, Sales, Region FROM sales_data ORDER BY Sales DESC",
        db_engine=db_engine,
        config=config_limited
    )
    
    print(f"  Limited execution: {result_limited.get('data_count', 0)} rows")
    
    # Configuration 2: No pagination, all data
    config_all = ChartExecutionConfig(
        enable_pagination=False,
        cache_results=False
    )
    
    result_all = await execute_chart_with_sql(
        chart_schema=chart_schema,
        sql_query="SELECT Date, Sales, Region FROM sales_data",
        db_engine=db_engine,
        config=config_all
    )
    
    print(f"  Full execution: {result_all.get('data_count', 0)} rows")
    
    print("\n=== Example completed ===")


async def example_with_real_database():
    """Example showing how to use with a real database engine"""
    
    print("\n=== Real Database Integration Example ===\n")
    
    # This is an example of how you would integrate with a real database
    # You would replace this with your actual database engine
    
    try:
        # Example with SQLAlchemy (uncomment and modify as needed)
        # from sqlalchemy import create_engine
        # from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        # 
        # # Create async engine
        # engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
        # 
        # # Generate chart schema (same as before)
        # chart_schema = {...}  # From chart generation
        # 
        # # Execute with real database
        # config = ChartExecutionConfig(max_rows=5000)
        # result = await execute_chart_with_sql(
        #     chart_schema=chart_schema,
        #     sql_query="SELECT * FROM sales_data",
        #     db_engine=engine,
        #     config=config
        # )
        
        print("Real database integration example:")
        print("1. Create your database engine (SQLAlchemy, asyncpg, etc.)")
        print("2. Generate chart schema using the existing pipeline")
        print("3. Execute chart with SQL data using ChartExecutor")
        print("4. Configure pagination and limits as needed")
        
    except ImportError:
        print("Database dependencies not available for this example")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(example_chart_execution())
    asyncio.run(example_with_real_database()) 