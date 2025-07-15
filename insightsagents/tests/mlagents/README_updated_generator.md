# Updated SelfCorrectingPipelineCodeGenerator

## Overview

The `SelfCorrectingPipelineCodeGenerator` has been enhanced to accept classification input, dataset descriptions, and column descriptions to generate more accurate and context-aware pipeline code.

## Key Changes

### 1. Enhanced Method Signature

The `generate_pipeline_code` method now accepts additional parameters:

```python
def generate_pipeline_code(self, 
                         context: str,
                         function_name: str,
                         function_inputs: Dict[str, Any],
                         dataframe_name: str = "df",
                         classification: Optional[Dict[str, Any]] = None,
                         dataset_description: Optional[str] = None,
                         columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
```

### 2. New Parameters

- **`classification`**: Dictionary containing intent analysis results
  - `intent_type`: Type of analysis (e.g., 'time_series_analysis')
  - `confidence_score`: Confidence in the classification (0.0-1.0)
  - `rephrased_question`: Rephrased version of the original question
  - `suggested_functions`: List of suggested functions to use
  - `reasoning`: Reasoning behind the classification
  - `required_data_columns`: Required columns for the analysis
  - `missing_columns`: Columns that are missing from the dataset
  - `can_be_answered`: Whether the question can be answered
  - `feasibility_score`: Feasibility score (0.0-1.0)
  - And more...

- **`dataset_description`**: Human-readable description of the dataset
- **`columns_description`**: Dictionary mapping column names to descriptions

### 3. Enhanced Context Processing

The generator now:
- Enhances the original context with classification information
- Uses intent type and confidence scores to guide pipeline selection
- Considers missing columns and data requirements
- Incorporates reasoning from the classification

### 4. Improved Code Generation

The code generation process now:
- Uses classification context to make better function choices
- Considers dataset structure and column descriptions
- Incorporates feasibility scores and missing data information
- Provides more targeted and accurate pipeline code

## Usage Example

```python
# Classification input from intent analysis
classification = {
    'intent_type': 'time_series_analysis',
    'confidence_score': 0.9,
    'rephrased_question': 'What is the 5-day rolling variance of flux over time for each project, cost center, and department?',
    'suggested_functions': ['variance_analysis', 'calculate_var'],
    'reasoning': 'The question specifically asks for rolling variance, matching the variance_analysis function.',
    'required_data_columns': ['Date', 'Project', 'Cost center', 'Department', 'Transactional value'],
    'missing_columns': ['Department'],
    'can_be_answered': True,
    'feasibility_score': 0.8
}

# Dataset information
dataset_description = "Financial transaction data with project, cost center, and department information over time"

columns_description = {
    'Date': 'Transaction date in YYYY-MM-DD format',
    'Project': 'Project identifier or name',
    'Cost center': 'Cost center code or name',
    'Transactional value': 'Monetary value of the transaction (flux)',
    'Department': 'Department name (may be missing in some records)'
}

# Function inputs
function_inputs = {
    'window': 5,
    'value_column': 'Transactional value',
    'group_by': ['Project', 'Cost center', 'Department'],
    'date_column': 'Date'
}

# Generate pipeline code
result = generator.generate_pipeline_code(
    context="Calculate 5-day rolling variance of transactional values",
    function_name="variance_analysis",
    function_inputs=function_inputs,
    dataframe_name="df",
    classification=classification,
    dataset_description=dataset_description,
    columns_description=columns_description
)
```

## Expected Output

The generator returns an enhanced result dictionary:

```python
{
    "status": "success",
    "generated_code": "result = (TimeSeriesPipe.from_dataframe(df) | variance_analysis(...) | ShowDataFrame())",
    "iterations": 1,
    "attempts": ["generated_code_attempts"],
    "reasoning": ["reasoning_steps"],
    "function_name": "variance_analysis",
    "pipeline_type": "TimeSeriesPipe",
    "classification": classification,  # Original classification input
    "dataset_description": dataset_description,  # Original dataset description
    "columns_description": columns_description,  # Original columns description
    "enhanced_context": "Enhanced context with classification information"
}
```

## Benefits

1. **More Accurate Pipelines**: Classification information helps generate more appropriate pipeline code
2. **Better Context Understanding**: Dataset and column descriptions provide better context
3. **Improved Error Handling**: Missing columns and feasibility scores help identify potential issues
4. **Enhanced Self-Correction**: Classification reasoning helps guide the self-correction process
5. **Better Function Selection**: Suggested functions and intent types guide function choice

## Backward Compatibility

The updated generator maintains backward compatibility. All existing parameters remain optional, and the generator will work with or without classification input.

## New Helper Methods

- `_enhance_context_with_classification()`: Enhances context with classification information
- `_format_classification_context()`: Formats classification for code generation prompts
- `_format_dataset_context()`: Formats dataset information for code generation prompts

## Migration Guide

To migrate existing code:

1. **No changes required** if you don't want to use the new features
2. **Add classification input** to get enhanced pipeline generation
3. **Add dataset descriptions** for better context understanding
4. **Update result handling** to use the new output fields if needed

The generator will automatically adapt based on the provided input parameters. 