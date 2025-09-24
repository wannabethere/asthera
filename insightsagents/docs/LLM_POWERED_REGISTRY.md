# LLM-Powered Function Registry

## Overview

The ML Function Registry has been enhanced with LLM (Large Language Model) integration to replace hardcoded mappings with intelligent, dynamic function identification. This system uses AI to analyze function definitions, generate metadata, and provide semantic matching capabilities.

## Key Features

### 🤖 **LLM-Powered Metadata Generation**
- **Dynamic Analysis**: Functions are analyzed using LLM to extract comprehensive metadata
- **Intelligent Categorization**: Categories are determined by AI analysis instead of hardcoded rules
- **Semantic Understanding**: LLM understands function purpose, use cases, and data requirements
- **Confidence Scoring**: Each analysis includes a confidence score for reliability

### 🔍 **Semantic Function Matching**
- **Natural Language Queries**: Find functions using natural language descriptions
- **Context-Aware Search**: Search considers user context and data requirements
- **Dynamic Use Case Mapping**: Use cases are identified and mapped dynamically
- **Intelligent Recommendations**: Get function recommendations based on semantic similarity

### 📊 **Dynamic Mappings**
- **No Hardcoding**: All mappings are generated dynamically by LLM
- **Scalable**: New functions are automatically analyzed and categorized
- **Adaptive**: System learns and improves with new function additions
- **Maintainable**: No need to update code when adding new tools

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM-Powered Registry                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │   LLM Metadata  │  │  Dynamic        │  │  Enhanced   │  │
│  │   Generator     │  │  Function       │  │  Registry   │  │
│  │                 │  │  Matcher        │  │             │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
│           │                     │                   │        │
│           └─────────────────────┼───────────────────┘        │
│                                 │                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              ChromaDB Vector Store                     │  │
│  │         (Function Definitions + Metadata)              │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. LLM Metadata Generator (`llm_metadata_generator.py`)

**Purpose**: Generates comprehensive metadata for functions using LLM analysis.

**Key Classes**:
- `LLMMetadataGenerator`: Main class for generating function metadata
- `DynamicFunctionMatcher`: Matches functions to queries using LLM
- `LLMGeneratedMetadata`: Data structure for LLM-generated metadata

**Features**:
- Function analysis with confidence scoring
- Dynamic category classification
- Use case identification
- Data requirement extraction
- Related function suggestions

### 2. Enhanced Function Registry (`enhanced_function_registry.py`)

**Purpose**: Enhanced registry that uses LLM-generated metadata instead of hardcoded mappings.

**Key Classes**:
- `EnhancedMLFunctionRegistry`: Main registry with LLM integration
- `EnhancedFunctionMetadata`: Enhanced metadata structure

**Features**:
- LLM-powered function registration
- Dynamic category generation
- Semantic search capabilities
- Use case and data requirement mapping

### 3. Updated Search Interface

**Purpose**: Enhanced search interface that uses LLM for semantic matching.

**Key Updates**:
- Replaced hardcoded use case mappings with LLM matching
- Dynamic data requirement matching
- Context-aware search capabilities
- Intelligent function recommendations

## Usage Examples

### Basic Setup

```python
from app.tools.mltools.registry import create_function_retrieval_service

# Create service with LLM integration
service = create_function_retrieval_service(
    chroma_path="./chroma_db",
    llm_model="gpt-3.5-turbo"
)
```

### Semantic Search

```python
# Natural language queries work automatically
results = service.search_functions_for_agent(
    "I need to detect anomalies in my time series data",
    context={
        "data_columns": ["timestamp", "value", "region"],
        "task_type": "anomaly_detection"
    }
)

for result in results:
    print(f"{result['function_name']}: {result['description']}")
    print(f"Relevance Score: {result['relevance_score']:.3f}")
```

### Dynamic Use Case Matching

```python
# Use cases are identified dynamically by LLM
use_cases = [
    "detect outliers in sensor data",
    "forecast sales for next quarter",
    "segment customers by behavior",
    "analyze cohort retention"
]

for use_case in use_cases:
    results = service.search_functions_by_use_case(use_case)
    print(f"{use_case}: {len(results)} functions found")
```

### Data Requirement Matching

```python
# Functions are matched based on available data columns
data_columns = ["user_id", "purchase_amount", "category", "date"]
results = service.search_functions_by_data_requirements(data_columns)

for result in results:
    print(f"{result['function_name']}: {result['description']}")
    print(f"Data Requirements: {result['data_requirements']}")
```

## Initialization

### Command Line

```bash
# Initialize enhanced registry with LLM
python -m app.tools.mltools.registry.initialize_enhanced_registry \
    --chroma-path ./chroma_db \
    --llm-model gpt-3.5-turbo \
    --force-recreate

# Run tests
python -m app.tools.mltools.registry.initialize_enhanced_registry --test

# Export catalog
python -m app.tools.mltools.registry.initialize_enhanced_registry \
    --export \
    --output-file enhanced_catalog.json
```

### Programmatic

```python
import chromadb
from app.tools.mltools.registry import initialize_enhanced_function_registry

# Initialize ChromaDB client
client = chromadb.PersistentClient(path="./chroma_db")

# Initialize enhanced registry
registry = initialize_enhanced_function_registry(client, "gpt-3.5-turbo")

# Get statistics
stats = registry.get_function_statistics()
print(f"Total functions: {stats['total_functions']}")
print(f"LLM generated: {stats['llm_generated_functions']}")
```

## LLM Integration Details

### Metadata Generation Process

1. **Function Analysis**: LLM analyzes function signature, docstring, and source code
2. **Category Classification**: AI determines appropriate category and subcategory
3. **Use Case Identification**: LLM identifies specific use cases for the function
4. **Data Requirements**: AI extracts data requirements from function analysis
5. **Confidence Scoring**: LLM provides confidence score for the analysis

### Semantic Matching Process

1. **Query Analysis**: LLM analyzes user query and context
2. **Function Comparison**: AI compares query against available functions
3. **Relevance Scoring**: LLM scores relevance of each function
4. **Reasoning**: AI provides reasoning for each recommendation

### Dynamic Mappings

- **Categories**: Generated dynamically based on function analysis
- **Use Cases**: Identified and mapped automatically by LLM
- **Data Requirements**: Extracted from function signatures and docstrings
- **Keywords**: Generated based on function purpose and implementation

## Benefits

### 🚀 **Scalability**
- **No Code Updates**: Adding new functions doesn't require code changes
- **Automatic Analysis**: New functions are automatically analyzed and categorized
- **Dynamic Adaptation**: System adapts to new function types automatically

### 🎯 **Accuracy**
- **Semantic Understanding**: LLM understands function purpose and context
- **Intelligent Matching**: Better function recommendations based on AI analysis
- **Context Awareness**: Search considers user context and requirements

### 🔧 **Maintainability**
- **No Hardcoding**: Eliminates need for hardcoded mappings
- **Self-Updating**: System updates itself as new functions are added
- **Reduced Maintenance**: Less manual maintenance required

### 📈 **Extensibility**
- **Easy Integration**: New tools can be added without code changes
- **Flexible Categorization**: Categories adapt to new function types
- **Dynamic Mappings**: All mappings are generated automatically

## Configuration

### LLM Model Selection

```python
# Use different LLM models
service = create_function_retrieval_service(
    chroma_path="./chroma_db",
    llm_model="gpt-4"  # or "gpt-3.5-turbo", "claude-3", etc.
)
```

### Temperature Settings

```python
# Adjust creativity vs consistency
metadata_generator = create_llm_metadata_generator(
    llm_model="gpt-3.5-turbo",
    temperature=0.1  # Lower = more consistent, Higher = more creative
)
```

## Testing

### Run Test Suite

```bash
# Run comprehensive LLM registry tests
python insightsagents/tests/mltools/test_llm_function_registry.py
```

### Test Components

```python
# Test individual components
from app.tools.mltools.registry import create_llm_metadata_generator

# Test metadata generation
generator = create_llm_metadata_generator("gpt-3.5-turbo")
metadata = generator.generate_function_metadata(your_function, "module_name")
print(f"Category: {metadata.category}")
print(f"Confidence: {metadata.confidence_score}")
```

## Migration from Hardcoded System

### Backward Compatibility

The enhanced system maintains backward compatibility:

```python
# Old way still works
from app.tools.mltools import create_function_retrieval_service

# New way with LLM integration
from app.tools.mltools.registry import create_function_retrieval_service
```

### Gradual Migration

1. **Phase 1**: Deploy enhanced system alongside existing system
2. **Phase 2**: Test with subset of functions
3. **Phase 3**: Migrate all functions to enhanced system
4. **Phase 4**: Remove hardcoded mappings

## Performance Considerations

### LLM API Costs

- **Caching**: Function metadata is cached to avoid repeated LLM calls
- **Batch Processing**: Multiple functions can be processed in batches
- **Selective Analysis**: Only new functions require LLM analysis

### Response Times

- **Cached Results**: Previously analyzed functions return instantly
- **Parallel Processing**: Multiple functions can be analyzed in parallel
- **Optimized Prompts**: Prompts are optimized for speed and accuracy

## Troubleshooting

### Common Issues

1. **LLM API Errors**: Check API key and rate limits
2. **Low Confidence Scores**: Review function docstrings and source code
3. **Poor Matching**: Adjust temperature or try different LLM model
4. **Memory Issues**: Clear cache or reduce batch sizes

### Debug Mode

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check cache statistics
generator = create_llm_metadata_generator()
stats = generator.get_cache_stats()
print(f"Cached functions: {stats['cached_functions']}")
```

## Future Enhancements

### Planned Features

1. **Multi-Model Support**: Support for multiple LLM providers
2. **Fine-Tuning**: Custom models trained on function data
3. **Feedback Loop**: Learn from user interactions
4. **Advanced Analytics**: Detailed usage and performance metrics

### Extension Points

1. **Custom Analyzers**: Add custom function analyzers
2. **Domain-Specific Models**: Specialized models for different domains
3. **Integration Hooks**: Custom integration points
4. **Plugin System**: Extensible plugin architecture

## Conclusion

The LLM-powered function registry represents a significant advancement in function discovery and management. By replacing hardcoded mappings with intelligent AI analysis, the system becomes more scalable, accurate, and maintainable. This approach ensures that as new tools and functions are added, the system automatically adapts and provides better recommendations without requiring manual updates.
