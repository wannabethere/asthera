"""
Example usage of the SQL Helper Service endpoints

This file demonstrates how to use the new SQL Helper Service endpoints
for generating SQL summaries, visualizations, and streaming results.
"""

import asyncio
import json
from typing import Dict, Any

# Example requests for the SQL Helper endpoints

def example_sql_summary_request() -> Dict[str, Any]:
    """Example request for SQL summary and visualization generation."""
    return {
        "sql": "SELECT date, region, sales_amount, product_category FROM sales_data ORDER BY date",
        "query": "Analyze sales performance trends by region and product category",
        "project_id": "example_project_123",
        "data_description": "Sales performance data across regions and product categories",
        "configuration": {
            "batch_size": 500,
            "chunk_size": 100,
            "language": "English",
            "enable_chart_generation": True,
            "chart_format": "vega_lite",
            "include_other_formats": True,
            "use_multi_format": True
        }
    }

def example_sql_streaming_request() -> Dict[str, Any]:
    """Example request for SQL streaming summary and visualization."""
    return {
        "sql": "SELECT customer_id, purchase_date, amount, product_category FROM customer_purchases ORDER BY purchase_date",
        "query": "Analyze customer purchase patterns over time",
        "project_id": "streaming_project_456",
        "data_description": "Customer purchase data with product categories and amounts",
        "configuration": {
            "batch_size": 100,  # Smaller batches for more frequent updates
            "chunk_size": 50,
            "language": "English",
            "enable_chart_generation": True,
            "chart_format": "plotly",
            "include_other_formats": False,
            "use_multi_format": True
        }
    }

def example_query_requirements_request() -> Dict[str, Any]:
    """Example request for query requirements analysis."""
    return {
        "query": "Show me sales data for the last quarter",
        "project_id": "requirements_project_789",
        "configuration": {
            "analysis_depth": "detailed",
            "include_suggestions": True
        },
        "schema_context": {
            "tables": ["sales_data", "products", "customers"],
            "time_period": "quarterly"
        }
    }

def example_sql_visualization_request() -> Dict[str, Any]:
    """Example request for SQL visualization generation."""
    return {
        "query": "Create a chart showing monthly sales trends",
        "sql_result": {
            "api_results": [
                {
                    "sql": "SELECT DATE_TRUNC('month', date) as month, SUM(sales_amount) as total_sales FROM sales_data GROUP BY month ORDER BY month"
                }
            ]
        },
        "project_id": "visualization_project_101",
        "chart_config": {
            "chart_type": "line",
            "x_axis": "month",
            "y_axis": "total_sales",
            "title": "Monthly Sales Trends"
        },
        "streaming": False
    }

# Example API calls using requests library
async def example_api_calls():
    """Example of how to call the SQL Helper endpoints using requests."""
    import requests
    
    base_url = "http://localhost:8000/sql-helper"
    
    # Example 1: Generate SQL summary and visualization
    print("=== Example 1: Generate SQL Summary and Visualization ===")
    summary_request = example_sql_summary_request()
    
    try:
        response = requests.post(f"{base_url}/summary", json=summary_request)
        if response.status_code == 200:
            result = response.json()
            print(f"Query ID: {result['query_id']}")
            print(f"Success: {result['success']}")
            if result['success']:
                data = result['data']
                print(f"Executive Summary: {data['executive_summary'][:200]}...")
                print(f"Data Overview: {data['data_overview']}")
                if 'visualization' in data:
                    viz = data['visualization']
                    if 'chart_schema' in viz:
                        print(f"Chart Type: {viz.get('chart_type', 'Unknown')}")
                        print(f"Chart Format: {viz.get('format', 'Unknown')}")
                    else:
                        print(f"Chart Generation Error: {viz.get('error', 'Unknown error')}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"HTTP Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error making API call: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Example 2: Analyze query requirements
    print("=== Example 2: Analyze Query Requirements ===")
    requirements_request = example_query_requirements_request()
    
    try:
        response = requests.post(f"{base_url}/analyze-requirements", json=requirements_request)
        if response.status_code == 200:
            result = response.json()
            print(f"Query ID: {result['query_id']}")
            print(f"Success: {result['success']}")
            if result['success']:
                data = result['data']
                print(f"Combined Analysis: {data.get('combined_analysis', {})}")
                print(f"Expansion Suggestions: {data.get('expansion_suggestions', {})}")
                print(f"Correction Suggestions: {data.get('correction_suggestions', {})}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"HTTP Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error making API call: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Example 3: Generate SQL visualization
    print("=== Example 3: Generate SQL Visualization ===")
    visualization_request = example_sql_visualization_request()
    
    try:
        response = requests.post(f"{base_url}/visualization", json=visualization_request)
        if response.status_code == 200:
            result = response.json()
            print(f"Query ID: {result['query_id']}")
            print(f"Success: {result['success']}")
            if result['success']:
                data = result['data']
                print(f"SQL Data: {data.get('sql_data', {})}")
                print(f"Summary: {data.get('summary', '')[:200]}...")
                if 'chart' in data:
                    chart = data['chart']
                    print(f"Chart Schema: {chart.get('chart_schema', {})}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"HTTP Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error making API call: {e}")

# Example streaming client
async def example_streaming_client():
    """Example of how to consume the streaming endpoint."""
    import aiohttp
    import asyncio
    
    base_url = "http://localhost:8000/sql-helper"
    streaming_request = example_sql_streaming_request()
    
    print("=== Example 4: Streaming SQL Summary and Visualization ===")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/summary/stream",
                json=streaming_request,
                headers={"Accept": "text/event-stream"}
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            try:
                                data = json.loads(line_str[6:])  # Remove 'data: ' prefix
                                status = data.get('status', 'unknown')
                                timestamp = data.get('timestamp', '')
                                
                                print(f"[{timestamp}] Status: {status}")
                                
                                if status == "fetch_data_complete":
                                    details = data.get('details', {})
                                    print(f"   📊 Data fetch completed - {details.get('total_count', 0)} records, {details.get('total_batches', 0)} batches")
                                    
                                elif status == "summarization_begin":
                                    details = data.get('details', {})
                                    print(f"   🔄 Starting summarization for batch {details.get('batch_number', 0)}/{details.get('total_batches', 0)}")
                                    
                                elif status == "summarization_complete":
                                    details = data.get('details', {})
                                    print(f"   ✅ Summarization completed for batch {details.get('batch_number', 0)}")
                                    if details.get('is_last_batch', False):
                                        print(f"   🎉 All batches processed!")
                                        
                                elif status == "chart_generation_begin":
                                    details = data.get('details', {})
                                    print(f"   📈 Starting chart generation with format: {details.get('chart_format', 'unknown')}")
                                    
                                elif status == "chart_generation_complete":
                                    details = data.get('details', {})
                                    if details.get('success', False):
                                        print(f"   ✅ Chart generation completed successfully")
                                    else:
                                        print(f"   ❌ Chart generation failed: {details.get('error', 'Unknown error')}")
                                        
                                elif status == "completed":
                                    result_data = data.get('data', {})
                                    print(f"\n🎯 FINAL RESULT:")
                                    print(f"   Executive Summary: {result_data.get('executive_summary', '')[:200]}...")
                                    print(f"   Data Overview: {result_data.get('data_overview', {})}")
                                    
                                    if 'visualization' in result_data:
                                        viz = result_data['visualization']
                                        if 'chart_schema' in viz:
                                            print(f"   Chart Generated: {viz.get('chart_type', 'Unknown')} ({viz.get('format', 'Unknown')})")
                                        else:
                                            print(f"   Chart Generation Error: {viz.get('error', 'Unknown error')}")
                                            
                                elif status == "error":
                                    error = data.get('error', 'Unknown error')
                                    print(f"   ❌ Error: {error}")
                                    
                                elif status == "stopped":
                                    print(f"   ⏹️ Query was stopped")
                                    
                            except json.JSONDecodeError:
                                print(f"   ⚠️ Invalid JSON in stream: {line_str}")
                else:
                    print(f"HTTP Error: {response.status} - {await response.text()}")
    except Exception as e:
        print(f"Error in streaming client: {e}")

if __name__ == "__main__":
    print("SQL Helper Service Examples")
    print("=" * 60)
    
    # Run the examples
    asyncio.run(example_api_calls())
    asyncio.run(example_streaming_client())
    
    print("\n✅ All examples completed!") 