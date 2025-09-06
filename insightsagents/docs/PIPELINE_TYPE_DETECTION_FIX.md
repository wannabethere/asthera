# Pipeline Type Detection Fix

## Problem Description

The system was incorrectly assigning functions to MetricsPipe that don't belong there. Specifically:

1. **`calculate_moving_average`** was being assigned to MetricsPipe instead of TrendPipe
2. **`variance_analysis`** was being assigned to MetricsPipe instead of TimeSeriesPipe  
3. **`moving_apply_by_group`** was being assigned to MetricsPipe instead of TimeSeriesPipe

This resulted in generated code like:
```python
# ❌ INCORRECT - calculate_moving_average should be in TrendPipe
result = (
    MetricsPipe.from_dataframe("Purchase Orders Data")
    | calculate_moving_average(...)
    ).to_df()

# ❌ INCORRECT - moving_apply_by_group should be in TimeSeriesPipe  
result = (
    MetricsPipe.from_dataframe("Purchase Orders Data")
    | moving_apply_by_group(...)
    ).to_df()
```

## Root Cause

The pipeline type detection logic was not properly utilizing the reasoning plan information that contained the correct pipeline type assignments. The system was falling back to incorrect default mappings instead of using the explicit pipeline type information provided in the reasoning plan.

## Solution

### 1. Enhanced Pipeline Type Detection Logic

Updated the `_detect_pipeline_type` method in `self_correcting_pipeline_generator.py` to prioritize information from the reasoning plan:

```python
async def _detect_pipeline_type(self, function_name: str, context: str, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None) -> PipelineType:
    # First, try to get pipeline type from reasoning plan if available
    if classification:
        reasoning_plan = None
        if hasattr(classification, 'reasoning_plan'):
            reasoning_plan = getattr(classification, 'reasoning_plan', None)
        else:
            reasoning_plan = classification.get('reasoning_plan', None)
        
        # Look for the function in reasoning plan to get its pipeline type
        if reasoning_plan and isinstance(reasoning_plan, list):
            for step in reasoning_plan:
                if isinstance(step, dict) and step.get('function_name') == function_name:
                    # Check for pipeline_type in the step
                    pipeline_type_str = step.get('pipeline_type')
                    if pipeline_type_str:
                        pipeline_type = self._map_pipe_name_to_pipeline_type(pipeline_type_str)
                        if pipeline_type:
                            return pipeline_type
                    
                    # Check for function_category in the step
                    function_category = step.get('function_category')
                    if function_category:
                        pipeline_type = self._get_pipeline_type_from_function_category(function_category)
                        if pipeline_type:
                            return pipeline_type
    
    # Fallback to other detection methods...
```

### 2. Function Category Mapping

Added a new method to map function categories to pipeline types:

```python
def _get_pipeline_type_from_function_category(self, function_category: str) -> Optional[PipelineType]:
    """Get pipeline type from function category string"""
    category_mapping = {
        "moving_average_analysis": PipelineType.TRENDS,
        "statistical_analysis": PipelineType.TIMESERIES,
        "time_series_analysis": PipelineType.TIMESERIES,
        "trend_analysis": PipelineType.TRENDS,
        "cohort_analysis": PipelineType.COHORT,
        "funnel_analysis": PipelineType.FUNNEL,
        "segmentation_analysis": PipelineType.SEGMENT,
        "anomaly_detection": PipelineType.ANOMALY,
        "risk_analysis": PipelineType.RISK,
        "metrics_calculation": PipelineType.METRICS,
        "operations_analysis": PipelineType.OPERATIONS
    }
    return category_mapping.get(function_category)
```

### 3. Updated Function-to-Pipe Mapping

Enhanced the function-to-pipe mapping in the `__init__` method to include correct pipeline type assignments:

```python
self.function_to_pipe = {
    # MetricsPipe functions
    "Mean": PipelineType.METRICS,
    "Sum": PipelineType.METRICS,
    "Count": PipelineType.METRICS,
    "Variance": PipelineType.METRICS,
    "GroupBy": PipelineType.METRICS,
    
    # TimeSeriesPipe functions
    "variance_analysis": PipelineType.TIMESERIES,
    "moving_apply_by_group": PipelineType.TIMESERIES,
    "lead": PipelineType.TIMESERIES,
    "lag": PipelineType.TIMESERIES,
    
    # TrendsPipe functions
    "calculate_moving_average": PipelineType.TRENDS,
    "aggregate_by_time": PipelineType.TRENDS,
    "calculate_growth_rates": PipelineType.TRENDS,
    
    # Other pipeline types...
}
```

### 4. Multi-Pipeline Detection Enhancement

Updated the `_filter_additional_computations` method to properly handle TrendsPipe functions:

```python
elif primary_pipeline_type == PipelineType.TRENDS:
    # TrendsPipe can work with MetricsPipe preprocessing
    if metrics_computations:
        needs_multi_pipeline = True
        first_pipeline_type = "MetricsPipe"
        detected_inputs["additional_computations"] = metrics_computations
        second_pipeline_type = primary_pipeline_type.value
    else:
        # Only trends computations
        detected_inputs["additional_computations"] = trends_computations
```

## Detection Priority Order

The pipeline type detection now follows this priority order:

1. **Reasoning Plan**: Check `pipeline_type` and `function_category` in reasoning plan steps
2. **Retrieved Functions**: Check `category` and `pipe_name` in retrieved functions
3. **Suggested Functions**: Extract pipeline type from suggested function format
4. **FunctionRetrieval**: Use FunctionRetrieval system if available
5. **Function Definition Store**: Fallback to function definition store
6. **Context-Based**: Final fallback using context keywords

## Expected Results

With these fixes, the generated code should now correctly use the appropriate pipeline types:

```python
# ✅ CORRECT - calculate_moving_average in TrendPipe
result = (
    TrendPipe.from_dataframe("Purchase Orders Data")
    | calculate_moving_average(...)
    ).to_df()

# ✅ CORRECT - variance_analysis in TimeSeriesPipe
result = (
    TimeSeriesPipe.from_dataframe("Purchase Orders Data")
    | variance_analysis(...)
    ).to_df()

# ✅ CORRECT - moving_apply_by_group in TimeSeriesPipe
result = (
    TimeSeriesPipe.from_dataframe("Purchase Orders Data")
    | moving_apply_by_group(...)
    ).to_df()
```

## Testing

A comprehensive test suite has been created to verify the fix:

- `test_pipeline_type_detection.py`: Unit tests for pipeline type detection
- `test_pipeline_fix.py`: Simple verification script

The tests verify that:
- Functions are correctly assigned to their proper pipeline types
- Reasoning plan information is properly utilized
- Function category mapping works correctly
- Fallback mechanisms function as expected

## Impact

This fix ensures that:
1. **Correct Pipeline Types**: Functions are assigned to their proper pipeline types
2. **Better Code Generation**: Generated code uses the correct pipeline initialization
3. **Improved Accuracy**: The system respects the reasoning plan's pipeline type assignments
4. **Reduced Errors**: Fewer pipeline failures due to incorrect function assignments

## Migration Notes

No breaking changes were introduced. The fix is backward compatible and improves accuracy without affecting existing functionality.
