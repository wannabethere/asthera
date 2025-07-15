# Analysis Intent Classification Pipeline

This module provides a comprehensive pipeline for classifying user analysis intent using the `AnalysisIntentPlanner`. The pipeline extends the `AgentPipeline` base class and provides async flow capabilities for determining the appropriate analysis approach based on available data and functions.

## Features

- **Async Processing**: Full async support for efficient processing
- **Batch Processing**: Process multiple questions concurrently
- **Retry Logic**: Built-in retry mechanism with exponential backoff
- **Input Validation**: Comprehensive input validation
- **Performance Metrics**: Track processing times and success rates
- **Configuration Management**: Flexible configuration options
- **Error Handling**: Robust error handling and logging

## Components

### AnalysisIntentClassificationPipeline

The main pipeline class that wraps the `AnalysisIntentPlanner` and provides additional functionality:

- **Initialization**: Set up with LLM, ChromaDB collections, and configuration
- **Async Processing**: Run single or batch classifications
- **Metrics Tracking**: Monitor performance and success rates
- **Configuration Management**: Update pipeline settings dynamically

### Factory Function

`create_analysis_intent_pipeline()` - A convenience function for creating pipeline instances with default settings.

## Usage

### Basic Usage

```python
import asyncio
from langchain_openai import ChatOpenAI
from app.pipelines.mlpipelines.stats_pipelines import create_analysis_intent_pipeline

async def basic_example():
    # Setup LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0.1)
    
    # Create pipeline
    pipeline = create_analysis_intent_pipeline(llm=llm)
    
    # Initialize
    await pipeline.initialize()
    
    # Run classification
    result = await pipeline.run(
        question="How does the variance of my data change over time?",
        dataframe_description="Financial metrics dataset",
        available_columns=["value", "timestamp", "category"]
    )
    
    print(f"Intent: {result['classification']['intent_type']}")
    print(f"Confidence: {result['classification']['confidence_score']}")
    print(f"Can be answered: {result['classification']['can_be_answered']}")
    
    # Cleanup
    await pipeline.cleanup()

# Run the example
asyncio.run(basic_example())
```

### Advanced Usage with ChromaDB

```python
import asyncio
import chromadb
from langchain_openai import ChatOpenAI
from app.pipelines.mlpipelines.stats_pipelines import create_analysis_intent_pipeline
from app.storage.documents import DocumentChromaStore

async def advanced_example():
    # Setup ChromaDB
    client = chromadb.PersistentClient(path="./chroma_db")
    
    function_collection = DocumentChromaStore(
        persistent_client=client,
        collection_name="function_definitions"
    )
    
    example_collection = DocumentChromaStore(
        persistent_client=client,
        collection_name="function_examples"
    )
    
    # Setup LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0.1)
    
    # Create pipeline with collections
    pipeline = create_analysis_intent_pipeline(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        pipeline_config={
            "enable_quick_check": True,
            "enable_llm_feasibility": True,
            "max_functions_to_retrieve": 15
        }
    )
    
    await pipeline.initialize()
    
    # Run with full context
    result = await pipeline.run(
        question="Calculate 5-day rolling variance of flux grouped by projects",
        dataframe_description="Financial metrics dataset with project performance data",
        dataframe_summary="Contains 10,000 rows with daily metrics from 2023-2024",
        available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"],
        enable_quick_check=True,
        enable_llm_feasibility=True
    )
    
    if result['status'] == 'success':
        classification = result['classification']
        print(f"Intent: {classification['intent_type']}")
        print(f"Suggested Functions: {classification['suggested_functions']}")
        print(f"Required Columns: {classification['required_data_columns']}")
        print(f"Feasibility Score: {classification['feasibility_score']}")
        
        if result.get('quick_check'):
            print(f"Quick Check Feasible: {result['quick_check'].get('feasible')}")
    
    await pipeline.cleanup()

asyncio.run(advanced_example())
```

### Batch Processing

```python
async def batch_example():
    pipeline = create_analysis_intent_pipeline(llm=llm)
    await pipeline.initialize()
    
    questions = [
        {
            "question": "What is the variance of my data?",
            "dataframe_description": "Simple dataset",
            "available_columns": ["value", "timestamp"]
        },
        {
            "question": "Show me user retention over time",
            "dataframe_description": "User dataset",
            "available_columns": ["user_id", "signup_date", "last_activity"]
        },
        {
            "question": "Segment my customers by behavior",
            "dataframe_description": "Customer dataset",
            "available_columns": ["customer_id", "purchase_amount", "visit_frequency"]
        }
    ]
    
    # Process in batches of 2
    results = await pipeline.batch_classify_intents(questions, batch_size=2)
    
    for i, result in enumerate(results):
        if result['status'] == 'success':
            print(f"Question {i+1}: {result['classification']['intent_type']}")
    
    await pipeline.cleanup()
```

### Retry Logic

```python
async def retry_example():
    pipeline = create_analysis_intent_pipeline(llm=llm)
    await pipeline.initialize()
    
    # Run with retry logic
    result = await pipeline.classify_with_retry(
        max_retries=3,
        retry_delay=1.0,
        question="Calculate correlation between revenue and satisfaction",
        dataframe_description="Business dataset",
        available_columns=["revenue", "satisfaction_score", "date"]
    )
    
    print(f"Final Status: {result['status']}")
    await pipeline.cleanup()
```

## Pipeline Parameters

### Required Parameters

- `question` (str): The user's natural language question

### Optional Parameters

- `dataframe_description` (str): Description of the dataframe
- `dataframe_summary` (str): Summary of the dataframe
- `available_columns` (List[str]): List of available columns
- `enable_quick_check` (bool): Enable quick feasibility check (default: True)
- `enable_llm_feasibility` (bool): Enable LLM-based feasibility assessment (default: True)

## Pipeline Configuration

### Available Configuration Options

- `max_functions_to_retrieve` (int): Maximum number of functions to retrieve (default: 10)
- `enable_quick_check` (bool): Enable quick feasibility check
- `enable_llm_feasibility` (bool): Enable enhanced LLM-based feasibility assessment
- `pipeline_config` (dict): Additional pipeline-specific configuration

### Updating Configuration

```python
# Update configuration
pipeline.update_configuration({
    "max_functions_to_retrieve": 15,
    "pipeline_config": {
        "enable_quick_check": False,
        "custom_setting": "value"
    }
})

# Get current configuration
config = pipeline.get_configuration()
print(f"Current config: {config}")
```

## Performance Monitoring

### Metrics

The pipeline tracks various performance metrics:

- `total_requests`: Total number of requests processed
- `successful_classifications`: Number of successful classifications
- `failed_classifications`: Number of failed classifications
- `success_rate`: Success rate as a percentage
- `average_processing_time`: Average processing time in seconds
- `total_processing_time`: Total processing time in seconds
- `last_request_time`: Timestamp of the last request

### Accessing Metrics

```python
# Get metrics
metrics = pipeline.get_metrics()
print(f"Success Rate: {metrics['success_rate']:.2%}")
print(f"Average Processing Time: {metrics['average_processing_time']:.2f}s")

# Reset metrics
pipeline.reset_metrics()
```

## Input Validation

The pipeline includes comprehensive input validation:

```python
# Validate input before processing
validation = await pipeline.validate_input(
    question="What is the variance?",
    available_columns=["value", "timestamp"],
    dataframe_description="Test dataset"
)

if validation['is_valid']:
    result = await pipeline.run(...)
else:
    print(f"Validation errors: {validation['errors']}")
    print(f"Warnings: {validation['warnings']}")
```

## Error Handling

The pipeline provides robust error handling:

```python
try:
    result = await pipeline.run(question="Invalid input")
    
    if result['status'] == 'error':
        error_info = result['error']
        print(f"Error: {error_info['message']}")
        print(f"Error Type: {error_info['type']}")
        
except Exception as e:
    print(f"Pipeline error: {e}")
```

## Available Analysis Types

The pipeline supports various analysis types:

- `time_series_analysis`: Analyze data patterns over time
- `trend_analysis`: Analyze trends and growth patterns
- `segmentation_analysis`: Group data into meaningful segments
- `cohort_analysis`: Analyze user behavior and retention
- `funnel_analysis`: Analyze user conversion funnels
- `risk_analysis`: Perform risk analysis and assessment
- `anomaly_detection`: Detect outliers and anomalies
- `metrics_calculation`: Calculate statistical metrics
- `operations_analysis`: Statistical operations and experiments

## Example Scripts

See `example_usage.py` for comprehensive examples demonstrating:

1. Single question classification
2. Batch processing
3. Retry logic
4. Pipeline metrics
5. Input validation
6. Error handling

## Dependencies

- `langchain_openai`: For LLM integration
- `chromadb`: For vector storage (optional)
- `langfuse`: For observability (optional)
- `asyncio`: For async processing
- `pydantic`: For data validation

## Running Tests

```bash
# Run the example script
python -m app.pipelines.mlpipelines.example_usage

# Run the pipeline tests
python -m app.pipelines.mlpipelines.stats_pipelines
```

## Best Practices

1. **Always initialize and cleanup**: Use `await pipeline.initialize()` and `await pipeline.cleanup()`
2. **Handle errors gracefully**: Check result status and handle errors appropriately
3. **Use batch processing**: For multiple questions, use `batch_classify_intents()`
4. **Monitor performance**: Regularly check metrics to ensure optimal performance
5. **Validate inputs**: Use `validate_input()` before processing
6. **Configure appropriately**: Set `max_functions_to_retrieve` based on your needs
7. **Use retry logic**: For production systems, use `classify_with_retry()`

## Troubleshooting

### Common Issues

1. **ChromaDB Connection Errors**: Ensure ChromaDB is running and accessible
2. **LLM API Errors**: Check API keys and rate limits
3. **Memory Issues**: Reduce `max_functions_to_retrieve` for large datasets
4. **Timeout Errors**: Increase timeout settings or use retry logic

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

When contributing to this pipeline:

1. Follow the existing code structure
2. Add comprehensive error handling
3. Include input validation
4. Add appropriate logging
5. Update tests and documentation
6. Follow async/await patterns consistently 