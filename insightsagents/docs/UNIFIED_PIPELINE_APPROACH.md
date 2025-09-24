# Unified Pipeline State Management

## Overview

This document describes the new unified approach to pipeline state management that allows each pipeline to run independently and merge its state into new columns of the original dataframe. This approach solves the problem of stateful pipelines that couldn't be used as direct dataframes.

## Problem Statement

Previously, pipeline classes had stateful `to_df()` methods that returned either:
1. Modified dataframes with new columns (like MovingAggrPipe)
2. Separate result dataframes (like OperationsPipe, MetricsPipe)
3. Analysis-specific results (like CohortPipe)

This made it difficult to:
- Use pipelines as direct dataframes
- Combine multiple pipelines independently
- Track which pipeline contributed which columns
- Avoid state conflicts between pipelines

## Solution: Unified State Merging

### New BasePipe Interface

The `BasePipe` class now provides a unified `to_df()` method that:

1. **Starts with original data**: Always begins with a copy of the original dataframe
2. **Merges state as new columns**: Each pipeline's state is merged into new columns with clear prefixes
3. **Adds pipeline identification**: Each pipeline adds identification columns to distinguish its contributions
4. **Maintains independence**: Each pipeline can run independently without affecting others

### Key Methods

#### `to_df(**kwargs) -> pd.DataFrame`
The main interface that:
- Validates data availability
- Checks for pipeline results
- Merges state into original dataframe
- Returns unified result

#### `merge_to_df(base_df: pd.DataFrame, **kwargs) -> pd.DataFrame`
Abstract method implemented by each pipeline to:
- Add pipeline identification columns
- Merge specific pipeline state as new columns
- Add metadata if requested
- Return enhanced dataframe

#### `_has_results() -> bool`
Abstract method to check if pipeline has results to merge.

## Implementation Examples

### MovingAggrPipe
```python
def merge_to_df(self, base_df: pd.DataFrame, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
    result_df = base_df.copy()
    
    # Add pipeline identification
    result_df['pipeline_type'] = 'moving_aggregation'
    result_df['pipeline_has_results'] = len(self.moving_metrics) > 0
    
    # Add metadata if requested
    if include_metadata and self.moving_metrics:
        for metric_name, metric_info in self.moving_metrics.items():
            for key, value in metric_info.items():
                if key != 'type':
                    result_df[f'moving_metadata_{metric_name}_{key}'] = str(value)
    
    return result_df
```

### MetricsPipe
```python
def merge_to_df(self, base_df: pd.DataFrame, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
    result_df = base_df.copy()
    
    # Add pipeline identification
    result_df['pipeline_type'] = 'metrics'
    result_df['pipeline_has_results'] = len(self.metrics) > 0 or len(self.pivot_tables) > 0
    
    # Add metrics as new columns
    for metric_name, metric_value in self.metrics.items():
        result_df[f'metrics_{metric_name}'] = metric_value
        
        if include_metadata:
            result_df[f'metrics_{metric_name}_type'] = 'metric'
            result_df[f'metrics_{metric_name}_metadata'] = f"Calculated metric: {metric_name}"
    
    return result_df
```

## Usage Examples

### Basic Usage
```python
# Each pipeline runs independently
moving_pipe = (MovingAggrPipe.from_dataframe(df)
               | moving_average('sales', window=7))

metrics_pipe = (MetricsPipe.from_dataframe(df)
                | Sum('revenue')
                | Mean('sales'))

# Each can be converted to a unified dataframe
moving_df = moving_pipe.to_df(include_metadata=True)
metrics_df = metrics_pipe.to_df(include_metadata=True)
```

### Combined Usage
```python
# Start with original data
combined_df = df.copy()

# Merge each pipeline's state
combined_df = moving_pipe.merge_to_df(combined_df, include_metadata=True)
combined_df = metrics_pipe.merge_to_df(combined_df, include_metadata=True)
combined_df = operations_pipe.merge_to_df(combined_df, include_metadata=True)

# Result: Single dataframe with all pipeline states merged as new columns
```

### Pipeline Independence
```python
# Pipelines can be combined in any order
result1 = metrics_pipe.merge_to_df(moving_pipe.merge_to_df(df))
result2 = moving_pipe.merge_to_df(metrics_pipe.merge_to_df(df))

# Results are identical regardless of order
assert result1.equals(result2)
```

## Column Naming Convention

### Pipeline Identification
- `pipeline_type`: Type of pipeline (e.g., 'moving_aggregation', 'metrics', 'operations')
- `pipeline_has_results`: Boolean indicating if pipeline has results

### Pipeline-Specific Columns
Each pipeline adds columns with its own prefix:
- **MovingAggrPipe**: `moving_*` prefix
- **MetricsPipe**: `metrics_*` prefix  
- **OperationsPipe**: `ops_*` prefix
- **CohortPipe**: `cohort_*` prefix
- **SegmentationPipe**: `segmentation_*` prefix

### Metadata Columns
When `include_metadata=True`:
- `{pipeline}_total_*`: Count of total items
- `{pipeline}_available_*`: List of available items
- `{pipeline}_current_*`: Current active item
- `{pipeline}_metadata_*`: Detailed metadata

## Benefits

### 1. Independence
- Each pipeline runs independently
- No state conflicts between pipelines
- Pipelines can be combined in any order

### 2. Transparency
- Clear column naming shows which pipeline contributed what
- Easy to track pipeline contributions
- Metadata provides detailed information

### 3. Flexibility
- Original data is always preserved
- New columns are clearly identified
- Easy to filter or select specific pipeline results

### 4. Consistency
- Unified interface across all pipeline types
- Consistent error handling
- Standardized metadata format

## Migration Guide

### For Existing Code
```python
# Old approach
result_df = pipe.to_df()

# New approach (same interface, different behavior)
result_df = pipe.to_df()  # Now returns original data + merged state
```

### For New Code
```python
# Recommended approach for combining pipelines
combined_df = df.copy()
combined_df = pipe1.merge_to_df(combined_df)
combined_df = pipe2.merge_to_df(combined_df)
combined_df = pipe3.merge_to_df(combined_df)
```

## Implementation Status

### Completed
- ✅ BasePipe unified interface
- ✅ MovingAggrPipe implementation
- ✅ MetricsPipe implementation
- ✅ OperationsPipe implementation
- ✅ CohortPipe implementation
- ✅ SegmentationPipe implementation

### Pending
- ⏳ AnomalyPipe implementation
- ⏳ TrendPipe implementation
- ⏳ TimeSeriesPipe implementation
- ⏳ RiskPipe implementation
- ⏳ CausalPipe implementation

## Testing

The new approach is demonstrated in `example_unified_pipeline.py` which shows:
- Individual pipeline usage
- Combined pipeline usage
- Pipeline independence verification
- Column naming and metadata examples

## Conclusion

The unified pipeline approach provides a clean, consistent way to manage pipeline state while maintaining independence and transparency. Each pipeline can run independently and merge its state into new columns of the original dataframe, making it easy to combine multiple pipelines and track their contributions.
