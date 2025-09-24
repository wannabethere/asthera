# ML Function Registry

The ML Function Registry is a comprehensive system for storing, searching, and retrieving ML tool function definitions using ChromaDB. It provides semantic search capabilities to help ML agents find the most relevant functions for their tasks.

## Overview

The function registry system consists of several components:

1. **FunctionRegistry** - Core registry for storing function metadata
2. **FunctionSearchInterface** - High-level search interface
3. **FunctionRetrievalService** - Agent-friendly service for function retrieval
4. **DocumentChromaStore Integration** - ChromaDB storage backend

## Features

- **Semantic Search**: Find functions using natural language queries
- **Metadata Extraction**: Automatic extraction of function descriptions, parameters, examples
- **Category Classification**: Functions are automatically categorized (anomaly_detection, time_series, etc.)
- **Complexity Assessment**: Functions are rated as simple, intermediate, or advanced
- **Agent Integration**: Easy integration with ML agents for function discovery
- **Export Capabilities**: Export function catalogs in JSON, CSV, or Markdown formats

## Installation and Setup

### 1. Install Dependencies

```bash
pip install chromadb langchain openai
```

### 2. Initialize the Registry

```python
import chromadb
from app.tools.mltools.registry import initialize_function_registry

# Initialize ChromaDB client
client = chromadb.PersistentClient(path="./chroma_db")

# Initialize function registry
registry = initialize_function_registry(client)
```

### 3. Using the Command Line Interface

```bash
# Initialize the registry
python -m app.tools.mltools.registry.initialize_function_registry --chroma-path ./chroma_db

# Run tests
python -m app.tools.mltools.registry.initialize_function_registry --test

# Export function catalog
python -m app.tools.mltools.registry.initialize_function_registry --export --output-file function_catalog.json
```

## Usage Examples

### Basic Search

```python
from app.tools.mltools.registry import create_function_retrieval_service

# Create service
service = create_function_retrieval_service("./chroma_db")

# Search for functions
results = service.search_functions_for_agent(
    "detect anomalies in time series data",
    max_results=5
)

for result in results:
    print(f"{result['function_name']}: {result['description']}")
```

### Advanced Search with Context

```python
# Search with agent context
results = service.search_functions_for_agent(
    "customer segmentation analysis",
    context={
        "task_type": "segmentation",
        "data_columns": ["user_id", "purchase_amount", "category"],
        "complexity_level": "intermediate"
    },
    max_results=3
)
```

### Search by Use Case

```python
# Find functions for specific use cases
use_cases = [
    "anomaly_detection",
    "time_series_forecasting", 
    "customer_segmentation",
    "cohort_analysis",
    "risk_analysis"
]

for use_case in use_cases:
    results = service.search_functions_by_use_case(use_case)
    print(f"{use_case}: {len(results)} functions found")
```

### Get Function Details

```python
# Get detailed information about a specific function
function_info = service.get_function_by_name("detect_contextual_anomalies")

if function_info:
    print(f"Function: {function_info['function_name']}")
    print(f"Module: {function_info['module']}")
    print(f"Parameters: {function_info['parameters']}")
    print(f"Examples: {function_info['examples']}")
```

### Get Function Recommendations

```python
# Get recommendations based on a function
recommendations = service.get_function_recommendations(
    "detect_contextual_anomalies",
    max_recommendations=5
)

for rec in recommendations:
    print(f"Recommended: {rec['function_name']} - {rec['description']}")
```

## Function Categories

The registry automatically categorizes functions into the following categories:

- **anomaly_detection**: Functions for detecting anomalies and outliers
- **time_series**: Functions for time series analysis and forecasting
- **cohort_analysis**: Functions for cohort and retention analysis
- **segmentation**: Functions for customer and data segmentation
- **metrics**: Functions for calculating various metrics and statistics
- **operations**: Functions for data operations and transformations
- **moving_averages**: Functions for moving averages and rolling calculations
- **risk_analysis**: Functions for risk analysis and financial metrics
- **funnel_analysis**: Functions for funnel and conversion analysis
- **trend_analysis**: Functions for trend analysis and forecasting
- **group_aggregation**: Functions for group-based aggregation operations

## Search Capabilities

### Semantic Search

The registry uses semantic search to find functions based on natural language queries:

```python
# These queries will find relevant functions
queries = [
    "detect outliers in my data",
    "forecast sales trends",
    "segment customers by behavior",
    "calculate moving averages",
    "analyze cohort retention"
]

for query in queries:
    results = service.search_functions_for_agent(query)
    print(f"'{query}': {len(results)} results")
```

### Filtering

You can filter results by various criteria:

```python
# Filter by category
results = service.search_functions_for_agent(
    "statistical analysis",
    category="anomaly_detection"
)

# Filter by complexity
results = service.search_functions_for_agent(
    "basic statistics",
    complexity="simple"
)

# Filter by tags
results = service.search_functions_for_agent(
    "time series analysis",
    tags=["time_series", "forecasting"]
)
```

## Integration with ML Agents

The function registry is designed to integrate seamlessly with ML agents:

```python
from app.tools.mltools.registry import create_function_retrieval_service

class MLAgent:
    def __init__(self):
        self.function_service = create_function_retrieval_service("./chroma_db")
    
    def find_relevant_functions(self, task_description, data_context):
        """Find functions relevant to the agent's task."""
        return self.function_service.search_functions_for_agent(
            task_description,
            context=data_context,
            max_results=5
        )
    
    def get_function_details(self, function_name):
        """Get detailed information about a function."""
        return self.function_service.get_function_by_name(function_name)
```

## Export and Reporting

### Export Function Catalog

```python
# Export to JSON
results = service.search_functions_for_agent("all functions")
catalog = service.export_search_results(results, format="json")

# Export to Markdown
catalog = service.export_search_results(results, format="markdown")
```

### Get Statistics

```python
# Get search statistics
stats = service.get_search_statistics()
print(f"Total searches: {stats['total_searches']}")
print(f"Most common queries: {stats['most_common_queries']}")
```

## API Reference

### FunctionRetrievalService

Main service class for function retrieval.

#### Methods

- `search_functions_for_agent(query, context=None, max_results=5)`: Search for functions with agent context
- `get_function_by_name(function_name)`: Get detailed function information
- `get_functions_by_category(category)`: Get all functions in a category
- `get_function_recommendations(function_name, max_recommendations=5)`: Get function recommendations
- `search_functions_by_use_case(use_case)`: Search by use case
- `get_available_categories()`: Get list of available categories
- `get_service_status()`: Get service status information

### FunctionSearchInterface

High-level search interface with advanced filtering.

#### Methods

- `search_functions(query, n_results=5, category=None, complexity=None, tags=None)`: Advanced search
- `find_functions_by_use_case(use_case)`: Find functions by use case
- `get_function_recommendations(function_name, n_recommendations=5)`: Get recommendations
- `get_functions_by_data_requirements(data_columns)`: Find functions by data requirements
- `export_search_results(results, format='json')`: Export results

### MLFunctionRegistry

Core registry for function metadata management.

#### Methods

- `register_function(func, module_name)`: Register a single function
- `register_module_functions(module)`: Register all functions from a module
- `search_functions(query, n_results=5, category=None)`: Search functions
- `get_function_by_name(function_name)`: Get function metadata
- `get_functions_by_category(category)`: Get functions by category
- `get_function_statistics()`: Get registry statistics

## Troubleshooting

### Common Issues

1. **Service not initialized**: Make sure to run the initialization script first
2. **No search results**: Check if functions are properly registered
3. **ChromaDB connection errors**: Verify ChromaDB is properly installed and accessible

### Debug Mode

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check service status
service = create_function_retrieval_service("./chroma_db")
status = service.get_service_status()
print(json.dumps(status, indent=2))
```

## Contributing

To add new functions to the registry:

1. Ensure your function has proper docstrings
2. Use descriptive parameter names
3. Include examples in the docstring
4. The registry will automatically extract metadata

## License

This function registry system is part of the ML tools package and follows the same license terms.
