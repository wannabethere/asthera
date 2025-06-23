# DataSummarizationPipeline Status Callback

The `DataSummarizationPipeline` now supports status callbacks to provide real-time updates during the data processing pipeline. This allows you to track progress and respond to different stages of the pipeline execution.

## Overview

The status callback functionality sends updates at the following key points:

1. **fetch_data_complete** - When data fetching is finished
2. **summarization_begin** - When summarization starts for each batch
3. **summarization_complete** - When summarization finishes for each batch
4. **chart_generation_begin** - When chart generation starts
5. **chart_generation_complete** - When chart generation finishes successfully
6. **chart_generation_error** - When chart generation encounters an error

## Usage

### Setting up the Status Callback

The status callback is passed directly to the `run` method, providing flexibility to use different callbacks for different runs:

```python
def my_status_callback(status: str, details: Dict[str, Any]):
    print(f"Status: {status}")
    print(f"Details: {details}")

# Create pipeline (no callback needed in constructor)
pipeline = DataSummarizationPipeline(
    name="My Pipeline",
    version="1.0",
    description="Pipeline with status updates",
    llm=llm,
    engine=engine,
    retrieval_helper=retrieval_helper
)

# Pass callback to run method
result = await pipeline.run(
    query="Analyze sales data",
    sql="SELECT * FROM sales_data",
    data_description="Sales performance data",
    project_id="my_project",
    status_callback=my_status_callback  # Pass callback here
)
```

### Status Callback Function Signature

```python
def status_callback(status: str, details: Dict[str, Any]) -> None:
    """
    Status callback function
    
    Args:
        status: The status message (e.g., "fetch_data_complete", "summarization_begin")
        details: Dictionary containing relevant details for the status
    """
    pass
```

### Status Types and Details

#### fetch_data_complete
```python
{
    "total_count": 1000,        # Total number of records
    "total_batches": 5,         # Number of batches to process
    "batch_size": 200,          # Size of each batch
    "project_id": "my_project"  # Project identifier
}
```

#### summarization_begin
```python
{
    "batch_number": 2,          # Current batch number (1-based)
    "total_batches": 5,         # Total number of batches
    "batch_size": 200,          # Number of records in this batch
    "project_id": "my_project"  # Project identifier
}
```

#### summarization_complete
```python
{
    "batch_number": 2,          # Current batch number (1-based)
    "total_batches": 5,         # Total number of batches
    "batch_size": 200,          # Number of records in this batch
    "project_id": "my_project", # Project identifier
    "is_last_batch": False      # Whether this is the final batch
}
```

#### chart_generation_begin
```python
{
    "project_id": "my_project",           # Project identifier
    "chart_format": "vega_lite",          # Chart format being used
    "total_batches": 5                    # Total number of batches processed
}
```

#### chart_generation_complete
```python
{
    "project_id": "my_project",           # Project identifier
    "success": True,                      # Whether chart generation succeeded
    "chart_format": "vega_lite",          # Chart format used
    "error": None                         # Error message if failed
}
```

#### chart_generation_error
```python
{
    "project_id": "my_project",           # Project identifier
    "error": "Chart generation failed",   # Error message
    "chart_format": "vega_lite"           # Chart format that was attempted
}
```

## Example Implementation

Here's a complete example showing how to use the status callback:

```python
import asyncio
from typing import Dict, Any

def comprehensive_status_callback(status: str, details: Dict[str, Any]):
    """Comprehensive status callback with different handling for each status"""
    
    if status == "fetch_data_complete":
        print(f"✅ Data fetch completed!")
        print(f"   📊 Total records: {details.get('total_count', 0)}")
        print(f"   📦 Total batches: {details.get('total_batches', 0)}")
        print(f"   📏 Batch size: {details.get('batch_size', 0)}")
        
    elif status == "summarization_begin":
        batch_num = details.get('batch_number', 0)
        total_batches = details.get('total_batches', 0)
        print(f"📊 Starting summarization for batch {batch_num}/{total_batches}")
        
    elif status == "summarization_complete":
        batch_num = details.get('batch_number', 0)
        total_batches = details.get('total_batches', 0)
        is_last = details.get('is_last_batch', False)
        
        print(f"✅ Completed summarization for batch {batch_num}/{total_batches}")
        if is_last:
            print(f"🎉 All batches processed successfully!")
            
    elif status == "chart_generation_begin":
        chart_format = details.get('chart_format', 'unknown')
        print(f"📈 Starting chart generation with {chart_format} format")
        
    elif status == "chart_generation_complete":
        success = details.get('success', False)
        if success:
            print(f"✅ Chart generation completed successfully")
        else:
            error = details.get('error', 'Unknown error')
            print(f"❌ Chart generation failed: {error}")
            
    elif status == "chart_generation_error":
        error = details.get('error', 'Unknown error')
        print(f"❌ Chart generation error: {error}")

# Create pipeline
pipeline = DataSummarizationPipeline(
    name="Status Tracking Pipeline",
    version="1.0",
    description="Pipeline with comprehensive status tracking",
    llm=llm,
    engine=engine,
    retrieval_helper=retrieval_helper
)

# Run the pipeline with status callback
result = await pipeline.run(
    query="Analyze sales data",
    sql="SELECT * FROM sales_data",
    data_description="Sales performance data",
    project_id="status_example",
    status_callback=comprehensive_status_callback
)
```

## Advantages of Run-Level Callbacks

1. **Flexibility**: Different callbacks for different runs
2. **Simplicity**: No need to manage callback state in the pipeline
3. **Cleaner API**: Callback is only used when needed
4. **Better Testing**: Easier to test with different callbacks
5. **Resource Management**: Callback is scoped to the run duration

## Use Cases

1. **Progress Tracking**: Show progress bars or percentage completion
2. **User Notifications**: Send real-time updates to users via WebSocket or SSE
3. **Logging**: Enhanced logging with structured status information
4. **Error Handling**: Immediate notification of failures
5. **Resource Management**: Track resource usage at different stages
6. **Analytics**: Collect timing and performance metrics

## Best Practices

1. **Keep callbacks lightweight**: Avoid heavy operations in the callback function
2. **Handle exceptions**: Always wrap callback logic in try-catch blocks
3. **Use async if needed**: If your callback needs to perform async operations, make it async
4. **Log status updates**: Consider logging status updates for debugging
5. **Batch status updates**: For high-frequency updates, consider batching them

## Error Handling

The pipeline automatically handles callback errors to prevent them from affecting the main processing:

```python
def send_status_update(status: str, details: Dict[str, Any] = None):
    """Send status update via callback if available"""
    if status_callback:
        try:
            status_callback(status, details or {})
        except Exception as e:
            logger.error(f"Error in status callback: {str(e)}")
    logger.info(f"Status Update - {status}: {details}")
```

This ensures that even if your callback function throws an exception, the pipeline will continue to function normally. 