# Function Detector Enhancement for SelfCorrectingPipelineCodeGenerator

## Overview

The `SelfCorrectingPipelineCodeGenerator` has been enhanced with a new function detector that can intelligently select the best function from a list of suggested functions using LLM-based analysis.

## New Features

### 1. Function Detection from Lists

The `generate_pipeline_code` method now accepts `function_name` as either:
- A string (existing behavior)
- A list of suggested functions (new functionality)

### 2. LLM-Powered Function Selection

When a list of functions is provided, the system uses an LLM to:
- Analyze the context and task requirements
- Evaluate each suggested function's relevance
- Select the most appropriate function with confidence scoring
- Provide reasoning for the selection
- Identify alternative functions

## Usage Examples

### Example 1: List of Suggested Functions

```python
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator

# Initialize the generator
generator = SelfCorrectingPipelineCodeGenerator(
    llm=your_llm_instance,
    usage_examples_store=your_usage_store,
    code_examples_store=your_code_store,
    function_definition_store=your_function_store
)

# Use a list of suggested functions
context = "Calculate the average sales value"
suggested_functions = ["Mean", "Sum", "Count", "Median"]
function_inputs = {}

result = await generator.generate_pipeline_code(
    context=context,
    function_name=suggested_functions,  # List of functions
    function_inputs=function_inputs,
    dataframe_name="df"
)

# Access function detection metadata
function_metadata = result["function_detection_metadata"]
print(f"Selected function: {function_metadata['selected_function']}")
print(f"Confidence: {function_metadata['confidence']}")
print(f"Reasoning: {function_metadata['reasoning']}")
print(f"Alternative functions: {function_metadata['alternative_functions']}")
```

### Example 2: Single Function (Existing Behavior)

```python
# Use a single function (existing behavior)
context = "Calculate the sum of revenue"
single_function = "Sum"
function_inputs = {"variable": "revenue"}

result = await generator.generate_pipeline_code(
    context=context,
    function_name=single_function,  # Single function
    function_inputs=function_inputs,
    dataframe_name="df"
)

# Function detection metadata shows direct selection
function_metadata = result["function_detection_metadata"]
print(f"Selected function: {function_metadata['selected_function']}")
print(f"Confidence: {function_metadata['confidence']}")  # Should be 1.0
```

## Return Structure

The enhanced generator now returns additional metadata in the result:

```json
{
    "status": "success",
    "generated_code": "...",
    "function_detection_metadata": {
        "selected_function": "Mean",
        "confidence": 0.95,
        "reasoning": "Mean is the most appropriate function for calculating average values",
        "alternative_functions": ["Sum", "Count"]
    },
    // ... other existing fields
}
```

## Function Detection Metadata

The `function_detection_metadata` contains:

- **selected_function**: The function chosen by the LLM
- **confidence**: Confidence score (0.0-1.0) for the selection
- **reasoning**: Explanation of why this function was selected
- **alternative_functions**: List of other functions that could be used

## Error Handling

The system includes robust error handling:

1. **JSON Parsing Errors**: If the LLM response cannot be parsed, it falls back to the first suggested function
2. **Empty Selection**: If no function is selected, it uses the first function in the list
3. **Detection Failures**: If the detection process fails, it provides fallback behavior

## Supported Function Types

The function detector works with all supported pipeline types:

- **MetricsPipe**: Mean, Sum, Count, Variance, etc.
- **OperationsPipe**: PercentChange, AbsoluteChange, CUPED, etc.
- **TimeSeriesPipe**: variance_analysis, lead, lag, etc.
- **CohortPipe**: form_time_cohorts, calculate_retention, etc.
- **RiskPipe**: calculate_var, calculate_cvar, etc.
- **FunnelPipe**: analyze_funnel, etc.

## Integration with Existing Features

The function detector integrates seamlessly with existing features:

- **Classification Analysis**: Uses intent classification results to inform function selection
- **Dataset Context**: Considers dataset descriptions and column information
- **Self-Correction**: Works within the existing self-correction loop
- **Document Retrieval**: Leverages existing document stores for better function selection

## Testing

Run the test script to verify functionality:

```bash
python test_function_detector.py
```

## Example Scenarios

### Scenario 1: Simple Metrics
- **Context**: "Calculate the average sales value"
- **Suggested Functions**: ["Mean", "Sum", "Count", "Median"]
- **Expected Selection**: "Mean" with high confidence

### Scenario 2: Complex Analysis
- **Context**: "Analyze customer retention patterns over time"
- **Suggested Functions**: ["calculate_retention", "form_time_cohorts", "variance_analysis", "Mean"]
- **Expected Selection**: "calculate_retention" or "form_time_cohorts" based on context

### Scenario 3: Risk Analysis
- **Context**: "Calculate the Value at Risk for portfolio returns"
- **Suggested Functions**: ["calculate_var", "calculate_cvar", "Variance", "StandardDeviation"]
- **Expected Selection**: "calculate_var" for VaR calculation

## Backward Compatibility

The enhancement is fully backward compatible:
- Existing code using single function names continues to work unchanged
- The `function_detection_metadata` is always included in the result
- All existing functionality is preserved

## Performance Considerations

- Function detection adds one additional LLM call when using a list of functions
- The detection is cached within the generation process
- Error handling ensures the system remains responsive even if detection fails 