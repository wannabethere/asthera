# Render Visualization Service

## Overview

The `render_visualization` service is a comprehensive solution that combines chart generation and execution to provide complete visualization capabilities. It generates chart schemas using sample data and then executes them with the full dataset, offering both synchronous and streaming interfaces.

## Features

- **Complete Visualization Pipeline**: Combines chart generation and execution in a single service
- **Multi-Format Support**: Supports Vega-Lite, Plotly, and PowerBI chart formats
- **Real-time Streaming**: Provides streaming updates during the rendering process
- **Flexible Configuration**: Extensive configuration options for customization
- **Error Handling**: Comprehensive error handling and status reporting
- **Caching**: Built-in caching for improved performance
- **Pagination**: Support for large datasets with pagination

## Service Methods

### 1. `render_visualization`

The main method that renders a complete visualization by generating a chart schema and executing it with full data.

#### Parameters

- `query_id` (str): Unique identifier for the query
- `query` (str): The user's query
- `sql` (str): The SQL query to execute
- `project_id` (str): Project identifier
- `configuration` (Optional[Dict[str, Any]]): Configuration parameters
- `status_callback` (Optional[Callable]): Callback function for status updates

#### Configuration Options

```python
configuration = {
    # Chart format options
    "chart_format": "vega_lite",  # vega_lite, plotly, powerbi
    "include_other_formats": False,  # Whether to include other format conversions
    "use_multi_format": True,  # Whether to use multi-format chart generation
    
    # Data processing options
    "page_size": 1000,  # Page size for data pagination
    "max_rows": 10000,  # Maximum rows to process
    "enable_pagination": True,  # Whether to enable pagination
    "sort_by": None,  # Column to sort by
    "sort_order": "ASC",  # Sort order (ASC/DESC)
    
    # Performance options
    "timeout_seconds": 30,  # Timeout for execution
    "cache_results": True,  # Whether to cache results
    "cache_ttl_seconds": 300,  # Cache TTL in seconds
    
    # Chart generation options
    "remove_data_from_chart_schema": True,  # Remove data from chart schema
    "language": "English"  # Language for chart generation
}
```

#### Return Value

```python
{
    "success": True,
    "data": {
        "chart_schema": {},  # The executed chart schema with full data
        "chart_type": "bar",  # Type of chart generated
        "reasoning": "...",  # Reasoning behind chart selection
        "chart_format": "vega_lite",  # Format of the chart
        "data_count": 1000,  # Number of data points in the chart
        "validation": {},  # Validation results
        "execution_config": {},  # Configuration used for execution
        "sample_data": {},  # Sample data used for schema generation
        
        # Optional: Other format schemas (if include_other_formats=True)
        "plotly_schema": {},
        "powerbi_schema": {},
        "vega_lite_schema": {}
    },
    "metadata": {},
    "error": None
}
```

### 2. `stream_visualization_rendering`

Streams the visualization rendering process with real-time updates.

#### Parameters

- `query_id` (str): Unique identifier for the query
- `query` (str): The user's query
- `sql` (str): The SQL query to execute
- `project_id` (str): Project identifier
- `configuration` (Optional[Dict[str, Any]]): Configuration parameters

#### Streaming Updates

The method yields status updates with the following structure:

```python
{
    "status": "started|getting_sample_data|sample_data_ready|generating_chart_schema|chart_schema_ready|executing_chart|chart_execution_complete|generating_other_formats|other_formats_ready|completed|error|stopped",
    "details": {},  # Additional details for the status
    "data": {},  # Status-specific data
    "timestamp": "2024-01-01T12:00:00"
}
```

## API Endpoints

### POST `/chart/render`

Renders a visualization using the `render_visualization` service.

#### Request Body

```json
{
    "query": "Show me sales trends by region",
    "sql": "SELECT date, region, sales_amount FROM sales_data ORDER BY date",
    "project_id": "my_project",
    "query_id": "unique_query_id",
    "configuration": {
        "chart_format": "vega_lite",
        "include_other_formats": true,
        "page_size": 1000
    }
}
```

#### Response

```json
{
    "success": true,
    "data": {
        "chart_schema": {},
        "chart_type": "line",
        "chart_format": "vega_lite",
        "data_count": 5000
    },
    "metadata": {},
    "error": null
}
```

### POST `/chart/render/stream`

Streams the visualization rendering process with real-time updates.

#### Request Body

Same as `/chart/render` endpoint.

#### Response

Server-Sent Events (SSE) stream with real-time status updates.

## Usage Examples

### Basic Usage

```python
from app.services.sql.sql_helper_services import SQLHelperService

# Create service instance
sql_helper_service = SQLHelperService()

# Render visualization
result = await sql_helper_service.render_visualization(
    query_id="my_query_123",
    query="Show me sales trends",
    sql="SELECT date, sales FROM sales_data ORDER BY date",
    project_id="my_project",
    configuration={
        "chart_format": "vega_lite",
        "page_size": 1000
    }
)

if result.get("success"):
    chart_schema = result["data"]["chart_schema"]
    print(f"Chart generated: {result['data']['chart_type']}")
```

### Streaming Usage

```python
# Stream visualization rendering
async for update in sql_helper_service.stream_visualization_rendering(
    query_id="my_query_123",
    query="Show me sales trends",
    sql="SELECT date, sales FROM sales_data ORDER BY date",
    project_id="my_project"
):
    print(f"Status: {update['status']}")
    if update['status'] == 'completed':
        chart_data = update['data']
        break
```

### Multi-Format Usage

```python
# Generate visualization with multiple formats
result = await sql_helper_service.render_visualization(
    query_id="my_query_123",
    query="Show me sales trends",
    sql="SELECT date, sales FROM sales_data ORDER BY date",
    project_id="my_project",
    configuration={
        "chart_format": "vega_lite",
        "include_other_formats": True,
        "use_multi_format": True
    }
)

if result.get("success"):
    data = result["data"]
    vega_schema = data["chart_schema"]
    plotly_schema = data.get("plotly_schema")
    powerbi_schema = data.get("powerbi_schema")
```

### Status Callback Usage

```python
def status_callback(status: str, details: dict = None):
    print(f"Status: {status}")
    if details:
        print(f"Details: {details}")

result = await sql_helper_service.render_visualization(
    query_id="my_query_123",
    query="Show me sales trends",
    sql="SELECT date, sales FROM sales_data ORDER BY date",
    project_id="my_project",
    status_callback=status_callback
)
```

## Error Handling

The service provides comprehensive error handling:

```python
result = await sql_helper_service.render_visualization(...)

if not result.get("success"):
    error_message = result.get("error", "Unknown error")
    print(f"Visualization failed: {error_message}")
else:
    # Process successful result
    chart_data = result["data"]
```

## Status Updates

The service provides detailed status updates throughout the process:

1. **started**: Service initialization
2. **getting_sample_data**: Fetching sample data for schema generation
3. **sample_data_ready**: Sample data retrieved successfully
4. **generating_chart_schema**: Generating chart schema from sample data
5. **chart_schema_ready**: Chart schema generated successfully
6. **executing_chart**: Executing chart with full dataset
7. **chart_execution_complete**: Chart execution completed
8. **generating_other_formats**: Generating other format conversions (if enabled)
9. **other_formats_ready**: Other formats generated successfully
10. **completed**: All processing completed successfully
11. **error**: An error occurred during processing
12. **stopped**: Processing was stopped

## Dependencies

The service requires the following components to be properly configured:

- **ChartExecutionPipeline**: For executing charts with full data
- **Chart Generation Pipelines**: For generating chart schemas (Vega-Lite, Plotly, PowerBI)
- **Database Engine**: For executing SQL queries
- **LLM**: For chart generation reasoning
- **RetrievalHelper**: For data processing

## Testing

Use the provided test scripts to verify the service functionality:

```bash
# Run comprehensive example
python -m app.agents.pipelines.render_visualization_example

# Run simple tests
python -m app.agents.pipelines.test_render_visualization
```

## Performance Considerations

- **Caching**: Enable caching for repeated queries
- **Pagination**: Use pagination for large datasets
- **Timeout**: Set appropriate timeouts for long-running operations
- **Batch Size**: Adjust page size based on data volume and memory constraints

## Troubleshooting

### Common Issues

1. **Missing Chart Execution Pipeline**: Ensure the `chart_execution` pipeline is registered
2. **Database Connection Issues**: Verify database connectivity and SQL validity
3. **Memory Issues**: Reduce `max_rows` or `page_size` for large datasets
4. **Timeout Issues**: Increase `timeout_seconds` for complex queries

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration

The service integrates with the existing SQL helper services and can be used alongside other visualization and data processing services. It follows the same patterns and conventions as other services in the system. 