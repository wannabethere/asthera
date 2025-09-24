# Comprehensive ML Function Registry

This enhanced function registry system integrates comprehensive function data including examples, usage patterns, code snippets, and instructions for better code generation. It combines data from multiple JSON sources to create rich function metadata stored in ChromaDB.

## Features

- **Comprehensive Data Integration**: Combines function specifications, examples, usage patterns, code snippets, and instructions
- **Rich Metadata Storage**: Stores detailed function information in ChromaDB for semantic search
- **Enhanced Search Capabilities**: Supports semantic search with filtering by category, complexity, and content type
- **Code Generation Support**: Provides comprehensive examples and instructions for better code generation
- **Flexible Query Interface**: Supports various search patterns including use case and data requirement matching

## Architecture

### Components

1. **ComprehensiveFunctionLoader**: Loads and combines data from multiple JSON sources
2. **EnhancedComprehensiveRegistry**: Main registry class that manages function data and search
3. **ComprehensiveFunctionData**: Data structure for comprehensive function information
4. **Initialization Scripts**: Scripts to populate ChromaDB with comprehensive data

### Data Sources

- **Function Specifications** (`toolspecs/`): Function definitions, parameters, and metadata
- **Instructions** (`instructions/`): Business cases, natural language questions, and configuration hints
- **Usage Examples** (`usage_examples/`): Code examples and usage patterns
- **Code Examples** (`code_examples/`): Additional code snippets and examples

## Usage

### Initialization

```python
import chromadb
from app.tools.mltools.registry.enhanced_comprehensive_registry import initialize_enhanced_comprehensive_registry

# Initialize ChromaDB client
client = chromadb.PersistentClient(path="./chroma_db")

# Initialize comprehensive registry
registry = initialize_enhanced_comprehensive_registry(
    chroma_client=client,
    collection_name="comprehensive_ml_functions",
    force_recreate=True
)
```

### Search Functions

```python
# Basic search
results = registry.search_functions("detect anomalies in time series data", n_results=5)

# Search with filters
results = registry.search_functions(
    "customer segmentation",
    category="segmentation_analysis",
    complexity="intermediate",
    has_examples=True,
    n_results=3
)

# Use case search
results = registry.search_by_use_case("anomaly detection in sensor data", n_results=5)

# Data requirement search
results = registry.search_by_data_requirements(["date", "value", "category"], n_results=5)
```

### Retrieve Function Details

```python
# Get comprehensive function data
function_data = registry.get_function_by_name("detect_statistical_outliers")

if function_data:
    print(f"Function: {function_data['function_name']}")
    print(f"Category: {function_data['category']}")
    print(f"Examples: {function_data['examples_count']}")
    print(f"Instructions: {function_data['instructions_count']}")
    print(f"Code snippets: {function_data['code_snippets_count']}")
    print(f"Business cases: {function_data['business_cases']}")
    print(f"Use cases: {function_data['use_cases']}")
```

### Filter by Category or Complexity

```python
# Get functions by category
anomaly_functions = registry.get_functions_by_category("anomaly_detection")

# Get functions by complexity
simple_functions = registry.get_functions_by_complexity("simple")

# Get functions with examples
functions_with_examples = registry.get_functions_with_examples()

# Get functions with instructions
functions_with_instructions = registry.get_functions_with_instructions()
```

## Data Structure

### ComprehensiveFunctionData

Each function is represented by a `ComprehensiveFunctionData` object containing:

- **Basic Info**: name, pipe_name, module, category, description, complexity
- **Parameters**: required_params, optional_params, outputs, data_requirements
- **Metadata**: tags, keywords, use_cases, confidence_score
- **Code**: source_code, function_signature, docstring
- **Examples**: examples, code_snippets, usage_patterns
- **Instructions**: instructions, business_cases, natural_language_questions
- **Configuration**: configuration_hints, typical_parameters
- **Historical Data**: historical_rules, insights, examples_store

### Search Results

Search results include:

- Function metadata (name, category, complexity, etc.)
- Content counts (examples, instructions, code snippets)
- Relevance score
- Full function data for detailed analysis

## Command Line Interface

### Initialize Registry

```bash
python -m app.tools.mltools.registry.initialize_comprehensive_registry \
    --chroma-path ./chroma_db \
    --collection-name comprehensive_ml_functions \
    --force-recreate
```

### Run Tests

```bash
python -m app.tools.mltools.registry.test_comprehensive_registry
```

### Export Catalog

```bash
python -m app.tools.mltools.registry.initialize_comprehensive_registry \
    --export \
    --output-file comprehensive_function_catalog.json
```

## Configuration

### Paths

The registry can be configured with custom paths for data sources:

```python
registry = initialize_enhanced_comprehensive_registry(
    chroma_client=client,
    toolspecs_path="/path/to/toolspecs",
    instructions_path="/path/to/instructions",
    usage_examples_path="/path/to/usage_examples",
    code_examples_path="/path/to/code_examples"
)
```

### ChromaDB Settings

The registry uses ChromaDB for vector storage with the following settings:

- **Collection**: `comprehensive_ml_functions` (configurable)
- **TF-IDF**: Enabled for better text search
- **Persistent Storage**: Uses persistent client for data persistence

## Examples

### Finding Anomaly Detection Functions

```python
# Search for anomaly detection functions
results = registry.search_functions("detect anomalies", n_results=5)

for result in results:
    print(f"Function: {result['function_name']}")
    print(f"Category: {result['category']}")
    print(f"Examples: {result['examples_count']}")
    print(f"Business cases: {result['business_cases']}")
    print("---")
```

### Getting Function with Complete Context

```python
# Get comprehensive function data
func_data = registry.get_function_by_name("detect_statistical_outliers")

if func_data:
    # Access examples
    for example in func_data['examples']:
        print(f"Example: {example['content']}")
        print(f"Query: {example['query']}")
    
    # Access business cases
    for case in func_data['business_cases']:
        print(f"Business case: {case}")
    
    # Access configuration hints
    for param, hint in func_data['configuration_hints'].items():
        print(f"{param}: {hint}")
```

### Use Case-Based Search

```python
# Find functions for specific use cases
use_cases = [
    "anomaly detection in sensor data",
    "customer behavior segmentation",
    "sales forecasting with seasonality"
]

for use_case in use_cases:
    results = registry.search_by_use_case(use_case, n_results=3)
    print(f"Use case: {use_case}")
    print(f"Found {len(results)} functions")
    for result in results:
        print(f"  - {result['function_name']} ({result['category']})")
```

## Benefits

1. **Rich Context**: Functions include comprehensive examples, instructions, and usage patterns
2. **Better Code Generation**: Detailed examples and instructions improve code generation quality
3. **Flexible Search**: Multiple search patterns and filtering options
4. **Semantic Understanding**: ChromaDB enables semantic search across function descriptions
5. **Comprehensive Metadata**: Rich metadata supports various use cases and filtering
6. **Extensible**: Easy to add new data sources and enhance existing functionality

## Performance

- **Initialization**: ~30-60 seconds for full dataset (depending on data size)
- **Search**: <100ms for typical queries
- **Memory Usage**: ~100-200MB for typical dataset
- **Storage**: ~50-100MB ChromaDB storage for typical dataset

## Troubleshooting

### Common Issues

1. **Path Not Found**: Ensure all data source paths exist and contain valid JSON files
2. **ChromaDB Errors**: Check ChromaDB client initialization and collection permissions
3. **Memory Issues**: For large datasets, consider processing in batches
4. **Search Results Empty**: Verify data is properly loaded and indexed

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- **LLM Integration**: Use LLM to generate additional examples and instructions
- **Dynamic Updates**: Support for real-time updates to function data
- **Performance Optimization**: Caching and indexing improvements
- **Advanced Filtering**: More sophisticated filtering options
- **API Interface**: REST API for remote access
- **Visualization**: Web interface for exploring function data
