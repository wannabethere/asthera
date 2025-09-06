# Enhanced Function Retrieval Service

## Overview

The `EnhancedFunctionRetrieval` service is a dedicated module that provides efficient and accurate function matching for analysis steps. It was created to improve separation of responsibilities and provide better function selection capabilities compared to the previous approach.

## Architecture

### Key Components

1. **EnhancedFunctionRetrieval**: Main service class that orchestrates function retrieval and matching
2. **FunctionMatch**: Data model for individual function matches
3. **StepFunctionMatch**: Data model for step-function matching results
4. **EnhancedFunctionRetrievalResult**: Comprehensive result model with metrics and metadata

### Service Flow

```
1. Input: Reasoning Plan + Context
   ↓
2. ChromaDB Function Retrieval
   - Batch retrieval using comprehensive context
   - Multiple search strategies
   - Duplicate removal
   ↓
3. LLM-Based Function Matching
   - Single LLM call for all step matching
   - Contextual reasoning
   - Relevance scoring
   ↓
4. Result Generation
   - Metrics calculation
   - Confidence scoring
   - Fallback handling
```

## Features

### 1. **Efficient ChromaDB Integration**
- **Batch Retrieval**: Fetches multiple relevant functions in a single operation
- **Context-Aware Queries**: Uses reasoning plan context for targeted searches
- **Multiple Search Strategies**: Implements comprehensive, rephrased, plan context, and original question searches
- **Duplicate Removal**: Ensures unique function results

### 2. **LLM-Based Step Matching**
- **Intelligent Assignment**: Uses LLM to match functions to specific analysis steps
- **Contextual Reasoning**: Considers step requirements and data needs
- **Single LLM Call**: Efficient processing with one comprehensive call
- **Structured Output**: Returns JSON-formatted step-function mappings

### 3. **Robust Error Handling**
- **Fallback Mechanisms**: Keyword-based matching when LLM fails
- **Graceful Degradation**: Continues operation even with partial failures
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Error Recovery**: Multiple strategies for different failure scenarios

### 4. **Performance Optimization**
- **Reduced LLM Calls**: From N calls (one per step) to 1 call
- **Efficient Caching**: Leverages existing caching mechanisms
- **Resource Optimization**: Better utilization of computational resources
- **Scalability**: Handles complex analysis plans efficiently

## Usage

### Basic Usage

```python
from app.agents.nodes.mlagents.enhanced_function_retrieval import EnhancedFunctionRetrieval

# Initialize the service
enhanced_retrieval = EnhancedFunctionRetrieval(
    llm=your_llm_instance,
    retrieval_helper=your_retrieval_helper
)

# Retrieve and match functions
result = await enhanced_retrieval.retrieve_and_match_functions(
    reasoning_plan=reasoning_plan,
    question="Calculate rolling variance",
    rephrased_question="Calculate rolling variance of flux values over 5-day windows",
    dataframe_description="Financial transaction data",
    dataframe_summary="Transaction summary",
    available_columns=["Transactional value", "Project", "Cost center", "Department", "Date"],
    project_id="project_123"
)

# Access results
print(f"Retrieved {result.total_functions_retrieved} functions")
print(f"Matched to {result.total_steps_covered} steps")
print(f"Average relevance: {result.average_relevance_score:.2f}")
print(f"Confidence score: {result.confidence_score:.2f}")

# Access step matches
for step_num, functions in result.step_matches.items():
    print(f"Step {step_num}: {len(functions)} functions")
    for func in functions:
        print(f"  - {func['function_name']} (relevance: {func['relevance_score']:.2f})")
```

### Integration with Analysis Intent Classification

The enhanced function retrieval service is automatically used by the `AnalysisIntentClassifier`:

```python
# The classifier automatically uses the enhanced service
classifier = AnalysisIntentClassifier(llm=llm)

result = await classifier.analyze_intent_and_plan(
    question="Calculate rolling variance of flux values over 5-day windows",
    available_columns=["Transactional value", "Project", "Cost center", "Department", "Date"],
    dataframe_description="Financial transaction data",
    project_id="project_123"
)

# Enhanced metrics are included in the result
enhanced_metrics = result.get("enhanced_retrieval_metrics", {})
print(f"Enhanced retrieval used: {enhanced_metrics.get('fallback_used', False)}")
```

## API Reference

### EnhancedFunctionRetrieval

#### `__init__(llm, retrieval_helper=None)`
Initialize the enhanced function retrieval service.

**Parameters:**
- `llm`: LangChain LLM instance
- `retrieval_helper`: RetrievalHelper instance (optional)

#### `retrieve_and_match_functions(...)`
Main method to retrieve and match functions to analysis steps.

**Parameters:**
- `reasoning_plan`: List of reasoning plan steps from Step 1
- `question`: Original user question
- `rephrased_question`: Rephrased question from Step 1
- `dataframe_description`: Description of the dataframe
- `dataframe_summary`: Summary of the dataframe
- `available_columns`: List of available columns
- `project_id`: Optional project ID

**Returns:**
- `EnhancedFunctionRetrievalResult` with comprehensive matching results

### EnhancedFunctionRetrievalResult

#### Properties:
- `step_matches`: Dictionary mapping step numbers to matched functions
- `total_functions_retrieved`: Total number of functions retrieved from ChromaDB
- `total_steps_covered`: Number of steps with function matches
- `average_relevance_score`: Average relevance score across all matches
- `confidence_score`: Overall confidence in the matching results
- `reasoning`: Human-readable reasoning for the results
- `fallback_used`: Whether fallback matching was used

## Configuration

The enhanced function retrieval service uses the same configuration as the existing system:

- **ChromaDB Settings**: Configured through the RetrievalHelper
- **LLM Settings**: Uses the same LLM instance as the rest of the system
- **Caching**: Leverages existing caching mechanisms for performance

## Testing

Comprehensive tests are included in `test_enhanced_function_retrieval_service.py`:

- **Unit Tests**: Test individual components (ChromaDB fetching, LLM matching, fallback mechanisms)
- **Integration Tests**: Test the complete retrieval and matching process
- **Error Handling Tests**: Test various failure scenarios and fallback mechanisms
- **Mock Testing**: Uses mocked dependencies for reliable testing

## Migration from Previous Approach

### Benefits of Migration

1. **Better Separation of Concerns**: Function retrieval logic is now isolated in its own service
2. **Improved Maintainability**: Easier to modify and extend function retrieval capabilities
3. **Enhanced Performance**: More efficient processing with reduced LLM calls
4. **Better Error Handling**: More robust error handling and fallback mechanisms
5. **Comprehensive Metrics**: Detailed metrics for monitoring and optimization

### Backward Compatibility

The enhanced function retrieval service is fully backward compatible. The `AnalysisIntentClassifier` automatically uses the new service without requiring changes to existing code.

### Migration Steps

1. **Automatic Migration**: The new service is automatically used by the classifier
2. **No Code Changes**: Existing code continues to work without modification
3. **Enhanced Results**: Results now include additional metrics and improved accuracy
4. **Optional Configuration**: Can be configured independently if needed

## Performance Comparison

### Before (Old Approach)
- **LLM Calls**: N calls (one per step)
- **ChromaDB Queries**: Individual queries per step
- **Processing Time**: Slower due to multiple sequential operations
- **Accuracy**: Lower due to simple keyword matching

### After (Enhanced Approach)
- **LLM Calls**: 1 call (comprehensive matching)
- **ChromaDB Queries**: Batch queries with multiple strategies
- **Processing Time**: Faster due to optimized operations
- **Accuracy**: Higher due to contextual LLM matching

## Future Enhancements

1. **Advanced Caching**: Implement more sophisticated caching strategies
2. **Parallel Processing**: Further optimize for parallel function retrieval
3. **Learning from Feedback**: Incorporate user feedback to improve matching accuracy
4. **Dynamic Thresholds**: Adjust similarity thresholds based on query complexity
5. **Custom Matching Algorithms**: Support for custom matching strategies
6. **Performance Monitoring**: Enhanced metrics and monitoring capabilities
