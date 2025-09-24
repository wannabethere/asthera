# Enhanced Function Retrieval System

## Overview

The Enhanced Function Retrieval System has been significantly improved to attach specific examples, instructions, and examples store data for every retrieved function. This enrichment provides LLMs with comprehensive context to make better decisions when generating functions or code.

## Key Enhancements

### 1. Enriched FunctionMatch Model

The `FunctionMatch` model now includes additional fields for rich context:

```python
class FunctionMatch(BaseModel):
    function_name: str
    pipe_name: str
    description: str
    usage_description: str
    relevance_score: float
    reasoning: str
    category: str = "unknown"
    function_definition: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None           # NEW
    instructions: Optional[List[Dict[str, Any]]] = None       # NEW
    examples_store: Optional[List[Dict[str, Any]]] = None     # NEW
    historical_rules: Optional[List[Dict[str, Any]]] = None   # NEW
```

### 2. Context Enrichment Process

For every retrieved function, the system now:

1. **Retrieves Examples** from `usage_examples_collection`
   - Real-world usage examples
   - Parameter configurations
   - Code snippets and patterns

2. **Retrieves Instructions** from `instructions_collection`
   - Project-specific guidance
   - Best practices
   - Custom rules and conventions

3. **Retrieves Examples Store** from `tools_insights_collection`
   - Historical patterns
   - Performance insights
   - Domain-specific knowledge

4. **Generates Historical Rules** from examples store
   - Pattern recognition from past implementations
   - Hardcoded rules based on function type
   - Best practice guidelines

### 3. Enhanced LLM Prompts

The LLM prompts now include:

- **Function descriptions** with examples
- **Instructions** for project-specific guidance
- **Historical rules** for better decision making
- **Examples store** data for pattern recognition

## Usage Examples

### Basic Function Retrieval

```python
from app.agents.nodes.mlagents.enhanced_function_retrieval import EnhancedFunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper

# Initialize
retrieval_helper = RetrievalHelper()
enhanced_retrieval = EnhancedFunctionRetrieval(
    llm=your_llm,
    retrieval_helper=retrieval_helper
)

# Retrieve functions with context enrichment
result = await enhanced_retrieval.retrieve_and_match_functions(
    reasoning_plan=reasoning_plan,
    question="Calculate rolling variance of sales data",
    dataframe_description="Sales dataset with daily metrics",
    available_columns=["sales", "date", "region"],
    project_id="your_project_id"
)

# Access enriched function data
for step_num, functions in result.step_matches.items():
    for func in functions:
        print(f"Function: {func['function_name']}")
        print(f"Examples: {len(func.get('examples', []))}")
        print(f"Instructions: {len(func.get('instructions', []))}")
        print(f"Historical Rules: {len(func.get('historical_rules', []))}")
```

### Function Input Extraction

```python
from app.agents.nodes.mlagents.function_input_extractor import create_input_extractor

# Create appropriate extractor
extractor = create_input_extractor(
    analysis_type="time_series_analysis",
    llm=your_llm,
    example_collection=example_collection,
    function_collection=function_collection,
    insights_collection=insights_collection
)

# Extract inputs with enriched context
inputs = extractor.extract_inputs(
    context="Calculate 5-day rolling variance of flux metric",
    function_name="variance_analysis",
    columns=["flux", "timestamp", "projects"],
    dataframe_description={"schema": {"flux": "float64"}}
)
```

## Data Sources

### 1. Examples Collection (`usage_examples_collection`)

Contains real-world usage examples:

```json
{
  "function_name": "variance_analysis",
  "example_code": "variance_analysis(df, columns=['price'], window_size=5)",
  "description": "Calculate 5-day rolling variance for price column",
  "parameters": {
    "columns": ["price"],
    "window_size": 5,
    "method": "rolling"
  }
}
```

### 2. Instructions Collection (`instructions_collection`)

Contains project-specific instructions:

```json
{
  "question": "How to calculate rolling variance?",
  "instruction": "Use variance_analysis function with appropriate window size based on data frequency",
  "project_id": "project_123"
}
```

### 3. Insights Collection (`tools_insights_collection`)

Contains historical patterns and insights:

```json
{
  "function_name": "variance_analysis",
  "insight": "Variance analysis works best with at least 30 data points per window",
  "best_practices": [
    "Ensure data is sorted by time",
    "Handle missing values before calculation",
    "Use appropriate window sizes based on data frequency"
  ]
}
```

## Hardcoded Rules

The system includes domain-specific hardcoded rules:

### Time Series Analysis
- Always ensure data is sorted by time column
- Use appropriate window sizes based on data frequency
- Daily data: 7-30 days, hourly data: 24-168 hours

### Cohort Analysis
- Ensure user_id and date columns are properly formatted
- Use consistent time periods for comparability
- Handle null values appropriately

### Risk Analysis
- Use appropriate confidence levels (95% for VaR, 99% for stress testing)
- Ensure sufficient historical data (minimum 1 year)

### Segmentation
- Normalize numerical features before clustering
- Use appropriate distance metrics
- Euclidean for continuous, Jaccard for categorical

### Funnel Analysis
- Ensure event sequences are properly ordered by timestamp
- Handle duplicate events by keeping first occurrence

## Benefits

### 1. Better Function Selection
- LLMs can make more informed decisions based on examples
- Historical patterns guide function choice
- Project-specific instructions ensure compliance

### 2. Improved Parameter Extraction
- Examples provide concrete parameter configurations
- Instructions guide parameter selection
- Historical rules prevent common mistakes

### 3. Enhanced Code Generation
- Rich context enables better code generation
- Examples serve as templates
- Instructions ensure project-specific requirements

### 4. Reduced Errors
- Historical rules prevent common pitfalls
- Examples show proven patterns
- Instructions enforce best practices

## Configuration

### Retrieval Parameters

```python
# Examples retrieval
examples_result = await retrieval_helper.get_function_examples(
    function_name=function_name,
    similarity_threshold=0.6,  # Lower threshold for more candidates
    top_k=5                    # Number of examples to retrieve
)

# Instructions retrieval
instructions_result = await retrieval_helper.get_instructions(
    query=question,
    project_id=project_id,
    similarity_threshold=0.7,  # Higher threshold for relevance
    top_k=5                    # Number of instructions to retrieve
)

# Insights retrieval
insights_result = await retrieval_helper.get_function_insights(
    function_name=function_name,
    similarity_threshold=0.6,
    top_k=3                    # Number of insights to retrieve
)
```

### LLM Prompt Configuration

The system automatically includes enriched context in LLM prompts:

- **Examples**: Up to 3 examples per function
- **Instructions**: Up to 2 instructions per function
- **Historical Rules**: Up to 2 rules per function
- **Context Length**: Truncated to prevent token limits

## Error Handling

The system includes comprehensive error handling:

1. **Graceful Degradation**: If enrichment fails, original function data is returned
2. **Fallback Mechanisms**: Uses hardcoded rules when examples are unavailable
3. **Logging**: Detailed logging for debugging and monitoring
4. **Timeout Protection**: Async operations have timeout limits

## Performance Considerations

### Parallel Retrieval
- Examples, instructions, and insights are retrieved in parallel
- Reduces total retrieval time significantly

### Caching
- RetrievalHelper includes built-in caching
- Reduces redundant database queries
- Improves response times for repeated requests

### Token Management
- Context is truncated to prevent token limit issues
- Priority given to most relevant examples and instructions
- Configurable limits for different context types

## Monitoring and Debugging

### Logging
```python
logger.info(f"Enriched {function_name} with {len(examples)} examples, {len(instructions)} instructions, {len(examples_store)} insights, {len(historical_rules)} historical rules")
```

### Metrics
- Function enrichment success rate
- Context retrieval times
- LLM prompt effectiveness
- Error rates and types

## Future Enhancements

1. **Dynamic Rule Learning**: Learn rules from successful implementations
2. **Context Ranking**: Prioritize most relevant context
3. **Cross-Function Patterns**: Learn patterns across different functions
4. **User Feedback Integration**: Incorporate user corrections into rules
5. **Performance Optimization**: Further optimize retrieval and caching

## Troubleshooting

### Common Issues

1. **Empty Context**: Check if collections are properly populated
2. **Low Relevance Scores**: Adjust similarity thresholds
3. **Token Limit Errors**: Reduce context length or increase limits
4. **Slow Performance**: Check caching configuration and database performance

### Debug Mode

Enable detailed logging to troubleshoot issues:

```python
import logging
logging.getLogger("enhanced-function-retrieval").setLevel(logging.DEBUG)
```

## Conclusion

The Enhanced Function Retrieval System provides a comprehensive solution for context-aware function selection and parameter extraction. By enriching functions with examples, instructions, and historical rules, the system enables LLMs to make more informed decisions and generate better code.

The system is designed to be:
- **Scalable**: Handles large function libraries efficiently
- **Flexible**: Adapts to different project requirements
- **Robust**: Includes comprehensive error handling
- **Maintainable**: Well-documented and modular design
