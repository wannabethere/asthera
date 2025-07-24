# Function Retrieval System

## Overview

The `FunctionRetrieval` class is designed to identify the most relevant analysis functions for user questions by reading the `all_pipes_functions.json` file and using LLMs to match user queries with appropriate functions. It returns the top 5 most relevant functions along with a rephrased question optimized for ChromaDB querying.

## Features

- **Semantic Function Matching**: Uses LLMs to understand user questions and match them with relevant functions
- **Comprehensive Function Library**: Reads from `all_pipes_functions.json` containing 150+ analysis functions
- **Rephrased Questions**: Generates optimized questions for ChromaDB function definition lookup
- **Relevance Scoring**: Provides confidence scores and reasoning for each function match
- **Pipeline Suggestions**: Recommends which analysis pipelines might be most useful
- **Utility Methods**: Includes helper methods for exploring the function library

## Installation and Setup

### Prerequisites

```bash
pip install langchain langfuse pydantic
```

### File Structure

```
genieml/
├── data/
│   └── meta/
│       └── all_pipes_functions.json  # Function library
└── insightsagents/
    └── app/
        └── agents/
            └── nodes/
                └── mlagents/
                    ├── function_retrieval.py           # Main class
                    ├── example_function_retrieval.py   # Usage examples
                    └── README_function_retrieval.md    # This file
```

## Usage

### Basic Usage

```python
import asyncio
from function_retrieval import FunctionRetrieval

# Initialize with your LLM
retrieval = FunctionRetrieval(llm=your_llm)

# Retrieve relevant functions
result = await retrieval.retrieve_relevant_functions(
    question="How does the 5-day rolling variance of flux change over time?",
    dataframe_description="Financial metrics dataset with project performance data",
    dataframe_summary="Contains 10,000 rows with daily metrics from 2023-2024",
    available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"]
)

# Access results
print(f"Rephrased Question: {result.rephrased_question}")
print(f"Confidence Score: {result.confidence_score}")
print(f"Top Functions: {[f.function_name for f in result.top_functions]}")
```

### Advanced Usage with Custom Function Library Path

```python
# Specify custom path to function library
retrieval = FunctionRetrieval(
    llm=your_llm,
    function_library_path="/path/to/your/all_pipes_functions.json"
)
```

## API Reference

### FunctionRetrieval Class

#### Constructor

```python
FunctionRetrieval(llm, function_library_path: Optional[str] = None)
```

**Parameters:**
- `llm`: LangChain LLM instance for function matching
- `function_library_path`: Optional path to the function library JSON file

#### Main Methods

##### `retrieve_relevant_functions()`

```python
async def retrieve_relevant_functions(
    self,
    question: str,
    dataframe_description: str = "",
    dataframe_summary: str = "",
    available_columns: Optional[List[str]] = None
) -> FunctionRetrievalResult
```

**Parameters:**
- `question`: User's natural language question
- `dataframe_description`: Description of the dataframe
- `dataframe_summary`: Summary of the dataframe
- `available_columns`: List of available columns in the dataframe

**Returns:**
- `FunctionRetrievalResult` object containing:
  - `top_functions`: List of top 5 relevant functions
  - `rephrased_question`: Optimized question for ChromaDB querying
  - `confidence_score`: Overall confidence in the function selection
  - `reasoning`: Explanation of the function selection
  - `suggested_pipes`: Recommended analysis pipelines
  - `total_functions_analyzed`: Total number of functions considered

#### Utility Methods

##### `get_function_details()`

```python
def get_function_details(self, function_name: str, pipe_name: str) -> Optional[Dict[str, Any]]
```

Get detailed information about a specific function.

##### `get_pipe_functions()`

```python
def get_pipe_functions(self, pipe_name: str) -> List[str]
```

Get all functions in a specific pipe.

##### `get_all_pipes()`

```python
def get_all_pipes(self) -> List[str]
```

Get all available pipe names.

##### `search_functions_by_keyword()`

```python
def search_functions_by_keyword(self, keyword: str) -> List[Tuple[str, str, Dict[str, Any]]]
```

Search for functions by keyword in their descriptions.

## Data Models

### FunctionMatch

```python
class FunctionMatch(BaseModel):
    function_name: str
    pipe_name: str
    description: str
    usage_description: str
    relevance_score: float
    reasoning: str
```

### FunctionRetrievalResult

```python
class FunctionRetrievalResult(BaseModel):
    top_functions: List[FunctionMatch]
    rephrased_question: str
    confidence_score: float
    reasoning: str
    suggested_pipes: List[str]
    total_functions_analyzed: int
```

## Function Library Structure

The `all_pipes_functions.json` file contains the following structure:

```json
{
  "PipeName": {
    "description": "Pipe description",
    "functions": {
      "function_name": {
        "description": "Function description",
        "usage_description": "Detailed usage description"
      }
    }
  }
}
```

### Available Pipes

- **CohortPipe**: Time-based and behavioral cohort analysis
- **FunnelPipe**: User funnel analysis
- **KMeansPipe**: K-means clustering
- **MovingAggrPipe**: Moving window and expanding window metrics
- **OperationsPipe**: Statistical and comparison operations
- **MetricsPipe**: Basic, derived, and statistical metrics
- **TrendPipe**: Trend analysis and forecasting
- **AnomalyPipe**: Anomaly and outlier detection
- **DistributionPipe**: Distribution analysis for time series data

## Examples

### Example 1: Variance Analysis

```python
question = "How does the 5-day rolling variance of flux change over time?"
result = await retrieval.retrieve_relevant_functions(question)

# Expected output:
# - variance_analysis (MovingAggrPipe)
# - moving_variance (MovingAggrPipe)
# - aggregate_by_time (TrendPipe)
# Rephrased: "Calculate 5-day rolling variance of flux metric over time"
```

### Example 2: Anomaly Detection

```python
question = "Detect anomalies in my dataset"
result = await retrieval.retrieve_relevant_functions(question)

# Expected output:
# - detect_statistical_outliers (AnomalyPipe)
# - detect_contextual_anomalies (AnomalyPipe)
# - detect_collective_anomalies (AnomalyPipe)
# Rephrased: "Detect statistical outliers in the dataset"
```

### Example 3: Cohort Analysis

```python
question = "Show me user retention over time"
result = await retrieval.retrieve_relevant_functions(question)

# Expected output:
# - calculate_retention (CohortPipe)
# - form_time_cohorts (CohortPipe)
# - calculate_conversion (CohortPipe)
# Rephrased: "Calculate user retention rates for different cohorts over time"
```

## Integration with ChromaDB

The rephrased question returned by the function is optimized for semantic search in ChromaDB:

```python
# Use the rephrased question to query ChromaDB
rephrased_question = result.rephrased_question

# Query ChromaDB for function definitions
chroma_results = chroma_collection.semantic_searches(
    query_texts=[rephrased_question],
    n_results=5
)
```

## Error Handling

The system includes comprehensive error handling:

- **File Loading Errors**: Graceful fallback if function library can't be loaded
- **LLM Errors**: Fallback responses when LLM calls fail
- **JSON Parsing Errors**: Robust parsing with error recovery
- **Missing Data**: Default values for missing fields

## Performance Considerations

- **Function Library Caching**: The function library is loaded once and cached
- **LLM Optimization**: Efficient prompt formatting to minimize token usage
- **Async Support**: Full async/await support for non-blocking operations
- **Memory Efficient**: Processes functions in batches to manage memory usage

## Testing

Run the example script to test the functionality:

```bash
cd genieml/insightsagents/app/agents/nodes/mlagents/
python example_function_retrieval.py
```

## Contributing

To add new functions to the system:

1. Update the `all_pipes_functions.json` file with new function definitions
2. Ensure proper descriptions and usage descriptions are provided
3. Test the function retrieval with relevant questions
4. Update documentation if needed

## Troubleshooting

### Common Issues

1. **Function Library Not Found**: Check the path to `all_pipes_functions.json`
2. **LLM Connection Issues**: Verify your LLM configuration
3. **Low Relevance Scores**: Ensure your question is specific and clear
4. **No Functions Returned**: Check if the function library is properly loaded

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger("function-retrieval").setLevel(logging.DEBUG)
```

## License

This code is part of the GenieML project and follows the same licensing terms. 