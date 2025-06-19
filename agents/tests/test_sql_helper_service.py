# Example usage functions
async def example_generate_sql_summary_and_visualization():
    """Example demonstrating how to use the generate_sql_summary_and_visualization method"""
    
    # Create SQL helper service
    sql_helper = SQLHelperService()
    
    # Example parameters
    query_id = "example_query_123"
    sql = "SELECT date, region, sales_amount, product_category FROM sales_data ORDER BY date"
    query = "Analyze sales performance trends by region and product category"
    project_id = "example_project"
    data_description = "Sales performance data across regions and product categories"
    
    # Configuration for the pipeline
    configuration = {
        "batch_size": 500,
        "chunk_size": 100,
        "language": "English",
        "enable_chart_generation": True,
        "chart_format": "vega_lite",
        "include_other_formats": True,
        "use_multi_format": True
    }
    
    try:
        # Generate summary and visualization
        result = await sql_helper.generate_sql_summary_and_visualization(
            query_id=query_id,
            sql=sql,
            query=query,
            project_id=project_id,
            data_description=data_description,
            configuration=configuration
        )
        
        if result.get("success"):
            print("=== SQL Summary and Visualization Result ===")
            print(f"Executive Summary: {result['data']['executive_summary'][:200]}...")
            print(f"Data Overview: {result['data']['data_overview']}")
            
            # Check if visualization was generated
            if 'visualization' in result['data']:
                viz = result['data']['visualization']
                if 'chart_schema' in viz:
                    print(f"Chart Type: {viz.get('chart_type', 'Unknown')}")
                    print(f"Chart Format: {viz.get('format', 'Unknown')}")
                    print(f"Chart Schema: {viz.get('chart_schema', {})}")
                else:
                    print(f"Chart Generation Error: {viz.get('error', 'Unknown error')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error in example: {str(e)}")


async def example_stream_sql_summary_and_visualization():
    """Example demonstrating how to use the stream_sql_summary_and_visualization method"""
    
    # Create SQL helper service
    sql_helper = SQLHelperService()
    
    # Example parameters
    query_id = "streaming_example_456"
    sql = "SELECT customer_id, purchase_date, amount, product_category FROM customer_purchases ORDER BY purchase_date"
    query = "Analyze customer purchase patterns over time"
    project_id = "streaming_project"
    data_description = "Customer purchase data with product categories and amounts"
    
    # Configuration for the pipeline
    configuration = {
        "batch_size": 100,  # Smaller batches for more frequent updates
        "chunk_size": 50,
        "language": "English",
        "enable_chart_generation": True,
        "chart_format": "plotly",
        "include_other_formats": False,
        "use_multi_format": True
    }
    
    try:
        print("=== Streaming SQL Summary and Visualization ===")
        
        # Stream summary and visualization
        async for update in sql_helper.stream_sql_summary_and_visualization(
            query_id=query_id,
            sql=sql,
            query=query,
            project_id=project_id,
            data_description=data_description,
            configuration=configuration
        ):
            status = update.get("status", "unknown")
            timestamp = update.get("timestamp", "")
            
            print(f"[{timestamp}] Status: {status}")
            
            if status == "fetch_data_complete":
                data = update.get("data", {})
                print(f"   📊 Data fetch completed - {data.get('total_count', 0)} records, {data.get('total_batches', 0)} batches")
                
            elif status == "summarization_begin":
                data = update.get("data", {})
                print(f"   🔄 Starting summarization for batch {data.get('batch_number', 0)}/{data.get('total_batches', 0)}")
                
            elif status == "summarization_complete":
                data = update.get("data", {})
                print(f"   ✅ Summarization completed for batch {data.get('batch_number', 0)}")
                if data.get('is_last_batch', False):
                    print(f"   🎉 All batches processed!")
                    
            elif status == "chart_generation_begin":
                data = update.get("data", {})
                print(f"   📈 Starting chart generation with format: {data.get('chart_format', 'unknown')}")
                
            elif status == "chart_generation_complete":
                data = update.get("data", {})
                if data.get('success', False):
                    print(f"   ✅ Chart generation completed successfully")
                else:
                    print(f"   ❌ Chart generation failed: {data.get('error', 'Unknown error')}")
                    
            elif status == "completed":
                data = update.get("data", {})
                print(f"\n🎯 FINAL RESULT:")
                print(f"   Executive Summary: {data.get('executive_summary', '')[:200]}...")
                print(f"   Data Overview: {data.get('data_overview', {})}")
                
                if 'visualization' in data:
                    viz = data['visualization']
                    if 'chart_schema' in viz:
                        print(f"   Chart Generated: {viz.get('chart_type', 'Unknown')} ({viz.get('format', 'Unknown')})")
                    else:
                        print(f"   Chart Generation Error: {viz.get('error', 'Unknown error')}")
                        
            elif status == "error":
                error = update.get("error", "Unknown error")
                print(f"   ❌ Error: {error}")
                
            elif status == "stopped":
                print(f"   ⏹️ Query was stopped")
                
    except Exception as e:
        print(f"Error in streaming example: {str(e)}")


if __name__ == "__main__":
    # Run the examples if this file is executed directly
    import asyncio
    
    async def run_examples():
        print("Running SQL Helper Service Examples...")
        
        print("\n1. Testing generate_sql_summary_and_visualization:")
        await example_generate_sql_summary_and_visualization()
        
        print("\n2. Testing stream_sql_summary_and_visualization:")
        await example_stream_sql_summary_and_visualization()
        
        print("\n✅ All examples completed!")
    
    asyncio.run(run_examples())